#!/usr/bin/python3

"""
Report generator for salted
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026 Rüdiger Voigt and contributors
Released under the Apache License 2.0
"""
import logging
import pathlib
from typing import Final

from jinja2 import FileSystemLoader, PackageLoader
from jinja2.sandbox import SandboxedEnvironment

from salted import err, memory_instance

# Templates shipped inside the package. Anything else is loaded from a
# path that may come from the checked folder, i.e. from untrusted input.
BUILTIN_TEMPLATES: Final[tuple] = ('default.cli.jinja', 'default.md.jinja')

# External templates must carry this extension. Without it, template_name
# can name any file the process can read — a .ini pointing at an SSH key
# or a .env file would have it rendered into the report verbatim, as a
# file without Jinja syntax renders as its own content. Secrets very
# rarely carry a .jinja extension, so this removes the easy targets.
TEMPLATE_SUFFIX: Final[str] = '.jinja'

# C0 control characters, plus DEL, except tab. Everything the report shows -
# link text, URLs, file paths - is read out of the checked documents, so it
# can carry terminal escape sequences. Printed unfiltered they are executed
# rather than displayed: '\x1b[2K\x1b[32mAll links OK' erases the line and
# writes a green success message inside the list of broken links, and a
# carriage return overwrites what came before. The report is the product
# here, so it must not be forgeable by the content it reports on.
_CONTROL_CHARACTERS: Final[dict] = {
    codepoint: None
    for codepoint in list(range(0, 9)) + list(range(10, 32)) + [127]
}

# Characters that end a markdown link target. A URL containing them - a
# Wikipedia '..._(programming_language)' link, for instance - would
# otherwise terminate the '[label](target)' construct early, breaking a
# legitimate link and letting a crafted one point somewhere else entirely.
_MD_URL_ESCAPES: Final[dict] = {
    '(': '%28', ')': '%29', '<': '%3C', '>': '%3E', ' ': '%20', '|': '%7C',
}

# Markdown inline markup that must not be honoured when it comes out of a
# checked document. The backslash leads, so escaping it first does not
# double-escape what follows. Punctuation such as '.' or '-' is left alone:
# it only carries meaning at the start of a line, which cannot happen for a
# value rendered inside a table cell or a list item.
_MD_ESCAPE_CHARS: Final[str] = '\\`*_[]<>|'


def strip_control_characters(value: str) -> str:
    """Remove control characters that a terminal would act on.

    Tab is kept: it is the one C0 character that is a normal part of text.
    Newlines are removed as well - a report line is one record, and an
    embedded newline lets a document fake an extra one.

    Args:
        value: A string taken from a checked document.

    Returns:
        The string without control characters.
    """
    return value.translate(_CONTROL_CHARACTERS)


def markdown_cell(value: object) -> str:
    """Escape a value taken from a document for use in markdown.

    Link text and URLs are content, not markup, and must render as
    written. Without escaping a document controls the report's structure:
    an unescaped pipe ends a table cell and lets it inject further columns
    or whole rows, brackets forge a link with a misleading target, and -
    since markdown passes HTML through - angle brackets carry live tags
    into anything that renders the report as HTML. Link text from
    Markdown, TeX and BibTeX sources is taken verbatim by the parsers, so
    it can contain any of these (HTML sources are tag-stripped earlier).

    The backslash must be escaped first, or it would double-escape the
    escapes added after it.

    Args:
        value: The value to render.

    Returns:
        The value as a string, safe to place in a markdown document.
    """
    text = str(value)
    for char in _MD_ESCAPE_CHARS:
        text = text.replace(char, '\\' + char)
    return text


def markdown_url(value: object) -> str:
    """Percent-encode the characters that break a markdown link target.

    Args:
        value: The URL to use as a link target.

    Returns:
        The URL with link-breaking characters percent-encoded. Servers
        decode these, so the target still resolves to the same resource.
    """
    text = str(value)
    for char, encoded in _MD_URL_ESCAPES.items():
        text = text.replace(char, encoded)
    return text


def _clean(value: object) -> object:
    """Strip control characters from strings, pass anything else through."""
    return strip_control_characters(value) if isinstance(value, str) else value


def _clean_rows(rows: list) -> list:
    """Apply _clean to every field of every row returned from the database."""
    return [tuple(_clean(field) for field in row) for row in rows]


