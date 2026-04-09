#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Report generator for salted
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026 Rüdiger Voigt and contributors
Released under the Apache License 2.0
"""
import logging
import pathlib
from typing import Optional, Union

from jinja2 import Environment, FileSystemLoader, PackageLoader

from salted import memory_instance


class ReportGenerator:
    """Generate reports about broken links and redirects.

    Reports can be styled using Jinja2 templates.
    """

    def __init__(self,
                 mem_instance: memory_instance.MemoryInstance,
                 show_redirects: bool = True,
                 show_exceptions: bool = True):
        self.db = mem_instance
        self.show_redirects = show_redirects
        self.show_exceptions = show_exceptions
        self.replace_path_by_url: Optional[dict] = None

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

    def generate_access_error_list(self) -> Optional[list]:
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

    def generate_error_list(self) -> Optional[list]:
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
            if self.replace_path_by_url:
                file_path = self.rewrite_path(file_path)
            result.append({'path': file_path,
                           'num_errors': num_errors,
                           'defects': defects})
        return result

    def generate_redirect_list(self) -> Optional[list]:
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
            if self.replace_path_by_url:
                file_path = self.rewrite_path(file_path)
            result.append({'path': file_path,
                           'num_redirects': num_redirects,
                           'redirects': redirects})
        return result

    def generate_exception_list(self) -> Optional[list]:
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
            if self.replace_path_by_url:
                file_path = self.rewrite_path(file_path)
            result.append({'path': file_path,
                           'num_exceptions': num_exceptions,
                           'exceptions': exceptions})
        return result

    def generate_mailto_list(self) -> Optional[list]:
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
            if self.replace_path_by_url:
                file_path = self.rewrite_path(file_path)
            result.append({
                'path': file_path,
                'url': url,
                'address': address,
                'valid': bool(valid),
            })
        return result

    def generate_invalid_doi_list(self) -> Optional[list]:
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
            if self.replace_path_by_url:
                file_path = self.rewrite_path(file_path)
            result.append({
                'doi': doi,
                'path': file_path,
                'description': description,
            })
        return result

    def generate_report(self,
                        statistics: dict,
                        template: dict,
                        write_to: Union[str, pathlib.Path],
                        replace_path_by_url: Union[dict, None] = None
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
        # The base URL is always given. Invalidate the parameter if no
        # replacement is provided.
        if not replace_path_by_url or not replace_path_by_url.get('replace_with_url'):
            replace_path_by_url = None
        else:
            self.replace_path_by_url = replace_path_by_url

        access_errors = self.generate_access_error_list()
        mailto_links = self.generate_mailto_list()
        invalid_dois = self.generate_invalid_doi_list()

        permanent_errors = self.generate_error_list()

        permanent_redirects: Optional[list] = None
        if self.show_redirects:
            permanent_redirects = self.generate_redirect_list()

        crawl_exceptions: Optional[list] = None
        if self.show_exceptions:
            crawl_exceptions = self.generate_exception_list()

        rendered_report = ''

        if template['name'] in ('default.cli.jinja', 'default.md.jinja'):
            # built-in template
            jinja_env = Environment(  # nosec B701 - built-in templates output plain text/markdown, not HTML
                loader=PackageLoader('salted', 'templates'),
                autoescape=False)
            builtin_template = jinja_env.get_template(template['name'])
            rendered_report = builtin_template.render(
                statistics=statistics,
                access_errors=access_errors,
                permanent=permanent_errors,
                redirects=permanent_redirects,
                exceptions=crawl_exceptions,
                mailto_links=mailto_links,
                invalid_dois=invalid_dois)
        else:
            # external template from file system
            jinja_env = Environment(
                loader=FileSystemLoader(searchpath=template['searchpath']),
                autoescape=True)
            user_template = jinja_env.get_template(template['name'])
            rendered_report = user_template.render(
                statistics=statistics,
                access_errors=access_errors,
                permanent=permanent_errors,
                redirects=permanent_redirects,
                exceptions=crawl_exceptions,
                mailto_links=mailto_links,
                invalid_dois=invalid_dois)

        if write_to == 'cli':
            print(rendered_report)
            return
        try:
            with open(write_to, 'w') as file:
                file.write(rendered_report)
            logging.info("Wrote report to file: %s",
                         pathlib.Path(write_to).resolve())
        except Exception:
            logging.exception('Exception while writing to file!',
                              exc_info=True)
            raise
