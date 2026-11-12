#!/usr/bin/python3

"""
Tests for the import-time detection of the optional dependencies
~~~~~~~~~~~~~~~~~~~~~
salted/parser.py decides once, when it is imported, whether lxml and pybtex
are available. These tests re-import the module with a dependency hidden or
replaced by a stand-in, so both outcomes are covered whether or not the
extras are installed (CI installs neither). Behaviour without pybtex, given
the flag, is in test_optional_bibtex.py.

Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026: Released under the Apache License 2.0
"""

import contextlib
import importlib
import importlib.util
import logging
import sys
import types
from unittest.mock import patch

from salted import parser

HIDE_PYBTEX = {'pybtex': None, 'pybtex.database': None}


@contextlib.contextmanager
def reloaded_parser(modules):
    """Re-import salted.parser with sys.modules patched by `modules`.

    A None value makes `import name` raise ImportError, as if the package
    were not installed; a module object is imported instead of the real
    package. The parser is reloaded once more on exit, after sys.modules is
    restored, so later tests see it as it really is.
    """
    try:
        with patch.dict(sys.modules, modules):
            importlib.reload(parser)
            yield parser
    finally:
        importlib.reload(parser)


def _fake_lxml():
    fake = types.ModuleType('lxml')
    fake.__version__ = '9.9.9'
    return fake


def _parser_messages(caplog):
    return [r.getMessage() for r in caplog.records if r.name == 'salted.parser']


def test_without_lxml_html_parser_is_the_fallback():
    with reloaded_parser({'lxml': None}):
        assert parser._BS_PARSER == 'html.parser'
        links = parser.Parser.extract_links_from_html(
            '<a href="https://example.com/">text</a>')
        assert links == [['https://example.com/', 'text']]


def test_without_lxml_the_fallback_is_logged(caplog):
    with reloaded_parser({'lxml': None}), \
            caplog.at_level(logging.INFO, logger='salted.parser'):
        parser.log_html_backend()
    messages = _parser_messages(caplog)
    assert len(messages) == 1
    assert 'lxml not installed' in messages[0]
    assert 'salted[lxml]' in messages[0]


def test_with_lxml_it_is_chosen_and_logged_with_its_version(caplog):
    # A stand-in module: nothing is parsed, only the detection is tested.
    with reloaded_parser({'lxml': _fake_lxml()}), \
            caplog.at_level(logging.INFO, logger='salted.parser'):
        assert parser._BS_PARSER == 'lxml'
        parser.log_html_backend()
    messages = _parser_messages(caplog)
    assert len(messages) == 1
    assert 'lxml 9.9.9 available' in messages[0]


def test_without_pybtex_the_flag_is_cleared():
    with reloaded_parser(HIDE_PYBTEX):
        assert parser.PYBTEX_AVAILABLE is False


def test_reload_restores_the_real_state():
    """The helper must not leak a hidden or fake module into later tests"""
    lxml_installed = importlib.util.find_spec('lxml') is not None
    with reloaded_parser({'lxml': None, **HIDE_PYBTEX}):
        pass
    assert parser.PYBTEX_AVAILABLE is True  # pybtex is in the test group
    assert parser._BS_PARSER == ('lxml' if lxml_installed else 'html.parser')
    with reloaded_parser({'lxml': _fake_lxml()}):
        pass
    assert parser._BS_PARSER == ('lxml' if lxml_installed else 'html.parser')
    if lxml_installed:
        assert parser.lxml.__version__ != '9.9.9'