class ReportGenerator:
    """Generate reports about broken links and redirects.

    Reports can be styled using Jinja2 templates.
    """

    def __init__(self,
                 mem_instance: memory_instance.MemoryInstance,
                 show_redirects: bool = True,
                 show_exceptions: bool = True):
        """Initialize the ReportGenerator.

        Args:
            mem_instance: In-memory database instance containing check results.
            show_redirects: If True, include permanent redirects in reports.
            show_exceptions: If True, include network exceptions in reports.
        """
        self.db = mem_instance
        self.show_redirects = show_redirects
        self.show_exceptions = show_exceptions
        self.replace_path_by_url: dict | None = None

    def rewrite_path(self,
                     path_to_rewrite: str) -> str:
        """Rewrite a file path by replacing it with the base URL.

        Args:
            path_to_rewrite: The file path to rewrite.

        Returns:
            The path with the folder path replaced by the base URL.

        Raises:
            ValueError: If path_to_be_replaced or replace_with_url is not set.
        """
        if not self.replace_path_by_url:
            raise ValueError('No path replacement configured.')
        if not self.replace_path_by_url.get('path_to_be_replaced'):
            raise ValueError('Cannot replace in URL not knowing what.')
        if not self.replace_path_by_url.get('replace_with_url'):
            raise ValueError('Cannot replace in URL not knowing with what.')

        return path_to_rewrite.replace(
            self.replace_path_by_url['path_to_be_replaced'],
            self.replace_path_by_url['replace_with_url'],
            1)

    def _display_path(self, file_path: str) -> str:
        """Transform a stored (absolute) file path for display in the report.

        The mode is decided by ``self.replace_path_by_url``:

        - base_url set   → rewrite the search-root prefix to that URL.
        - base_url unset → show the path relative to the search root.
        - no mapping     → return the path unchanged.

        Args:
            file_path: The file path as stored in the database.

        Returns:
            The path rewritten to a URL, made relative, or left unchanged.
            Control characters are stripped: a file name can contain them
            on most filesystems, and the report is printed to a terminal.
        """
        if not self.replace_path_by_url:
            return strip_control_characters(file_path)
        if self.replace_path_by_url.get('replace_with_url'):
            return strip_control_characters(self.rewrite_path(file_path))
        base = self.replace_path_by_url.get('path_to_be_replaced')
        if not base:
            return strip_control_characters(file_path)
        try:
            return strip_control_characters(
                str(pathlib.Path(file_path).relative_to(base)))
        except ValueError:
            # file_path is not under base (unexpected) — leave it untouched.
            return strip_control_characters(file_path)

    def generate_access_error_list(self) -> list | None:
        """Generate a list of file access errors.

        Returns:
            List of dictionaries containing 'path' and 'problem' keys,
            or None if no access errors occurred.
        """
        cursor = self.db.get_cursor()
        cursor.execute(
            '''SELECT filePath, problem
               FROM fileAccessErrors;''')
        access_errors = cursor.fetchall()
        if not access_errors:
            return None
        result = list()
        for file_path, problem in access_errors:
            result.append({'path': self._display_path(file_path),
                           'problem': strip_control_characters(problem)})
        return result

    def generate_error_list(self) -> list | None:
        """Generate a list of permanent link errors.

        Returns:
            List of dictionaries containing:
                - path: File path (rewritten if base_url is set)
                - num_errors: Number of errors in the file
                - defects: List of (url, linktext, httpCode) tuples
            Returns None if no permanent errors were found.
        """
        cursor = self.db.get_cursor()
        result = list()
        cursor.execute(
            '''SELECT filePath, numErrors
               FROM v_errorCountByFile
               ORDER BY numErrors DESC, filePath ASC;''')
        pages_w_permanent_errors = cursor.fetchall()
        if not pages_w_permanent_errors:
            return None
        for file_path, num_errors in pages_w_permanent_errors:
            # The url as in the code, not the normalized version used to check.
            cursor.execute('''
                SELECT url, linktext, httpCode
                FROM v_errorsByFile
                WHERE filePath = ?;''', [file_path])
            defects = _clean_rows(cursor.fetchall())
            file_path = self._display_path(file_path)
            result.append({'path': file_path,
                           'num_errors': num_errors,
                           'defects': defects})
        return result

    def generate_redirect_list(self) -> list | None:
        """Generate a list of permanent redirects.

        Returns:
            List of dictionaries containing:
                - path: File path (rewritten if base_url is set)
                - num_redirects: Number of redirects in the file
                - redirects: List of (url, linktext, httpCode) tuples
            Returns None if no permanent redirects were found.
        """
        cursor = self.db.get_cursor()
        result = list()
        cursor.execute(
            '''SELECT filePath, numRedirects
                FROM v_redirectCountByFile
                ORDER BY numRedirects DESC, filePath ASC;''')
        pages_w_redirects = cursor.fetchall()
        if not pages_w_redirects:
            return None
        for file_path, num_redirects in pages_w_redirects:
            # The url as in the code, not the normalized version used to check.
            cursor.execute('''
                SELECT url, linktext, httpCode
                FROM v_redirectsByFile
                WHERE filePath = ?;''', [file_path])
            redirects = _clean_rows(cursor.fetchall())
            file_path = self._display_path(file_path)
            result.append({'path': file_path,
                           'num_redirects': num_redirects,
                           'redirects': redirects})
        return result

    def generate_exception_list(self) -> list | None:
        """Generate a list of exceptions that occurred during link checking.

        Returns:
            List of dictionaries containing:
                - path: File path (rewritten if base_url is set)
                - num_exceptions: Number of exceptions in the file
                - exceptions: List of (url, linktext, reason) tuples
            Returns None if no exceptions occurred.
        """
        cursor = self.db.get_cursor()
        result = list()
        cursor.execute(
            '''SELECT filePath, numExceptions
                FROM v_exceptionCountByFile
                ORDER BY numExceptions DESC, filePath ASC;''')
        pages_w_exceptions = cursor.fetchall()
        if not pages_w_exceptions:
            return None
        for file_path, num_exceptions in pages_w_exceptions:
            # The url as in the code, not the normalized version used to check.
            cursor.execute('''
                SELECT url, linktext, reason
                FROM v_exceptionsByFile
                WHERE filePath = ?;''', [file_path])
            exceptions = _clean_rows(cursor.fetchall())
            file_path = self._display_path(file_path)
            result.append({'path': file_path,
                           'num_exceptions': num_exceptions,
                           'exceptions': exceptions})
        return result

    def generate_internal_link_list(self) -> list | None:
        """Generate a list of internal link findings grouped by file.

        Returns:
            List of dictionaries containing:
                - path: File path (rewritten if base_url is set)
                - num_findings: Number of findings in the file
                - findings: List of (url, linktext, reason, isError) tuples
            Returns None if all internal links were fine.
        """
        cursor = self.db.get_cursor()
        cursor.execute('''
            SELECT filePath, COUNT(*) AS numFindings
            FROM internalLinkFindings
            GROUP BY filePath
            ORDER BY numFindings DESC, filePath ASC;''')
        files_w_findings = cursor.fetchall()
        if not files_w_findings:
            return None
        result = []
        for file_path, num_findings in files_w_findings:
            cursor.execute('''
                SELECT url, linktext, reason, isError
                FROM internalLinkFindings
                WHERE filePath = ?
                ORDER BY isError DESC, url ASC;''', [file_path])
            findings = _clean_rows(cursor.fetchall())
            file_path = self._display_path(file_path)
            result.append({'path': file_path,
                           'num_findings': num_findings,
                           'findings': findings})
        return result

    def generate_mailto_list(self) -> list | None:
        """Generate a list of mailto links found during the scan.

        Note: addresses are only checked for basic format validity using
        is_email() — no DNS lookup or delivery verification is performed.

        Returns:
            List of dicts with keys 'path', 'url', 'address', 'valid',
            or None if no mailto links were found.
        """
        cursor = self.db.get_cursor()
        cursor.execute('''
            SELECT filePath, url, address, valid
            FROM mailtoLinks
            ORDER BY filePath, url;''')
        rows = cursor.fetchall()
        if not rows:
            return None
        result = []
        for file_path, url, address, valid in rows:
            result.append({
                'path': self._display_path(file_path),
                'url': strip_control_characters(url),
                'address': strip_control_characters(address),
                'valid': bool(valid),
            })
        return result

    def generate_invalid_doi_list(self) -> list | None:
        """Generate a list of invalid DOIs and the files that reference them.

        Joins the invalidDois table with queue_doi to find which files
        contain each invalid DOI.

        Returns:
            List of dicts with keys 'doi', 'path', 'description',
            or None if no invalid DOIs were found.
        """
        cursor = self.db.get_cursor()
        cursor.execute('''
            SELECT invalidDois.doi, queue_doi.filePath, queue_doi.description
            FROM invalidDois
            INNER JOIN queue_doi ON invalidDois.doi = queue_doi.doi
            ORDER BY queue_doi.filePath, invalidDois.doi;''')
        rows = cursor.fetchall()
        if not rows:
            return None
        result = []
        for doi, file_path, description in rows:
            result.append({
                'doi': strip_control_characters(doi),
                'path': self._display_path(file_path),
                'description': strip_control_characters(description),
            })
        return result

    @staticmethod
    def _reject_unsafe_template_name(name: str) -> None:
        """Refuse template names that do not look like a template file.

        Args:
            name: The template file name as configured.

        Raises:
            err.UnsafeTemplateError: If the name lacks the template
                extension. Jinja2 renders a file without template syntax
                as its own content, so an arbitrary file named here would
                be copied into the report.
        """
        if not name.lower().endswith(TEMPLATE_SUFFIX):
            raise err.UnsafeTemplateError(
                f"Refusing to load template '{name}': a template file name "
                f"must end in '{TEMPLATE_SUFFIX}'. Any other file would be "
                'rendered into the report as its own content.')

    def generate_report(self,
                        statistics: dict,
                        template: dict,
                        write_to: str | pathlib.Path,
                        replace_path_by_url: dict | None = None
                        ) -> None:
        """Generate and output the final report.

        Renders a Jinja2 template with link checking results and either
        displays it to the CLI or writes it to a file.

        Args:
            statistics: Dictionary containing statistics about the check.
            template: Dictionary with 'name' and optionally 'searchpath' keys.
            write_to: Output destination - 'cli' for stdout or a file path.
            replace_path_by_url: Optional dictionary with 'path_to_be_replaced'
                and 'replace_with_url' keys for path rewriting.

        Raises:
            Exception: If writing to file fails.
        """
        # Keep the path mapping whenever a base path is provided: with a
        # base_url it rewrites paths to URLs, without one it shows paths
        # relative to that base. Drop it entirely if no base path is given.
        if replace_path_by_url and replace_path_by_url.get('path_to_be_replaced'):
            self.replace_path_by_url = replace_path_by_url
        else:
            self.replace_path_by_url = None

        access_errors = self.generate_access_error_list()
        mailto_links = self.generate_mailto_list()
        invalid_dois = self.generate_invalid_doi_list()
        internal_links = self.generate_internal_link_list()

        permanent_errors = self.generate_error_list()

        permanent_redirects: list | None = None
        if self.show_redirects:
            permanent_redirects = self.generate_redirect_list()

        crawl_exceptions: list | None = None
        if self.show_exceptions:
            crawl_exceptions = self.generate_exception_list()

        render_context = {
            'statistics': statistics,
            'access_errors': access_errors,
            'permanent': permanent_errors,
            'redirects': permanent_redirects,
            'exceptions': crawl_exceptions,
            'mailto_links': mailto_links,
            'invalid_dois': invalid_dois,
            'internal_links': internal_links,
        }

        # Rendering is sandboxed in both cases. A plain Environment lets a
        # template walk the object graph of any variable it is given
        # (value.__class__.__mro__ ... __subclasses__()) and reach code
        # execution. autoescape does not prevent that: it escapes the
        # *result* of an expression, not what the expression may evaluate.
        if template['name'] in BUILTIN_TEMPLATES:
            jinja_env = SandboxedEnvironment(  # nosec B701 - built-in templates output plain text/markdown, not HTML
                loader=PackageLoader('salted', 'templates'),
                autoescape=False)
        else:
            self._reject_unsafe_template_name(template['name'])
            jinja_env = SandboxedEnvironment(
                loader=FileSystemLoader(searchpath=template['searchpath']),
                autoescape=True)

        # Markdown needs escaping of its own: autoescape works on HTML and
        # would mangle a markdown document rather than protect it. Offered
        # to custom templates too, since they face the same input.
        jinja_env.filters['md_cell'] = markdown_cell
        jinja_env.filters['md_url'] = markdown_url

        rendered_report = jinja_env.get_template(
            template['name']).render(**render_context)

        if write_to == 'cli':
            print(rendered_report)
            return
        try:
            with open(write_to, 'w', encoding='utf-8') as file:
                file.write(rendered_report)
            logging.info("Wrote report to file: %s",
                         pathlib.Path(write_to).resolve())
        except Exception:
            logging.exception('Exception while writing to file!',
                              exc_info=True)
            raise
