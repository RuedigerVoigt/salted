#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Smart, Asynchronous Link Tester with Database backend (SALTED)
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2021: Released under the Apache License 2.0
"""

from collections import Counter
import configparser
import datetime
import logging
import pathlib
import time
from typing import Optional, Union

import compatibility

from salted import _version as version
from salted import cache_reader
from salted import database_io
from salted import doi_check
from salted import err
from salted import input_handler
from salted import memory_instance
from salted import url_check
from salted import report_generator


class Salted:
    """Main class. Creates the other Objects, starts workers,
       collects results and starts the report of results. """
    # pylint: disable=too-few-public-methods
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-instance-attributes

    VERSION = version.__version__
    CONFIG_NAME = 'salted-linkcheck.ini'

    def __init__(self) -> None:

        compatibility.Check(
            package_name='salted',
            package_version=self.VERSION,
            release_date=version.release_date,
            python_version_support={
                'min_version': '3.8',
                'incompatible_versions': ['3.6', '3.7'],
                'max_tested_version': '3.9'},
            nag_over_update={
                    'nag_days_after_release': 60,
                    'nag_in_hundred': 100},
            language_messages='en',
            system_support={'full': {'Linux', 'MacOS', 'Windows'}}
            )

        # #################### Application defaults ####################
        # Files
        self.searchpath: Union[str, pathlib.Path] = '.'
        self.file_types: str = 'supported'
        # Behavior
        self.num_workers: Union[int, str] = 'automatic'
        self.timeout: int = 5
        self.raise_for_dead_links = False
        self.user_agent = f"salted/{self.VERSION}"
        # Cache
        self.cache_file: Union[pathlib.Path, str] = 'salted-cache.sqlite3'
        self.dont_check_again_within_hours: int = 24
        # Template
        self.template_searchpath: str = 'salted/templates'
        self.template_name: str = 'default.cli.jinja'
        self.write_to: Union[str, pathlib.Path] = 'cli'
        self.base_url: Optional[str] = None

        # If there is a configfile, overwrite defaults with those settings
        self.__parse_configfile()

        self.cnt: Counter = Counter()

    def __parse_configfile(self) -> None:
        """If there is a configfile read it and overwrite defaults if new
           value is set for them. If a specific parameter is not set,
           fall back to the application default.
           Config file settings can be overwritten trough CLI parameters."""
        cfg = configparser.ConfigParser()
        # read does not throw an exception if the file is not there!
        cfg.read(self.CONFIG_NAME)
        for section in cfg.sections():
            if section not in {'BEHAVIOR', 'CACHE', 'FILES', 'TEMPLATE'}:
                raise ValueError('Configfile contains unknown section!')

        if 'BEHAVIOR' in cfg.sections():
            behavior = cfg['BEHAVIOR']
            self.num_workers = behavior.get('num_workers', self.num_workers)  # type: ignore[arg-type]
            self.timeout = behavior.getint('timeout', self.timeout)
            self.raise_for_dead_links = behavior.getboolean(
                        'raise_for_dead_links',
                        self.raise_for_dead_links)
            self.user_agent = behavior.get('user_agent', self.user_agent)
        if 'CACHE' in cfg.sections():
            cache = cfg['CACHE']
            self.cache_file = cache.get('cache_file', self.cache_file)  # type: ignore[arg-type]
            self.dont_check_again_within_hours = cache.getint(
                        'dont_check_again_within_hours',
                        self.dont_check_again_within_hours)
        if 'FILES' in cfg.sections():
            files = cfg['FILES']
            self.searchpath = files.get('searchpath', self.searchpath)  # type: ignore[arg-type]
            self.file_types = files.get('file_types', self.file_types)
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
        if self.base_url:
            self.base_url = self.base_url.rstrip('/')

    def check(self,
              searchpath: Union[str, pathlib.Path]) -> None:
        """Check all links and DOIs found in a specific file or in all supported
           files within the provided folder and its subfolders."""
        start_time = time.monotonic()

        # check might be reused with the same salted object. Therefore
        # the in memory database has to initialized here instead of on
        # a higher level.
        mem_instance = memory_instance.MemoryInstance()
        db = database_io.DatabaseIO(mem_instance, self.cache_file)

        cache_handler = cache_reader.CacheReader(
            mem_instance,
            self.dont_check_again_within_hours,
            self.cache_file)

        cache_handler.load_disk_cache()

        # Expand path as otherwise a relative path will not be rewritten
        # in output:
        path = pathlib.Path(searchpath).resolve()

        if not path.exists():
            msg = f"File or folder to check ({path}) does not exist."
            logging.exception(msg)
            raise FileNotFoundError(msg)

        file_io = input_handler.InputHandler(db)
        files_to_check = list()
        if path.is_dir():
            logging.info('Base folder: %s', path)
            files_to_check = file_io.find_files_by_extensions(path)
            if files_to_check:
                file_io.scan_files(files_to_check)
                mem_instance.generate_indices()
                db.del_links_that_can_be_skipped()
                db.del_dois_that_can_be_skipped()
            else:
                logging.warning(
                    "No supported files in this folder or its subfolders.")
                return
        elif path.is_file() and file_io.is_supported_format(path):
            files_to_check.append(path)
        else:
            msg = f"File format of {path} not supported"
            logging.exception(msg)
            raise ValueError(msg)

        # ##### START CHECKS #####

        urls = url_check.UrlCheck(
            self.user_agent,
            db,
            self.num_workers,
            self.timeout)
        urls.check_urls()

        doi = doi_check.DoiCheck(db)
        doi.check_dois()

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

        display_result.generate_report(
            statistics={
                'timestamp': '{:%Y-%b-%d %H:%Mh}'.format(datetime.datetime.now()),
                'num_links': file_io.cnt['links_found'],
                'num_checked': urls.cnt['checked_urls'],
                'time_to_check': (round(runtime_check)),
                'checks_per_second': (
                    round(urls.cnt['checked_urls'] / runtime_check, 2)),
                'num_fine': urls.cnt['fine'],
                'needed_full_request': urls.cnt['neededFullRequest']
                          },
            template={
                'searchpath': self.template_searchpath,
                'name': self.template_name,
                'foldername_to_replace': str(path),
                'base_url': self.base_url},
            write_to=self.write_to,
            replace_path_by_url={
                'path_to_be_replaced': str(path),
                'replace_with_url': self.base_url
            })
        if self.raise_for_dead_links:
            if db.count_errors() > 0:
                raise err.DeadLinksException("Found dead URLs")
        cache_handler.overwrite_cache_file()
        mem_instance.tear_down_in_memory_db()
