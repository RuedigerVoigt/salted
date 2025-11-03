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
from typing import Optional, Union

import aiohttp
import sys
from aiohttp import ClientTimeout
from tqdm.asyncio import tqdm  # type: ignore

from salted import database_io
from salted.rate_limiter import DomainRateLimiter


class UrlCheck:
    """Interact with the network to check URLs."""
    # pylint: disable=too-many-instance-attributes

    def __init__(self,
                 user_agent: str,
                 db: database_io.DatabaseIO,
                 workers: Union[int, str] = 'automatic',
                 timeout_sec: int = 5,
                 ignore_urls: Optional[set] = None,
                 domain_delay: float = 0.25
                 ) -> None:
        # pylint: disable=too-many-arguments
        self.headers: dict = dict()
        if user_agent:
            self.headers = {'User-Agent': user_agent}

        self.db = db
        self.timeout = int(timeout_sec)
        self.ignore_urls = ignore_urls if ignore_urls else set()

        self.num_workers: Union[int, str] = workers

        self.cnt: Counter = Counter()

        self.pbar_links: tqdm = None

        self.session: aiohttp.ClientSession = None  # type: ignore

        # Initialize domain-based rate limiter
        self.rate_limiter = DomainRateLimiter(delay_seconds=domain_delay)

    async def __create_session(self) -> None:
        # Create a client session bound to the current running loop
        self.session = aiohttp.ClientSession()

    async def __close_session(self) -> None:
        """Close the session object once it is no longer needed."""
        if self.session:
            await self.session.close()

    def __recommend_num_workers(self,
                                num_checks: int) -> int:
        """Recommend the number of async workers to use.

        If the number of workers is set to 'automatic', estimates an appropriate
        number based on the number of hyperlinks to check. If the user provided
        a specific number, that value is returned instead.

        Args:
            num_checks: Number of URLs to check.

        Returns:
            Recommended number of worker coroutines (4-64).

        Raises:
            ValueError: If num_checks is less than 1.
        """

        if self.num_workers == 'automatic':
            if num_checks < 1:
                raise ValueError

            if num_checks > 5000:
                recommendation = 64
            elif num_checks > 99:
                recommendation = 32
            elif num_checks > 24:
                recommendation = 12
            else:
                recommendation = 4
        else:
            # i.e. user set a specific number
            recommendation = int(self.num_workers)
        # Set the logging message here to flush the cache. Cannot use
        # flush() as it is unknown which or how many logging methods are used.
        logging.debug("Using %s workers to check %s hyperlinks.",
                      recommendation, num_checks)
        return recommendation

    async def head_request(self,
                           url: str) -> int:
        """Send an HTTP HEAD request to check the URL.

        The HTTP HEAD method requests headers but not the page body,
        reducing server load and network traffic. Falls back to GET
        if HEAD is not supported (405 Method Not Allowed).

        Args:
            url: The URL to check.

        Returns:
            HTTP status code from the response.
        """
        # Try HEAD first
        async with self.session.head(url,
                                    headers=self.headers,
                                    raise_for_status=False,
                                    timeout=ClientTimeout(total=self.timeout)) as response:
            # If server doesn't support HEAD (405 Method Not Allowed), fall back to GET
            if response.status == 405:
                # Count how often a full GET was needed
                self.cnt['neededFullRequest'] += 1
                async with self.session.get(url,
                                           headers=self.headers,
                                           raise_for_status=False,
                                           timeout=ClientTimeout(total=self.timeout)) as get_response:
                    return get_response.status
            return response.status

    async def validate_url(self,
                           url: str) -> None:
        """Validate a URL and log the result to the database.

        Uses HTTP HEAD request (or GET if necessary) to check the link.
        Applies domain-based rate limiting and handles various HTTP status
        codes and exceptions appropriately.

        Args:
            url: The URL to validate.
        """
        if url in self.ignore_urls:
            self.cnt['ignored_urls'] += 1
            return

        self.cnt['checked_urls'] += 1

        # Apply domain-based rate limiting
        await self.rate_limiter.wait_if_needed(url)

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
        """Worker coroutine to process URL checks from the queue.

        Args:
            name: Worker identifier for debugging purposes.
            queue: Async queue containing URLs to check.
        """
        # DO NOT REMOVE 'while True'. Without that the queue is stopped
        # after the first iteration.
        while True:
            url = await queue.get()
            await self.validate_url(url)
            self.pbar_links.update(1)
            queue.task_done()

    async def __distribute_work(self,
                                urls_to_check: list) -> None:
        """Start a queue and spawn workers to work in parallel.

        Args:
            urls_to_check: List of tuples containing URLs to validate.
        """
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
        """Process all URLs that are not assumed as valid in the cache.

        Synchronous wrapper for the async URL checking process.
        """
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
        self.pbar_links = tqdm(total=num_checks, disable=not sys.stdout.isatty())

        # Synchronous wrapper for environments without an event loop
        asyncio.run(self.__distribute_work(urls_to_check))

        self.pbar_links.close()

    async def check_urls_async(self) -> None:
        """Check URLs asynchronously.

        Async variant of check_urls for integration in async applications.
        """
        urls_to_check = self.db.urls_to_check()
        if not urls_to_check:
            logging.info(
                "No URLs to check after skipping cached results."
                "All hyperlinks are considered valid.")
            return
        num_checks = len(urls_to_check)
        self.num_workers = self.__recommend_num_workers(num_checks)
        print(f"{num_checks} URLs to check with {self.num_workers} workers:")
        self.pbar_links = tqdm(total=num_checks, disable=not sys.stdout.isatty())
        try:
            await self.__distribute_work(urls_to_check)
        finally:
            self.pbar_links.close()
