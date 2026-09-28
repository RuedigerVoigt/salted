#!/usr/bin/python3
"""
Settings set as attributes pass the same rules as config and CLI values.

Before, only config file and command line values were validated. An
attribute set in Python was used as given: file_types = 'htlm' checked
every file type, the string 'False' counted as true, timeout = 0 switched
the request timeout off, and an ignore_domains entry written as a URL never
matched, so salted contacted the domain it was told to skip.

Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026 Rüdiger Voigt and contributors
Released under the Apache License 2.0
"""

import pathlib
from unittest.mock import AsyncMock, patch

import pytest

import salted
from salted import err


@pytest.fixture
def checker(tmp_path, monkeypatch):
    """A Salted object without any config file."""
    monkeypatch.chdir(tmp_path)
    return salted.Salted()


class TestInvalidValuesAreRejected:

    @pytest.mark.parametrize('name,value', [
        ('file_types', 'htlm'),
        ('file_types', 5),
        ('num_workers', 0),
        ('num_workers', 'many'),
        ('timeout', 0),
        ('timeout', 7.5),
        ('raise_for_dead_links', 'maybe'),
        ('check_internal_links', 2),
        ('quiet', 'sometimes'),
        ('domain_delay', -1),
        ('max_file_size_mb', 0),
        ('dont_check_again_within_hours', -5),
    ])
    def test_rule_violation(self, checker, name, value):
        setattr(checker, name, value)
        with pytest.raises(err.InvalidSettingError,
                           match=f'for {name} set as an attribute'):
            checker.check_parameters()

    @pytest.mark.parametrize('name,value', [
        ('ignore_urls', 'https://example.com/'),     # a string, not a set
        ('ignore_domains', 'example.com'),
        ('exclude_paths', 'drafts'),
        ('exclude_paths', pathlib.Path('drafts')),
        ('ignore_urls', {pathlib.Path('x')}),        # paths only for exclusions
        ('ignore_domains', {42}),
        ('ignore_urls', None),
    ])
    def test_not_a_set_of_strings(self, checker, name, value):
        setattr(checker, name, value)
        with pytest.raises(err.InvalidSettingError,
                           match=f'for {name} set as an attribute'):
            checker.check_parameters()

    def test_error_is_a_value_error(self, checker):
        """num_workers < 1 raised a ValueError before; callers may catch that."""
        checker.num_workers = 0
        with pytest.raises(ValueError):
            checker.check_parameters()

    def test_nothing_is_requested(self, checker, tmp_path):
        (tmp_path / 'index.html').write_text(
            '<a href="https://example.com/">x</a>', encoding='utf-8')
        checker.timeout = 0
        with patch('salted.url_check.UrlCheck.head_request',
                   new_callable=AsyncMock) as mock_head:
            with pytest.raises(err.InvalidSettingError):
                checker.check(tmp_path)
        mock_head.assert_not_awaited()


class TestValuesAreConverted:

    def test_config_style_strings(self, checker):
        checker.file_types = 'HTML'
        checker.raise_for_dead_links = 'False'
        checker.quiet = 'no'
        checker.timeout = '7'
        checker.num_workers = 'Automatic'
        checker.check_parameters()
        assert checker.file_types == 'html'
        assert checker.raise_for_dead_links is False
        assert checker.quiet is False
        assert checker.timeout == 7
        assert checker.num_workers == 'automatic'

    def test_lists_become_sets(self, checker):
        checker.ignore_urls = ['https://a.example/', 'https://a.example/']
        checker.exclude_paths = ('drafts', pathlib.Path('vendor'))
        checker.check_parameters()
        assert checker.ignore_urls == {'https://a.example/'}
        assert checker.exclude_paths == {'drafts', pathlib.Path('vendor')}

    def test_ignore_domains_reduced_to_host(self, checker, caplog):
        checker.ignore_domains = {'https://Example.com/path', 'skip.org',
                                  'https://'}
        with caplog.at_level('WARNING', logger='salted'):
            checker.check_parameters()
        assert checker.ignore_domains == {'example.com', 'skip.org'}
        assert "'https://' is not a valid domain" in caplog.text

    def test_defaults_are_left_unchanged(self, checker):
        before = {name: getattr(checker, name) for name in (
            'file_types', 'num_workers', 'timeout', 'raise_for_dead_links',
            'domain_delay', 'check_internal_links', 'max_file_size_mb',
            'dont_check_again_within_hours', 'quiet', 'ignore_urls',
            'ignore_domains', 'exclude_paths')}
        checker.check_parameters()
        after = {name: getattr(checker, name) for name in before}
        assert after == before


@patch('salted.url_check.UrlCheck.head_request', new_callable=AsyncMock,
       return_value=200)
def test_ignore_domains_url_is_not_contacted(mock_head, checker, tmp_path):
    """The domain the caller excluded must not receive a request."""
    (tmp_path / 'index.html').write_text(
        '<a href="https://example.com/a">skip</a>'
        '<a href="https://other.example/">check</a>', encoding='utf-8')
    checker.cache_file = None
    checker.quiet = True
    checker.domain_delay = 0
    checker.ignore_domains = {'https://example.com/'}
    with patch('salted.report_generator.ReportGenerator.generate_report'):
        checker.check(tmp_path)
    requested = [call.args[0] for call in mock_head.await_args_list]
    assert requested == ['https://other.example/']
