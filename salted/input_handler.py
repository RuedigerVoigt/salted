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
from typing import List
import re
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

        self.pattern_latex_url = re.compile(
            r"\\url\{(?P<url>[^{]*?)\}",
            flags=re.MULTILINE | re.IGNORECASE)

        self.pattern_latex_href = re.compile(
            r"\\href(\[.*\]){0,1}\{(?P<url>[^}]*)\}\{(?P<linktext>[^}]*?)\}",
            flags=re.MULTILINE | re.IGNORECASE)

        self.pattern_md_link = re.compile(
            r"\[(?P<linktext>[^\[]*)\]\((?P<url>[^\)]*?)[\s\)]+",
            flags=re.MULTILINE | re.IGNORECASE)

        self.pattern_md_link_pointy = re.compile(
            r"<(?P<url>[^>]*?)>",
            flags=re.MULTILINE | re.IGNORECASE)

    @staticmethod
    def find_files_by_extensions(
            path_to_base_folder: pathlib.Path,
            suffixes: set = {".htm", ".html", '.md', '.tex'}
                                 ) -> List[pathlib.Path]:
        """Find all files with specific file type suffixes in the base folder
           and its subfolders. If no file suffix is specified, this will look
           for all file formats supported by salted."""
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
        """Find all markdown files in the base folder and its subfolders."""
        logging.info("Looking for Markdown files...")
        suffixes = {".md"}
        return self.find_files_by_extensions(path_to_base_folder, suffixes)

    def find_tex_files(self,
                       path_to_base_folder: pathlib.Path
                       ) -> List[pathlib.Path]:
        """Find all .tex files in the base folder and its subfolders."""
        logging.info("Looking for TeX files...")
        suffixes = {".tex"}
        return self.find_files_by_extensions(path_to_base_folder, suffixes)

    def extract_links_from_html(self,
                                file_content: str) -> List:
        """Extract all links from a HTML file."""
        matches = []
        soup = BeautifulSoup(file_content, 'html.parser')
        for link in soup.find_all('a'):
            matches.append([link.get('href'), link.text])
        return matches

    def extract_links_from_markdown(self,
                                    file_content: str) -> List:
        """Extract all links from a Markdown file.
        Returns a list of lists: [[url, linktext], [url, linktext]]"""
        matches = []
        md_links_in_file = re.findall(self.pattern_md_link, file_content)
        for match in md_links_in_file:
            matches.append([match[1], match[0]])
        pointy_links_in_file = re.findall(self.pattern_md_link_pointy,
                                          file_content)
        for url in pointy_links_in_file:
            matches.append([url, url])
        return matches

    def extract_links_from_tex(self,
                               file_content: str) -> List:
        """Extract all links from a .tex file.
        Returns a list of lists: [[url, linktext], [url, linktext]]"""
        matches = []
        # extract class \href{url}{text} links
        href_in_file = re.findall(self.pattern_latex_href, file_content)
        for match in href_in_file:
            # The RegEx returns the optinal Element as first element.
            # (Empty, but still in the return if it is not in the string.)
            matches.append([match[1], match[2]])
        # extract \url{url} links
        url_in_file = re.findall(self.pattern_latex_url, file_content)
        for url in url_in_file:
            matches.append([url, url])
        return matches

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
            content = ''
            with open(file_path, 'r') as code:
                content = code.read()
            if file_path.suffix in {".htm", ".html"}:
                extracted = self.extract_links_from_html(content)
            elif file_path.suffix in {".md"}:
                extracted = self.extract_links_from_markdown(content)
            elif file_path.suffix in {".tex"}:
                extracted = self.extract_links_from_tex(content)
            else:
                raise RuntimeError('Invalid extension. Should never happen.')

            links_found = []
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

            # Push the found links once for each file instead for all files
            # at once. The latter would kill performance for large document
            # collections.
            if links_found:
                self.db.save_found_links(links_found)

        return None
