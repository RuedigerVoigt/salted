#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests to ensure single-file scanning enqueues URLs (regression guard).
"""

from pathlib import Path
from unittest.mock import patch

import salted


class FakeUrlCheck:
    """Capture queued URLs without performing network calls."""

    last_urls = None

    def __init__(self, user_agent, db, workers, timeout_sec, ignore_urls, domain_delay, ignore_domains=None, quiet=False):
        # Store db handle so check_urls can inspect queued URLs
        self.db = db
        self.cnt = {
            'checked_urls': 0,
            'fine': 0,
            'neededFullRequest': 0,
        }

    def check_urls(self):
        # Read what Salted enqueued before network checks would run
        urls = self.db.urls_to_check()
        FakeUrlCheck.last_urls = urls
        self.cnt['checked_urls'] = len(urls) if urls else 0


class NoopDoiCheck:
    """Skip DOI checks to avoid network and progress bars in tests."""

    def __init__(self, db, quiet=False, mailto=None):
        self.valid_doi_list = []
        self.invalid_doi_list = []

    def check_dois(self):
        return None


def write_html(tmp_dir: Path, name: str, html_body: str) -> Path:
    tmp_dir.mkdir(parents=True, exist_ok=True)
    p = tmp_dir / name
    p.write_text(html_body)
    return p


def test_single_file_scanning_enqueues_urls(tmp_path):
    html = (
        "<html><body>"
        "<a href='https://example.com/page1'>One</a>"
        "<a href=\"https://example.com/page2\">Two</a>"
        "</body></html>"
    )
    file_path = write_html(tmp_path / 'one', 'test.html', html)

    with patch('salted.__main__.url_check.UrlCheck', FakeUrlCheck), \
         patch('salted.__main__.doi_check.DoiCheck', NoopDoiCheck):
        checker = salted.Salted()
        checker.check(file_path)

    assert FakeUrlCheck.last_urls is not None
    # Expect two distinct normalized URLs queued for checking
    assert len(FakeUrlCheck.last_urls) == 2


def test_directory_mode_still_enqueues_urls(tmp_path):
    html = (
        "<html><body>"
        "<a href='https://example.org/a'>A</a>"
        "<a href='https://example.org/b'>B</a>"
        "</body></html>"
    )
    # Place file inside directory
    dir_path = tmp_path / 'dir'
    write_html(dir_path, 'index.html', html)

    with patch('salted.__main__.url_check.UrlCheck', FakeUrlCheck), \
         patch('salted.__main__.doi_check.DoiCheck', NoopDoiCheck):
        checker = salted.Salted()
        checker.check(dir_path)

    assert FakeUrlCheck.last_urls is not None
    assert len(FakeUrlCheck.last_urls) == 2


def test_file_types_html_excludes_markdown(tmp_path):
    """--file_types html should only scan HTML files, not Markdown."""
    dir_path = tmp_path / 'mixed'
    dir_path.mkdir(parents=True, exist_ok=True)

    (dir_path / 'page.html').write_text(
        "<html><body><a href='https://html-link.example.com/'>x</a></body></html>")
    (dir_path / 'notes.md').write_text(
        "[link](https://markdown-link.example.com/)")

    with patch('salted.__main__.url_check.UrlCheck', FakeUrlCheck), \
         patch('salted.__main__.doi_check.DoiCheck', NoopDoiCheck):
        checker = salted.Salted()
        checker.file_types = 'html'
        checker.check(dir_path)

    urls = [u[0] for u in FakeUrlCheck.last_urls] if FakeUrlCheck.last_urls else []
    assert any('html-link' in u for u in urls)
    assert not any('markdown-link' in u for u in urls)


def test_file_types_markdown_excludes_html(tmp_path):
    """--file_types markdown should only scan Markdown files, not HTML."""
    dir_path = tmp_path / 'mixed'
    dir_path.mkdir(parents=True, exist_ok=True)

    (dir_path / 'page.html').write_text(
        "<html><body><a href='https://html-link.example.com/'>x</a></body></html>")
    (dir_path / 'notes.md').write_text(
        "[link](https://markdown-link.example.com/)")

    with patch('salted.__main__.url_check.UrlCheck', FakeUrlCheck), \
         patch('salted.__main__.doi_check.DoiCheck', NoopDoiCheck):
        checker = salted.Salted()
        checker.file_types = 'markdown'
        checker.check(dir_path)

    urls = [u[0] for u in FakeUrlCheck.last_urls] if FakeUrlCheck.last_urls else []
    assert any('markdown-link' in u for u in urls)
    assert not any('html-link' in u for u in urls)


def test_excluded_folder_is_not_scanned(tmp_path):
    """exclude_paths keeps a whole subtree out of the scan."""
    dir_path = tmp_path / 'site'
    write_html(dir_path, 'index.html',
               "<html><body><a href='https://kept.example.com/'>x</a></body></html>")
    write_html(dir_path / 'vendor', 'bundled.html',
               "<html><body><a href='https://vendored.example.com/'>x</a></body></html>")

    with patch('salted.__main__.url_check.UrlCheck', FakeUrlCheck), \
         patch('salted.__main__.doi_check.DoiCheck', NoopDoiCheck):
        checker = salted.Salted()
        checker.exclude_paths = {str(dir_path / 'vendor')}
        checker.check(dir_path)

    urls = [u[0] for u in FakeUrlCheck.last_urls] if FakeUrlCheck.last_urls else []
    assert any('kept' in u for u in urls)
    assert not any('vendored' in u for u in urls)


def test_excluded_single_file_is_not_scanned(tmp_path):
    """A single excluded file is skipped while its siblings are checked."""
    dir_path = tmp_path / 'site'
    write_html(dir_path, 'index.html',
               "<html><body><a href='https://kept.example.com/'>x</a></body></html>")
    write_html(dir_path, 'draft.html',
               "<html><body><a href='https://drafted.example.com/'>x</a></body></html>")

    with patch('salted.__main__.url_check.UrlCheck', FakeUrlCheck), \
         patch('salted.__main__.doi_check.DoiCheck', NoopDoiCheck):
        checker = salted.Salted()
        checker.exclude_paths = {str(dir_path / 'draft.html')}
        checker.check(dir_path)

    urls = [u[0] for u in FakeUrlCheck.last_urls] if FakeUrlCheck.last_urls else []
    assert any('kept' in u for u in urls)
    assert not any('drafted' in u for u in urls)


def test_excluded_file_named_as_searchpath_is_honored(tmp_path):
    """A file handed to -i directly must still obey the exclusion list.

    It ends in the same 'nothing to check' path as an empty folder rather
    than being checked anyway.
    """
    file_path = write_html(
        tmp_path / 'site', 'draft.html',
        "<html><body><a href='https://drafted.example.com/'>x</a></body></html>")

    FakeUrlCheck.last_urls = None
    with patch('salted.__main__.url_check.UrlCheck', FakeUrlCheck), \
         patch('salted.__main__.doi_check.DoiCheck', NoopDoiCheck):
        checker = salted.Salted()
        checker.exclude_paths = {str(file_path)}
        checker.check(file_path)  # returns early, does not raise

    assert FakeUrlCheck.last_urls is None


def test_exclusion_of_an_unrelated_path_changes_nothing(tmp_path):
    """An exclusion that matches nothing leaves the scan untouched."""
    dir_path = tmp_path / 'site'
    write_html(dir_path, 'index.html',
               "<html><body><a href='https://kept.example.com/'>x</a></body></html>")

    with patch('salted.__main__.url_check.UrlCheck', FakeUrlCheck), \
         patch('salted.__main__.doi_check.DoiCheck', NoopDoiCheck):
        checker = salted.Salted()
        checker.exclude_paths = {str(tmp_path / 'does-not-exist')}
        checker.check(dir_path)

    urls = [u[0] for u in FakeUrlCheck.last_urls] if FakeUrlCheck.last_urls else []
    assert any('kept' in u for u in urls)


def test_file_types_supported_scans_all(tmp_path):
    """--file_types supported (default) should scan all supported formats."""
    dir_path = tmp_path / 'mixed'
    dir_path.mkdir(parents=True, exist_ok=True)

    (dir_path / 'page.html').write_text(
        "<html><body><a href='https://html-link.example.com/'>x</a></body></html>")
    (dir_path / 'notes.md').write_text(
        "[link](https://markdown-link.example.com/)")

    with patch('salted.__main__.url_check.UrlCheck', FakeUrlCheck), \
         patch('salted.__main__.doi_check.DoiCheck', NoopDoiCheck):
        checker = salted.Salted()
        checker.file_types = 'supported'
        checker.check(dir_path)

    urls = [u[0] for u in FakeUrlCheck.last_urls] if FakeUrlCheck.last_urls else []
    assert any('html-link' in u for u in urls)
    assert any('markdown-link' in u for u in urls)
