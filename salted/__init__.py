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

from salted.__main__ import Salted
from salted.user_agents import get_user_agent, list_presets

NAME = "salted"
__author__ = "Rüdiger Voigt"

# Single source of truth: pyproject.toml (via installed package metadata)
__version__ = pkg_version("salted")

__all__ = ['Salted', 'get_user_agent', 'list_presets']
