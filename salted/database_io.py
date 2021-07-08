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
    "Log the crawler's results to sqlite."

    def __init__(self,
                 mem_instance: memory_instance.MemoryInstance,
                 cache_file: Union[pathlib.Path, str] = None):
        self.cursor = mem_instance.get_cursor()
        self.cache_file_path = None
        if cache_file:
            self.cache_file_path = pathlib.Path(cache_file).resolve()

    def save_found_links(self,
                         links_found: list) -> None:
        "Save the links found into the memory database."
        if not links_found:
            logging.debug('No links in this file to save them.')
        else:
            self.cursor.executemany('''
            INSERT INTO queue
            (filePath, hostname, url, normalizedUrl, linktext)
            VALUES(?, ?, ?, ?, ?);''', links_found)

    def save_found_dois(self,
                        dois_found: list) -> None:
        "Save a list of DOIs into the in memory database."
        if not dois_found:
            logging.debug('No DOI in this file to save them.')
            return None
        self.cursor.executemany('''
        INSERT INTO queue_doi
        (filePath, doi, description)
        VALUES (?, ?, ?);''', dois_found)
        return None

    def urls_to_check(self) -> Optional[list]:
        "Return a list of all distinct URLs to check."
        self.cursor.execute('SELECT DISTINCT normalizedUrl FROM queue;')
        return self.cursor.fetchall()

    def get_dois_to_check(self) -> Optional[list]:
        """Return all DOI that are not validated yet or None
           if DOI queue is empty."""
        # Maybe replace it with a generator but for several thousnad DOIs
        # this way should be no problem!
        self.cursor.execute('SELECT DISTINCT doi FROM queue_doi;')
        query_result = self.cursor.fetchall()
        doi_list = [doi[0] for doi in query_result]
        return doi_list if doi_list else None

    def log_url_is_fine(self,
                        url: str) -> None:
        """If a request to an URL returns a HTTP status code that indicates a
           working hyperlink, note that with a timestamp."""
        self.cursor.execute('''
            INSERT INTO validUrls
            (normalizedUrl, lastValid)
            VALUES (?, strftime('%s','now'));''', [url])

    def save_valid_dois(self, valid_dois: list) -> None:
        """Permanently store a list of valid DOIs in the cache.
           Contrary to URLs, DOIs are made to be persistent - so no need
           to recheck them once they have been validated."""
        # TO DO: batches!!
        self.cursor.executemany('''
        INSERT OR IGNORE INTO validDois (doi) VALUES (?);''', valid_dois)

    def log_invalid_dois(self,
                         invalid_dois: list) -> None:
        # TO DO
        pass

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

        self.cursor.execute('SELECT COUNT(*) FROM queue;')
        num_links_before = self.cursor.fetchone()[0]

        self.cursor.execute('''DELETE FROM queue
                            WHERE normalizedUrl IN (
                            SELECT normalizedUrl FROM validUrls);''')

        self.cursor.execute('SELECT COUNT(*) FROM queue;')
        num_links_after = self.cursor.fetchone()[0]

        # if num_links_before > num_links_after:
        #     msg = (f"Tests for {num_links_before - num_links_after} " +
        #            "hyperlinks skipped - they checked out valid within " +
        #            f"the last {self.dont_check_again_within_hours} " +
        #            "hours.\n" +
        #            f"{num_links_after} unique links have to be tested.")
        #     logging.info(msg)
        return num_links_after

    def del_dois_that_can_be_skipped(self) -> None:
        "Delete DOI from the check queue which were already validated."
        self.cursor.execute('SELECT COUNT(*) FROM queue_doi;')
        num_dois_before = self.cursor.fetchone()[0]

        self.cursor.execute('''DELETE FROM queue_doi
                            WHERE doi IN (
                            SELECT doi FROM validDois);''')
        self.cursor.execute('SELECT COUNT(*) FROM queue_doi;')
        num_dois_after = self.cursor.fetchone()[0]

        if num_dois_before > num_dois_after:
            logging.info("Skipped tests for %s DOIs: already validated!",
                         (num_dois_before - num_dois_after))

    def count_errors(self) -> int:
        "Return the number of errors."
        self.cursor.execute('SELECT COUNT(*) FROM errors;')
        return self.cursor.fetchone()[0]

    def list_errors(self,
                    error_code: int) -> list:
        """Return a list of normalized URLs that yield a specific
           error code (from the HTTP status codes)."""
        self.cursor.execute('''SELECT normalizedUrl
                          FROM errors
                          WHERE error = ?;''', [error_code])
        urls_with_error = self.cursor.fetchall()
        if urls_with_error:
            return urls_with_error
        return list()
