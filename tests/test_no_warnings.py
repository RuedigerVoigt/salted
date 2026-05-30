#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests to ensure no Python warnings are raised during normal usage.
"""

import subprocess
import sys


class TestNoWarnings:
    """Test that the package doesn't raise Python warnings."""

    def test_no_syntax_warning_on_import(self):
        """Test that importing salted doesn't raise SyntaxWarning."""
        # Run in subprocess to capture warnings
        result = subprocess.run(
            [sys.executable, '-W', 'error::SyntaxWarning', '-c',
             'from salted import Salted; print("OK")'],
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should succeed without SyntaxWarning
        assert result.returncode == 0, f"SyntaxWarning detected: {result.stderr}"
        assert 'OK' in result.stdout

    def test_no_syntax_warning_on_module_run(self):
        """Test that python -m salted doesn't raise SyntaxWarning."""
        result = subprocess.run(
            [sys.executable, '-W', 'error::SyntaxWarning', '-m', 'salted', '--help'],
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should succeed without SyntaxWarning
        assert result.returncode == 0, f"SyntaxWarning detected: {result.stderr}"
        assert 'Salted' in result.stdout

    def test_no_return_in_finally_warning(self):
        """Test that the specific 'return in finally' warning is fixed."""
        # This warning was in input_handler.py line 65
        result = subprocess.run(
            [sys.executable, '-W', 'error::SyntaxWarning', '-c',
             'from salted.input_handler import InputHandler; print("OK")'],
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should succeed
        assert result.returncode == 0, f"SyntaxWarning in InputHandler: {result.stderr}"
        assert 'OK' in result.stdout
