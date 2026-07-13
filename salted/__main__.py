#!/usr/bin/python3

"""
Smart, Asynchronous Link Tester with Database backend (SALTED)
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026 Rüdiger Voigt and contributors
Released under the Apache License 2.0
"""

import configparser
import datetime
import logging
import pathlib
import time
from collections import Counter
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from typing import Any

import compatibility
from userprovided import err as user_err
from userprovided import url as user_url
from userprovided.parameters import separated_string_to_set

from salted import (
    cache_reader,
    database_io,
    doi_check,
    err,
    file_finder,
    input_handler,
    internal_link_check,
    memory_instance,
    parameter_rules,
    report_generator,
    url_check,
)


def _normalize_url_set(raw: set[str] | None) -> set[str]:
    """Return a set of URLs in a normalized form suitable for matching.

    Normalization ensures entries in ignore lists match the same canonical
    form used when queueing URLs for checks.
    """
    if not raw:
        return set()
    normalized: set[str] = set()
    for u in raw:
        try:
            normalized.add(user_url.normalize_url(u))
        except user_err.QueryKeyConflict:
            normalized.add(user_url.normalize_url(u, do_not_change_query_part=True))
        except Exception:
            # If normalization fails unexpectedly, keep original entry
            normalized.add(u)
    return normalized


