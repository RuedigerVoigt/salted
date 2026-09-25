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


@patch('salted.url_check.UrlCheck.head_request', new_callable=AsyncMock, return_value=200)
def test_unreadable_file_fails_the_run(mock_head, tmp_path):
    """A file that could not be read fails --raise_for_dead_links.

    Its links were never checked, so passing the run would hide dead
    links in exactly the pipeline meant to catch them. The oversized
    file stands in for every reason a file is skipped.
    """
    d = tmp_path / "unreadable"
    d.mkdir()
    (d / "fine.html").write_text("<a href='https://www.example.com/'>ok</a>")
    (d / "huge.html").write_text("<html>" + "x" * (2 * 1024 * 1024) + "</html>")

    my_check = salted.Salted()
    my_check.raise_for_dead_links = True
    my_check.max_file_size_mb = 1
    with pytest.raises(err.DeadLinksException) as excinfo:
        my_check.check(searchpath=d)

    message = str(excinfo.value)
    assert 'could not be checked' in message
    # Nothing was dead, so the message must not send anyone hunting for
    # a broken link that does not exist.
    assert 'dead link' not in message


@patch('salted.url_check.UrlCheck.head_request', new_callable=AsyncMock, return_value=200)
def test_malformed_links_are_reported_not_fatal(mock_head, tmp_path):
    """Links without a host or with an invalid port must not abort the run.

    userprovided refuses to normalize them. They are listed in the report
    as exceptions, and only the valid link is requested.
    """
    d = tmp_path / "malformed"
    d.mkdir()
    (d / "links.md").write_text(
        "[no host](http://:8080/)\n"
        "[bad port](http://example.com:99999/)\n"
        "[fine](https://www.example.com/)\n")
    report = tmp_path / "report.txt"

    my_check = salted.Salted()
    # A shared cache from other tests would skip the valid link.
    my_check.cache_file = tmp_path / "cache.sqlite3"
    my_check.write_to = report
    my_check.check(searchpath=d)

    assert mock_head.await_count == 1
    assert mock_head.await_args.args[0] == 'https://www.example.com/'
    text = report.read_text(encoding='utf-8')
    assert 'http://:8080/' in text
    assert 'http://example.com:99999/' in text
    assert text.count('Malformed URL - not checked') == 2


@patch('salted.url_check.UrlCheck.head_request', new_callable=AsyncMock, return_value=200)
def test_malformed_link_fails_the_run(mock_head, tmp_path):
    """No client can reach a malformed link, so it fails --raise_for_dead_links."""
    d = tmp_path / "malformed_fail"
    d.mkdir()
    (d / "links.md").write_text(
        "[no host](http://:8080/)\n"
        "[again](http://:8080/)\n"
        "[fine](https://www.example.com/)\n")

    my_check = salted.Salted()
    my_check.cache_file = tmp_path / "cache.sqlite3"
    my_check.raise_for_dead_links = True
    with pytest.raises(err.DeadLinksException) as excinfo:
        my_check.check(searchpath=d)

    message = str(excinfo.value)
    # Counted once per distinct link, like dead links.
    assert 'Found 1 malformed link(s)' in message
    assert 'dead link' not in message


@patch('salted.url_check.UrlCheck.head_request', new_callable=AsyncMock, return_value=200)
def test_unreadable_file_passes_without_the_flag(mock_head, tmp_path):
    """Without --raise_for_dead_links an unreadable file only gets reported."""
    d = tmp_path / "unreadable_no_flag"
    d.mkdir()
    (d / "fine.html").write_text("<a href='https://www.example.com/'>ok</a>")
    (d / "huge.html").write_text("<html>" + "x" * (2 * 1024 * 1024) + "</html>")

    my_check = salted.Salted()
    my_check.max_file_size_mb = 1
    my_check.check(searchpath=d)  # should not raise


def test_failure_message_names_every_reason():
    """The exception is often the only thing read in a CI log."""
    both = salted.Salted._failure_message(2, 1, 0)
    assert 'Found 2 dead link(s)' in both
    assert '1 file(s) could not be checked' in both

    only_dead = salted.Salted._failure_message(3, 0, 0)
    assert 'could not be checked' not in only_dead

    # A .bib skipped for want of pybtex is already part of num_unreadable;
    # it only adds the install hint.
    with_bib = salted.Salted._failure_message(0, 1, 1)
    assert '1 file(s) could not be checked' in with_bib
    assert 'salted[bibtex]' in with_bib

    all_three = salted.Salted._failure_message(2, 1, 0, num_malformed=4)
    assert 'Found 2 dead link(s)' in all_three
    assert 'Found 4 malformed link(s)' in all_three
    assert '1 file(s) could not be checked' in all_three
    assert 'malformed' not in both


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


