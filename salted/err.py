#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Salted: Custom Exceptions

Source: https://github.com/RuedigerVoigt/salted
(c) 2019-2021 Rüdiger Voigt:
Released under the Apache License 2.0
"""


class SaltedException(Exception):
    """Base exception for salted-specific errors."""
    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        Exception.__init__(self, *args, **kwargs)


class DeadLinksException(SaltedException):
    """Raised when dead links are found and raise_for_dead_links is enabled.

    This exception is raised if dead links are found and the configuration
    requires raising an exception for them (typically in CI/CD pipelines).
    """
