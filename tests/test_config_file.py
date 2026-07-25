#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Tests for configuration file handling in __main__
~~~~~~~~~~~~~~~~~~~~~
Smart, Asynchronous Link Tester with Database backend (SALTED)
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2025: Released under the Apache License 2.0
"""

import pathlib

import pytest

from salted import Salted
from salted.err import ConfigFileError


class TestAutodiscoveredConfigPathJail:
    """A config file merely found in the CWD may not reach outside it.

    Such a file can ship with the content being checked, so the paths it
    sets are confined to its own folder. Without that, it could point
    template_searchpath at any readable directory (Jinja2 renders a file
    without template syntax as its own content) or write_to / cache_file
    at any writable location.
    """

    @staticmethod
    def _write_config(folder, body):
        (folder / "salted-linkcheck.ini").write_text(body, encoding='utf-8')

    @pytest.mark.parametrize('key, section', [
        ('template_searchpath', 'TEMPLATE'),
        ('write_to', 'TEMPLATE'),
        ('cache_file', 'CACHE'),
    ])
    def test_path_outside_the_config_folder_is_refused(
            self, tmp_path, monkeypatch, key, section):
        """Each path-valued key is confined to the config file's folder."""
        outside = tmp_path.parent / "elsewhere"
        outside.mkdir(exist_ok=True)
        work = tmp_path / "work"
        work.mkdir()
        self._write_config(work, f"[{section}]\n{key} = {outside}\n")
        monkeypatch.chdir(work)

        checker = Salted()
        with pytest.raises(ConfigFileError, match='points outside'):
            checker.check_parameters()

    @pytest.mark.parametrize('key, section', [
        ('template_searchpath', 'TEMPLATE'),
        ('write_to', 'TEMPLATE'),
        ('cache_file', 'CACHE'),
    ])
    def test_path_inside_the_config_folder_is_allowed(
            self, tmp_path, monkeypatch, key, section):
        """A repo may still point at its own files."""
        self._write_config(tmp_path, f"[{section}]\n{key} = local/thing\n")
        monkeypatch.chdir(tmp_path)

        checker = Salted()
        checker.check_parameters()
        assert getattr(checker, key) == 'local/thing'

    def test_write_to_cli_is_not_treated_as_a_path(self, tmp_path, monkeypatch):
        """'cli' means stdout and must not be resolved as a filesystem path."""
        self._write_config(tmp_path, "[TEMPLATE]\nwrite_to = cli\n")
        monkeypatch.chdir(tmp_path)

        checker = Salted()
        checker.check_parameters()
        assert checker.write_to == 'cli'

    def test_explicit_config_is_trusted(self, tmp_path, monkeypatch):
        """Naming a config with --config opts into it, so it is unrestricted."""
        outside = tmp_path.parent / "elsewhere"
        outside.mkdir(exist_ok=True)
        cfg = tmp_path / "explicit.ini"
        cfg.write_text(f"[CACHE]\ncache_file = {outside / 'c.sqlite3'}\n",
                       encoding='utf-8')
        monkeypatch.chdir(tmp_path)

        checker = Salted(config_path=cfg)
        checker.check_parameters()
        assert str(outside) in str(checker.cache_file)

    def test_overriding_the_value_lifts_the_restriction(
            self, tmp_path, monkeypatch):
        """An operator override is deliberate, whatever the config said.

        This is the library API: attributes are assigned directly, with no
        command line involved.
        """
        outside = tmp_path.parent / "elsewhere"
        outside.mkdir(exist_ok=True)
        work = tmp_path / "work"
        work.mkdir()
        self._write_config(work, f"[CACHE]\ncache_file = {outside}\n")
        monkeypatch.chdir(work)

        checker = Salted()
        checker.cache_file = str(outside / "chosen.sqlite3")
        checker.check_parameters()
        assert checker.cache_file == str(outside / "chosen.sqlite3")

    def test_untouched_defaults_are_not_restricted(self, tmp_path, monkeypatch):
        """Only keys the config file actually sets are confined."""
        self._write_config(tmp_path, "[BEHAVIOR]\ntimeout = 7\n")
        monkeypatch.chdir(tmp_path)

        checker = Salted()
        checker.cache_file = "/somewhere/else/cache.sqlite3"
        checker.check_parameters()
        assert checker.timeout == 7


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
        """Test that invalid section in config raises ConfigFileError"""
        # Create a config file with invalid section
        config_file = tmp_path / "salted-linkcheck.ini"
        config_file.write_text("""
[INVALID_SECTION]
some_setting = value
""")

        monkeypatch.chdir(tmp_path)

        with pytest.raises(ConfigFileError, match="unknown section"):
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
        # num_workers is validated and converted to int
        assert checker.num_workers == 10
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
        # Paths stay inside the config file's own folder: a config that was
        # merely found in the working directory may not reach outside it.
        config_file.write_text("""
[TEMPLATE]
template_searchpath = templates
template_name = custom.jinja
write_to = report.md
base_url = http://example.com/
""")

        monkeypatch.chdir(tmp_path)

        checker = Salted()
        assert checker.template_searchpath == 'templates'
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


