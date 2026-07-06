#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Automatic Tests for salted - Integration Tests

Integration tests for end-to-end workflows.
Unit tests for individual components are in their respective test files:
- test_parser.py - Parsing logic (regex, extraction)
- test_url_check.py - URL checking logic
- test_cache_reader.py - Cache operations
- test_config_file.py - Configuration handling
- test_database_io.py - Database operations
- etc.

~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026: Released under the Apache License 2.0
"""

import sqlite3

import pytest
from unittest.mock import AsyncMock, patch

import salted
from salted import err, file_finder, memory_instance


html_example = r"""
<html>
<body>
<h1>Example</h1>
<p><a href="https://www.example.com/">some text</a> bla bla
<a     href="https://2.example.com">another</a>!</p>
</body>
</html>"""

md_example = r"""
bla bla <https://www.example.com> bla bla
[inline-style link](https://www.google.com) bla
[link with title](http://www.example.com/index.php?id=foo "Title for this link")
"""

bibtex_example = r"""
% Encoding: UTF-8

@Article{Doe2021,
author  = {Jon Doe},
journal = {Journal of valid references},
title   = {Some Title},
year    = {2021},
doi     = {invalidDOI},
url     = {https://www.example.com/},
}
"""


# Integration tests focus on end-to-end workflows

# fs is a fixture provided by pyfakefs
def test_file_discovery(fs):
    """Test file discovery with fake filesystem"""
    fs.create_file('/fake/latex.tex')
    fs.create_file('/fake/markdown.md')
    fs.create_file('/fake/hypertext.html')
    fs.create_file('/fake/short.html')
    fs.create_file('/fake/unknown.txt')
    fs.create_file('/fake/fake/foo.tex')
    fs.create_file('/fake/fake/foo.md')
    fs.create_file('/fake/fake/noextension')
    fs.create_file('/fake/fake/foo.htmlandmore')
    fs.create_file('/fake/fake/fake/foo.bib')
    filesearch = file_finder.FileFinder()
    supported_files = filesearch.find_files_by_extensions('/fake')
    assert len(supported_files) == 7
    html_files = filesearch.find_files_by_extensions('/fake', {'.htm', '.html'})
    assert len(html_files) == 2
    md_files = filesearch.find_files_by_extensions('/fake', {'.md'})
    assert len(md_files) == 2
    tex_files = filesearch.find_files_by_extensions('/fake', {'.tex'})
    assert len(tex_files) == 2


def test_create_object():
    """Test basic object creation and error handling"""
    my_check = salted.Salted()
    with pytest.raises(FileNotFoundError):
        my_check.check(searchpath='non_existent.tex')


@patch('salted.url_check.UrlCheck.head_request', new_callable=AsyncMock, return_value=200)
def test_actual_run_html(mock_head, tmp_path):
    """End-to-end test with HTML file"""
    d = tmp_path / "htmltest"
    d.mkdir()
    p = d / "test.html"
    p.write_text(html_example)
    my_check = salted.Salted()
    my_check.check(searchpath=(d / "test.html"))


@patch('salted.url_check.UrlCheck.head_request', new_callable=AsyncMock, return_value=200)
def test_actual_run_markdown(mock_head, tmp_path):
    """End-to-end test with Markdown file"""
    d = tmp_path / "markdowntest"
    d.mkdir()
    p = d / "test.md"
    p.write_text(md_example)
    my_check = salted.Salted()
    my_check.check(searchpath=(d / "test.md"))


@patch('salted.url_check.UrlCheck.head_request', new_callable=AsyncMock, return_value=200)
def test_actual_run_bibtex(mock_head, tmp_path):
    """End-to-end test with BibTeX file.

    'invalidDOI' fails the basic DOI format check (10.NNNN/suffix) so no
    CrossRef API call is made — the test runs entirely offline.
    """
    d = tmp_path / "bibtextest"
    d.mkdir()
    p = d / "test.bib"
    p.write_text(bibtex_example)
    my_check = salted.Salted()
    my_check.check(searchpath=(d / "test.bib"))


@patch('salted.url_check.UrlCheck.head_request', new_callable=AsyncMock, return_value=200)
def test_actual_run_multiple_files(mock_head, tmp_path):
    """End-to-end test with multiple files"""
    d = tmp_path / "multifiletest"
    d.mkdir()
    p = d / "test.html"
    p.write_text(html_example)
    p = d / "test.md"
    p.write_text(md_example)
    my_check = salted.Salted()
    my_check.check(searchpath=(d))


def test_check_unsupported_file_raises(tmp_path):
    """Passing a single unsupported file type raises ValueError."""
    f = tmp_path / "document.xyz"
    f.write_text("hello")
    my_check = salted.Salted()
    with pytest.raises(ValueError):
        my_check.check(searchpath=f)


def test_check_empty_folder_returns_early(tmp_path):
    """An empty folder (no supported files) returns without error."""
    d = tmp_path / "empty"
    d.mkdir()
    my_check = salted.Salted()
    my_check.check(searchpath=d)  # should not raise


@patch('salted.url_check.UrlCheck.head_request', new_callable=AsyncMock, return_value=404)
def test_throw_for_dead_link(mock_head, tmp_path):
    """DeadLinksException is raised when raise_for_dead_links is True and a 404 is returned."""
    d = tmp_path / "deadlink"
    d.mkdir()
    p = d / "deadlink.html"
    p.write_text("<a href='https://www.example.com/broken'>Dead Link</a>")
    my_check = salted.Salted()
    my_check.raise_for_dead_links = True
    with pytest.raises(err.DeadLinksException):
        my_check.check(searchpath=(d))


@patch('salted.url_check.UrlCheck.head_request', new_callable=AsyncMock, return_value=404)
def test_teardown_runs_when_dead_links_raise(mock_head, tmp_path):
    """The in-memory DB is torn down even when check() raises DeadLinksException.

    Regression test for the leaked sqlite connection (ResourceWarning) on the
    raise path: check() must close the connection via try/finally.
    """
    d = tmp_path / "deadlink_teardown"
    d.mkdir()
    (d / "deadlink.html").write_text(
        "<a href='https://www.example.com/broken'>Dead Link</a>")

    original = memory_instance.MemoryInstance.tear_down_in_memory_db
    calls = []

    def spy(self):
        calls.append(True)
        return original(self)

    my_check = salted.Salted()
    my_check.raise_for_dead_links = True
    with patch.object(memory_instance.MemoryInstance,
                      'tear_down_in_memory_db', spy):
        with pytest.raises(err.DeadLinksException):
            my_check.check(searchpath=d)

    assert calls, "tear_down_in_memory_db was not called on the raise path"


@patch('salted.url_check.UrlCheck.head_request', new_callable=AsyncMock)
def test_cache_is_written_when_dead_links_raise(mock_head, tmp_path):
    """Valid URLs are cached even when check() raises DeadLinksException.

    Regression test: the cache used to be written only after the
    raise_for_dead_links check, so a failing CI run lost all freshly
    validated URLs and the next run rechecked everything.
    """
    mock_head.side_effect = lambda url: 200 if 'good' in url else 404

    d = tmp_path / "deadlink_cache"
    d.mkdir()
    (d / "links.html").write_text(
        "<a href='https://www.example.com/good'>Fine Link</a>"
        "<a href='https://www.example.com/broken'>Dead Link</a>")
    cache_file = tmp_path / "test-cache.sqlite3"

    my_check = salted.Salted()
    my_check.raise_for_dead_links = True
    my_check.cache_file = cache_file
    with pytest.raises(err.DeadLinksException):
        my_check.check(searchpath=d)

    assert cache_file.exists(), "cache file was not written on the raise path"
    cache = sqlite3.connect(cache_file)
    try:
        rows = cache.execute('SELECT normalizedUrl FROM validUrls;').fetchall()
    finally:
        cache.close()
    cached_urls = {row[0] for row in rows}
    assert 'https://www.example.com/good' in cached_urls
    assert 'https://www.example.com/broken' not in cached_urls
