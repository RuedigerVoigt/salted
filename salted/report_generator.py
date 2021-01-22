#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Report generator for salted
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020: Released under the Apache License 2.0
"""
import logging
import pathlib
from typing import Optional, Union

from jinja2 import Environment, FileSystemLoader, PackageLoader

from salted import database_io


class ReportGenerator:
    """Generates a report about broken links and redirects for display.
       Reports can be styled using Jinja2 templates."""

    def __init__(self,
                 db_object: database_io.DatabaseIO,
                 show_redirects: bool = True,
                 show_exceptions: bool = True):
        self.db = db_object
        self.show_redirects = show_redirects
        self.show_exceptions = show_exceptions
        self.replace_path_by_url: Optional[dict] = None

    def __list_errors(self,
                      error_code: int) -> list:
        """Return a list of normalized URLs that yield a specific
           error code (from the HTTP status codes)."""
        cursor = self.db.get_cursor()
        cursor.execute('''SELECT normalizedUrl
                               FROM errors
                               WHERE error = ?;''', [error_code])
        urls_with_error = cursor.fetchall()
        if urls_with_error:
            return urls_with_error
        return list()

    def rewrite_path(self,
                     path_to_rewrite: str) -> str:
        """In a given path, replace the path to the folder
           with the base URL."""
        # Silence mypy index error, because this assures the values
        # are available:
        if not self.replace_path_by_url['path_to_be_replaced']:  # type: ignore
            raise ValueError('Cannot replace in URL not knowing what.')
        if not self.replace_path_by_url['replace_with_url']:  # type: ignore
            raise ValueError('Cannot replace in URL not knowing with what.')

        return path_to_rewrite.replace(
            self.replace_path_by_url['path_to_be_replaced'],  # type: ignore
            self.replace_path_by_url['replace_with_url'],  # type: ignore
            1)

    def generate_access_error_list(self) -> Optional[list]:
        """If there were errors reading the files (FileNotFoundError, ...)
           return a list of dictionaries containing the file path
           and the reason."""
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
        """If the crawl found hyperlinks that yield permanent errors, return
           a list of dictionaries containing the file path, the number of
           permanent errors in that file, and a list of the actual errors."""
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
        """If the crawl found hyperlinks that yield permanent redirects, return
           a list of dictionaries containing the file path, the number of
           permanent redirects in that file, and a list of the redirects."""
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
        """If it was not possible due to exceptions to check or more links,
           return a list of dictionaries containing the file path, the number
           of exception causing links in that file, and a list of the
           actual exceptions."""
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

    def generate_report(self,
                        statistics: dict,
                        template: dict,
                        write_to: Union[str, pathlib.Path],
                        replace_path_by_url: dict = None
                        ) -> None:
        """Generate the report for the user with a Jinja2 template.
           Either display it at the command line interface or write
           it to a file. """
        # The base URL is always given. Invalidate the parameter if no
        # replacement is provided.
        if not replace_path_by_url['replace_with_url']:  # type: ignore[index]
            replace_path_by_url = None
        else:
            self.replace_path_by_url = replace_path_by_url

        access_errors = self.generate_access_error_list()

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
            jinja_env = Environment(loader=PackageLoader('salted', 'templates'))
            builtin_template = jinja_env.get_template(template['name'])
            rendered_report = builtin_template.render(
                statistics=statistics,
                access_errors=access_errors,
                permanent=permanent_errors,
                redirects=permanent_redirects,
                exceptions=crawl_exceptions)
        else:
            # external template from file system
            jinja_env = Environment(loader=FileSystemLoader(
                searchpath=template['searchpath']))
            user_template = jinja_env.get_template(template['name'])
            rendered_report = user_template.render(
                statistics=statistics,
                access_errors=access_errors,
                permanent=permanent_errors,
                redirects=permanent_redirects,
                exceptions=crawl_exceptions)

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
