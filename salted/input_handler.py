#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Input Handler for salted
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020: Released under the Apache License 2.0
"""

from collections import Counter
import logging
import pathlib
from typing import List
import urllib.parse


from bs4 import BeautifulSoup  # type: ignore
import userprovided
from tqdm.asyncio import tqdm  # type: ignore

from salted import database_io


class InputHandler:
    """Methods to find files and the hyperlinks inside them."""

    def __init__(self,
                 db: database_io.DatabaseIO):
        self.db = db
        self.cnt: Counter = Counter()

    @staticmethod
    def find_files_by_extensions(path_to_base_folder: pathlib.Path,
                                 suffixes: set
                                 ) -> List[pathlib.Path]:
        """Find all with a specific file type suffix in the
           base folder and its subfolders."""
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
        """Find all HTML files in the base folder and its subfolders."""
        logging.info("Looking for HTML files...")
        suffixes = {".htm", ".html"}
        return self.find_files_by_extensions(path_to_base_folder, suffixes)

    def find_markdown_files(self,
                            path_to_base_folder: pathlib.Path
                            ) -> List[pathlib.Path]:
        """NOT YET USED BY THIS APPLICATION
           Find all markdown files in the base folder and its subfolders."""
        logging.info("Looking for Markdown files...")
        suffixes = {".md"}
        return self.find_files_by_extensions(path_to_base_folder, suffixes)

    def scan_html_files_for_links(self,
                                  files_to_check: List[pathlib.Path]) -> None:
        """Scan each file within a list of paths for hyperlinks and write
           those to the SQLite database. """
        if not files_to_check:
            logging.warning('No files to check')
            return None

        print("Scanning files for links:")
        for file_path in tqdm(files_to_check):
            content = ''
            links_found = []
            with open(file_path, 'r') as code:
                content = code.read()
            soup = BeautifulSoup(content, 'html.parser')
            for link in soup.find_all('a'):
                href = link.get('href')
                linktext = link.text
                if href.startswith('http'):
                    # It may be that multiple links point to the same resource.
                    # Normalizing them means they only need to be tested once.
                    # The non-normalized version is stored anyway, because if
                    # the link is broken, that version is used to show the
                    # user the broken link on a specific page.
                    normalized_url = userprovided.url.normalize_url(href)
                    parsed_url = urllib.parse.urlparse(href)
                    links_found.append([str(file_path),
                                        parsed_url.hostname,
                                        href,
                                        normalized_url,
                                        linktext])
                    self.cnt['links_found'] += 1
            self.db.save_found_links(links_found)

        return None
