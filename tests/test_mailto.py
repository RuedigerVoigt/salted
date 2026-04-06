#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for mailto link handling.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from salted.parser import Parser
import salted


# ---------------------------------------------------------------------------
# Unit tests for extract_mails_from_mailto
# ---------------------------------------------------------------------------

class TestExtractMailsFromMailto:

    def setup_method(self):
        self.parser = Parser()

    def test_single_address(self):
        result = self.parser.extract_mails_from_mailto("mailto:alice@example.com")
        assert result == ["alice@example.com"]

    def test_multiple_addresses(self):
        result = self.parser.extract_mails_from_mailto(
            "mailto:alice@example.com,bob@example.com")
        assert result == ["alice@example.com", "bob@example.com"]

    def test_address_with_query_params_ignored(self):
        result = self.parser.extract_mails_from_mailto(
            "mailto:alice@example.com?subject=Hi&cc=bob@example.com")
        # only the to-address in the path is returned
        assert result == ["alice@example.com"]

    def test_empty_mailto(self):
        result = self.parser.extract_mails_from_mailto("mailto:")
        assert result == []

    def test_urlparse_exception_returns_empty(self):
        """If urlparse raises internally, an empty list is returned."""
        with patch('urllib.parse.urlparse', side_effect=Exception("boom")):
            result = self.parser.extract_mails_from_mailto('mailto:test@example.com')
        assert result == []

    def test_whitespace_stripped(self):
        result = self.parser.extract_mails_from_mailto(
            "mailto: alice@example.com , bob@example.com ")
        assert result == ["alice@example.com", "bob@example.com"]


# ---------------------------------------------------------------------------
# Integration-style: mailto links stored and passed to report
# ---------------------------------------------------------------------------

class StubUrlCheck:
    def __init__(self, *args, **kwargs):
        self.cnt = {'checked_urls': 0, 'fine': 0, 'neededFullRequest': 0}

    def check_urls(self):
        return None


class NoopDoiCheck:
    def __init__(self, db, quiet=False):
        pass

    def check_dois(self):
        return None


captured_mailto = None


def capture_report(statistics, template, write_to, replace_path_by_url):
    global captured_mailto
    # We need to reach into the report generator's generate_mailto_list output.
    # We do this by patching generate_report itself and calling generate_mailto_list
    # directly before; easier: just capture via the template render side-effect.
    pass


def test_empty_mailto_flagged_as_invalid(tmp_path):
    """A bare mailto: with no address hits the empty-address branch."""
    d = tmp_path / 'site'
    d.mkdir()
    (d / 'index.html').write_text("<a href='mailto:'>empty</a>")

    report_data = {}

    def fake_generate_report(self, statistics, template, write_to,
                              replace_path_by_url=None):
        report_data['mailto'] = self.generate_mailto_list()

    with patch('salted.__main__.url_check.UrlCheck', StubUrlCheck), \
         patch('salted.__main__.doi_check.DoiCheck', NoopDoiCheck), \
         patch('salted.report_generator.ReportGenerator.generate_report',
               fake_generate_report):
        checker = salted.Salted()
        checker.check(d)

    assert report_data['mailto'] is not None
    entry = report_data['mailto'][0]
    assert entry['address'] == ''
    assert entry['valid'] is False


def test_valid_mailto_stored(tmp_path):
    """A valid mailto link must appear in the report data."""
    d = tmp_path / 'site'
    d.mkdir()
    (d / 'index.html').write_text(
        "<a href='mailto:alice@example.com'>mail me</a>")

    report_data = {}

    def fake_generate_report(self, statistics, template, write_to,
                              replace_path_by_url=None):
        report_data['mailto'] = self.generate_mailto_list()

    with patch('salted.__main__.url_check.UrlCheck', StubUrlCheck), \
         patch('salted.__main__.doi_check.DoiCheck', NoopDoiCheck), \
         patch('salted.report_generator.ReportGenerator.generate_report',
               fake_generate_report):
        checker = salted.Salted()
        checker.check(d)

    assert report_data['mailto'] is not None
    assert len(report_data['mailto']) == 1
    entry = report_data['mailto'][0]
    assert entry['address'] == 'alice@example.com'
    assert entry['valid'] is True


def test_malformed_mailto_flagged(tmp_path):
    """A mailto with no @ in the address must be flagged as invalid."""
    d = tmp_path / 'site'
    d.mkdir()
    (d / 'index.html').write_text(
        "<a href='mailto:not-an-email'>bad link</a>")

    report_data = {}

    def fake_generate_report(self, statistics, template, write_to,
                              replace_path_by_url=None):
        report_data['mailto'] = self.generate_mailto_list()

    with patch('salted.__main__.url_check.UrlCheck', StubUrlCheck), \
         patch('salted.__main__.doi_check.DoiCheck', NoopDoiCheck), \
         patch('salted.report_generator.ReportGenerator.generate_report',
               fake_generate_report):
        checker = salted.Salted()
        checker.check(d)

    assert report_data['mailto'] is not None
    entry = report_data['mailto'][0]
    assert entry['valid'] is False


def test_no_mailto_returns_none(tmp_path):
    """When no mailto links exist, generate_mailto_list must return None."""
    d = tmp_path / 'site'
    d.mkdir()
    (d / 'index.html').write_text(
        "<a href='https://example.com'>link</a>")

    report_data = {}

    def fake_generate_report(self, statistics, template, write_to,
                              replace_path_by_url=None):
        report_data['mailto'] = self.generate_mailto_list()

    with patch('salted.__main__.url_check.UrlCheck', StubUrlCheck), \
         patch('salted.__main__.doi_check.DoiCheck', NoopDoiCheck), \
         patch('salted.report_generator.ReportGenerator.generate_report',
               fake_generate_report):
        checker = salted.Salted()
        checker.check(d)

    assert report_data['mailto'] is None


def test_mailto_not_counted_as_checked_url(tmp_path):
    """mailto links must not increment the checked_urls counter."""
    d = tmp_path / 'site'
    d.mkdir()
    (d / 'index.html').write_text(
        "<a href='mailto:alice@example.com'>mail</a>")

    stats_data = {}

    def fake_generate_report(self, statistics, template, write_to,
                              replace_path_by_url=None):
        stats_data['num_checked'] = statistics['num_checked']

    with patch('salted.__main__.url_check.UrlCheck', StubUrlCheck), \
         patch('salted.__main__.doi_check.DoiCheck', NoopDoiCheck), \
         patch('salted.report_generator.ReportGenerator.generate_report',
               fake_generate_report):
        checker = salted.Salted()
        checker.check(d)

    assert stats_data['num_checked'] == 0
