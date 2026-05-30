#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for path handling edge cases, particularly Windows-specific issues.
"""

import subprocess
import sys
from unittest.mock import patch, MagicMock

from salted import command_line
import salted


class TestPathQuoteStripping:
    """Test that paths with preserved quotes are handled correctly."""

    def test_path_with_trailing_quote(self, tmp_path):
        """Test path with trailing quote due to backslash escaping on Windows."""
        # Create a test file
        test_file = tmp_path / "test.html"
        test_file.write_text('<html><body><a href="https://example.com">Link</a></body></html>')

        # Simulate what happens when user types: "C:\path\" on Windows
        # The trailing backslash escapes the quote, so it becomes: C:\path\"
        path_with_quote = str(tmp_path) + '"'

        test_args = ['salted', '-i', path_with_quote]

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                # Should strip the quote and use the correct path
                assert mock_checker.searchpath == tmp_path
                # The quote should be stripped
                assert '"' not in str(mock_checker.searchpath)

    def test_path_with_single_quotes(self, tmp_path):
        """Test path with single quotes is stripped."""
        test_file = tmp_path / "test.html"
        test_file.write_text('<html><body><a href="https://example.com">Link</a></body></html>')

        path_with_quote = f"'{str(tmp_path)}'"

        test_args = ['salted', '-i', path_with_quote]

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                # Should strip single quotes
                assert "'" not in str(mock_checker.searchpath)

    def test_check_method_strips_quotes_from_string(self, tmp_path):
        """Test that the check() method itself also strips quotes."""
        test_file = tmp_path / "test.html"
        test_file.write_text('<html><body><a href="https://example.com">Link</a></body></html>')

        checker = salted.Salted()

        # Pass path with trailing quote as string
        path_with_quote = str(tmp_path) + '"'

        # Should not raise FileNotFoundError
        checker.check(path_with_quote)

    def test_check_method_with_pathlib_path(self, tmp_path):
        """Test that check() works with pathlib.Path objects (no quote stripping needed)."""
        test_file = tmp_path / "test.html"
        test_file.write_text('<html><body><a href="https://example.com">Link</a></body></html>')

        checker = salted.Salted()

        # Pass as pathlib.Path object
        checker.check(tmp_path)

        # Should work without issues

    def test_normal_path_without_quotes(self, tmp_path):
        """Test that normal paths without quotes still work."""
        test_file = tmp_path / "test.html"
        test_file.write_text('<html><body><a href="https://example.com">Link</a></body></html>')

        test_args = ['salted', '-i', str(tmp_path)]

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                # Should work normally
                assert mock_checker.searchpath == tmp_path


class TestPathNormalization:
    """Test path normalization in various scenarios."""

    def test_subprocess_with_trailing_backslash_quote(self, tmp_path):
        """Integration test: python -m salted with path containing trailing quote."""
        test_file = tmp_path / "page.html"
        test_file.write_text('<html><body><a href="https://google.com">Link</a></body></html>')

        # Simulate the problematic case
        path_with_quote = str(tmp_path) + '"'

        result = subprocess.run(
            [sys.executable, '-c',
             f'import sys; sys.argv = ["salted", "-i", r\'{path_with_quote}\']; '
             f'from salted.command_line import main; main()'],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should succeed, not fail with FileNotFoundError
        assert result.returncode == 0
        assert 'RESULTS' in result.stdout
        assert 'does not exist' not in result.stderr.lower()
