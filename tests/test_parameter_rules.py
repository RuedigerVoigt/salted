#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Tests for the central parameter validation rules
~~~~~~~~~~~~~~~~~~~~~
Smart, Asynchronous Link Tester with Database backend (SALTED)
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026: Released under the Apache License 2.0
"""

import pytest

from salted import parameter_rules


SRC = 'in a test'


class TestValidateDispatch:
    """The validate() entry point routes by parameter name."""

    def test_unknown_parameter_raises_keyerror(self):
        """An unknown name is a programming error, not a user error."""
        with pytest.raises(KeyError):
            parameter_rules.validate('no_such_parameter', '1', SRC)

    def test_source_appears_in_error_message(self):
        """The error message must name the origin of the bad value."""
        with pytest.raises(ValueError, match='in config file test.ini'):
            parameter_rules.validate(
                'timeout', 'five', 'in config file test.ini')

    def test_parameter_name_appears_in_error_message(self):
        with pytest.raises(ValueError, match='timeout'):
            parameter_rules.validate('timeout', 'five', SRC)


class TestMailto:
    """mailto must be a valid address, or absent.

    It is sent to the CrossRef API in the User-Agent header. Validating it
    here - at the boundary where the parameter arrives - keeps doi_check.py
    a DOI client: it receives a value that is already known good.
    """

    @pytest.mark.parametrize('address', [
        'you@example.com',
        'first.last@sub.example.org',
        "o'brien@example.com",
        'A@EXAMPLE.COM',
    ])
    def test_valid_addresses_accepted(self, address):
        assert parameter_rules.validate('mailto', address, SRC) == address

    def test_value_is_trimmed(self):
        assert parameter_rules.validate(
            'mailto', '  you@example.com  ', SRC) == 'you@example.com'

    @pytest.mark.parametrize('empty', ['', '   '])
    def test_empty_means_not_set(self, empty):
        """An empty value is 'no address', which is allowed."""
        assert parameter_rules.validate('mailto', empty, SRC) is None

    @pytest.mark.parametrize('bad', [
        'nonsense',
        'a@b',
        'you@example.com, me@example.com',   # a single address only
        'me@x.com\r\nX-Injected: yes',       # header injection attempt
        'me@x.com\nX-Injected: yes',
        'me@x.com\x1b[31m',                  # terminal escape
        42,
        True,
    ])
    def test_invalid_values_raise(self, bad):
        with pytest.raises(ValueError, match='mailto'):
            parameter_rules.validate('mailto', bad, SRC)

    def test_rejected_value_cannot_forge_a_log_line(self):
        """The message repr()s the value, so newlines cannot break out."""
        with pytest.raises(ValueError) as exc:
            parameter_rules.validate(
                'mailto', 'me@x.com\nX-Injected: yes', SRC)

        assert '\n' not in str(exc.value)
        assert '\\n' in str(exc.value)


class TestNumWorkers:
    """num_workers accepts 'automatic' or an integer >= 1."""

    def test_automatic_accepted(self):
        assert parameter_rules.validate('num_workers', 'automatic', SRC) == 'automatic'

    def test_automatic_case_insensitive_and_trimmed(self):
        assert parameter_rules.validate('num_workers', ' Automatic ', SRC) == 'automatic'

    def test_positive_int_accepted(self):
        assert parameter_rules.validate('num_workers', 8, SRC) == 8

    def test_positive_int_string_accepted(self):
        assert parameter_rules.validate('num_workers', '8', SRC) == 8

    @pytest.mark.parametrize('bad', [0, -1, '0', 'abc', '', True])
    def test_invalid_values_raise(self, bad):
        with pytest.raises(ValueError, match='num_workers'):
            parameter_rules.validate('num_workers', bad, SRC)


class TestIntParameters:
    """Integer parameters enforce their minimum on both input types."""

    def test_timeout_one_accepted(self):
        assert parameter_rules.validate('timeout', 1, SRC) == 1

    def test_timeout_string_converted(self):
        assert parameter_rules.validate('timeout', '15', SRC) == 15

    @pytest.mark.parametrize('bad', [0, '0', -1, '-1', 'five', '', '5.5', True])
    def test_timeout_invalid_values_raise(self, bad):
        """Zero is rejected too: it would disable the timeout entirely and
        a never-responding server could occupy a worker forever."""
        with pytest.raises(ValueError, match='timeout'):
            parameter_rules.validate('timeout', bad, SRC)

    def test_cache_hours_zero_accepted(self):
        assert parameter_rules.validate(
            'dont_check_again_within_hours', 0, SRC) == 0

    def test_cache_hours_negative_raises(self):
        with pytest.raises(ValueError, match='dont_check_again_within_hours'):
            parameter_rules.validate('dont_check_again_within_hours', -24, SRC)

    def test_max_file_size_minimum_is_one(self):
        assert parameter_rules.validate('max_file_size_mb', 1, SRC) == 1
        with pytest.raises(ValueError, match='max_file_size_mb'):
            parameter_rules.validate('max_file_size_mb', 0, SRC)


class TestFloatParameters:
    """domain_delay accepts numbers >= 0."""

    def test_zero_accepted(self):
        assert parameter_rules.validate('domain_delay', 0, SRC) == 0.0

    def test_string_converted(self):
        assert parameter_rules.validate('domain_delay', '0.5', SRC) == 0.5

    def test_float_passed_through(self):
        assert parameter_rules.validate('domain_delay', 0.25, SRC) == 0.25

    @pytest.mark.parametrize('bad', [-0.1, '-1', 'fast', '', True])
    def test_invalid_values_raise(self, bad):
        with pytest.raises(ValueError, match='domain_delay'):
            parameter_rules.validate('domain_delay', bad, SRC)


class TestBoolParameters:
    """Boolean parameters accept real bools and config file spellings."""

    @pytest.mark.parametrize('name', ['raise_for_dead_links', 'check_dois'])
    def test_real_bool_passed_through(self, name):
        assert parameter_rules.validate(name, True, SRC) is True
        assert parameter_rules.validate(name, False, SRC) is False

    @pytest.mark.parametrize('spelling,expected', [
        ('true', True), ('True', True), ('yes', True), ('on', True),
        ('1', True),
        ('false', False), ('no', False), ('off', False), ('0', False),
    ])
    def test_config_spellings_parsed(self, spelling, expected):
        assert parameter_rules.validate(
            'raise_for_dead_links', spelling, SRC) is expected

    @pytest.mark.parametrize('bad', ['maybe', '', 2, 1.0])
    def test_invalid_values_raise(self, bad):
        with pytest.raises(ValueError, match='raise_for_dead_links'):
            parameter_rules.validate('raise_for_dead_links', bad, SRC)


class TestChoiceParameters:
    """file_types accepts a fixed set of values."""

    @pytest.mark.parametrize('value', ['supported', 'html', 'tex', 'markdown'])
    def test_valid_choices_accepted(self, value):
        assert parameter_rules.validate('file_types', value, SRC) == value

    def test_choice_trimmed_and_lowercased(self):
        assert parameter_rules.validate('file_types', ' HTML ', SRC) == 'html'

    def test_unknown_choice_raises_and_lists_allowed(self):
        """A typo must fail loudly instead of silently checking everything."""
        with pytest.raises(ValueError, match='markdown'):
            parameter_rules.validate('file_types', 'htlm', SRC)

    def test_empty_choice_raises(self):
        with pytest.raises(ValueError, match='file_types'):
            parameter_rules.validate('file_types', '', SRC)