class TestSettingsFailBeforeChecking:
    """A setting that cannot work stops the run before any link is checked.

    The report is rendered and written last. A mistyped template name or an
    output folder that does not exist used to surface only then, after every
    link had been checked, throwing the results away.
    """

    @staticmethod
    def _site(tmp_path):
        """Create a folder with one HTML file holding an external link."""
        d = tmp_path / "site"
        d.mkdir()
        (d / "index.html").write_text(
            "<a href='https://www.example.com/'>link</a>")
        return d

    @staticmethod
    def _assert_fails_early(checker, searchpath, expected):
        """Run check() and assert it raised before any URL was checked."""
        with patch('salted.url_check.UrlCheck.check_urls') as mock_check_urls:
            with pytest.raises(expected) as excinfo:
                checker.check(searchpath=searchpath)
        mock_check_urls.assert_not_called()
        return excinfo.value

    def test_missing_searchpath(self, tmp_path, caplog):
        """Still a FileNotFoundError, so existing callers keep working."""
        missing = tmp_path / "does-not-exist"
        exc = self._assert_fails_early(
            salted.Salted(), missing, err.SearchpathNotFoundError)
        assert isinstance(exc, FileNotFoundError)
        assert isinstance(exc, err.InvalidSettingError)
        assert str(missing) in str(exc)
        # logging.exception() outside an except block printed a bogus
        # "NoneType: None" traceback; the library no longer logs this.
        assert 'NoneType' not in caplog.text

    def test_unsupported_single_file(self, tmp_path):
        """Still a ValueError; the message names the supported formats."""
        f = tmp_path / "document.xyz"
        f.write_text("hello")
        exc = self._assert_fails_early(
            salted.Salted(), f, err.InvalidSettingError)
        assert isinstance(exc, ValueError)
        assert '.html' in str(exc)

    def test_cache_file_is_a_folder(self, tmp_path):
        """A folder given as cache_file is rejected up front."""
        checker = salted.Salted()
        checker.cache_file = tmp_path
        self._assert_fails_early(
            checker, self._site(tmp_path), err.InvalidSettingError)

    def test_missing_template(self, tmp_path):
        """A template that is not there is found out before checking."""
        templates = tmp_path / "templates"
        templates.mkdir()
        checker = salted.Salted()
        checker.template_searchpath = templates
        checker.template_name = 'nope.jinja'
        exc = self._assert_fails_early(
            checker, self._site(tmp_path), err.InvalidSettingError)
        assert 'nope.jinja' in str(exc)

    def test_template_with_syntax_error(self, tmp_path):
        """A template that does not compile is found out before checking."""
        templates = tmp_path / "templates"
        templates.mkdir()
        (templates / "broken.jinja").write_text("{% for x in %}")
        checker = salted.Salted()
        checker.template_searchpath = templates
        checker.template_name = 'broken.jinja'
        exc = self._assert_fails_early(
            checker, self._site(tmp_path), err.InvalidSettingError)
        assert 'broken.jinja' in str(exc)

    def test_unsafe_template_name(self, tmp_path):
        """The template name check now also runs before checking."""
        templates = tmp_path / "templates"
        templates.mkdir()
        (templates / "secret.txt").write_text("SECRET")
        checker = salted.Salted()
        checker.template_searchpath = templates
        checker.template_name = 'secret.txt'
        self._assert_fails_early(
            checker, self._site(tmp_path), err.UnsafeTemplateError)

    def test_write_to_in_missing_folder(self, tmp_path):
        """The report file's folder must exist before checking starts."""
        checker = salted.Salted()
        checker.write_to = tmp_path / "no-such-folder" / "report.txt"
        exc = self._assert_fails_early(
            checker, self._site(tmp_path), err.InvalidSettingError)
        assert 'no-such-folder' in str(exc)

    def test_write_to_is_a_folder(self, tmp_path):
        """write_to must name a file, not a folder."""
        checker = salted.Salted()
        checker.write_to = tmp_path
        self._assert_fails_early(
            checker, self._site(tmp_path), err.InvalidSettingError)

    @patch('salted.url_check.UrlCheck.head_request', new_callable=AsyncMock,
           return_value=200)
    def test_valid_custom_template_and_file_still_work(self, mock_head, tmp_path):
        """The early checks must not reject a working setup."""
        templates = tmp_path / "templates"
        templates.mkdir()
        (templates / "mine.jinja").write_text(
            "links: {{ statistics.num_links }}")
        report = tmp_path / "report.txt"
        checker = salted.Salted()
        checker.template_searchpath = templates
        checker.template_name = 'mine.jinja'
        checker.write_to = report
        checker.check(searchpath=self._site(tmp_path))
        assert report.read_text(encoding='utf-8') == 'links: 1'
