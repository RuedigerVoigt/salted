#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Smart, Asynchronous Link Tester with Database backend (SALTED)
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020: Released under the Apache License 2.0
"""

from collections import Counter
import datetime
import logging
import pathlib
import time
from typing import Optional, Union

import compatibility
import userprovided

from salted import database_io
from salted import doi_check
from salted import input_handler
from salted import url_check
from salted import report_generator


class Salted:
    """Main class. Creates the other Objects, starts workers,
       collects results and starts the report of results. """

    VERSION = '0.6.1'

    def __init__(self,
                 cache_file: Union[pathlib.Path, str],
                 workers: Union[int, str] = 'automatic',
                 timeout_sec: int = 5,
                 dont_check_again_within_hours: int = 24,
                 raise_for_dead_links: bool = False,
                 user_agent: str = f"salted/{VERSION}") -> None:

        compatibility.Check(
            package_name='salted',
            package_version=self.VERSION,
            release_date=datetime.date(2021, 1, 22),
            python_version_support={
                'min_version': '3.8',
                'incompatible_versions': ['3.7'],
                'max_tested_version': '3.9'},
            nag_over_update={
                    'nag_days_after_release': 30,
                    'nag_in_hundred': 100},
            language_messages='en')

        self.num_workers = workers
        self.timeout = int(timeout_sec)

        userprovided.parameters.enforce_boolean(
            raise_for_dead_links,
            'raise_for_dead_links')
        self.raise_for_dead_links = raise_for_dead_links

        self.user_agent = user_agent

        self.db = database_io.DatabaseIO(
            dont_check_again_within_hours,
            cache_file)
        self.file_io = input_handler.InputHandler(self.db)

        self.display_result = report_generator.ReportGenerator(
            self.db)

        self.cnt: Counter = Counter()

    def check_links(self,
                    path_to_base_folder: Union[str, pathlib.Path],
                    template_searchpath: str = 'salted/templates',
                    template_name: str = 'default.cli.jinja',
                    write_to: Union[str, pathlib.Path] = 'cli',
                    base_url: Optional[str] = None) -> None:
        """Check all links found in files within the provided folder
           and its subfolders."""
        start_time = time.monotonic()

        # check_links might be reused with the same salted object. Therefore
        # the database has to reinitialized to remove data like exceptions
        # et cetera from previous runs. However this loads the disk cache.
        self.db.reinitialize_in_memory_db()

        # Expand path as otherwise a relative path will not be rewritten
        # in output:
        path_to_base_folder = pathlib.Path(path_to_base_folder).resolve()
        logging.info('Base folder: %s', path_to_base_folder)

        # Remove trailing slash in base URL if there is one:
        if base_url:
            base_url = base_url.rstrip('/')

        files_to_check = self.file_io.find_files_by_extensions(
            path_to_base_folder)
        if files_to_check:
            self.file_io.scan_files_for_links(files_to_check)
            self.db.del_links_that_can_be_skipped()
        else:
            logging.warning(
                "No supported files in this folder or its subfolders.")
            return

        # ##### START CHECKS #####

        urls = url_check.UrlCheck(
            self.user_agent,
            self.db,
            self.num_workers,
            self.timeout)
        urls.check_urls()

        doi = doi_check.DoiCheck(self.db)
        doi.check_dois()

        # ##### END CHECKS #####

        self.db.generate_indices()
        self.db.generate_db_views()

        runtime_check = time.monotonic() - start_time

        self.display_result.generate_report(
            statistics={
                'timestamp': '{:%Y-%b-%d %H:%Mh}'.format(datetime.datetime.now()),
                'num_links': self.file_io.cnt['links_found'],
                'num_checked': urls.num_checks,
                'time_to_check': (round(runtime_check)),
                'checks_per_second': (
                    round(urls.num_checks / runtime_check, 2)),
                'num_fine': urls.cnt['fine'],
                'needed_full_request': urls.cnt['neededFullRequest'],
                'percentage_full_request': (
                    round(urls.cnt['neededFullRequest'] /
                          urls.num_checks * 100, 2))
                          },
            template={
                'searchpath': template_searchpath,
                'name': template_name,
                'foldername_to_replace': str(path_to_base_folder),
                'base_url': base_url},
            write_to=write_to,
            replace_path_by_url={
                'path_to_be_replaced': str(path_to_base_folder),
                'replace_with_url': base_url
            })
        if self.raise_for_dead_links:
            if self.db.count_errors() > 0:
                raise Exception("Found dead URLs")
        self.db.overwrite_cache_file()
        self.db.tear_down_in_memory_db()
