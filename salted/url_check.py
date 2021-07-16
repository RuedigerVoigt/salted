#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Hyperlink checks for salted.
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2021 by Rüdiger Voigt
Released under the Apache License 2.0
"""
import asyncio
from collections import Counter
import logging
from typing import Union

import aiohttp
from tqdm.asyncio import tqdm  # type: ignore

from salted import database_io


class UrlCheck:
    "Interacts with the network to check URLs."

    def __init__(self,
                 user_agent: str,
                 db: database_io.DatabaseIO,
                 workers: Union[int, str] = 'automatic',
                 timeout_sec: int = 5
                 ) -> None:
        self.headers: dict = dict()
        if user_agent:
            self.headers = {'User-Agent': user_agent}

        self.db = db
        self.timeout = int(timeout_sec)

        self.num_workers: Union[int, str] = workers

        self.cnt: Counter = Counter()

        self.pbar_links: tqdm = None

        self.session: aiohttp.ClientSession = None  # type: ignore

    async def __create_session(self) -> None:
        self.session = aiohttp.ClientSession(loop=asyncio.get_running_loop())

    async def __close_session(self) -> None:
        "Close the session object once it is no longer needed"
        if self.session:
            await self.session.close()

    def __recommend_num_workers(self,
                                num_checks: int) -> int:
        """If the number of workers is set to 'automatic', this returns an
           estimate an appropriate number of async workers to use - based on
           the number of hyperlinks to check.
           If the user provided a specific number of workers, that will be
           returned instead."""

        if self.num_workers == 'automatic':
            if num_checks < 1:
                raise ValueError

            recommendation = 4
            if 24 < num_checks < 100:
                recommendation = 12
            elif num_checks > 99:
                recommendation = 32
            elif num_checks > 5000:
                recommendation = 64
        else:
            # i.e. user set a specific number
            recommendation = int(self.num_workers)
        # Set the logging message here to flush the cache. Cannot use
        # flush() as it is unknow which or how many logging methods are used.
        logging.debug("Using %s workers to check %s hyperlinks.",
                      recommendation, num_checks)
        return recommendation

    async def head_request(self,
                           url: str) -> int:
        """The HTTP HEAD method requests the headers, but not the body of
           a page. Requesting this way reduces load on the server and
           reduces network traffic."""
        async with self.session.get(url,
                                    headers=self.headers,
                                    raise_for_status=False,
                                    timeout=self.timeout) as response:
            return response.status

    async def validate_url(self,
                           url: str) -> None:
        """Check the URL by using a HTTP HEAD request (or if necessary a full
           request with limited data read) to check the link and log the result
           to the database. """
        self.cnt['checked_urls'] += 1
        try:
            response_code = await self.head_request(url)
            if response_code in (200, 302, 303, 307):
                self.cnt['fine'] += 1
                self.db.log_url_is_fine(url)
            elif response_code in (301, 308):
                self.db.log_redirect(url, response_code)
            elif response_code in (403, 404, 410):
                self.db.log_error(url, response_code)
            elif response_code == 429:
                self.db.log_exception(url, 'Rate Limit (429)')
            else:
                self.db.log_exception(url, f"Other ({response_code})")
        # Log but do not raise. Raising leads to the worker not returning
        # and the application does not finish the loop.
        except asyncio.TimeoutError:
            self.db.log_exception(url, 'Timeout')
        except aiohttp.client_exceptions.ClientConnectorError:
            self.db.log_exception(url, 'ClientConnectorError')
        except aiohttp.client_exceptions.ClientResponseError:
            self.db.log_exception(url, 'ClientResponseError')
        except aiohttp.client_exceptions.ClientOSError:
            self.db.log_exception(url, 'ClientOSError')
        except aiohttp.client_exceptions.ServerDisconnectedError:
            self.db.log_exception(url, 'Server disconnected')
        except Exception:
            logging.exception('Exception. URL %s', url,  exc_info=True)

    async def __worker(self,
                       name: str,
                       queue: asyncio.Queue) -> None:
        "Worker of the queue."
        # DO NOT REMOVE 'while True'. Without that the queue is stopped
        # after the first iteration.
        while True:
            url = await queue.get()
            await self.validate_url(url)
            self.pbar_links.update(1)
            queue.task_done()

    async def __distribute_work(self,
                                urls_to_check: list) -> None:
        "Start a queue and spawn workers to work in parallel."
        queue: asyncio.Queue = asyncio.Queue()
        for entry in urls_to_check:
            queue.put_nowait(entry[0])

        await self.__create_session()

        tasks = []
        for i in range(int(self.num_workers)):
            task = asyncio.create_task(self.__worker(f'worker-{i}', queue))
            tasks.append(task)
        await queue.join()

        # Cancel worker tasks.
        for task in tasks:
            task.cancel()

        # Close aiohttp session
        await self.__close_session()

        # Wait until all worker tasks are cancelled.
        await asyncio.gather(*tasks, return_exceptions=True)

    def check_urls(self) -> None:
        "Process all URLs that are not assumed as valid in the cache."
        urls_to_check = self.db.urls_to_check()
        if not urls_to_check:
            msg = ("No URLs to check after skipping cached results." +
                   "All hyperlinks are considered valid.")
            logging.info(msg)
            return
        num_checks = len(urls_to_check)
        # Set of number of workers here instead of __distribute_work as
        # otherwise the logging message will force the progress bar to repaint.
        self.num_workers = self.__recommend_num_workers(num_checks)
        print(f"{num_checks} URLs to check with {self.num_workers} workers:")
        self.pbar_links = tqdm(total=num_checks)

        asyncio.run(self.__distribute_work(urls_to_check))

        self.pbar_links.close()