class TestConfigNumWorkersValidation:
    """Validate num_workers from a config file.

    Regression tests: num_workers = 0 used to pass through unvalidated,
    spawn zero workers, and hang forever on queue.join(). The CLI rejected
    such values; the config file path must do the same.
    """

    @staticmethod
    def _write_config(tmp_path, value):
        config_file = tmp_path / "salted-linkcheck.ini"
        config_file.write_text(f"[BEHAVIOR]\nnum_workers = {value}\n")

    def test_num_workers_zero_raises(self, tmp_path, monkeypatch):
        """num_workers = 0 must fail loudly instead of hanging the run."""
        self._write_config(tmp_path, '0')
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigFileError, match="num_workers"):
            Salted()

    def test_num_workers_negative_raises(self, tmp_path, monkeypatch):
        """A negative num_workers must fail loudly instead of hanging."""
        self._write_config(tmp_path, '-3')
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigFileError, match="num_workers"):
            Salted()

    def test_num_workers_non_numeric_raises(self, tmp_path, monkeypatch):
        """A non-numeric num_workers must raise ConfigFileError, not ValueError mid-run."""
        self._write_config(tmp_path, 'abc')
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigFileError, match="num_workers"):
            Salted()

    def test_num_workers_empty_raises(self, tmp_path, monkeypatch):
        """An empty num_workers value must raise ConfigFileError."""
        self._write_config(tmp_path, '')
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigFileError, match="num_workers"):
            Salted()

    def test_num_workers_automatic_accepted(self, tmp_path, monkeypatch):
        """The literal 'automatic' is accepted (case-insensitive)."""
        self._write_config(tmp_path, 'Automatic')
        monkeypatch.chdir(tmp_path)
        checker = Salted()
        assert checker.num_workers == 'automatic'

    def test_num_workers_positive_int_accepted(self, tmp_path, monkeypatch):
        """A positive integer is accepted and converted to int."""
        self._write_config(tmp_path, '32')
        monkeypatch.chdir(tmp_path)
        checker = Salted()
        assert checker.num_workers == 32

    def test_num_workers_absent_keeps_default(self, tmp_path, monkeypatch):
        """Without a num_workers key the default 'automatic' is kept."""
        config_file = tmp_path / "salted-linkcheck.ini"
        config_file.write_text("[BEHAVIOR]\ntimeout = 5\n")
        monkeypatch.chdir(tmp_path)
        checker = Salted()
        assert checker.num_workers == 'automatic'


