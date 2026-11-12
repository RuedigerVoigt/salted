#!/usr/bin/env python3

"""
Tests that ignore_urls are normalized before being used for matching.
"""

from unittest.mock import patch

import salted


class FakeUrlCheck:
    """Capture the ignore set passed from Salted.check without doing network work."""

    last_ignore = None

    def __init__(self, user_agent, db, workers, timeout_sec, ignore_urls,
                 domain_delay, ignore_domains=None, quiet=False):
        FakeUrlCheck.last_ignore = ignore_urls
        self.cnt = {
            'checked_urls': 0,
            'fine': 0,
            'neededFullRequest': 0,
        }

    def check_urls(self):
        return None


def test_ignore_urls_are_normalized(tmp_path, monkeypatch):
    # Arrange: create a simple HTML file to ensure the pipeline runs
    d = tmp_path / "sample"
    d.mkdir()
    p = d / "index.html"
    p.write_text("<a href='https://example.com/?x=1'>x</a>")

    # Write a config with a messy ignore entry (unsorted query, spaces)
    cfg = tmp_path / 'salted-linkcheck.ini'
    cfg.write_text("""
[BEHAVIOR]
ignore_urls =  https://example.com/?b=2&a=1 ,
""")

    # Act: run check with UrlCheck patched to our fake
    # Change to tmp_path so config file is found
    monkeypatch.chdir(tmp_path)
    with patch('salted.__main__.url_check.UrlCheck', FakeUrlCheck):
        checker = salted.Salted()
        checker.check(d)

    # Assert: normalization sorts query params
    assert 'https://example.com/?a=1&b=2' in FakeUrlCheck.last_ignore
    assert 'https://example.com/?b=2&a=1' not in FakeUrlCheck.last_ignore


def test_ignore_entry_with_conflicting_query_keys_keeps_its_query():
    # normalize_url raises QueryKeyConflict for a key with two values; the
    # entry is normalized without touching the query instead.
    from salted.__main__ import _normalize_url_set
    assert _normalize_url_set({'HTTPS://Example.com/?a=1&a=2'}) == {
        'https://example.com/?a=1&a=2'}


def test_ignore_entry_that_cannot_be_normalized_is_kept_as_written():
    # A malformed entry is not dropped: it can still match a malformed
    # link, which is queued under its own spelling.
    from salted.__main__ import _normalize_url_set
    assert _normalize_url_set({'foo', 'https://example.com:99999/'}) == {
        'foo', 'https://example.com:99999/'}
