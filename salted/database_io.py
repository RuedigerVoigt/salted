#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Handle the database and cache for salted.
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2021: Released under the Apache License 2.0
"""

import logging
import pathlib
import sqlite3
from typing import Optional, Union


class DatabaseIO:
    """Create the database schema (tables, views, ...), handle the cache file
       and log the crawler's results to sqlite. """

    def __init__(self,
                 dont_check_again_within_hours: int,
                 cache_file: Union[pathlib.Path, str] = None):

        self.dont_check_again_within_hours = dont_check_again_within_hours

        self.cache_file_path: Optional[pathlib.Path] = None
        if cache_file:
            self.cache_file_path = pathlib.Path(cache_file).resolve()
            logging.debug('Absolute path to cache file: %s',
                          self.cache_file_path)
            self.check_cache_file_path()

        # Prepare to create a sqlite database in memory
        # Not actually created here, because users might reuse the object
        # for multiple checks on different document sets. Therefore the
        # check_links() function in __main__.py will call init_in_memory_db
        # and tear_down_in_memory_db().
        self.conn = sqlite3.connect(
            ':memory:',
            isolation_level=None  # reenable autocommit
            )
        self.cursor = self.conn.cursor()

    def get_cursor(self) -> sqlite3.Cursor:
        """Returns a valid cursor. is used by the report generator that
           directly accesses the database outside this class.
           If user reuse the object a new database is created and in that case
           the old cursor is invalid."""
        return self.cursor

    def reinitialize_in_memory_db(self):
        """If there is already an in memory instance, close it. Then create
           and initialize a new in memory instance of the database by
           creating its schema and loading the disk cache (if available)."""
        logging.debug('Reinitialize in memory database.')
        self.tear_down_in_memory_db()
        self.conn = sqlite3.connect(
            ':memory:',
            isolation_level=None  # reenable autocommit
            )
        self.cursor = self.conn.cursor()
        self.create_schema()
        self.load_disk_cache()

    def tear_down_in_memory_db(self):
        """If there is an active in memory instance, close the connection.
           All data not stored elsewhere will be lost."""
        if self.conn:
            logging.debug("tear down in memory instance")
            self.conn.close()

    def check_cache_file_path(self) -> None:
        """Check if the given path is valid in order to fail if it is not
           before the linkcheck runs.
           Raise ValueError if the path is a directory or if parent
           folders do not exists."""

        if not self.cache_file_path:
            raise RuntimeError('check_cache_file path called without path set')

        if self.cache_file_path.exists() and self.cache_file_path.is_file():
            return

        # Established that the file does not exist, but check if it can
        # exist before returning False.
        if not self.cache_file_path.parent.is_dir():
            raise ValueError('Incorrect path to cache_file. ' +
                             'Parameter cache_file must be the path to ' +
                             'a file and parent directories must exist.')
        if self.cache_file_path.is_dir():
            raise ValueError('Parameter cache_file is a directory, ' +
                             'but must include file name!')

    def create_schema(self) -> None:
        """Create the SQLite database schema. """
        self.cursor.execute('''
            CREATE TABLE links (
            filePath text,
            hostname text,
            url text,
            normalizedUrl text,
            linktext text);''')
        self.cursor.execute('''
            CREATE TABLE errors (
            normalizedUrl text,
            error integer);''')
        self.cursor.execute('''
            CREATE TABLE fileAccessErrors (
                filePath text,
                problem text
                );''')
        self.cursor.execute('''
            CREATE TABLE permanentRedirects (
                normalizedUrl text,
                error integer);''')
        self.cursor.execute('''
            CREATE TABLE exceptions (
            normalizedUrl text,
            reason text);''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS validUrls (
            normalizedUrl text,
            lastValid integer);''')

        logging.debug("Created database schema.")

    def load_disk_cache(self) -> None:
        """If there is a cache file open it, read the valid URLs and
           load them into the in-memory instance of sqlite."""

        if not self.cache_file_path:
            return

        try:
            disk_cache = sqlite3.connect(
                self.cache_file_path,
                isolation_level=None  # reenable autocommit
            )
            disk_cache_cursor = disk_cache.cursor()
            disk_cache_cursor.execute('''
                SELECT
                normalizedUrl, lastValid
                FROM validUrls
                WHERE lastValid > (strftime('%s','now') - (? * 3600));''',
                [self.dont_check_again_within_hours])
            valid_urls = disk_cache_cursor.fetchall()
            disk_cache.close()

            if valid_urls:
                self.cursor.executemany('''
                    INSERT INTO validUrls
                    (normalizedUrl, lastValid)
                    VALUES (?, ?);''', valid_urls)

        except Exception:
            logging.debug('No cache file or could not read it.', exc_info=True)
            pass

    def generate_indices(self) -> None:
        """Add indices to the in memory database. This is not done on creation
           for performance reasons."""
        # While adding links to the database the index is not needed,
        # but would be updated with every insert. It is faster to create it
        # once the table has it contents.
        self.cursor.execute('''
            CREATE INDEX IF NOT EXISTS index_timestamp
            ON validUrls (lastValid);''')
        self.cursor.execute('''
            CREATE INDEX IF NOT EXISTS index_normalized_url
            ON links (normalizedUrl);''')

    def generate_db_views(self) -> None:
        """ Generate Views for Analytics and Output Generating."""
        # Separate function to execute after all links have been checked
        # and the respective tables are stable."""
        self.cursor.execute('''
            CREATE VIEW IF NOT EXISTS v_errorCountByFile AS
            SELECT COUNT(*) AS numErrors, filePath
            FROM links
            WHERE normalizedUrl IN (
            SELECT normalizedUrl FROM errors
            ) GROUP BY filePath;''')
        self.cursor.execute('''
            CREATE VIEW IF NOT EXISTS v_redirectCountByFile AS
            SELECT COUNT(*) AS numRedirects, filePath
            FROM links
            WHERE normalizedUrl IN (
            SELECT normalizedUrl FROM permanentRedirects
            ) GROUP BY filePath;''')
        self.cursor.execute('''
            CREATE VIEW IF NOT EXISTS v_exceptionCountByFile AS
            SELECT COUNT(*) AS numExceptions, filePath
            FROM links
            WHERE normalizedUrl IN (
            SELECT normalizedUrl FROM exceptions
            ) GROUP BY filePath;''')

        self.cursor.execute('''
            CREATE VIEW IF NOT EXISTS v_errorsByFile AS
            SELECT links.filePath,
            links.url,
            links.linktext,
            errors.error AS httpCode
            FROM links
            INNER JOIN errors
            ON links.normalizedUrl = errors.normalizedUrl;''')

        self.cursor.execute('''
            CREATE VIEW IF NOT EXISTS v_redirectsByFile AS
            SELECT links.filePath,
            links.url,
            links.linktext,
            permanentRedirects.error AS httpCode
            FROM links
            INNER JOIN permanentRedirects
            ON links.normalizedUrl = permanentRedirects.normalizedUrl;''')

        self.cursor.execute('''
            CREATE VIEW IF NOT EXISTS v_exceptionsByFile AS
            SELECT links.filePath,
            links.url,
            links.linktext,
            exceptions.reason
            FROM links
            INNER JOIN exceptions
            ON links.normalizedUrl = exceptions.normalizedUrl;''')

        logging.debug('Created Views for analytics and output generating.')

    def save_found_links(self,
                         links_found: list) -> None:
        """Save the links found into the memory database."""
        if not links_found:
            logging.debug('No links in this file to save them.')
        else:
            self.cursor.executemany('''
            INSERT INTO links
            (filePath, hostname, url, normalizedUrl, linktext)
            VALUES(?, ?, ?, ?, ?);''', links_found)

    def urls_to_check(self) -> Optional[list]:
        """Return a list of all distinct URLs to check."""
        self.cursor.execute('SELECT DISTINCT normalizedUrl FROM links;')
        return self.cursor.fetchall()

    def log_url_is_fine(self,
                        url: str) -> None:
        """If a request to an URL returns a HTTP status code that indicates a
           working hyperlink, note that with a timestamp."""
        self.cursor.execute('''
            INSERT INTO validUrls
            (normalizedUrl, lastValid)
            VALUES (?, strftime('%s','now'));''', [url])

    def log_error(self,
                  url: str,
                  error_code: int) -> None:
        """An error is logged for HTTP status codes that indicate a permanently
           broken link like '404 - File Not found' or '410 Gone'."""
        self.cursor.execute('INSERT INTO errors VALUES (?, ?);',
                            [url, error_code])

    def log_redirect(self,
                     url: str,
                     code: int) -> None:
        """Logs permanent redirects. Those links *should* be fixed. """
        self.cursor.execute('''INSERT INTO permanentRedirects
                               (normalizedUrl, error)
                               VALUES (?, ?);''', [url, code])

    def log_exception(self,
                      url: str,
                      exception_str: str) -> None:
        """An exception is logged if it was not possible to check
           a specific URL."""
        self.cursor.execute('''INSERT INTO exceptions VALUES (?, ?);''',
                            [url, exception_str])

    def log_file_access_error(self,
                              file_path: str,
                              reason: str) -> None:
        "Log the reason if a file cannot be read."
        self.cursor.execute(
            'INSERT INTO fileAccessErrors VALUES (?, ?);',
            [file_path, reason])

    def del_links_that_can_be_skipped(self) -> int:
        """If links from a non-expired cache have been read, try to eliminate
           them in the list of URLs to check.
           Return the absolute number of (non-normalized) URLs to check."""

        self.cursor.execute('SELECT COUNT(*) FROM links;')
        num_links_before = self.cursor.fetchone()[0]

        self.cursor.execute('''DELETE FROM links
                            WHERE normalizedUrl IN (
                            SELECT normalizedUrl FROM validUrls);''')

        self.cursor.execute('SELECT COUNT(*) FROM links;')
        num_links_after = self.cursor.fetchone()[0]

        if num_links_before > num_links_after:
            msg = (f"Tests for {num_links_before - num_links_after} " +
                   "hyperlinks skipped - they checked out valid within " +
                   f"the last {self.dont_check_again_within_hours} " +
                   "hours.\n" +
                   f"{num_links_after} unique links have to be tested.")
            logging.info(msg)
        return num_links_after

    def count_errors(self) -> int:
        """Return the number of errors. """
        self.cursor.execute('SELECT COUNT(*) FROM errors;')
        return self.cursor.fetchone()[0]

    def overwrite_cache_file(self) -> None:
        """Write the current in-memory database into a file.
           Overwrite any file in the given path."""

        self.cache_file_path.unlink(missing_ok=True)  # type: ignore[union-attr]

        if self.cache_file_path:
            new_cache_file = sqlite3.connect(self.cache_file_path)
            with new_cache_file:
                self.conn.backup(new_cache_file, name='main')
            new_cache_file.close()
