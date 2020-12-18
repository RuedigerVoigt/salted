#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Smart, Asynchronous Link Tester with Database backend (SALTED)
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020 by Rüdiger Voigt
Released under the Apache License 2.0
"""
import sys

if sys.version_info.major != 3 or sys.version_info.minor < 8:
    raise RuntimeError('You need at least Python 3.8 to run salted. ' +
                       'You are running: ' + str(sys.version_info.major) +
                       '.' + str(sys.version_info.minor))

from salted.__main__ import Salted

NAME = "salted"
__version__ = "0.5.4"
__author__ = "Rüdiger Voigt"
