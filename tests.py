#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Automatic Tests for salted

To run these tests:
coverage run --source salted -m pytest tests.py
To generate a report afterwards.
coverage html
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2021: Released under the Apache License 2.0
"""

import pathlib
import re
import tempfile


import pyfakefs
import pytest
import pytest_mock

import salted
from salted import parser

myTest = salted.Salted(cache_file='./salted-test-cache.sqlite3')

my_parser = parser.Parser()

# print(myTest.__dict__.keys())


def test_latex_regex():
    """Test the regular expressions to match a link in LaTeX.
       Tested for itself and not in aggregate within another function to
       get a more precise error in case some test fails."""
    # get the regex patterns used in production
    p_latex_url = my_parser.pattern_latex_url
    p_latex_href = my_parser.pattern_latex_href
    # basic examples to test with the \url command
    latex_url = r"\url{https://www.example.com/index.php?id=foo}"
    # Test if greedy or non-greedy match:
    latex_url_encapsulated = r"\footnote{\url{https://www.example.com}}"
    # test the \url{} command
    matched = re.search(p_latex_url, latex_url)
    assert matched['url'] == 'https://www.example.com/index.php?id=foo'
    # test the \url{} command - encapsulated
    matched = re.search(p_latex_url, latex_url_encapsulated)
    assert matched['url'] == 'https://www.example.com'
    # basic examples to test with the \href command
    latex_href_blank = r"\href{https://www.example.com/index.php?id=foo}{description}"
    latex_href_w_optional = r"\href[dontcare]{https://www.example.com}{description}"
    latex_href_encapsulated = r"\footnote{\href[dontcare]{https://www.example.com}{description}}"
    # test the \href{}{} command - blank
    matched = re.search(p_latex_href, latex_href_blank)
    assert matched['url'] == 'https://www.example.com/index.php?id=foo'
    assert matched['linktext'] == 'description'
    # test the \href{}{} command - with optional param
    matched = re.search(p_latex_href, latex_href_w_optional)
    assert matched['url'] == 'https://www.example.com'
    assert matched['linktext'] == 'description'
    # test the \href{}{} command - encapsulated
    matched = re.search(p_latex_href, latex_href_encapsulated)
    assert matched['url'] == 'https://www.example.com'
    assert matched['linktext'] == 'description'


def test_markdown_regex():
    """Test the regular expressions to match a link in Markdown.
       Tested for itself and not in aggregate within another function to
       get a more precise error in case some test fails."""
    # get the regex pattern used in production
    p_md_link = my_parser.pattern_md_link
    # basic examples standard inline
    md_link_plain = '[visible text](https://www.example.com)'
    md_link_w_title = '[visible text](https://www.example.com/index.html?foo=1 "Title")'
    md_link_w_title_single_quotes = "[visible text](https://www.example.com/ 'Title')"
    # test inline links
    matched = re.search(p_md_link, md_link_plain)
    assert matched['url'] == 'https://www.example.com'
    assert matched['linktext'] == 'visible text'
    matched = re.search(p_md_link, md_link_w_title)
    assert matched['url'] == 'https://www.example.com/index.html?foo=1'
    assert matched['linktext'] == 'visible text'
    matched = re.search(p_md_link, md_link_w_title_single_quotes)
    assert matched['url'] == 'https://www.example.com/'
    assert matched['linktext'] == 'visible text'
    # get the regex pattern used in production
    p_md_link_pointy = my_parser.pattern_md_link_pointy
    # example pointy brackets shorthand
    md_pandoc_pointy_brackets = '<https://www.example.com>'
    # test pointy bracket version
    matched = re.search(p_md_link_pointy, md_pandoc_pointy_brackets)
    assert matched['url'] == 'https://www.example.com'


def test_extract_links_from_html():
    """Test the function that extracts links from HTML."""
    html_example = """
    <html>
    <body>
    <h1>Example</h1>
    <p><a href="https://www.example.com/">some text</a> bla bla
    <a     href="https://2.example.com">another</a>!</p>
    </body>
    </html>"""
    extracted_links = my_parser.extract_links_from_html(
        file_content=html_example)
    assert len(extracted_links) == 2
    # First sub-element should be URL, second the link text.
    assert extracted_links[0][0] == 'https://www.example.com/'
    assert extracted_links[0][1] == 'some text'
    assert extracted_links[1][0] == 'https://2.example.com'
    assert extracted_links[1][1] == 'another'


def test_extract_links_from_markdown():
    """Test the function that extracts links from Markdown."""
    md_example = """
    bla bla <https://www.example.com> bla bla
    [inline-style link](https://www.google.com) bla
    [link with title](http://www.example.com/index.php?id=foo "Title for this link")
    """
    extracted_links = my_parser.extract_links_from_markdown(
        file_content=md_example)
    assert len(extracted_links) == 3
    # ! The function does first extract links in standard format, then the
    #   special case pointy brakets! Order is different than in the text.
    # First sub-element should be URL, second the link text.
    assert extracted_links[0][0] == 'https://www.google.com'
    assert extracted_links[0][1] == 'inline-style link'
    assert extracted_links[1][0] == 'http://www.example.com/index.php?id=foo'
    assert extracted_links[1][1] == 'link with title'
    assert extracted_links[2][0] == 'https://www.example.com'
    assert extracted_links[2][1] == 'https://www.example.com'


def test_extract_links_from_tex():
    """Test the functions that extracts links from LaTeX .tex files."""
    latex_example = r"""
    \section{Example}
    bla bla\footnote{\url{https://www.example.com/1}} bla
    \href{https://latex.example.com/}{linktext} bla
    bla\url{https://www.example.com/2}bla
    bla\href[doesnotmatter]{https://with-optional.example.com}{with optional}bla
    """
    extracted_links = my_parser.extract_links_from_tex(
                        file_content=latex_example)
    assert len(extracted_links) == 4
    # ! The function does first extract \href links, then the \url
    #   format! Order is different than in the text.
    # First sub-element should be URL, second the link text.
    assert extracted_links[0][0] == 'https://latex.example.com/'
    assert extracted_links[0][1] == 'linktext'
    assert extracted_links[1][0] == 'https://with-optional.example.com'
    assert extracted_links[1][1] == 'with optional'
    assert extracted_links[2][0] == 'https://www.example.com/1'
    assert extracted_links[2][1] == 'https://www.example.com/1'
    assert extracted_links[3][0] == 'https://www.example.com/2'
    assert extracted_links[3][1] == 'https://www.example.com/2'


def test_extract_mails_from_mailto():
    # TO DO
    # 'mailto:foo@example.com'
    pass


# fs is a fixture provided by pyfakefs
def test_file_discovery(fs):
    fs.create_file('/fake/latex.tex')
    fs.create_file('/fake/markdown.md')
    fs.create_file('/fake/hypertext.html')
    fs.create_file('/fake/short.html')
    fs.create_file('/fake/unknown.txt')
    fs.create_file('/fake/fake/foo.tex')
    fs.create_file('/fake/fake/foo.md')
    fs.create_file('/fake/fake/noextension')
    fs.create_file('/fake/fake/foo.htmlandmore')
    supported_files = myTest.file_io.find_files_by_extensions('/fake')
    assert len(supported_files) == 6
    html_files = myTest.file_io.find_html_files('/fake')
    assert len(html_files) == 2
    md_files = myTest.file_io.find_markdown_files('/fake')
    assert len(md_files) == 2
    tex_files = myTest.file_io.find_tex_files('/fake')
    assert len(tex_files) == 2
