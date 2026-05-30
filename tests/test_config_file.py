#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Tests for configuration file handling in __main__
~~~~~~~~~~~~~~~~~~~~~
Smart, Asynchronous Link Tester with Database backend (SALTED)
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2025: Released under the Apache License 2.0
"""

import pytest

from salted import Salted


class TestConfigFileHandling:
    """Test configuration file loading"""

    def test_no_config_file_uses_defaults(self, tmp_path, monkeypatch):
        """Test that when no config file exists, defaults are used"""
        # Change to a directory with no config file
        monkeypatch.chdir(tmp_path)

        checker = Salted()
        # Should use default values without raising errors (searchpath defaults to cwd)
        assert checker.searchpath is not None

    def test_config_file_with_invalid_section(self, tmp_path, monkeypatch):
        """Test that invalid section in config raises ValueError"""
        # Create a config file with invalid section
        config_file = tmp_path / "salted-linkcheck.ini"
        config_file.write_text("""
[INVALID_SECTION]
some_setting = value
""")

        monkeypatch.chdir(tmp_path)

        with pytest.raises(ValueError, match="unknown section"):
            Salted()

    def test_config_file_with_behavior_section(self, tmp_path, monkeypatch):
        """Test loading BEHAVIOR section from config"""
        config_file = tmp_path / "salted-linkcheck.ini"
        config_file.write_text("""
[BEHAVIOR]
num_workers = 10
timeout = 15
raise_for_dead_links = true
user_agent = chrome
domain_delay = 0.5
ignore_urls = http://example.com,http://test.com
""")

        monkeypatch.chdir(tmp_path)

        checker = Salted()
        # Config parser returns strings, not ints
        assert checker.num_workers == '10'
        assert checker.timeout == 15
        assert checker.raise_for_dead_links is True
        assert checker.user_agent == 'chrome'
        assert checker.domain_delay == 0.5
        assert 'http://example.com' in checker.ignore_urls
        assert 'http://test.com' in checker.ignore_urls

    def test_config_file_with_ignore_domains(self, tmp_path, monkeypatch):
        """Test loading ignore_domains from BEHAVIOR section."""
        config_file = tmp_path / "salted-linkcheck.ini"
        config_file.write_text("""
[BEHAVIOR]
ignore_domains = example.com,skip.org
""")
        monkeypatch.chdir(tmp_path)
        checker = Salted()
        assert 'example.com' in checker.ignore_domains
        assert 'skip.org' in checker.ignore_domains

    def test_config_file_ignore_domains_full_url_normalized(self, tmp_path, monkeypatch):
        """Full URLs in ignore_domains are normalized to bare hostnames."""
        config_file = tmp_path / "salted-linkcheck.ini"
        config_file.write_text("""
[BEHAVIOR]
ignore_domains = https://example.com/some/path,skip.org
""")
        monkeypatch.chdir(tmp_path)
        checker = Salted()
        assert 'example.com' in checker.ignore_domains
        assert 'skip.org' in checker.ignore_domains

    def test_config_file_with_cache_section(self, tmp_path, monkeypatch):
        """Test loading CACHE section from config"""
        config_file = tmp_path / "salted-linkcheck.ini"
        config_file.write_text("""
[CACHE]
cache_file = my-cache.db
dont_check_again_within_hours = 48
""")

        monkeypatch.chdir(tmp_path)

        checker = Salted()
        assert checker.cache_file == 'my-cache.db'
        assert checker.dont_check_again_within_hours == 48

    def test_config_file_with_files_section(self, tmp_path, monkeypatch):
        """Test loading FILES section from config"""
        config_file = tmp_path / "salted-linkcheck.ini"
        config_file.write_text("""
[FILES]
searchpath = /path/to/files
file_types = html
""")

        monkeypatch.chdir(tmp_path)

        checker = Salted()
        assert checker.searchpath == '/path/to/files'
        assert checker.file_types == 'html'

    def test_config_file_with_template_section(self, tmp_path, monkeypatch):
        """Test loading TEMPLATE section from config"""
        config_file = tmp_path / "salted-linkcheck.ini"
        config_file.write_text("""
[TEMPLATE]
template_searchpath = /path/to/templates
template_name = custom.jinja
write_to = report.md
base_url = http://example.com/
""")

        monkeypatch.chdir(tmp_path)

        checker = Salted()
        assert checker.template_searchpath == '/path/to/templates'
        assert checker.template_name == 'custom.jinja'
        assert checker.write_to == 'report.md'
        # Base URL still has slash at this point; stripped in check_parameters()
        assert checker.base_url == 'http://example.com/'
        # Call check_parameters to strip trailing slash
        checker.check_parameters()
        assert checker.base_url == 'http://example.com'

    def test_config_file_with_all_sections(self, tmp_path, monkeypatch):
        """Test loading config with all valid sections"""
        config_file = tmp_path / "salted-linkcheck.ini"
        config_file.write_text("""
