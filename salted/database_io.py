#!/usr/bin/python3

"""
Log the crawler's results to sqlite.
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026 Rüdiger Voigt and contributors
Released under the Apache License 2.0
"""

import logging
import pathlib

from salted import doi_format, memory_instance

logger = logging.getLogger(__name__)

# Report text for a link userprovided cannot normalize, e.g. one without a
# host, with an invalid port, or longer than it accepts.
MALFORMED_URL_REASON = 'Malformed URL - not checked'


class DatabaseIO:
    """Log the crawler's results to SQLite database.

    Provides methods to save found links, log validation results, and
    manage the check queue.
    """

    def __init__(self,
                 mem_instance: memory_instance.MemoryInstance,
                 cache_file: pathlib.Path | str | None = None,
                 quiet: bool = False):
        """Initialize the database I/O handler.

        Args:
            mem_instance: In-memory database instance for storing results.
            cache_file: Path to the cache file on disk. If None, no cache is used.
            quiet: If True, suppress progress messages.
        """
        self.cursor = mem_instance.get_cursor()
        self.quiet = quiet
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
            logger.debug('No links in this file to save them.')
        else:
            self.cursor.executemany('''
            INSERT INTO queue
            (filePath, hostname, url, normalizedUrl, linktext)
            VALUES(?, ?, ?, ?, ?);''', links_found)

    def save_found_dois(self,
                        dois_found: list) -> None:
        """Save DOIs from BibTeX doi fields into the in memory database.

        Args:
            dois_found: List of tuples (filePath, doi, description,
                wellFormed) where wellFormed is 1 or 0.
        """
        if not dois_found:
            logger.debug('No DOI in this file to save them.')
            return
        self.cursor.executemany('''
        INSERT INTO foundDois
        (filePath, doi, description, wellFormed)
        VALUES (?, ?, ?, ?);''', dois_found)

    def log_outdated_doi_links(self,
                               outdated: list) -> None:
        """Save DOIs written in an outdated form.

        Args:
            outdated: List of tuples (filePath, found, recommended,
                description).
        """
        if not outdated:
            return
        self.cursor.executemany('''
        INSERT INTO outdatedDoiLinks
        (filePath, found, recommended, description)
        VALUES (?, ?, ?, ?);''', outdated)

    def confirm_dois_from_links(self) -> None:
        """Store the DOIs of doi.org links that answered as fine.

        doi.org answers 302 for a registered DOI and 404 for an unknown one,
        for every registration agency, without the publisher being
        contacted. A doi.org link that was checked as fine therefore
        confirms its DOI - also for the same DOI in a BibTeX doi field.

        Covers links checked in this run and links still valid in the URL
        cache, as long as they are in the queue. Call it before cached
        links are removed from the queue and again after the URL check.
        """
        self.cursor.execute('''
            SELECT DISTINCT queue.url FROM queue
            INNER JOIN validUrls
            ON queue.normalizedUrl = validUrls.normalizedUrl
            WHERE queue.hostname IN ('doi.org', 'dx.doi.org');''')
        confirmed = []
        for (url, ) in self.cursor.fetchall():
            doi = doi_format.doi_from_link(url)
            if doi and doi_format.is_well_formed(doi):
                confirmed.append((doi.lower(), ))
        self.cursor.executemany(
            'INSERT OR IGNORE INTO validDois (doi) VALUES (?);', confirmed)

    def count_dois(self) -> int:
        """Return the number of distinct DOIs found in BibTeX doi fields.

        Returns:
            Count of distinct DOIs, compared case-insensitively.
        """
        self.cursor.execute(
            'SELECT COUNT(DISTINCT lower(doi)) FROM foundDois;')
        return self.cursor.fetchone()[0]

    def count_malformed_dois(self) -> int:
        """Return the number of distinct DOIs that fail the format check.

        Returns:
            Count of distinct malformed DOIs, compared case-insensitively.
        """
        self.cursor.execute('''SELECT COUNT(DISTINCT lower(doi))
                            FROM foundDois WHERE wellFormed = 0;''')
        return self.cursor.fetchone()[0]

    def count_confirmed_dois(self) -> int:
        """Return how many distinct found DOIs a doi.org link confirmed.

        Returns:
            Count of distinct DOIs from BibTeX doi fields that are stored as
            confirmed, in this run or in the cache.
        """
        self.cursor.execute('''SELECT COUNT(DISTINCT lower(doi))
                            FROM foundDois
                            WHERE wellFormed = 1 AND lower(doi) IN (
                            SELECT lower(doi) FROM validDois);''')
        return self.cursor.fetchone()[0]

    def urls_to_check(self) -> list:
        """Return a list of all distinct URLs to check.

        URLs that already have an exception at this point were rejected
        while reading the files (see log_malformed_url) and are left out.

        Returns:
            List of tuples containing distinct normalized URLs; empty list if none.
        """
        self.cursor.execute('''SELECT DISTINCT normalizedUrl FROM queue
                            WHERE normalizedUrl NOT IN (
                            SELECT normalizedUrl FROM exceptions);''')
        return self.cursor.fetchall()

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

    def save_mailto_links(self,
                          mailto_links: list) -> None:
        """Save mailto links found in files to the database.

        Args:
            mailto_links: List of tuples (filePath, url, address, valid)
                where valid is 1 if is_email() passed, 0 if malformed.
        """
        if not mailto_links:
            return
        self.cursor.executemany('''
            INSERT INTO mailtoLinks (filePath, url, address, valid)
            VALUES (?, ?, ?, ?);''', mailto_links)

    def log_internal_link_finding(self,
                                  file_path: str,
                                  url: str,
                                  linktext: str,
                                  reason: str,
                                  is_error: int) -> None:
        """Log a finding for an internal link.

        Args:
            file_path: Path to the file containing the link.
            url: The link exactly as written in the document.
            linktext: The link's text content.
            reason: Why the link is broken or could not be verified.
            is_error: 1 for a broken link, 0 for an unverifiable one.
        """
        self.cursor.execute('''
            INSERT INTO internalLinkFindings
            (filePath, url, linktext, reason, isError)
            VALUES (?, ?, ?, ?, ?);''',
            [file_path, url, linktext, reason, is_error])

    def count_internal_link_errors(self) -> int:
        """Return the number of broken internal links.

        Unverifiable links (isError = 0) are not counted, so they can
        never fail a CI run.

        Returns:
            Count of internal links whose target is missing.
        """
        self.cursor.execute(
            'SELECT COUNT(*) FROM internalLinkFindings WHERE isError = 1;')
        return self.cursor.fetchone()[0]

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

    def log_malformed_url(self,
                          url: str) -> None:
        """Log a link that cannot be requested because it is malformed.

        Stored as an exception under the link's own spelling, which is also
        its normalizedUrl in the queue. Logged only once per URL: the report
        joins exceptions with the queue, so a second row would list every
        occurrence of the link twice.

        Args:
            url: The link exactly as written in the document.
        """
        self.cursor.execute('''INSERT INTO exceptions
                            SELECT ?, ?
                            WHERE NOT EXISTS (
                            SELECT 1 FROM exceptions WHERE normalizedUrl = ?);''',
                            [url, MALFORMED_URL_REASON, url])

    def count_malformed_urls(self) -> int:
        """Return the number of distinct malformed links.

        Returns:
            Count of links logged by log_malformed_url.
        """
        self.cursor.execute('SELECT COUNT(*) FROM exceptions WHERE reason = ?;',
                            [MALFORMED_URL_REASON])
        return self.cursor.fetchone()[0]

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

    def count_file_access_errors(self) -> int:
        """Return the number of files that could not be read.

        Covers every reason a file was skipped: missing, no permission,
        over the size limit, or unparseable (such as a malformed BibTeX
        file). Each one means links that were never checked.

        Returns:
            Total count of logged file access errors.
        """
        self.cursor.execute('SELECT COUNT(*) FROM fileAccessErrors;')
        return self.cursor.fetchone()[0]

    def count_distinct_urls(self) -> int:
        """Return the number of distinct normalized URLs in the check queue.

        Returns:
            Number of distinct targets the found hyperlinks point to.
        """
        self.cursor.execute(
            'SELECT COUNT(DISTINCT normalizedUrl) FROM queue;')
        return self.cursor.fetchone()[0]

    def count_cached_urls(self) -> int:
        """Return how many distinct queued URLs are still valid in the cache.

        Must be called before del_links_that_can_be_skipped removes them
        from the queue.

        Returns:
            Number of distinct targets that need no new request.
        """
        self.cursor.execute('''SELECT COUNT(DISTINCT normalizedUrl) FROM queue
                            WHERE normalizedUrl IN (
                            SELECT normalizedUrl FROM validUrls);''')
        return self.cursor.fetchone()[0]

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
            if not self.quiet:
                print(f"Skipped {num_skipped} cached URL{'s' if num_skipped != 1 else ''} (still valid in cache)")
        return num_links_after

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
