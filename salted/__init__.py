#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Smart, Asynchronous Link Tester with Database backend (SALTED)
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2021 by Rüdiger Voigt
Released under the Apache License 2.0
"""

from importlib.metadata import version as pkg_version

from salted.user_agents import get_user_agent, list_presets

NAME = "salted"
__author__ = "Rüdiger Voigt"

# Single source of truth: pyproject.toml (via installed package metadata)
__version__ = pkg_version("salted")

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
