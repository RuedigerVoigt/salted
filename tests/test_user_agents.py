#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Tests for user agent presets
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2025: Released under the Apache License 2.0
"""

import pytest

from salted.user_agents import get_user_agent, list_presets, USER_AGENTS


class TestListPresets:
    """Test listing available presets"""

    def test_list_presets_returns_list(self):
        """Test that list_presets returns a list"""
        presets = list_presets()
        assert isinstance(presets, list)

    def test_list_presets_not_empty(self):
        """Test that there are presets available"""
        presets = list_presets()
        assert len(presets) > 0

    def test_list_presets_contains_expected_presets(self):
        """Test that expected presets are available"""
        presets = list_presets()
        assert 'chrome' in presets
        assert 'firefox' in presets
        assert 'edge' in presets
        assert 'safari' in presets

    def test_list_presets_matches_user_agents_keys(self):
        """Test that list_presets matches USER_AGENTS keys"""
        presets = list_presets()
        assert set(presets) == set(USER_AGENTS.keys())


class TestGetUserAgent:
    """Test getting user agent strings"""

    def test_get_chrome_user_agent(self):
        """Test getting Chrome user agent"""
        ua = get_user_agent('chrome')
        assert isinstance(ua, str)
        assert len(ua) > 0
        assert 'Chrome' in ua
        assert 'Mozilla' in ua

    def test_get_firefox_user_agent(self):
        """Test getting Firefox user agent"""
        ua = get_user_agent('firefox')
        assert 'Firefox' in ua
        assert 'Mozilla' in ua

    def test_get_edge_user_agent(self):
        """Test getting Edge user agent"""
        ua = get_user_agent('edge')
        assert 'Edg' in ua  # Edge uses 'Edg' not 'Edge'
        assert 'Chrome' in ua  # Edge is Chromium-based

    def test_get_safari_user_agent(self):
        """Test getting Safari user agent"""
        ua = get_user_agent('safari')
        assert 'Safari' in ua
        assert 'Macintosh' in ua

    def test_get_chrome_mac_user_agent(self):
        """Test getting Chrome on macOS user agent"""
        ua = get_user_agent('chrome-mac')
        assert 'Chrome' in ua
        assert 'Macintosh' in ua

    def test_get_chrome_linux_user_agent(self):
        """Test getting Chrome on Linux user agent"""
        ua = get_user_agent('chrome-linux')
        assert 'Chrome' in ua
        assert 'Linux' in ua or 'X11' in ua


class TestCaseInsensitivity:
    """Test that preset names are case-insensitive"""

    def test_uppercase_preset_name(self):
        """Test uppercase preset name"""
        ua_lower = get_user_agent('chrome')
        ua_upper = get_user_agent('CHROME')
        assert ua_lower == ua_upper

    def test_mixed_case_preset_name(self):
        """Test mixed case preset name"""
        ua_lower = get_user_agent('firefox')
        ua_mixed = get_user_agent('FireFox')
        assert ua_lower == ua_mixed


class TestErrorHandling:
    """Test error handling for invalid inputs"""

    def test_invalid_preset_raises_valueerror(self):
        """Test that invalid preset name raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            get_user_agent('invalid-browser-name')

        assert 'Unknown user agent preset' in str(exc_info.value)
        assert 'invalid-browser-name' in str(exc_info.value)

    def test_error_message_includes_available_presets(self):
        """Test that error message lists available presets"""
        with pytest.raises(ValueError) as exc_info:
            get_user_agent('nonexistent')

        error_msg = str(exc_info.value)
        assert 'Available presets:' in error_msg
        assert 'chrome' in error_msg
        assert 'firefox' in error_msg

    def test_empty_string_raises_valueerror(self):
        """Test that empty string raises ValueError"""
        with pytest.raises(ValueError):
            get_user_agent('')


class TestUserAgentQuality:
    """Test that user agent strings are valid and complete"""

    def test_all_presets_return_non_empty_strings(self):
        """Test that all presets return non-empty strings"""
        for preset in list_presets():
            ua = get_user_agent(preset)
            assert isinstance(ua, str)
            assert len(ua) > 0

    def test_all_user_agents_contain_mozilla(self):
        """Test that all user agents start with Mozilla"""
        for preset in list_presets():
            ua = get_user_agent(preset)
            assert ua.startswith('Mozilla/')

    def test_user_agents_have_reasonable_length(self):
        """Test that user agents are not suspiciously short or long"""
        for preset in list_presets():
            ua = get_user_agent(preset)
            # Typical user agents are 80-150 characters
            assert 50 < len(ua) < 300

    def test_user_agents_no_trailing_whitespace(self):
        """Test that user agents don't have trailing whitespace"""
        for preset in list_presets():
            ua = get_user_agent(preset)
            assert ua == ua.strip()
