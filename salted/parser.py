#!/usr/bin/python3

"""
Input Parser for salted
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026 Rüdiger Voigt and contributors
Released under the Apache License 2.0
"""

import logging
import re
import urllib.parse
from typing import Final

from bs4 import BeautifulSoup  # type: ignore

from salted import err

try:
    import lxml  # type: ignore[import-untyped]
    _BS_PARSER = 'lxml'
    logging.info("lxml %s available — using it as HTML parser backend.", lxml.__version__)
except ImportError:
    _BS_PARSER = 'html.parser'
    logging.warning("lxml not installed — falling back to html.parser. "
                    "Install salted[lxml] for faster HTML parsing.")

# BibTeX support is optional. Unlike lxml - which only swaps the HTML
# backend for a faster one - pybtex has no fallback: without it a .bib
# file cannot be read at all. So this import stays silent. Warning here
# would nag the majority who never check a .bib file, while the ones who
# do are told at the point where such a file is actually encountered.
try:
    from pybtex.database import parse_string  # type: ignore
    PYBTEX_AVAILABLE = True
except ImportError:
    PYBTEX_AVAILABLE = False

# The message is defined once: the run aborts with it when a .bib file
# was named explicitly, and it is written into the report when one was
# merely found while scanning a folder.
MISSING_PYBTEX_MSG: Final[str] = (
    'BibTeX support requires the optional dependency pybtex, which is not '
    'installed. Install it with: pip install salted[bibtex]')
# a future version of pybtex might get type hints, see:
# https://bitbucket.org/pybtex-devs/pybtex/issues/141/type-annotations


class Parser:
    """Methods to extract hyperlinks and mail addresses from different formats."""

    def __init__(self) -> None:
        """Compile regex patterns for URL extraction from all supported formats."""
        # Specification: https://www.ctan.org/pkg/hyperref
        self.pattern_latex_url = re.compile(
            r"\\url\{(?P<url>[^{]*?)\}",
            flags=re.MULTILINE | re.IGNORECASE)
        # The optional argument is deliberately matched by a *bounded*
        # character class rather than '.*'. Two reasons:
        #   Performance: with '.*' every '\href[' that has no closing
        #   bracket makes the engine scan ahead and backtrack, which is
        #   quadratic in the line length — a crafted .tex file well within
        #   max_file_size_mb could stall a run for hours. An unbounded
        #   class such as '[^]]*' does not help here; only the length
        #   bound makes each attempt constant work and the scan linear.
        #   Correctness: '.*' is greedy, so a line holding an href plus a
        #   later '[...]' swallowed everything up to the last bracket and
        #   the first link was lost.
        # Excluding newlines keeps the argument on one line, as '.' did.
        # The limit applies to the *optional argument only* — the URL and
        # the link text are matched by unbounded groups, so URLs of any
        # length are still extracted in full. Even a stacked option list
        # ("page=42,pdfremotestartview=FitBH,pdfnewwindow=true,...") stays
        # under 150 characters, so 500 is ample headroom; an \href whose
        # optional argument exceeded it would be skipped, and a skipped
        # link is an unchecked link. The headroom is free: on documents
        # that are not the pathological unclosed-bracket case the bound
        # never comes into play (measured: no difference at 20 MB).
        # The group stays capturing — extract_links_from_tex() reads the
        # url and linktext as match[1] and match[2].
        self.pattern_latex_href = re.compile(
            r"\\href(\[[^]\r\n]{0,500}\]){0,1}\{(?P<url>[^}]*)\}\{(?P<linktext>[^}]*?)\}",
            flags=re.MULTILINE | re.IGNORECASE)

        # Specs:
        # https://pandoc.org/MANUAL.html
        # https://daringfireball.net/projects/markdown/syntax
        # https://github.github.com/gfm/
        # The url group allows balanced parentheses so links such as
        # Wikipedia's `..._(programming_language)` are not truncated at the
        # first ')'. It still stops at whitespace (a following "title") or
        # the link's closing ')'.
        self.pattern_md_link = re.compile(
            r"\[(?P<linktext>[^\[]*)\]\((?P<url>(?:[^\s()]|\([^\s()]*\))*)[\s\)]+",
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
        soup = BeautifulSoup(file_content, _BS_PARSER)
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

        Raises:
            err.MissingOptionalDependencyError: If pybtex is not installed.
        """
        if not PYBTEX_AVAILABLE:
            raise err.MissingOptionalDependencyError(MISSING_PYBTEX_MSG)
        url_list = []
        doi_list = []
        bib_data = parse_string(file_content, bib_format='bibtex')
        for entry in bib_data.entries:
            # Neither the URL, nor the DOI field is required by BiBTeX.
            # pybtex throws a KeyError if the field does not exist.
            try:
                url = bib_data.entries[entry].fields['url']
                url_list.append([url, f"Key: {entry}, Field: url"])
            except KeyError:
                pass

            try:
                doi = bib_data.entries[entry].fields['doi']
                doi_list.append([doi.strip(), f"Key: {entry}, Field: doi"])
            except KeyError:
                pass

        return [url_list, doi_list]

    @staticmethod
    def extract_mails_from_mailto(mailto_link: str) -> list:
        """Extract mail addresses from a mailto link.

        A single mailto link can contain multiple mail addresses in the
        path component (the ``to`` field), separated by commas.
        Query parameters (subject, cc, bcc, …) are intentionally ignored.

        Args:
            mailto_link: The mailto URL string to parse.

        Returns:
            List of raw address strings found in the ``to`` field.
            Empty list if the link is empty or cannot be parsed.
        """
        try:
            parsed = urllib.parse.urlparse(mailto_link)
            to_part = urllib.parse.unquote(parsed.path)
            if not to_part:
                return []
            return [addr.strip() for addr in to_part.split(',') if addr.strip()]
        except Exception:
            return []
