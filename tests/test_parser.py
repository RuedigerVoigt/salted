#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Tests for parser module
~~~~~~~~~~~~~~~~~~~~~
Smart, Asynchronous Link Tester with Database backend (SALTED)
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2025: Released under the Apache License 2.0
"""

import pytest
from salted.parser import Parser


class TestHtmlParsing:
    """Test HTML link extraction"""

    def test_extract_links_from_html_with_valid_links(self):
        """Test extracting links from valid HTML"""
        parser = Parser()
        html = '<a href="http://example.com">Example</a><a href="http://test.com">Test</a>'
        links = parser.extract_links_from_html(html)
        assert len(links) == 2
        assert ['http://example.com', 'Example'] in links
        assert ['http://test.com', 'Test'] in links

    def test_extract_links_from_html_without_href(self):
        """Test HTML with anchor tags but no href attribute"""
        parser = Parser()
        html = '<a>No href here</a><a name="anchor">Named anchor</a>'
        links = parser.extract_links_from_html(html)
        # Should skip anchors without href and return empty list
        assert links == []

    def test_extract_links_from_html_empty(self):
        """Test empty HTML"""
        parser = Parser()
        html = '<html><body></body></html>'
        links = parser.extract_links_from_html(html)
        assert links == []

    def test_extract_links_from_html_uppercase_tags(self):
        """Uppercase <A HREF=...> tags (e.g. Chrome bookmark exports) are matched."""
        parser = Parser()
        html = '<A HREF="https://example.com/">link</A>'
        links = parser.extract_links_from_html(html)
        assert links == [['https://example.com/', 'link']]


class TestBibtexParsing:
    """Test BibTeX parsing with missing fields"""

    def test_extract_links_from_bib_with_url_only(self):
        """Test BibTeX entry with URL but no DOI"""
        parser = Parser()
        bib = """
        @article{test2024,
            title = {Test Article},
            author = {Test Author},
            Url = {http://example.com}
        }
        """
        result = parser.extract_links_from_bib(bib)
        url_list, doi_list = result

        assert len(url_list) == 1
        assert url_list[0][0] == 'http://example.com'
        assert 'test2024' in url_list[0][1]
        assert len(doi_list) == 0

    def test_extract_links_from_bib_with_doi_only(self):
        """Test BibTeX entry with DOI but no URL"""
        parser = Parser()
        bib = """
        @article{test2024,
            title = {Test Article},
            author = {Test Author},
            Doi = {10.1234/test}
        }
        """
        result = parser.extract_links_from_bib(bib)
        url_list, doi_list = result

        assert len(url_list) == 0
        assert len(doi_list) == 1
        assert doi_list[0][0] == '10.1234/test'
        assert 'test2024' in doi_list[0][1]

    def test_extract_links_from_bib_without_url_or_doi(self):
        """Test BibTeX entry with neither URL nor DOI (KeyError handling)"""
        parser = Parser()
        bib = """
        @article{test2024,
            title = {Test Article},
            author = {Test Author},
            year = {2024}
        }
        """
        result = parser.extract_links_from_bib(bib)
        url_list, doi_list = result

        # Should handle missing fields gracefully
        assert len(url_list) == 0
        assert len(doi_list) == 0

    def test_extract_links_from_bib_with_both_url_and_doi(self):
        """Test BibTeX entry with both URL and DOI"""
        parser = Parser()
        bib = """
        @article{test2024,
            title = {Test Article},
            Url = {http://example.com},
            Doi = {10.1234/test}
        }
        """
        result = parser.extract_links_from_bib(bib)
        url_list, doi_list = result

        assert len(url_list) == 1
        assert len(doi_list) == 1

    def test_extract_links_from_bib_doi_with_whitespace(self):
        """Test that DOIs are stripped of whitespace"""
        parser = Parser()
        bib = """
        @article{test2024,
            Doi = {  10.1234/test  }
        }
        """
        result = parser.extract_links_from_bib(bib)
        url_list, doi_list = result

        # DOI should be stripped of whitespace
        assert doi_list[0][0] == '10.1234/test'


class TestMailtoParsing:
    """Test mailto link extraction"""

    def test_extract_mails_from_mailto(self):
        """Test mailto extraction returns the address."""
        parser = Parser()
        result = parser.extract_mails_from_mailto('mailto:test@example.com')
        assert result == ['test@example.com']

    def test_extract_mails_from_mailto_multiple(self):
        """Test mailto with multiple addresses returns all of them."""
        parser = Parser()
        result = parser.extract_mails_from_mailto('mailto:test1@example.com,test2@example.com')
        assert result == ['test1@example.com', 'test2@example.com']


class TestMarkdownParsing:
    """Test Markdown link extraction edge cases"""

    def test_extract_links_from_markdown_mixed_formats(self):
        """Test Markdown with both standard and pointy bracket links"""
        parser = Parser()
        markdown = """
        [Link 1](http://example.com)
        <http://pointy.com>
        [Link 2](http://test.com)
        """
        links = parser.extract_links_from_markdown(markdown)

        assert len(links) == 3
        # Check that both formats are captured
        urls = [link[0] for link in links]
        assert 'http://example.com' in urls
        assert 'http://pointy.com' in urls
        assert 'http://test.com' in urls


class TestTexParsing:
    """Test TeX link extraction edge cases"""

    def test_extract_links_from_tex_with_optional_href_params(self):
        """Test TeX with optional parameters in href"""
        parser = Parser()
        tex = r"""
        \href[optional]{http://example.com}{Link Text}
        \href{http://test.com}{Another Link}
        """
        links = parser.extract_links_from_tex(tex)

        assert len(links) == 2
        urls = [link[0] for link in links]
        assert 'http://example.com' in urls
        assert 'http://test.com' in urls

    def test_extract_links_from_tex_mixed_commands(self):
        """Test TeX with both url and href commands"""
        parser = Parser()
        tex = r"""
        \url{http://url-example.com}
        \href{http://href-example.com}{Link}
        """
        links = parser.extract_links_from_tex(tex)

        assert len(links) == 2
        urls = [link[0] for link in links]
        assert 'http://url-example.com' in urls
        assert 'http://href-example.com' in urls
