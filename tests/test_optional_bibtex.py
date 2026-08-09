#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Tests for BibTeX support as an optional dependency
~~~~~~~~~~~~~~~~~~~~~
Smart, Asynchronous Link Tester with Database backend (SALTED)
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026: Released under the Apache License 2.0
"""

import pathlib
from unittest.mock import AsyncMock, patch

import pytest

import salted
from salted import database_io, err, input_handler, memory_instance, parser


BIBTEX_EXAMPLE = r"""
@Article{Doe2021,
author = {Jon Doe},
title  = {Some Title},
year   = {2021},
url    = {https://www.example.com/},
}
"""


@pytest.fixture
def no_pybtex(monkeypatch):
    """Pretend pybtex is not installed."""
    monkeypatch.setattr(parser, 'PYBTEX_AVAILABLE', False)


def _handler():
    mem_inst = memory_instance.MemoryInstance()
    db = database_io.DatabaseIO(mem_inst, None, quiet=True)
    return mem_inst, input_handler.InputHandler(db, quiet=True)


class TestParserWithoutPybtex:
    """The parser refuses to parse BibTeX without the dependency"""

    def test_raises_missing_dependency(self, no_pybtex):
        """extract_links_from_bib raises a salted exception, not ImportError"""
        with pytest.raises(err.MissingOptionalDependencyError) as excinfo:
            parser.Parser().extract_links_from_bib(BIBTEX_EXAMPLE)
        assert 'salted[bibtex]' in str(excinfo.value)

    def test_exception_is_a_salted_exception(self, no_pybtex):
        """Callers may catch the base class"""
        with pytest.raises(err.SaltedException):
            parser.Parser().extract_links_from_bib(BIBTEX_EXAMPLE)

    def test_other_formats_still_work(self, no_pybtex):
        """Missing pybtex must not affect the other parsers"""
        links = parser.Parser().extract_links_from_markdown(
            '[text](https://example.com)')
        assert links == [['https://example.com', 'text']]


class TestInputHandlerWithoutPybtex:
    """A .bib file found while scanning is reported, not silently dropped"""

    def test_bib_is_counted_as_skipped(self, no_pybtex):
        """The skip is counted so it can reach the exit code"""
        mem_inst, handler = _handler()
        url_list, doi_list = handler._extract_links_and_dois(
            pathlib.Path('refs.bib'), BIBTEX_EXAMPLE)
        assert url_list is None
        assert doi_list is None
        assert handler.cnt['bib_files_skipped'] == 1
        mem_inst.tear_down_in_memory_db()

    def test_skip_is_logged_as_file_access_error(self, no_pybtex):
        """The report must show the file was not checked"""
        mem_inst, handler = _handler()
        handler._extract_links_and_dois(
            pathlib.Path('refs.bib'), BIBTEX_EXAMPLE)
        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT filePath, problem FROM fileAccessErrors;')
        rows = cursor.fetchall()
        assert len(rows) == 1
        assert 'refs.bib' in rows[0][0]
        assert 'salted[bibtex]' in rows[0][1]
        mem_inst.tear_down_in_memory_db()

    def test_counter_is_zero_when_pybtex_present(self):
        """With pybtex installed nothing is skipped"""
        mem_inst, handler = _handler()
        handler._extract_links_and_dois(
            pathlib.Path('refs.bib'), BIBTEX_EXAMPLE)
        assert handler.cnt['bib_files_skipped'] == 0
        mem_inst.tear_down_in_memory_db()

    def test_aggregate_warning_once_for_many_files(self, no_pybtex, tmp_path,
                                                   caplog):
        """Many .bib files produce one warning, not one per file"""
        mem_inst, handler = _handler()
        paths = []
        for name in ('a.bib', 'b.bib', 'c.bib'):
            p = tmp_path / name
            p.write_text(BIBTEX_EXAMPLE, encoding='utf-8')
            paths.append(p)
        handler.scan_files(paths)
        assert handler.cnt['bib_files_skipped'] == 3
        warnings = [r for r in caplog.records
                    if 'BibTeX file(s) were NOT checked' in r.message]
        assert len(warnings) == 1
        mem_inst.tear_down_in_memory_db()


class TestExplicitBibFileWithoutPybtex:
    """Naming a .bib file directly fails loudly"""

    def test_single_bib_file_raises(self, no_pybtex, tmp_path):
        """-i refs.bib is an explicit request and must not be skipped"""
        p = tmp_path / 'refs.bib'
        p.write_text(BIBTEX_EXAMPLE, encoding='utf-8')
        checker = salted.Salted()
        with pytest.raises(err.MissingOptionalDependencyError) as excinfo:
            checker.check(searchpath=p)
        assert 'salted[bibtex]' in str(excinfo.value)

    def test_uppercase_suffix_also_raises(self, no_pybtex, tmp_path):
        """File discovery accepts .BIB, so the guard must too"""
        p = tmp_path / 'refs.BIB'
        p.write_text(BIBTEX_EXAMPLE, encoding='utf-8')
        checker = salted.Salted()
        with pytest.raises(err.MissingOptionalDependencyError):
            checker.check(searchpath=p)


class TestExitCodeWithoutPybtex:
    """Skipped .bib files fail a --raise_for_dead_links run"""

    @patch('salted.url_check.UrlCheck.head_request',
           new_callable=AsyncMock, return_value=200)
    def test_folder_scan_raises_when_configured(self, mock_head, no_pybtex,
                                                tmp_path):
        """An unchecked .bib file counts as a failure"""
        (tmp_path / 'refs.bib').write_text(BIBTEX_EXAMPLE, encoding='utf-8')
        (tmp_path / 'page.html').write_text(
            '<a href="https://example.com">ok</a>', encoding='utf-8')
        checker = salted.Salted()
        checker.raise_for_dead_links = True
        with pytest.raises(err.DeadLinksException) as excinfo:
            checker.check(searchpath=tmp_path)
        assert 'BibTeX' in str(excinfo.value)

    @patch('salted.url_check.UrlCheck.head_request',
           new_callable=AsyncMock, return_value=200)
    def test_folder_scan_passes_without_the_flag(self, mock_head, no_pybtex,
                                                 tmp_path):
        """Without the flag the run completes, the rest is still checked"""
        (tmp_path / 'refs.bib').write_text(BIBTEX_EXAMPLE, encoding='utf-8')
        (tmp_path / 'page.html').write_text(
            '<a href="https://example.com">ok</a>', encoding='utf-8')
        checker = salted.Salted()
        checker.raise_for_dead_links = False
        checker.check(searchpath=tmp_path)

    @patch('salted.url_check.UrlCheck.head_request',
           new_callable=AsyncMock, return_value=200)
    def test_no_raise_when_pybtex_present(self, mock_head, tmp_path):
        """With pybtex installed the same folder passes"""
        (tmp_path / 'refs.bib').write_text(BIBTEX_EXAMPLE, encoding='utf-8')
        checker = salted.Salted()
        checker.raise_for_dead_links = True
        checker.check(searchpath=tmp_path)
