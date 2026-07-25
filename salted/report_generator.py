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
        """
        if not self.replace_path_by_url:
            return file_path
        if self.replace_path_by_url.get('replace_with_url'):
            return self.rewrite_path(file_path)
        base = self.replace_path_by_url.get('path_to_be_replaced')
        if not base:
            return file_path
        try:
            return str(pathlib.Path(file_path).relative_to(base))
        except ValueError:
            # file_path is not under base (unexpected) — leave it untouched.
            return file_path

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
            result.append({'path': file_path, 'problem': problem})
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
            defects = cursor.fetchall()
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
            redirects = cursor.fetchall()
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
            exceptions = cursor.fetchall()
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
            findings = cursor.fetchall()
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
            file_path = self._display_path(file_path)
            result.append({
                'path': file_path,
                'url': url,
                'address': address,
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
            file_path = self._display_path(file_path)
            result.append({
                'doi': doi,
                'path': file_path,
                'description': description,
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
