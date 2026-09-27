#!/usr/bin/python3
"""
Tests for the DOI format check (salted/doi_format.py).

Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026 Rüdiger Voigt and contributors
Released under the Apache License 2.0
"""

import pytest

from salted import doi_format
from salted.doi_format import DoiField


class TestIsWellFormed:

    @pytest.mark.parametrize('doi', [
        '10.1038/nature14539',
        '10.1038/NATURE14539',
        '10.48550/arXiv.1706.03762',
        '10.5281/zenodo.1239',
        '10.1000/1',
        '10.1000.10/123',                  # subdivided registrant code
        '10.1000.10.5/x',
        '10.1175/1520-0469(1963)020<0130:DNF>2.0.CO;2',
        '10.1002/(SICI)1097-4571(199806)49:8<693::AID-ASI4>3.0.CO;2-0',
        '10.1007/978-3-642-00296-0_5',
        '10.12345/a/b/c',                  # the suffix may hold slashes
    ])
    def test_valid(self, doi):
        assert doi_format.is_well_formed(doi)

    @pytest.mark.parametrize('doi', [
        '',
        '10.1038',                         # no suffix
        '10.1038/',                        # empty suffix
        '10.123/abc',                      # registrant code too short
        '11.1234/abc',                     # not the DOI directory
        '10.abcd/efg',
        '10.1000./x',                      # empty subdivision
        '10.1234/with space',
        ' 10.1234/abc',
        'doi:10.1234/abc',                 # prefix must be removed first
        'https://doi.org/10.1234/abc',
    ])
    def test_invalid(self, doi):
        assert not doi_format.is_well_formed(doi)


class TestDoiFromLink:

    @pytest.mark.parametrize('url,doi', [
        ('https://doi.org/10.1234/abc', '10.1234/abc'),
        ('http://dx.doi.org/10.1234/abc', '10.1234/abc'),
        ('HTTPS://DOI.ORG/10.1234/abc', '10.1234/abc'),
        ('https://doi.org/10.1175/1520-0469(1963)020%3C0130:DNF%3E2.0.CO;2',
         '10.1175/1520-0469(1963)020<0130:DNF>2.0.CO;2'),
    ])
    def test_doi_links(self, url, doi):
        assert doi_format.doi_from_link(url) == doi

    @pytest.mark.parametrize('url', [
        'https://example.com/10.1234/abc',
        'https://www.doi.org/10.1234/abc',
        'ftp://doi.org/10.1234/abc',
        'https://doi.org/',
        'http://[::1',                     # urlsplit rejects it
    ])
    def test_not_a_doi_link(self, url):
        assert doi_format.doi_from_link(url) is None


class TestRecommendedLink:

    @pytest.mark.parametrize('url,recommended', [
        ('http://doi.org/10.1234/abc', 'https://doi.org/10.1234/abc'),
        ('http://dx.doi.org/10.1234/abc', 'https://doi.org/10.1234/abc'),
        ('https://dx.doi.org/10.1234/abc', 'https://doi.org/10.1234/abc'),
        ('https://dx.doi.org/10.1234/a%3Cb%3E', 'https://doi.org/10.1234/a%3Cb%3E'),
        ('http://doi.org/10.1234/abc?x=1', 'https://doi.org/10.1234/abc?x=1'),
    ])
    def test_outdated_forms(self, url, recommended):
        assert doi_format.recommended_link(url) == recommended

    @pytest.mark.parametrize('url', [
        'https://doi.org/10.1234/abc',
        'https://example.com/10.1234/abc',
    ])
    def test_nothing_to_recommend(self, url):
        assert doi_format.recommended_link(url) is None


class TestParseDoiField:

    @pytest.mark.parametrize('value,expected', [
        ('10.1234/abc', DoiField('10.1234/abc', True, False)),
        ('  10.1234/abc \n', DoiField('10.1234/abc', True, False)),
        ('https://doi.org/10.1234/abc', DoiField('10.1234/abc', True, False)),
        ('http://dx.doi.org/10.1234/abc', DoiField('10.1234/abc', True, True)),
        ('https://dx.doi.org/10.1234/abc', DoiField('10.1234/abc', True, True)),
        ('doi:10.1234/abc', DoiField('10.1234/abc', True, True)),
        ('DOI: 10.1234/abc', DoiField('10.1234/abc', True, True)),
        ('10.123/abc', DoiField('10.123/abc', False, False)),
        ('doi:nonsense', DoiField('nonsense', False, True)),
        ('https://example.com/10.1234/abc',
         DoiField('https://example.com/10.1234/abc', False, False)),
    ])
    def test_fields(self, value, expected):
        assert doi_format.parse_doi_field(value) == expected
