#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit Tests for Command Line Interface in SALTED
Tests the CLI argument parsing, parameter validation, and error handling.
This addresses the 0% coverage gap in command_line.py
"""

import pathlib
from unittest.mock import patch, MagicMock
import pytest

from salted import command_line


class TestCommandLineArguments:
    """Test CLI argument parsing and validation."""

    def test_main_no_arguments_uses_defaults(self):
        """Test that main() works with no arguments (uses defaults)."""
        test_args = ['salted']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                # Should create Salted instance and call check
                mock_salted_class.assert_called_once()
                mock_checker.check.assert_called_once()

    def test_main_with_searchpath_argument(self):
        """Test CLI with -i/--searchpath argument."""
        test_args = ['salted', '-i', './test-folder']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                # Should set searchpath on checker instance
                assert mock_checker.searchpath == pathlib.Path('./test-folder')

    def test_main_with_long_searchpath_argument(self):
        """Test CLI with --searchpath (long form) argument."""
        test_args = ['salted', '--searchpath', '/home/user/docs']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                assert mock_checker.searchpath == pathlib.Path('/home/user/docs')

    def test_main_with_file_types_argument(self):
        """Test CLI with --file_types argument."""
        test_cases = ['supported', 'html', 'tex', 'markdown']

        for file_type in test_cases:
            test_args = ['salted', '--file_types', file_type]

            with patch('sys.argv', test_args):
                with patch('salted.Salted') as mock_salted_class:
                    mock_checker = MagicMock()
                    mock_salted_class.return_value = mock_checker

                    command_line.main()

                    assert mock_checker.file_types == file_type

    def test_main_with_workers_argument(self):
        """Test CLI with -w/--num_workers argument."""
        test_args = ['salted', '-w', '16']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                assert mock_checker.num_workers == 16

    def test_main_with_timeout_argument(self):
        """Test CLI with --timeout argument."""
        test_args = ['salted', '--timeout', '30']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                assert mock_checker.timeout == 30

    def test_main_timeout_zero_is_rejected(self):
        """`--timeout 0` would disable the timeout and is rejected."""
        test_args = ['salted', '--timeout', '0']
        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_salted_class.return_value = MagicMock()
                with pytest.raises(SystemExit):
                    command_line.main()

    def test_main_dont_check_again_zero_is_honored(self):
        """`--dont_check_again_within_hours 0` (force recheck) is honored."""
        test_args = ['salted', '--dont_check_again_within_hours', '0']
        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                assert mock_checker.dont_check_again_within_hours == 0

    def test_main_num_workers_zero_is_rejected(self):
        """`-w 0` is invalid and exits with an error instead of hanging."""
        test_args = ['salted', '-w', '0']
        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_salted_class.return_value = MagicMock()
                with pytest.raises(SystemExit):
                    command_line.main()

    def test_main_negative_timeout_is_rejected(self):
        """`--timeout -1` is rejected by the central parameter rules."""
        test_args = ['salted', '--timeout', '-1']
        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_salted_class.return_value = MagicMock()
                with pytest.raises(SystemExit):
                    command_line.main()

    def test_main_negative_domain_delay_is_rejected(self):
        """`--domain_delay -1` is rejected instead of silently accepted."""
        test_args = ['salted', '--domain_delay', '-1']
        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_salted_class.return_value = MagicMock()
                with pytest.raises(SystemExit):
                    command_line.main()

    def test_main_max_file_size_zero_is_rejected(self):
        """`--max_file_size_mb 0` would skip every file and is rejected."""
        test_args = ['salted', '--max_file_size_mb', '0']
        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_salted_class.return_value = MagicMock()
                with pytest.raises(SystemExit):
                    command_line.main()

    def test_cli_error_message_names_the_option(self, capsys):
        """The error must say the bad value came from the command line."""
        test_args = ['salted', '--timeout', '-1']
        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_salted_class.return_value = MagicMock()
                with pytest.raises(SystemExit):
                    command_line.main()
        stderr = capsys.readouterr().err
        assert 'command line (--timeout)' in stderr

    def test_main_with_user_agent_argument(self):
        """Test CLI with --user_agent argument."""
        test_args = ['salted', '--user_agent', 'MyBot/1.0']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                assert mock_checker.user_agent == 'MyBot/1.0'

    def test_main_with_ignore_urls_argument(self):
        """Test CLI with --ignore_urls argument."""
        test_args = ['salted', '--ignore_urls', 'https://skip1.com,https://skip2.com']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                assert mock_checker.ignore_urls == {'https://skip1.com', 'https://skip2.com'}

    def test_main_with_ignore_domains_argument(self):
        """Test CLI with --ignore_domains argument."""
        test_args = ['salted', '--ignore_domains', 'example.com,skip.org']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_checker._validate_domains.return_value = {'example.com', 'skip.org'}
                mock_salted_class.return_value = mock_checker

                command_line.main()

                mock_checker._validate_domains.assert_called_once()
                assert mock_checker.ignore_domains == {'example.com', 'skip.org'}

    def test_main_with_ignore_urls_trims_and_drops_empty(self):
        """Test CLI cleaning of --ignore_urls (trims whitespace, drops empties)."""
        test_args = ['salted', '--ignore_urls', ' https://a.com , , https://b.com  , ']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                assert mock_checker.ignore_urls == {'https://a.com', 'https://b.com'}

    def test_main_with_cache_file_argument(self):
        """Test CLI with --cache_file argument."""
        test_args = ['salted', '--cache_file', './my-cache.sqlite3']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                assert mock_checker.cache_file == pathlib.Path('./my-cache.sqlite3')

    def test_main_with_cache_hours_argument(self):
        """Test CLI with --dont_check_again_within_hours argument."""
        test_args = ['salted', '--dont_check_again_within_hours', '48']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                assert mock_checker.dont_check_again_within_hours == 48


class TestRaiseForDeadLinksParameter:
    """Test --raise_for_dead_links / --no-raise_for_dead_links flags."""

    def test_raise_for_dead_links_flag_sets_true(self):
        """--raise_for_dead_links sets the flag to True."""
        test_args = ['salted', '--raise_for_dead_links']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                assert mock_checker.raise_for_dead_links is True

    def test_no_raise_for_dead_links_flag_sets_false(self):
        """--no-raise_for_dead_links explicitly sets the flag to False."""
        test_args = ['salted', '--no-raise_for_dead_links']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                assert mock_checker.raise_for_dead_links is False

    def test_raise_for_dead_links_absent_leaves_default(self):
        """When the flag is omitted, raise_for_dead_links is not overwritten."""
        test_args = ['salted']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_checker.raise_for_dead_links = False  # default
                mock_salted_class.return_value = mock_checker

                command_line.main()

                # Attribute must not have been overwritten
                assert mock_checker.raise_for_dead_links is False

    def test_main_with_domain_delay_argument(self):
        """Test CLI with --domain_delay argument."""
        test_args = ['salted', '--domain_delay', '0.5']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                assert mock_checker.domain_delay == 0.5


class TestTemplateArguments:
    """Test template-related CLI arguments."""

    def test_main_with_template_searchpath(self):
        """Test CLI with --template_searchpath argument."""
        test_args = ['salted', '--template_searchpath', './my-templates']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                assert mock_checker.template_searchpath == pathlib.Path('./my-templates')

    def test_main_with_template_name(self):
        """Test CLI with --template_name argument."""
        test_args = ['salted', '--template_name', 'custom.md.jinja']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                assert mock_checker.template_name == 'custom.md.jinja'

    def test_main_with_write_to_argument(self):
        """Test CLI with --write_to argument."""
        test_args = ['salted', '--write_to', './report.md']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                assert mock_checker.write_to == './report.md'

    def test_main_with_base_url_argument(self):
        """Test CLI with --base_url argument."""
        test_args = ['salted', '--base_url', 'https://www.example.com']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                assert mock_checker.base_url == 'https://www.example.com'


class TestCombinedArguments:
    """Test combinations of CLI arguments."""

    def test_main_with_multiple_arguments(self):
        """Test CLI with multiple arguments combined."""
        test_args = [
            'salted',
            '-i', './docs',
            '--file_types', 'markdown',
            '-w', '8',
            '--timeout', '10',
            '--user_agent', 'TestBot/1.0',
            '--raise_for_dead_links',
            '--write_to', 'cli'
        ]

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                # Verify all parameters were set correctly
                assert mock_checker.searchpath == pathlib.Path('./docs')
                assert mock_checker.file_types == 'markdown'
                assert mock_checker.num_workers == 8
                assert mock_checker.timeout == 10
                assert mock_checker.user_agent == 'TestBot/1.0'
                assert mock_checker.raise_for_dead_links is True
                assert mock_checker.write_to == 'cli'

    def test_main_argument_override_precedence(self):
        """Test that CLI arguments override defaults properly."""
        test_args = ['salted', '--timeout', '99']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                # Set a default value
                mock_checker.timeout = 5
                mock_salted_class.return_value = mock_checker

                command_line.main()

                # CLI argument should override default
                assert mock_checker.timeout == 99


class TestArgumentParsingEdgeCases:
    """Test edge cases and error scenarios in argument parsing."""

    def test_help_argument_exits_cleanly(self):
        """Test that --help exits before the Salted instance is created."""
        test_args = ['salted', '--help']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                # argparse calls sys.exit() during parse_args(), before Salted() is created
                with pytest.raises(SystemExit):
                    command_line.main()

                mock_salted_class.assert_not_called()
                mock_checker.check.assert_not_called()

    def test_invalid_file_types_argument(self):
        """Test CLI with invalid --file_types argument."""
        test_args = ['salted', '--file_types', 'invalid_type']

        with patch('sys.argv', test_args):
            # argparse should raise SystemExit for invalid choice
            with pytest.raises(SystemExit):
                command_line.main()

    def test_non_numeric_workers_argument(self):
        """Test CLI with non-numeric --num_workers argument."""
        test_args = ['salted', '--num_workers', 'not-a-number']

        with patch('sys.argv', test_args):
            # argparse should raise SystemExit for invalid int
            with pytest.raises(SystemExit):
                command_line.main()

    def test_non_numeric_timeout_argument(self):
        """Test CLI with non-numeric --timeout argument."""
        test_args = ['salted', '--timeout', 'not-a-number']

        with patch('sys.argv', test_args):
            # argparse should raise SystemExit for invalid int
            with pytest.raises(SystemExit):
                command_line.main()


class TestParameterTypesAndConversion:
    """Test that CLI arguments are converted to correct types."""

    def test_pathlib_path_conversion(self):
        """Test that path arguments are converted to pathlib.Path objects."""
        test_args = ['salted', '-i', './test', '--cache_file', './cache.db']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                # Should be pathlib.Path objects, not strings
                assert isinstance(mock_checker.searchpath, pathlib.Path)
                assert isinstance(mock_checker.cache_file, pathlib.Path)

    def test_integer_conversion(self):
        """Test that numeric arguments are converted to integers."""
        test_args = ['salted', '--num_workers', '42', '--timeout', '15']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                # Should be integers, not strings
                assert isinstance(mock_checker.num_workers, int)
                assert isinstance(mock_checker.timeout, int)
                assert mock_checker.num_workers == 42
                assert mock_checker.timeout == 15


class TestCheckerExecution:
    """Test that the checker.check() method is called properly."""

    def test_checker_called_with_searchpath(self):
        """Test that checker.check() is called with the searchpath."""
        test_args = ['salted', '-i', './my-docs']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_checker.searchpath = pathlib.Path('./my-docs')
                mock_salted_class.return_value = mock_checker

                command_line.main()

                # Should call check with the configured searchpath
                mock_checker.check.assert_called_once_with(mock_checker.searchpath)

    def test_checker_exceptions_propagate(self):
        """Test that exceptions from checker.check() are not caught."""
        test_args = ['salted']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_checker.check.side_effect = RuntimeError("Test error")
                mock_salted_class.return_value = mock_checker

                # Exception should propagate up
                with pytest.raises(RuntimeError, match="Test error"):
                    command_line.main()


class TestQuietMode:
    """Test --quiet / -q flag."""

    def test_quiet_flag_long(self):
        """Test that --quiet sets quiet=True on the checker."""
        test_args = ['salted', '--quiet']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                assert mock_checker.quiet is True

    def test_quiet_flag_short(self):
        """Test that -q sets quiet=True on the checker."""
        test_args = ['salted', '-q']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                assert mock_checker.quiet is True

    def test_quiet_not_set_by_default(self):
        """Test that quiet is not set when flag is absent."""
        test_args = ['salted']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                # quiet should not be set on the checker
                assert mock_checker.quiet != True  # noqa: E712


class TestConfigArgument:
    """Test --config argument for alternative config file path."""

    def test_config_argument_passed_to_salted(self, tmp_path):
        """--config passes the path to Salted() as config_path."""
        config_file = tmp_path / "my.ini"
        config_file.write_text("[BEHAVIOR]\ntimeout = 99\n")
        test_args = ['salted', '--config', str(config_file)]

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                mock_salted_class.assert_called_once_with(config_path=config_file)

    def test_no_config_argument_passes_none(self):
        """Without --config, Salted() is called with config_path=None."""
        test_args = ['salted']

        with patch('sys.argv', test_args):
            with patch('salted.Salted') as mock_salted_class:
                mock_checker = MagicMock()
                mock_salted_class.return_value = mock_checker

                command_line.main()

                mock_salted_class.assert_called_once_with(config_path=None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
