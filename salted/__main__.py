#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Smart, Asynchronous Link Tester with Database backend (SALTED)
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020: Released under the Apache License 2.0
"""

import asyncio
from collections import Counter
import datetime
import logging
import pathlib
import time
from typing import Optional, Union

import compatibility
from tqdm.asyncio import tqdm  # type: ignore
import userprovided

from salted import database_io
from salted import input_handler
from salted import network_interaction
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
        self.num_checks = 0
        self.pbar_links: tqdm = None

    def __recommend_num_workers(self) -> int:
        """If the number of workers is set to 'automatic', this returns an
           estimate an appropriate number of async workers to use - based on
           the number of hyperlinks to check.
           If the user provided a specific number of workers, that will be
           returned instead."""

        if self.num_workers == 'automatic':
            if self.num_checks < 1:
                raise ValueError

            if self.num_checks < 25:
                recommendation = 4
            elif self.num_checks < 100:
                recommendation = 12
            elif self.num_checks > 99:
                recommendation = 32
        else:
            recommendation = int(self.num_workers)
        # Set the logging message here to flush the cache. Cannot use
        # flush() as it is unknow which or how many logging methods are used.
        logging.info("%s unique hyperlinks to check. Using %s workers.",
                     self.num_checks, recommendation)
        return recommendation

    async def __worker(self,
                       name: str,
                       queue: asyncio.Queue) -> None:
        while True:
            url = await queue.get()
            await self.network.check_url(url, 'head')
            self.pbar_links.update(1)
            queue.task_done()

    async def __distribute_work(self,
                                urls_to_check: list) -> None:
        """Start a queue and spawn workers to work in parallel."""
        queue: asyncio.Queue = asyncio.Queue()
        for entry in urls_to_check:
            queue.put_nowait(entry[0])

        # initialize here as there has to exist an event loop
        self.network = network_interaction.NetworkInteraction(
            self.db,
            self.timeout,
            self.user_agent)

        tasks = []
        for i in range(int(self.num_workers)):
            task = asyncio.create_task(self.__worker(f'worker-{i}', queue))
            tasks.append(task)
        await queue.join()

        # Cancel worker tasks.
        for task in tasks:
            task.cancel()

        # Close aiohttp session
        await self.network.close_session()

        # Wait until all worker tasks are cancelled.
        await asyncio.gather(*tasks, return_exceptions=True)

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
        # et cetera from previous runs. however this loads the disk cache.
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
            num_links_to_check = self.db.del_links_that_can_be_skipped()
            if num_links_to_check == 0:
                msg = ("Nothing to do after skipping cached results." +
                       "All hyperlinks are considered valid.")
                logging.info(msg)
                return
        else:
            logging.warning(
                "No supported files in this folder or its subfolders.")
            return

        urls_to_check = self.db.urls_to_check()

        if not urls_to_check:
            logging.warning("Found no hyperlinks to check!")
            return

        # Class level because this number is needed to initialize the progress
        # bar and will be logged in some messages:
        self.num_checks = len(urls_to_check)

        # Set of number of workers here instead of __distribute_work as
        # otherwise the logging message will force the progress bar to repaint.
        self.num_workers = self.__recommend_num_workers()

        self.pbar_links = tqdm(total=self.num_checks)

        # ##### START ASYNCHRONOUS CODE #####

        asyncio.run(self.__distribute_work(urls_to_check))

        # ##### END ASYNCHRONOUS CODE #####
        self.db.generate_indices()
        self.db.generate_db_views()
        self.pbar_links.close()

        runtime_check = time.monotonic() - start_time

        self.display_result.generate_report(
            statistics={
                'timestamp': '{:%Y-%b-%d %H:%Mh}'.format(datetime.datetime.now()),
                'num_links': self.file_io.cnt['links_found'],
                'num_checked': self.num_checks,
                'time_to_check': (round(runtime_check)),
                'checks_per_second': (
                    round(self.num_checks / runtime_check, 2)),
                'num_fine': self.network.cnt['fine'],
                'needed_full_request': self.network.cnt['neededFullRequest'],
                'percentage_full_request': (
                    round(self.network.cnt['neededFullRequest'] /
                          self.num_checks * 100, 2))
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