class Salted:
    """Main class for the SALTED link checker.

    Creates the other objects, starts workers, collects results and
    generates the report of results.
    """
    # pylint: disable=too-few-public-methods
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-instance-attributes

    try:
        VERSION = pkg_version("salted")
    except PackageNotFoundError:
        VERSION = "unknown"
    CONFIG_NAME = 'salted-linkcheck.ini'
    # Release date kept for compatibility dependency, not exposed
    RELEASE_DATE = datetime.date(2026, 4, 7)

    def __init__(self, config_path: pathlib.Path | None = None) -> None:

        compatibility.Check(
            package_name='salted',
            package_version=self.VERSION,
            release_date=self.RELEASE_DATE,
            python_version_support={
                'min_version': '3.11',
                'incompatible_versions': ['3.6', '3.7', '3.8', '3.9', '3.10'],
                'max_tested_version': '3.14'},
            nag_over_update={
                    'nag_days_after_release': 365,
                    'nag_in_hundred': 10},
            language_messages='en',
            system_support={'full': {'Linux', 'MacOS', 'Windows'}}
            )

        # #################### Application defaults ####################
        # Files
        self.searchpath: str | pathlib.Path = pathlib.Path.cwd()
        self.file_types: str = 'supported'
        # Behavior
        self.num_workers: int | str = 'automatic'
        self.timeout: int = 5
        self.raise_for_dead_links = False
        self.user_agent = f"salted/{self.VERSION}"
        self.ignore_urls: set = set()
        self.ignore_domains: set = set()
        self.domain_delay: float = 0.25
        self.mailto: str | None = None
        self.check_dois: bool = True
        self.check_internal_links: bool = True
        self.max_file_size_mb: int = 20
        # Cache
        self.cache_file: pathlib.Path | str = 'salted-cache.sqlite3'
        self.dont_check_again_within_hours: int = 24
        # Template
        self.template_searchpath: str = 'salted/templates'
        self.template_name: str = 'default.cli.jinja'
        self.write_to: str | pathlib.Path = 'cli'
        self.base_url: str | None = None
        self.quiet: bool = False

        # If there is a configfile, overwrite defaults with those settings
        self.__parse_configfile(config_path)

        self.cnt: Counter = Counter()

    @staticmethod
    def _validate_domains(raw: set[str] | None) -> set[str]:
        """Normalize and validate domain entries, returning only valid hostnames.

        Accepts plain hostnames (e.g. 'example.com') or full URLs
        (e.g. 'https://example.com/path') — extract_domain normalizes both
        to bare hostnames. Entries that cannot be parsed are logged as
        warnings and dropped.
        """
        if not raw:
            return set()
        valid: set[str] = set()
        for entry in raw:
            entry = entry.strip()
            if not entry:
                continue
            try:
                url_to_parse = entry if '://' in entry else f'https://{entry}'
                domain = user_url.extract_domain(url_to_parse)
                valid.add(domain)
            except ValueError:
                logging.warning("'%s' is not a valid domain — ignored.", entry)
        return valid

    def _from_config(self,
                     section: configparser.SectionProxy,
                     key: str,
                     target: pathlib.Path) -> Any:
        """Read a value from a config file section and validate it.

        Validation uses the central rules in parameter_rules, so the same
        checks apply to a value no matter whether it was set on the command
        line or in a config file.

        Args:
            section: The config file section to read from.
            key: The option name, which is also the attribute name.
            target: Path to the config file, used in error messages.

        Returns:
            The validated value, or the current default if the key is absent.

        Raises:
            err.ConfigFileError: If the value violates the parameter rules.
        """
        raw = section.get(key)
        if raw is None:
            return getattr(self, key)
        try:
            return parameter_rules.validate(
                key, raw, f"in config file {target}")
        except ValueError as exc:
            logging.error(str(exc))
            raise err.ConfigFileError(str(exc)) from exc

    def __parse_configfile(self, config_path: pathlib.Path | None = None) -> None:
        """Parse configuration file and overwrite defaults with its settings.

        Reads the config file (if present) and overwrites default values with
        configured values. If a specific parameter is not set in the config,
        falls back to the application default. Config file settings can be
        overwritten through CLI parameters.

        Args:
            config_path: Explicit path to a config file. If None, looks for
                CONFIG_NAME in the current working directory.

        Raises:
            err.ConfigFileError: If an explicitly provided config file is
                missing, cannot be read (e.g. a permission error), or is
                corrupted; or if any config file that is found contains an
                unknown section or is not valid INI. A missing default config
                file (none provided, none in the working directory) is not an
                error — defaults are used.
        """
        cfg = configparser.ConfigParser()

        if config_path is not None:
            # The user explicitly asked for this file. Any problem using it
            # must stop salted with a clear message rather than silently
            # falling back to defaults.
            config_path = pathlib.Path(config_path)
            if not config_path.is_file():
                msg = (f"Config file not found: {config_path} - check the path "
                       "passed via --config (or config_path).")
                logging.error(msg)
                raise err.ConfigFileError(msg)
            target = config_path
        else:
            # No explicit path: look for the default in the working directory.
            # Its absence is fine — fall back to defaults.
            default = pathlib.Path(self.CONFIG_NAME)
            if not default.is_file():
                logging.info('No configfile found. Using defaults.')
                return
            target = default

        # Read the file ourselves: ConfigParser.read() silently ignores files
        # it cannot open, so reading the text here lets a permission problem or
        # a non-UTF-8 file surface with a clear message instead of being lost.
        try:
            config_text = target.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError) as exc:
            msg = f"Config file could not be read: {target} - {exc}"
            logging.error(msg)
            raise err.ConfigFileError(msg) from exc

        try:
            cfg.read_string(config_text, source=str(target))
        except configparser.Error as exc:
            msg = f"Config file is corrupted (not valid INI): {target} - {exc}"
            logging.error(msg)
            raise err.ConfigFileError(msg) from exc

        for section in cfg.sections():
            if section not in {'BEHAVIOR', 'CACHE', 'FILES', 'TEMPLATE'}:
                msg = (f"Config file contains unknown section '{section}': "
                       f"{target} - allowed sections are BEHAVIOR, CACHE, "
                       "FILES, TEMPLATE.")
                logging.error(msg)
                raise err.ConfigFileError(msg)

        if 'BEHAVIOR' in cfg.sections():
            behavior = cfg['BEHAVIOR']
            self.num_workers = self._from_config(behavior, 'num_workers', target)
            self.timeout = self._from_config(behavior, 'timeout', target)
            self.raise_for_dead_links = self._from_config(
                behavior, 'raise_for_dead_links', target)
            self.user_agent = behavior.get('user_agent', self.user_agent)
            self.domain_delay = self._from_config(behavior, 'domain_delay', target)
            parsed_ignores = separated_string_to_set(behavior.get('ignore_urls'))
            if parsed_ignores is not None:
                self.ignore_urls = parsed_ignores
            parsed_domains = separated_string_to_set(behavior.get('ignore_domains'))
            if parsed_domains is not None:
                self.ignore_domains = self._validate_domains(parsed_domains)
            mailto = behavior.get('mailto')
            if mailto:
                self.mailto = mailto.strip()
            self.check_dois = self._from_config(behavior, 'check_dois', target)
            self.check_internal_links = self._from_config(
                behavior, 'check_internal_links', target)
            self.max_file_size_mb = self._from_config(
                behavior, 'max_file_size_mb', target)
        if 'CACHE' in cfg.sections():
            cache = cfg['CACHE']
            self.cache_file = cache.get('cache_file', self.cache_file)  # type: ignore[arg-type]
            self.dont_check_again_within_hours = self._from_config(
                cache, 'dont_check_again_within_hours', target)
        if 'FILES' in cfg.sections():
            files = cfg['FILES']
            self.searchpath = files.get('searchpath', self.searchpath)  # type: ignore[arg-type]
            self.file_types = self._from_config(files, 'file_types', target)
        if 'TEMPLATE' in cfg.sections():
            template = cfg['TEMPLATE']
            self.template_searchpath = template.get(
                'template_searchpath', self.template_searchpath)
            self.template_name = template.get(
                'template_name', self.template_name)
            self.write_to = template.get('write_to', self.write_to)  # type: ignore[arg-type]
            self.base_url = template.get('base_url', self.base_url)

    def check_parameters(self) -> None:
        # Now the params are fixed => Apply corrections and checks
        # base_url is optional. A config file or CLI may pass the literal
        # string "None" (or an empty value) for it — treat those as unset so
        # path rewriting stays off and paths are shown relative instead.
        if isinstance(self.base_url, str) and self.base_url.strip().lower() in ('', 'none'):
            self.base_url = None
        if self.base_url:
            self.base_url = self.base_url.rstrip('/')

    def check(self,
              searchpath: str | pathlib.Path) -> None:
        """Check all links and DOIs found in files.

        Validates all links and DOIs found in a specific file or in all supported
        files within the provided folder and its subfolders.

        Args:
            searchpath: Path to a file or folder to check for links.
        """
        start_time = time.monotonic()
        self.check_parameters()

        # check might be reused with the same salted object. Therefore
        # the in memory database has to initialized here instead of on
        # a higher level.
        mem_instance = memory_instance.MemoryInstance()
        try:
            self._run_check(mem_instance, searchpath, start_time)
        finally:
            # Guarantee the in-memory SQLite connection is closed on every
            # exit path (early return, DeadLinksException, or an unexpected
            # error), preventing a leaked connection / ResourceWarning.
            mem_instance.tear_down_in_memory_db()

    def _run_check(self,
                   mem_instance: memory_instance.MemoryInstance,
                   searchpath: str | pathlib.Path,
                   start_time: float) -> None:
        """Run the link and DOI checks against an already-open in-memory DB.

        Separated from check() so the caller can guarantee teardown of the
        in-memory database via try/finally, regardless of how this returns
        (normal completion, early return, or a raised exception).

        Args:
            mem_instance: The open in-memory database instance.
            searchpath: Path to a file or folder to check for links.
            start_time: Monotonic start timestamp, for runtime statistics.
        """
        db = database_io.DatabaseIO(mem_instance, self.cache_file, quiet=self.quiet)

        cache_handler = cache_reader.CacheReader(
            mem_instance,
            self.dont_check_again_within_hours,
            self.cache_file)

        cache_handler.load_disk_cache()

        # Normalize path: strip quotes and resolve
        # This handles cases like 'C:\path\"' where trailing backslash
        # escapes the quote on Windows
        if isinstance(searchpath, str):
            # Strip leading/trailing quotes that may have been preserved
            searchpath = searchpath.strip('"').strip("'")

        # Expand path as otherwise a relative path will not be rewritten
        # in output:
        path = pathlib.Path(searchpath).resolve()

        if not path.exists():
            msg = f"File or folder to check ({path}) does not exist."
            logging.exception(msg)
            raise FileNotFoundError(msg)

        filesearch = file_finder.FileFinder()

        # Internal links are resolved against the checked folder, which
        # also acts as a security boundary: targets resolving outside it
        # are never probed on disk. For a single file, its parent folder
        # is the boundary.
        internal_checker = None
        if self.check_internal_links:
            internal_checker = internal_link_check.InternalLinkCheck(
                root=path if path.is_dir() else path.parent,
                max_file_size_mb=self.max_file_size_mb)

        file_io = input_handler.InputHandler(
            db,
            quiet=self.quiet,
            max_file_size_mb=self.max_file_size_mb,
            internal_checker=internal_checker)

        FILE_TYPE_SUFFIXES = {
            'html': {'.htm', '.html'},
            'tex': {'.tex', '.bib'},
            'markdown': {'.md'},
        }
        suffixes = FILE_TYPE_SUFFIXES.get(self.file_types)  # None for 'supported'

        # Select files to check (directory or single supported file)
        if path.is_dir():
            logging.info('Base folder: %s', path)
            files_to_check = filesearch.find_files_by_extensions(path, suffixes=suffixes)
        elif path.is_file() and filesearch.is_supported_format(path):
            files_to_check = [path]
        else:
            msg = f"File format of {path} not supported"
            logging.exception(msg)
            raise ValueError(msg)

        # Scan and prune for both directory and single-file modes
        if not files_to_check:
            logging.warning("No supported files in this folder or its subfolders.")
            return

        file_io.scan_files(files_to_check)
        mem_instance.generate_indices()
        if self.check_dois:
            db.convert_doi_urls_to_dois()
        db.del_links_that_can_be_skipped()
        db.del_dois_that_can_be_skipped()

        # ##### START CHECKS #####

        # Normalize ignore list to align with normalized URLs in the queue
        normalized_ignores = _normalize_url_set(self.ignore_urls)

        urls = url_check.UrlCheck(
            self.user_agent,
            db,
            self.num_workers,
            self.timeout,
            normalized_ignores,
            self.domain_delay,
            ignore_domains=self.ignore_domains,
            quiet=self.quiet)
        urls.check_urls()

        num_valid_dois = 0
        num_invalid_dois = 0
        if self.check_dois:
            doi = doi_check.DoiCheck(db, quiet=self.quiet, mailto=self.mailto)
            doi.check_dois()
            num_valid_dois = len(doi.valid_doi_list)
            num_invalid_dois = len(doi.invalid_doi_list)

        # ##### END CHECKS #####

        mem_instance.generate_db_views()

        runtime_check = time.monotonic() - start_time

        # Although time.monotonic() works with fractional seconds,
        # runtime_check is falsely 0 with unit tests on Windows
        # (neither Linux, nor MacOS).
        # To avoid division by zero later on:
        runtime_check = 1 if runtime_check == 0 else runtime_check
        # TO DO: check why this happens on Windows

        display_result = report_generator.ReportGenerator(mem_instance)

        # Base folder used to transform stored (absolute) file paths for the
        # report: rewritten to base_url when set, otherwise shown relative to
        # this folder (its parent when a single file was checked).
        relative_base = path if path.is_dir() else path.parent

        display_result.generate_report(
            statistics={
                'timestamp': f'{datetime.datetime.now():%Y-%b-%d %H:%Mh}',
                'num_links': file_io.cnt['links_found'],
                'num_checked': urls.cnt['checked_urls'],
                'time_to_check': (round(runtime_check)),
                'checks_per_second': (
                    round(urls.cnt['checked_urls'] / runtime_check, 2)),
                'num_fine': urls.cnt['fine'],
                'needed_full_request': urls.cnt['neededFullRequest'],
                'percentage_full_request': (
                    round((urls.cnt['neededFullRequest'] / urls.cnt['checked_urls']) * 100, 2)
                    if urls.cnt['checked_urls'] > 0 else 0
                ),
                'check_dois': self.check_dois,
                'num_valid_dois': num_valid_dois,
                'num_invalid_dois': num_invalid_dois,
                'check_internal_links': self.check_internal_links,
                'num_internal_checked': (
                    internal_checker.cnt['internal_checked']
                    if internal_checker else 0),
                'num_internal_fine': (
                    internal_checker.cnt['internal_fine']
                    if internal_checker else 0),
                          },
            template={
                'searchpath': self.template_searchpath,
                'name': self.template_name,
                'foldername_to_replace': str(path),
                'base_url': self.base_url},
            write_to=self.write_to,
            replace_path_by_url={
                'path_to_be_replaced': str(relative_base),
                'replace_with_url': self.base_url
            })
        # Persist the cache before potentially raising: URLs validated in
        # this run must survive a DeadLinksException, otherwise a failing
        # CI run would recheck everything on the next attempt.
        cache_handler.overwrite_cache_file()
        num_dead = db.count_errors() + db.count_internal_link_errors()
        if self.raise_for_dead_links and num_dead > 0:
            raise err.DeadLinksException("Found dead URLs")


if __name__ == '__main__':
    from salted.command_line import main
    main()
