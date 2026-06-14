#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Smart, Asynchronous Link Tester with Database backend (SALTED)
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026 Rüdiger Voigt and contributors
Released under the Apache License 2.0
"""

import pathlib
import re
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version

from salted.user_agents import get_user_agent, list_presets

NAME = "salted"
__author__ = "Rüdiger Voigt"

try:
    __version__ = pkg_version("salted")
except PackageNotFoundError:
    # Running from source without installation — read directly from pyproject.toml
    try:
        _pyproject = pathlib.Path(__file__).parent.parent / "pyproject.toml"
        _m = re.search(r'^version\s*=\s*"([^"]+)"',
                       _pyproject.read_text(encoding="utf-8"), re.MULTILINE)
        __version__ = _m.group(1) if _m else "unknown"
    except Exception:
        __version__ = "unknown"

__all__ = ['get_user_agent', 'list_presets']


def __getattr__(name):
    """Lazy import to avoid circular import with __main__.

    This allows `from salted import Salted` to work without causing
    the RuntimeWarning about __main__ being in sys.modules.
    """
    if name == 'Salted':
        from salted.__main__ import Salted
        return Salted
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
