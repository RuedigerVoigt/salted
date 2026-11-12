#!/usr/bin/python3

"""
Tests for salted.__version__ when the package is not installed
~~~~~~~~~~~~~~~~~~~~~
Running from a source checkout without installing it, there is no package
metadata, so salted/__init__.py reads the version from pyproject.toml. The
tests re-import the package with the metadata lookup failing.

Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026: Released under the Apache License 2.0
"""

import contextlib
import importlib
import importlib.metadata
import logging
import pathlib
import re
from unittest.mock import patch

import salted

PYPROJECT = pathlib.Path(__file__).parent.parent / 'pyproject.toml'


def _not_installed(_name):
    raise importlib.metadata.PackageNotFoundError('salted')


@contextlib.contextmanager
def reloaded_salted(*extra_patches):
    """Re-import salted as if it were not installed; restore it on exit."""
    package_logger = logging.getLogger('salted')
    handlers = list(package_logger.handlers)
    try:
        with patch('importlib.metadata.version', _not_installed), \
                contextlib.ExitStack() as stack:
            for extra in extra_patches:
                stack.enter_context(extra)
            importlib.reload(salted)
            yield salted
    finally:
        importlib.reload(salted)
        # Each import adds a NullHandler; drop the ones the reloads added.
        package_logger.handlers = handlers


def test_version_is_read_from_pyproject():
    expected = re.search(r'^version\s*=\s*"([^"]+)"',
                         PYPROJECT.read_text(encoding='utf-8'),
                         re.MULTILINE).group(1)
    with reloaded_salted():
        assert salted.__version__ == expected


def test_version_is_unknown_without_a_readable_pyproject():
    unreadable = patch.object(pathlib.Path, 'read_text',
                              side_effect=OSError('simulated'))
    with reloaded_salted(unreadable):
        assert salted.__version__ == 'unknown'


def test_reload_restores_the_installed_version():
    with reloaded_salted():
        pass
    assert salted.__version__ == importlib.metadata.version('salted')
    assert len(logging.getLogger('salted').handlers) == 1
