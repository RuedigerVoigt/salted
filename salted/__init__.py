#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Smart, Asynchronous Link Tester with Database backend (SALTED)
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2021 by Rüdiger Voigt
Released under the Apache License 2.0
"""

from salted.__main__ import Salted
from salted import _version
from salted.user_agents import get_user_agent, list_presets

NAME = "salted"
__version__ = _version.__version__
__author__ = "Rüdiger Voigt"

__all__ = ['Salted', 'get_user_agent', 'list_presets']
