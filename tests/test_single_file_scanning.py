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

    def __init__(self, user_agent, db, workers, timeout_sec, ignore_urls, domain_delay):
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

    def __init__(self, db):
        pass

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

