#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Predefined User Agent Strings
~~~~~~~~~~~~~~~~~~~~~
Smart, Asynchronous Link Tester with Database backend (SALTED)
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026 Rüdiger Voigt and contributors
Released under the Apache License 2.0
"""

# Predefined user agent strings to help avoid basic bot detection.
# REFRESH PERIODICALLY: a years-old browser version is itself a bot signal.
# Last refreshed: 2026-05 (Chrome/Edge 142, Firefox 144, Safari 18.3).
USER_AGENTS = {
    'chrome': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
    'firefox': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0',
    'edge': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0',
    'safari': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 15_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15',
    'chrome-mac': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
    'chrome-linux': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
}


def get_user_agent(preset: str) -> str:
    """
    Get a predefined user agent string by preset name.

    Args:
        preset: Name of the preset (e.g., 'chrome', 'firefox', 'edge', 'safari')

    Returns:
        User agent string for the specified preset

    Raises:
        ValueError: If preset name is not recognized
    """
    if preset.lower() not in USER_AGENTS:
        available = ', '.join(USER_AGENTS.keys())
        raise ValueError(
            f"Unknown user agent preset: '{preset}'. "
            f"Available presets: {available}"
        )
    return USER_AGENTS[preset.lower()]


def list_presets() -> list:
    """
    Get a list of available user agent preset names.

    Returns:
        List of preset names
    """
    return list(USER_AGENTS.keys())
