#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Input Parser for salted
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2021: Released under the Apache License 2.0
"""

import re
from typing import List

from bs4 import BeautifulSoup  # type: ignore


class Parser():
    "Methods to extract hyperlinks and mail addresses from different formats."

    def __init__(self):

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
    def extract_links_from_html(file_content: str) -> List:
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

    @staticmethod
    def extract_mails_from_mailto(mailto_link):
        """A single mailto link can contain *multiple* mail addresses.
           Extract them and return them as a list."""
        mailto_link = mailto_link[7:]  # cut off the mailto: part
        # TO DO
        pass
