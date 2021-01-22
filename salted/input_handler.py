#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Input Handler for salted
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2021: Released under the Apache License 2.0
"""

from collections import Counter
import logging
import pathlib
from typing import List, Optional
import urllib.parse

import userprovided
from tqdm.asyncio import tqdm  # type: ignore

from salted import database_io
from salted import parser


class InputHandler:
    """Methods to find files and the hyperlinks inside them."""

    def __init__(self,
                 db: database_io.DatabaseIO):
        self.db = db
        self.cnt: Counter = Counter()
        self.parser = parser.Parser()

    @staticmethod
    def find_files_by_extensions(
            path_to_base_folder: pathlib.Path,
            suffixes: set = {".htm", ".html", '.md', '.tex'}
                                 ) -> List[pathlib.Path]:
        """Find all files with specific file type suffixes in the base folder
           and its subfolders. If no file suffix is specified, this will look
           for all file formats supported by salted."""
        # Pylint  warns about the set as default, but that is wanted here:
        # pylint: disable=W0102
        files_to_check = []
        path_to_check = pathlib.Path(path_to_base_folder)
        all_files = path_to_check.glob('**/*')
        for candidate in all_files:
            if candidate.suffix in suffixes:
                files_to_check.append(candidate.resolve())
        logging.debug('Found %s files', len(files_to_check))
        return files_to_check

    def find_html_files(self,
                        path_to_base_folder: pathlib.Path
                        ) -> List[pathlib.Path]:
        "Find all HTML files in the base folder and its subfolders."
        return self.find_files_by_extensions(
            path_to_base_folder,
            {".htm", ".html"})

    def find_markdown_files(self,
                            path_to_base_folder: pathlib.Path
                            ) -> List[pathlib.Path]:
        "Find all markdown files in the base folder and its subfolders."
        return self.find_files_by_extensions(
            path_to_base_folder,
            {".md"})

    def find_tex_files(self,
                       path_to_base_folder: pathlib.Path
                       ) -> List[pathlib.Path]:
        "Find all .tex files in the base folder and its subfolders."
        return self.find_files_by_extensions(
            path_to_base_folder,
            {".tex"})

    def read_file_content(self,
                          path_to_file: pathlib.Path) -> Optional[str]:
        "Return the file content or log an error if file cannot be accessed."
        content: Optional[str] = None
        try:
            with open(path_to_file, 'r') as code:
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
        finally:  # pylint: disable=W0150
            return content

    def scan_files_for_links(self,
                             files_to_check: List[pathlib.Path]) -> None:
        """Scan each file within a list of paths for hyperlinks and write
           those to the SQLite database. """
        if not files_to_check:
            logging.warning('No files to check')
            return None

        # Reset counter as check_links might be used multiple times and this
        # should be per run:
        self.cnt['links_found'] = 0

        print("Scanning files for links:")
        for file_path in tqdm(files_to_check):
            content = self.read_file_content(file_path)
            if not content:
                # If for any reason this file could not be read, try the next.
                continue

            if file_path.suffix in {".htm", ".html"}:
                extracted = self.parser.extract_links_from_html(content)
            elif file_path.suffix in {".md"}:
                extracted = self.parser.extract_links_from_markdown(content)
            elif file_path.suffix in {".tex"}:
                extracted = self.parser.extract_links_from_tex(content)
            else:
                raise RuntimeError('Invalid extension. Should never happen.')

            links_found: list = []
            mailto_found: list = []
            for link in extracted:
                url = link[0]
                linktext = link[1]
                if url.startswith('http'):
                    # It may be that multiple links point to the same resource.
                    # Normalizing them means they only need to be tested once.
                    # The non-normalized version is stored anyway, because if
                    # the link is broken, that version is used to show the
                    # user the broken links on a specific page.
                    normalized_url = userprovided.url.normalize_url(url)
                    parsed_url = urllib.parse.urlparse(url)
                    links_found.append([str(file_path),
                                        parsed_url.hostname,
                                        url,
                                        normalized_url,
                                        linktext])
                    self.cnt['links_found'] += 1
                elif url.startswith('mailto:'):
                    mail_addresses = self.parser.extract_mails_from_mailto(url)
                    if not mail_addresses:
                        continue
                    for address in mail_addresses:
                        if userprovided.mail.is_email(address):
                            host = address.split('@')[1]
                            # TO DO: ...
                        else:
                            # Invalid email
                            # TO DO: ...
                            pass
                else:
                    # cannot check this kind of link
                    # TO DO: at least count
                    pass

            # Push the found links once for each file instead for all files
            # at once. The latter would kill performance for large document
            # collections.
            if links_found:
                self.db.save_found_links(links_found)
            if mailto_found:
                pass

        return None
