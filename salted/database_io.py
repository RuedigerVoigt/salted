#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Log the crawler's results to sqlite.
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2021 Rüdiger Voigt
Released under the Apache License 2.0
"""

import logging
import pathlib
from typing import Optional, Union

from salted import memory_instance


class DatabaseIO:
    """Log the crawler's results to SQLite database.

    Provides methods to save found links, log validation results, and
    manage the check queue.
    """

    def __init__(self,
                 mem_instance: memory_instance.MemoryInstance,
                 cache_file: Union[pathlib.Path, str, None] = None):
        """Initialize the database I/O handler.

        Args:
            mem_instance: In-memory database instance for storing results.
            cache_file: Path to the cache file on disk. If None, no cache is used.
        """
        self.cursor = mem_instance.get_cursor()
        self.cache_file_path = None
        if cache_file:
            self.cache_file_path = pathlib.Path(cache_file).resolve()

    def save_found_links(self,
                         links_found: list) -> None:
        """Save the links found into the memory database.

        Args:
            links_found: List of tuples containing link information
                (filePath, hostname, url, normalizedUrl, linktext).
        """
        if not links_found:
            logging.debug('No links in this file to save them.')
        else:
            self.cursor.executemany('''
            INSERT INTO queue
            (filePath, hostname, url, normalizedUrl, linktext)
            VALUES(?, ?, ?, ?, ?);''', links_found)

    def save_found_dois(self,
                        dois_found: list) -> None:
        """Save a list of DOIs into the in memory database.

        Args:
            dois_found: List of tuples containing DOI information
                (filePath, doi, description).
        """
        if not dois_found:
            logging.debug('No DOI in this file to save them.')
            return None
        self.cursor.executemany('''
        INSERT INTO queue_doi
        (filePath, doi, description)
        VALUES (?, ?, ?);''', dois_found)
        return None

    def urls_to_check(self) -> Optional[list]:
        """Return a list of all distinct URLs to check.

        Returns:
            List of tuples containing distinct normalized URLs, or None if empty.
        """
        self.cursor.execute('SELECT DISTINCT normalizedUrl FROM queue;')
        return self.cursor.fetchall()

    def get_dois_to_check(self) -> Optional[list]:
        """Return all DOIs that are not validated yet.

        Returns:
            List of DOI strings, or None if DOI queue is empty.
        """
        # Maybe replace it with a generator but for several thousnad DOIs
        # this way should be no problem!
        self.cursor.execute('SELECT DISTINCT doi FROM queue_doi;')
        query_result = self.cursor.fetchall()
        doi_list = [doi[0] for doi in query_result]
        return doi_list if doi_list else None

    def log_url_is_fine(self,
                        url: str) -> None:
        """Log a URL as valid with a timestamp.

        Args:
            url: The normalized URL that returned a successful HTTP status code.
        """
        self.cursor.execute('''
            INSERT INTO validUrls
            (normalizedUrl, lastValid)
            VALUES (?, strftime('%s','now'));''', [url])

    def save_valid_dois(self, valid_dois: list) -> None:
        """Permanently store a list of valid DOIs in the cache.

        Contrary to URLs, DOIs are made to be persistent identifiers,
        so no need to recheck them once they have been validated.

        Args:
            valid_dois: List of validated DOI strings to store in cache.
        """
        # TO DO: batches!!
        self.cursor.executemany('''
        INSERT OR IGNORE INTO validDois (doi) VALUES (?);''', valid_dois)

    def log_invalid_dois(self,
                         invalid_dois: list) -> None:
        """Log an invalid DOI.

        Args:
            invalid_dois: List of invalid DOI strings to log.
        """
        # TO DO
        pass

    def log_error(self,
                  url: str,
                  error_code: int) -> None:
        """Log a permanent error for a URL.

        An error is logged for HTTP status codes that indicate a permanently
        broken link like '404 - File Not found' or '410 Gone'.

        Args:
            url: The normalized URL that returned an error.
            error_code: HTTP status code indicating the error type.
        """
        self.cursor.execute('INSERT INTO errors VALUES (?, ?);',
                            [url, error_code])

    def log_redirect(self,
                     url: str,
                     code: int) -> None:
        """Log permanent redirects.

        Those links *should* be fixed.

        Args:
            url: The normalized URL that returned a redirect.
            code: HTTP status code indicating the redirect type (e.g., 301, 308).
        """
        self.cursor.execute('''INSERT INTO permanentRedirects
                               (normalizedUrl, error)
                               VALUES (?, ?);''', [url, code])

    def log_exception(self,
                      url: str,
                      exception_str: str) -> None:
        """Log an exception that occurred while checking a URL.

        Args:
            url: The normalized URL that caused the exception.
            exception_str: String representation of the exception.
        """
        self.cursor.execute('''INSERT INTO exceptions VALUES (?, ?);''',
                            [url, exception_str])

    def log_file_access_error(self,
                              file_path: str,
                              reason: str) -> None:
        """Log the reason if a file cannot be read.

        Args:
            file_path: Path to the file that could not be accessed.
            reason: Description of why the file could not be accessed.
        """
        self.cursor.execute(
            'INSERT INTO fileAccessErrors VALUES (?, ?);',
            [file_path, reason])

    def del_links_that_can_be_skipped(self) -> int:
        """Delete links from the check queue that are still valid in the cache.

        If links from a non-expired cache have been read, eliminate them
        from the list of URLs to check.

        Returns:
            The absolute number of (non-normalized) URLs still to check.
        """

        self.cursor.execute('SELECT COUNT(*) FROM queue;')
        num_links_before = self.cursor.fetchone()[0]

        self.cursor.execute('''DELETE FROM queue
                            WHERE normalizedUrl IN (
                            SELECT normalizedUrl FROM validUrls);''')

        self.cursor.execute('SELECT COUNT(*) FROM queue;')
        num_links_after = self.cursor.fetchone()[0]

        if num_links_before > num_links_after:
            num_skipped = num_links_before - num_links_after
            print(f"Skipped {num_skipped} cached URL{'s' if num_skipped != 1 else ''} (still valid in cache)")
        return num_links_after

    def del_dois_that_can_be_skipped(self) -> None:
        """Delete DOIs from the check queue that were already validated.

        DOIs that have been previously validated are removed from the
        queue to avoid redundant checks.
        """
        self.cursor.execute('SELECT COUNT(*) FROM queue_doi;')
        num_dois_before = self.cursor.fetchone()[0]

        self.cursor.execute('''DELETE FROM queue_doi
                            WHERE doi IN (
                            SELECT doi FROM validDois);''')
        self.cursor.execute('SELECT COUNT(*) FROM queue_doi;')
        num_dois_after = self.cursor.fetchone()[0]

        if num_dois_before > num_dois_after:
            num_skipped = num_dois_before - num_dois_after
            print(f"Skipped {num_skipped} cached DOI{'s' if num_skipped != 1 else ''} (already validated)")

    def count_errors(self) -> int:
        """Return the number of errors.

        Returns:
            Total count of logged errors.
        """
        self.cursor.execute('SELECT COUNT(*) FROM errors;')
        return self.cursor.fetchone()[0]

    def list_errors(self,
                    error_code: int) -> list:
        """Return a list of normalized URLs that yield a specific error code.

        Args:
            error_code: HTTP status code to filter by (e.g., 404, 410).

        Returns:
            List of tuples containing normalized URLs with the specified error code.
        """
        self.cursor.execute('''SELECT normalizedUrl
                          FROM errors
                          WHERE error = ?;''', [error_code])
        urls_with_error = self.cursor.fetchall()
        if urls_with_error:
            return urls_with_error
        return list()
