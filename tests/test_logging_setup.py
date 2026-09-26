#!/usr/bin/python3

"""
Tests that salted behaves as a library towards Python's logging
~~~~~~~~~~~~~~~~~~~~~
Smart, Asynchronous Link Tester with Database backend (SALTED)
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026: Released under the Apache License 2.0

salted used to log to the root logger, and parser.py did so at import time.
A module-level logging call runs logging.basicConfig() when the root logger
has no handler, so importing salted configured logging for the whole
program and the application's own basicConfig() call did nothing.
"""

import logging
import pathlib
import re
import subprocess
import sys

from salted import parser

SALTED_DIR = pathlib.Path(__file__).resolve().parent.parent / 'salted'


def _run_python(code: str, *args: str) -> subprocess.CompletedProcess:
    """Run code in a fresh interpreter, where pytest has not set up logging."""
    return subprocess.run([sys.executable, '-c', code, *args],
                          capture_output=True, text=True, timeout=60,
                          check=False)


def test_import_leaves_logging_unconfigured():
    """Importing salted must not configure the root logger"""
    result = _run_python(
        'import logging\n'
        'from salted import Salted\n'
        'import salted.parser\n'
        'assert logging.getLogger().handlers == [], logging.getLogger().handlers\n'
        'logging.basicConfig(level=logging.INFO)\n'
        'assert logging.getLogger().level == logging.INFO\n')
    assert result.returncode == 0, result.stderr


def test_library_is_silent_without_logging_setup():
    """Unconfigured, salted prints nothing: output is the application's call"""
    result = _run_python(
        'import logging\n'
        'from salted import Salted\n'
        'logging.getLogger("salted.test").warning("must not be printed")\n')
    assert result.returncode == 0, result.stderr
    assert 'must not be printed' not in result.stderr


def test_cli_still_reports_errors_on_stderr(tmp_path):
    """The CLI configures logging itself, so its messages still appear"""
    missing = tmp_path / 'does-not-exist'
    result = _run_python('from salted.command_line import main; main()',
                         '-i', str(missing))
    assert result.returncode == 1
    assert 'ERROR: ' in result.stderr
    assert 'does not exist' in result.stderr


def test_no_module_logs_to_the_root_logger():
    """Every module must log through its own logger, never logging.x()"""
    root_call = re.compile(
        r'\blogging\.(debug|info|warning|error|exception|critical|log)\(')
    offenders = [f'{path.name}:{number}'
                 for path in sorted(SALTED_DIR.glob('*.py'))
                 for number, line in enumerate(
                     path.read_text(encoding='utf-8').splitlines(), start=1)
                 if root_call.search(line)]
    assert not offenders, f'root logger used in {offenders}'


def test_html_backend_is_logged_at_info_level(caplog):
    """The backend is reported when a check starts, never as a warning"""
    with caplog.at_level(logging.DEBUG, logger='salted'):
        parser.log_html_backend()
    records = [r for r in caplog.records if r.name == 'salted.parser']
    assert len(records) == 1
    assert records[0].levelno == logging.INFO
    assert 'html' in records[0].getMessage().lower()
