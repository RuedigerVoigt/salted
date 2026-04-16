#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests that the report receives percentage_full_request derived from counters.
"""

from pathlib import Path
from unittest.mock import patch

import salted


class StubUrlCheck:
    def __init__(self, *args, **kwargs):
        self.cnt = {
            'checked_urls': 10,
            'fine': 7,
            'neededFullRequest': 3,
        }

    def check_urls(self):
        return None


class NoopDoiCheck:
    def __init__(self, db, quiet=False, mailto=None):
        self.valid_doi_list = []
        self.invalid_doi_list = []

    def check_dois(self):
        return None


captured_stats = {}


def capture_report(statistics, template, write_to, replace_path_by_url):  # noqa: D401
    global captured_stats
    captured_stats = statistics


def test_percentage_full_request_computed(tmp_path):
    # Arrange: single HTML file to trigger a minimal run
    d = tmp_path / 'stats'
    d.mkdir()
    (d / 'index.html').write_text("<a href='https://x.test'>x</a>")

    with patch('salted.__main__.url_check.UrlCheck', StubUrlCheck), \
         patch('salted.__main__.doi_check.DoiCheck', NoopDoiCheck), \
         patch('salted.report_generator.ReportGenerator.generate_report', side_effect=capture_report):
        checker = salted.Salted()
        checker.check(d)

    assert 'percentage_full_request' in captured_stats
    assert captured_stats['percentage_full_request'] == 30.0

