#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Input Parser for salted
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2021 Rüdiger Voigt
Released under the Apache License 2.0
"""

import re

from bs4 import BeautifulSoup  # type: ignore
from pybtex.database import parse_string # type: ignore
# a future version of pybtex might get type hints, see:
# https://bitbucket.org/pybtex-devs/pybtex/issues/141/type-annotations


class Parser():
    """Methods to extract hyperlinks and mail addresses from different formats."""

    def __init__(self) -> None:

        # Specification: https://www.ctan.org/pkg/hyperref
        self.pattern_latex_url = re.compile(
            r"\\url\{(?P<url>[^{]*?)\}",
            flags=re.MULTILINE | re.IGNORECASE)
        self.pattern_latex_href = re.compile(
            r"\\href(\[.*\]){0,1}\{(?P<url>[^}]*)\}\{(?P<linktext>[^}]*?)\}",
            flags=re.MULTILINE | re.IGNORECASE)

        # Specs:
        # https://pandoc.org/MANUAL.html
        # https://daringfireball.net/projects/markdown/syntax
        # https://github.github.com/gfm/
        self.pattern_md_link = re.compile(
            r"\[(?P<linktext>[^\[]*)\]\((?P<url>[^\)]*?)[\s\)]+",
            flags=re.MULTILINE | re.IGNORECASE)
        self.pattern_md_link_pointy = re.compile(
            r"<(?P<url>[^>]*?)>",
            flags=re.MULTILINE | re.IGNORECASE)

    @staticmethod
    def extract_links_from_html(file_content: str) -> list:
        """Extract all links from a HTML file.

        Args:
            file_content: HTML file content as a string.

        Returns:
            List of [url, linktext] pairs extracted from anchor tags.
        """
        matches = []
        soup = BeautifulSoup(file_content, 'html.parser')
        for link in soup.find_all('a'):
            if hasattr(link, 'get'):
                href = link.get('href')
                if href:
                    matches.append([href, link.text])
        return matches

    def extract_links_from_markdown(self,
                                    file_content: str) -> list:
        """Extract all links from a Markdown file.

        Supports both [text](url) and <url> syntax.

        Args:
            file_content: Markdown file content as a string.

        Returns:
            List of [url, linktext] pairs extracted from the markdown.
        """
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
                               file_content: str) -> list:
        """Extract all links from a TeX file.

        Supports \\url{url} and \\href{url}{text} commands.

        Args:
            file_content: TeX file content as a string.

        Returns:
            List of [url, linktext] pairs extracted from hyperref commands.
        """
        matches = []
        # extract class \href{url}{text} links
        href_in_file = re.findall(self.pattern_latex_href, file_content)
        for match in href_in_file:
            # The RegEx returns the optional element as first element.
            # (Empty, but still in the return if it is not in the string.)
            matches.append([match[1], match[2]])
        # extract \url{url} links
        url_in_file = re.findall(self.pattern_latex_url, file_content)
        for url in url_in_file:
            matches.append([url, url])
        return matches

    @staticmethod
    def extract_links_from_bib(file_content: str) -> list:
        """Extract all URLs and DOIs from a BibTeX file.

        Args:
            file_content: BibTeX file content as a string.

        Returns:
            List containing two lists:
                - First list: [[url, text], [url, text]] where text is the
                  bibtex entry key and field name.
                - Second list: [[doi, text], [doi, text]] where text is the
                  bibtex entry key and field name.
        """
        url_list = []
        doi_list = []
        bib_data = parse_string(file_content, bib_format='bibtex')
        for entry in bib_data.entries:
            # Neither the URL, nor the DOI field is required by BiBTeX.
            # pybtex throws a KeyError if the field does not exist.
            try:
                url = bib_data.entries[entry].fields['Url']
                url_list.append([url, f"Key: {entry}, Field: Url"])
            except KeyError:
                pass

            try:
                doi = bib_data.entries[entry].fields['Doi']
                doi_list.append([doi.strip(), f"Key: {entry}, Field: DOI"])
            except KeyError:
                pass

        return [url_list, doi_list]

    @staticmethod
    def extract_mails_from_mailto(mailto_link: str) -> None:
        """Extract mail addresses from a mailto link.

        A single mailto link can contain multiple mail addresses.

        Args:
            mailto_link: The mailto URL string to parse.

        Returns:
            List of email addresses extracted from the mailto link.
        """
        mailto_link = mailto_link[7:]  # cut off the mailto: part
        # TO DO
        pass
