#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for python -m salted entry point
Tests that __main__.py correctly invokes the CLI when run as a module.
"""

import subprocess
import sys


class TestModuleEntryPoint:
    """Test that python -m salted works correctly."""

    def test_python_m_salted_help(self):
        """Test that python -m salted --help produces output."""
        result = subprocess.run(
            [sys.executable, '-m', 'salted', '--help'],
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should exit successfully
        assert result.returncode == 0

        # Should contain help text
        assert 'Salted is an extremely fast link checker' in result.stdout
        assert 'usage:' in result.stdout or 'Usage:' in result.stdout

    def test_python_m_salted_version_in_help(self):
        """Test that version information appears in help output."""
        result = subprocess.run(
            [sys.executable, '-m', 'salted', '--help'],
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should mention version in help text
        assert 'version' in result.stdout.lower()

    def test_python_m_salted_runs_check(self, tmp_path):
        """Test that python -m salted actually runs link checking."""
        # Create a test HTML file with a known link
        test_file = tmp_path / "test.html"
        test_file.write_text("""
            <!DOCTYPE html>
            <html>
            <head><title>Test</title></head>
            <body>
                <a href="https://www.google.com">Google</a>
            </body>
            </html>
        """)

        result = subprocess.run(
            [sys.executable, '-m', 'salted', '-i', str(test_file)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should exit successfully (even if links fail, it shouldn't crash)
        # unless --raise_for_dead_links is set
        assert result.returncode == 0

        # Should produce results output
        assert 'RESULTS' in result.stdout
        assert 'hyperlinks' in result.stdout.lower() or 'links' in result.stdout.lower()

    def test_python_m_salted_with_directory(self, tmp_path):
        """Test that python -m salted works with a directory path."""
        # Create test directory with HTML file
        test_dir = tmp_path / "docs"
        test_dir.mkdir()
        test_file = test_dir / "page.html"
        test_file.write_text("""
            <!DOCTYPE html>
            <html>
            <body><a href="https://example.com">Link</a></body>
            </html>
        """)

        result = subprocess.run(
            [sys.executable, '-m', 'salted', '-i', str(test_dir)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should exit successfully
        assert result.returncode == 0

        # Should produce results
        assert 'RESULTS' in result.stdout

    def test_python_m_salted_nonexistent_path(self):
        """Test that python -m salted handles nonexistent paths gracefully."""
        result = subprocess.run(
            [sys.executable, '-m', 'salted', '-i', '/nonexistent/path/to/nowhere'],
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should exit with error
        assert result.returncode != 0

        # Should mention the error (in stdout or stderr)
        output = result.stdout + result.stderr
        assert 'does not exist' in output.lower() or 'not found' in output.lower()
