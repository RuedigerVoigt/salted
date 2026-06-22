#!/usr/bin/python3

"""
Input Handler for salted
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026 Rüdiger Voigt and contributors
Released under the Apache License 2.0
"""

import logging
import pathlib
import sys
import urllib.parse
from collections import Counter

import userprovided
import userprovided.mail as mail_check
from tqdm.asyncio import tqdm  # type: ignore

from salted import database_io, parser


class InputHandler:
    """Read files and extract the hyperlinks inside them."""

    def __init__(self,
                 db: database_io.DatabaseIO,
                 quiet: bool = False,
                 max_file_size_mb: int = 20):
        """Initialize the InputHandler.

        Args:
            db: Database I/O handler for storing found links and errors.
            quiet: If True, suppress progress messages.
            max_file_size_mb: Maximum file size in megabytes to process.
                Files exceeding this limit are skipped. Default: 20 MB.
        """
        self.db = db
        self.quiet = quiet
        self.max_file_size_mb = max_file_size_mb
        self.cnt: Counter = Counter()
        self.parser = parser.Parser()

        # Map a file suffix to the name of the parser method that extracts
        # its URLs. Names (not bound methods) are stored so the method is
        # resolved on self.parser at call time. BibTeX is deliberately
        # absent: it is the only format that also returns a DOI list and
        # needs its own error handling, so it is dispatched separately in
        # _extract_links_and_dois().
        self._url_extractors = {
            ".htm": "extract_links_from_html",
            ".html": "extract_links_from_html",
            ".md": "extract_links_from_markdown",
            ".tex": "extract_links_from_tex",
        }

    def read_file_content(self,
                          path_to_file: pathlib.Path) -> str | None:
        """Return the file content or log an error if file cannot be accessed.

        Args:
            path_to_file: Path to the file to read.

        Returns:
            File content as a string, or None if the file could not be read.
        """
        content: str | None = None
        try:
            size_bytes = path_to_file.stat().st_size
            limit_bytes = self.max_file_size_mb * 1024 * 1024
            if size_bytes > limit_bytes:
                size_mb = size_bytes / (1024 * 1024)
                self.db.log_file_access_error(
                    str(path_to_file),
                    f'file too large ({size_mb:.1f} MB, limit {self.max_file_size_mb} MB)')
                return None
            try:
                with open(path_to_file, encoding='utf-8') as code:
                    content = code.read()
            except UnicodeDecodeError:
                logging.warning("File %s is not UTF-8, retrying with latin-1", path_to_file)
                with open(path_to_file, encoding='latin-1') as code:
                    content = code.read()
        except FileNotFoundError:
            self.db.log_file_access_error(
                str(path_to_file), 'file not found')
        except PermissionError:
            self.db.log_file_access_error(
                str(path_to_file), 'permission error')
        except TimeoutError:
            self.db.log_file_access_error(
                str(path_to_file), 'system timeout')
        except BlockingIOError:
            self.db.log_file_access_error(
                str(path_to_file), 'blocking IO')
        except Exception as unexpected:  # pylint: disable=W0703
            self.db.log_file_access_error(
                str(path_to_file), str(unexpected))
        return content

    def handle_found_urls(self,
                          file_path: pathlib.Path,
                          url_list: list) -> None:
        """Extract all hyperlinks from url_list and add them to the test queue.

        Normalizes URLs to eliminate duplicates before adding to queue.

        Args:
            file_path: Path to the file where URLs were found.
            url_list: List of [url, linktext] pairs extracted from the file.
        """

        links_found: list = []
        mailto_found: list = []

        for link in url_list:
            url = link[0]
            linktext = link[1]
            if url.startswith('http'):
                # It may be that multiple links point to the same resource.
                # Normalizing them means they only need to be tested once.
                # The non-normalized version is stored anyway, because in case
                # the link is broken, that version is used to show the user
                # the broken links on a specific page.
                try:
                    normalized_url = userprovided.url.normalize_url(url)
                except userprovided.err.QueryKeyConflict:
                    normalized_url = userprovided.url.normalize_url(
                        url, do_not_change_query_part=True)

                parsed_url = urllib.parse.urlparse(url)
                links_found.append([str(file_path),
                                    parsed_url.hostname,
                                    url,
                                    normalized_url,
                                    linktext])
                self.cnt['links_found'] += 1

            elif url.startswith('mailto:'):
                addresses = self.parser.extract_mails_from_mailto(url)
                if not addresses:
                    mailto_found.append((str(file_path), url, '', 0))
                else:
                    for address in addresses:
                        valid = 1 if mail_check.is_email(address) else 0
                        mailto_found.append((str(file_path), url, address, valid))
            else:
                # cannot check this kind of link
                self.cnt['unsupported_scheme'] += 1

        # Push the found links once for each file instead for all files
        # at once. The latter would kill performance for large document
        # collections.
        if links_found:
            self.db.save_found_links(links_found)
        if mailto_found:
            self.db.save_mailto_links(mailto_found)

    def handle_found_dois(self,
                          file_path: pathlib.Path,
                          doi_list: list) -> None:
        """Convert DOI list to the needed format and save to database.

        Sends DOIs to the database in batches for performance.

        Args:
            file_path: Path to the file where DOIs were found.
            doi_list: List of [doi, text] pairs extracted from the file.
        """
        if not doi_list:
            return None
        # The parser generated a list in the format [[doi, text], [doi, text]]
        #  - text being the key-value of the bibtex-entry and the field in
        # which the DOI was found.
        dois_found = list()
        for entry in doi_list:
            dois_found.append([str(file_path), entry[0], entry[1]])
        # In case of a bibliography that can be a very long list.
        # So feed it to sqlite in little pieces
        first = 0
        step = 50
        while first < len(dois_found):
            self.db.save_found_dois(dois_found[first:first + step])
            first += step
        return None

    def _extract_links_and_dois(self,
                                file_path: pathlib.Path,
                                content: str) -> tuple[list | None, list | None]:
        """Extract URLs (and DOIs for BibTeX) from one file's content.

        Dispatches on the file suffix via self._url_extractors. Every
        supported format yields a URL list; only BibTeX additionally yields
        a DOI list and is handled separately because it can fail to parse.

        Args:
            file_path: Path to the file being scanned (used for the suffix
                and for error messages).
            content: The file's text content.

        Returns:
            A (url_list, doi_list) tuple. doi_list is None for every format
            except BibTeX, and is also None when a BibTeX file cannot be
            parsed (the parse error is logged as a file access error).

        Raises:
            RuntimeError: If the suffix has no registered extractor. This
                should never happen because callers pre-filter by supported
                extension.
        """
        if file_path.suffix == ".bib":
            try:
                url_list, doi_list = self.parser.extract_links_from_bib(content)
                return url_list, doi_list
            except Exception as e:
                self.db.log_file_access_error(
                    str(file_path), f'BibTeX parse error: {e}')
                return None, None

        extractor_name = self._url_extractors.get(file_path.suffix)
        if extractor_name is None:
            raise RuntimeError('Invalid extension. Should never happen.')
        extractor = getattr(self.parser, extractor_name)
        return extractor(content), None

    def scan_files(self,
                   files_to_check: list[pathlib.Path]) -> None:
        """Scan files for hyperlinks and DOIs.

        Scans each file in the provided list, extracts URLs and DOIs,
        and writes them to the SQLite database.

        Args:
            files_to_check: List of file paths to scan for links.
        """
        if not files_to_check:
            logging.warning('No files to check')
            return None

        # Reset counter as check_links might be used multiple times and this
        # should be per run:
        self.cnt['links_found'] = 0

        if not self.quiet:
            print("Scanning files for links:")
        for file_path in tqdm(files_to_check, disable=self.quiet or not sys.stdout.isatty()):
            content = self.read_file_content(file_path)
            if not content:
                # If for any reason this file could not be read, try the next.
                continue

            url_list, doi_list = self._extract_links_and_dois(file_path, content)

            if url_list:
                self.handle_found_urls(file_path, url_list)
            if doi_list:
                self.handle_found_dois(file_path, doi_list)

        return None