class TestConfigTypedValueValidation:
    """Typed config values go through the central parameter rules.

    Regression tests: malformed values used to raise a bare ValueError
    traceback from the configparser getters, and out-of-range values were
    accepted silently (e.g. a negative cache lifetime disabled the cache
    without any message).
    """

    @staticmethod
    def _write_config(tmp_path, section, line):
        config_file = tmp_path / "salted-linkcheck.ini"
        config_file.write_text(f"[{section}]\n{line}\n")

    @pytest.mark.parametrize('section,line,key', [
        ('BEHAVIOR', 'timeout = five', 'timeout'),
        ('BEHAVIOR', 'timeout = -1', 'timeout'),
        ('BEHAVIOR', 'timeout = 0', 'timeout'),
        ('BEHAVIOR', 'raise_for_dead_links = maybe', 'raise_for_dead_links'),
        ('BEHAVIOR', 'check_dois = maybe', 'check_dois'),
        ('BEHAVIOR', 'domain_delay = fast', 'domain_delay'),
        ('BEHAVIOR', 'domain_delay = -0.5', 'domain_delay'),
        ('BEHAVIOR', 'max_file_size_mb = 0', 'max_file_size_mb'),
        ('CACHE', 'dont_check_again_within_hours = -24',
         'dont_check_again_within_hours'),
        ('FILES', 'file_types = htlm', 'file_types'),
    ])
    def test_invalid_value_raises_configfileerror(
            self, tmp_path, monkeypatch, section, line, key):
        """Invalid values raise ConfigFileError naming the parameter."""
        self._write_config(tmp_path, section, line)
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigFileError, match=key):
            Salted()

    def test_error_message_names_the_config_file(self, tmp_path, monkeypatch):
        """The message must point at the config file as the place to fix."""
        self._write_config(tmp_path, 'BEHAVIOR', 'timeout = five')
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigFileError, match='config file'):
            Salted()

    def test_boolean_spellings_accepted(self, tmp_path, monkeypatch):
        """ConfigParser-style boolean spellings keep working."""
        self._write_config(tmp_path, 'BEHAVIOR', 'raise_for_dead_links = yes')
        monkeypatch.chdir(tmp_path)
        checker = Salted()
        assert checker.raise_for_dead_links is True

    def test_valid_typed_values_accepted(self, tmp_path, monkeypatch):
        """Valid values are converted to their proper types."""
        config_file = tmp_path / "salted-linkcheck.ini"
        config_file.write_text(
            "[BEHAVIOR]\ntimeout = 1\ndomain_delay = 0.5\n"
            "max_file_size_mb = 5\n"
            "[CACHE]\ndont_check_again_within_hours = 0\n"
            "[FILES]\nfile_types = HTML\n")
        monkeypatch.chdir(tmp_path)
        checker = Salted()
        assert checker.timeout == 1
        assert checker.domain_delay == 0.5
        assert checker.max_file_size_mb == 5
        assert checker.dont_check_again_within_hours == 0
        assert checker.file_types == 'html'


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
        """ConfigFileError is raised when the given config path does not exist."""
        missing = tmp_path / "does_not_exist.ini"
        with pytest.raises(ConfigFileError, match="not found"):
            Salted(config_path=missing)

    def test_explicit_config_path_invalid_section_raises(self, tmp_path):
        """ConfigFileError is raised for unknown sections in the explicit config."""
        config_file = tmp_path / "bad.ini"
        config_file.write_text("[UNKNOWN_SECTION]\nfoo = bar\n")
        with pytest.raises(ConfigFileError, match="unknown section"):
            Salted(config_path=config_file)

    def test_corrupted_explicit_config_raises(self, tmp_path):
        """A malformed explicit config (no section header) stops with an error."""
        config_file = tmp_path / "broken.ini"
        config_file.write_text("this line has no section header\n")
        with pytest.raises(ConfigFileError, match="corrupted"):
            Salted(config_path=config_file)

    def test_corrupted_default_config_raises(self, tmp_path, monkeypatch):
        """A malformed config found in the working directory stops with an error."""
        config_file = tmp_path / "salted-linkcheck.ini"
        config_file.write_text("garbage without a section header\n")
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigFileError, match="corrupted"):
            Salted()

    def test_unreadable_explicit_config_raises(self, tmp_path, monkeypatch):
        """An explicit config that exists but cannot be read stops with an error.

        Permission semantics differ across platforms, so the read failure is
        simulated by making read_text raise PermissionError.
        """
        config_file = tmp_path / "locked.ini"
        config_file.write_text("[BEHAVIOR]\ntimeout = 5\n")

        original_read_text = pathlib.Path.read_text

        def deny(self, *args, **kwargs):
            if self == config_file:
                raise PermissionError("permission denied")
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr(pathlib.Path, "read_text", deny)
        with pytest.raises(ConfigFileError, match="could not be read"):
            Salted(config_path=config_file)
