#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Salted: Custom Exceptions

Source: https://github.com/RuedigerVoigt/salted
(c) 2019-2021 Rüdiger Voigt:
Released under the Apache License 2.0
"""


class SaltedException(Exception):
    "An exception occured"
    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        Exception.__init__(self, *args, **kwargs)


class DeadLinksException(SaltedException):
    """Raised if dead links are found and the settings require raising
       an exception for them."""