[BEHAVIOR]
timeout = 10

[CACHE]
dont_check_again_within_hours = 12

[FILES]
file_types = markdown

[TEMPLATE]
base_url = http://test.com/docs/
""")

        monkeypatch.chdir(tmp_path)

        checker = Salted()
        assert checker.timeout == 10
        assert checker.dont_check_again_within_hours == 12
        assert checker.file_types == 'markdown'
        assert checker.base_url == 'http://test.com/docs/'
        # Call check_parameters to strip trailing slash
        checker.check_parameters()
        assert checker.base_url == 'http://test.com/docs'

    def test_base_url_stripping_in_check_parameters(self, tmp_path, monkeypatch):
        """Test that base_url has trailing slashes stripped"""
        config_file = tmp_path / "salted-linkcheck.ini"
        config_file.write_text("""
[TEMPLATE]
base_url = http://example.com///
""")

        monkeypatch.chdir(tmp_path)
        checker = Salted()
        assert checker.base_url == 'http://example.com///'
        checker.check_parameters()
        assert checker.base_url == 'http://example.com'

    def test_base_url_none_check_parameters(self):
        """Test check_parameters with no base_url"""
        checker = Salted()
        # Set base_url to None after initialization
        checker.base_url = None
        checker.check_parameters()
        assert checker.base_url is None

    def test_base_url_literal_none_string_coerced_to_unset(self, tmp_path, monkeypatch):
        """A config file with `base_url = None` must be treated as unset.

        ConfigParser returns the literal string "None"; check_parameters()
        coerces it to a real None so path rewriting stays off.
        """
        config_file = tmp_path / "salted-linkcheck.ini"
        config_file.write_text("""
[TEMPLATE]
base_url = None
""")
        monkeypatch.chdir(tmp_path)
        checker = Salted()
        # Parsed as the literal string before normalization.
        assert checker.base_url == 'None'
        checker.check_parameters()
        assert checker.base_url is None

    def test_base_url_empty_or_whitespace_coerced_to_unset(self):
        """An empty / whitespace base_url is treated as unset."""
        checker = Salted()
        checker.base_url = '   '
        checker.check_parameters()
        assert checker.base_url is None

    def test_base_url_real_value_preserved(self):
        """A genuine base_url survives the coercion (trailing slash stripped)."""
        checker = Salted()
        checker.base_url = 'https://example.com/'
        checker.check_parameters()
        assert checker.base_url == 'https://example.com'


class TestAlternativeConfigFilePath:
    """Test loading config from an explicit path via Salted(config_path=...)."""

    def test_explicit_config_path_is_loaded(self, tmp_path):
        """Settings from an explicitly provided config file are applied."""
        config_file = tmp_path / "custom.ini"
        config_file.write_text("[BEHAVIOR]\ntimeout = 42\n")

        checker = Salted(config_path=config_file)
        assert checker.timeout == 42

    def test_explicit_config_path_overrides_cwd_config(self, tmp_path, monkeypatch):
        """Explicit config_path takes precedence over salted-linkcheck.ini in cwd."""
        # Write a config in cwd that would be picked up by default
        cwd_config = tmp_path / "salted-linkcheck.ini"
        cwd_config.write_text("[BEHAVIOR]\ntimeout = 1\n")
        monkeypatch.chdir(tmp_path)

        # Write the explicit config elsewhere with a different value
        explicit_dir = tmp_path / "subdir"
        explicit_dir.mkdir()
        explicit_config = explicit_dir / "other.ini"
        explicit_config.write_text("[BEHAVIOR]\ntimeout = 99\n")

        checker = Salted(config_path=explicit_config)
        assert checker.timeout == 99

    def test_nonexistent_explicit_config_raises(self, tmp_path):
        """FileNotFoundError is raised when the given config path does not exist."""
        missing = tmp_path / "does_not_exist.ini"
        with pytest.raises(FileNotFoundError, match="does_not_exist.ini"):
            Salted(config_path=missing)

    def test_explicit_config_path_invalid_section_raises(self, tmp_path):
        """ValueError is raised for unknown sections in the explicit config."""
        config_file = tmp_path / "bad.ini"
        config_file.write_text("[UNKNOWN_SECTION]\nfoo = bar\n")
        with pytest.raises(ValueError, match="unknown section"):
            Salted(config_path=config_file)
