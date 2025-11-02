#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for parsing helper provided by userprovided.parameters
"""

from userprovided.parameters import separated_string_to_set


class TestParseCommaSeparatedSet:
    def test_none_returns_none(self):
        assert separated_string_to_set(None) is None

    def test_basic_split(self):
        assert separated_string_to_set("a,b,c") == {"a", "b", "c"}

    def test_trims_whitespace(self):
        assert separated_string_to_set(" a ,  b , c ") == {"a", "b", "c"}

    def test_ignores_empty_entries(self):
        assert separated_string_to_set(",,a,,b,,") == {"a", "b"}
