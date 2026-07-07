#!/usr/bin/python3

"""
Check DOI via the API
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026 Rüdiger Voigt and contributors
Released under the Apache License 2.0
"""
import asyncio
import logging
import re
import sys
import urllib.parse
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from typing import Final

import aiohttp
from aiohttp import ClientTimeout
from tqdm.asyncio import tqdm  # type: ignore

from salted import database_io

# DOI format: prefix 10.NNNN[NN...] / suffix (at least one non-whitespace char)
_DOI_PATTERN: Final = re.compile(r'^10\.\d{4,}/\S+$')


class DoiCheck:
    """Interact with the API to check DOIs."""
    # pylint: disable=too-few-public-methods

    API_BASE_URL: Final[str] = 'https://api.crossref.org/works/'
    NUM_API_WORKERS: Final[int] = 5

    def __init__(self,
                 db_io: database_io.DatabaseIO,
                 quiet: bool = False,
                 mailto: str | None = None) -> None:

        self.db = db_io
        self.quiet = quiet

        # Do NOT conceal the user agent for API requests.
        # The providers of the API explicitly ask that bots identify themselves
        # with an user agent, a project URL and a mailto address.
        # Requests of polite bots get directed to a separate pool of machines.
        # See: https://github.com/CrossRef/rest-api-doc
        try:
            _version = pkg_version('salted')
        except PackageNotFoundError:
            _version = "unknown"
        if not mailto:
            logging.warning(
                "No mailto address configured for CrossRef API requests. "
                "Without contact information in the User-Agent, requests are "
                "not routed to CrossRef's polite pool and may be rate-limited "
                "more aggressively. Set 'mailto' in [BEHAVIOR] of your config "
                "file or via the --mailto CLI argument.")
        ua = (f"salted/{_version} "
              "(https://github.com/RuedigerVoigt/salted"
              + (f"; mailto:{mailto}" if mailto else "")
              + ")")
        self.headers = {'User-Agent': ua}

        self.session: aiohttp.ClientSession | None = None
        self.timeout_sec = 3

        self.pbar_doi: tqdm | None = None

        self.valid_doi_list: list = list()
        self.invalid_doi_list: list = list()

        # Shared rate limiter: one global lock and timestamp ensures all workers
        # together respect the API rate limit without per-worker multiplication.
        self._rate_lock = asyncio.Lock()
        self._last_send: float = 0.0
        # Conservative default (public pool: 5 req/s). Overwritten after the
        # first response arrives with the actual X-Rate-Limit-* headers.
        self._min_interval: float = 0.2

    @staticmethod
    def _is_valid_doi_format(doi: str) -> bool:
        """Return True if doi matches the basic DOI format 10.NNNN/suffix."""
        return bool(_DOI_PATTERN.match(doi.strip()))

    async def __create_session(self) -> None:
        # Create a client session bound to the current running loop
        self.session = aiohttp.ClientSession()

    async def __close_session(self) -> None:
        """Close the session object once it is no longer needed."""
        if self.session:
            await self.session.close()

    async def __rate_limit_wait(self,
                                max_queries: int,
                                seconds: int
                                ) -> None:
        """Enforce the CrossRef API rate limit using a shared lock.

        A single global lock gates all workers, so the interval between any
        two consecutive requests is enforced across the whole worker pool —
        no per-worker multiplication needed.

        Args:
            max_queries: Maximum number of queries allowed in the time window.
            seconds: Time window in seconds for the rate limit.

        Raises:
            ValueError: If max_queries or seconds is less than 1.
        """
        if max_queries < 1:
            raise ValueError('Parameter "max_queries" must be an integer > 0.')
        if seconds < 1:
            raise ValueError('Parameter "seconds" must be an integer > 0.')
        # Stay at 90% of the limit to avoid hitting the ceiling.
        effective = max(1, round(max_queries * 0.9))
        self._min_interval = seconds / effective

        async with self._rate_lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_send
            if elapsed < self._min_interval:
                wait = self._min_interval - elapsed
                logging.debug("CrossRef rate limit: sleeping %.3fs", wait)
                await asyncio.sleep(wait)
            self._last_send = asyncio.get_event_loop().time()

    async def __api_send_head_request(self,
                                      doi: str) -> dict:
        """Send a HTTP HEAD request to the CrossRef API.

        Args:
            doi: The DOI string to check.

        Returns:
            Dictionary containing:
                - max_queries: Maximum queries allowed per time window.
                - seconds: Time window in seconds.
                - status: HTTP status code (200 if DOI exists, 404 if not).
        """
        logging.debug("Sending head request to Crossref API: check %s", doi)
        # The HTTP HEAD method requests the headers, but not the page's body.
        # Requesting this way reduces load on the server and network traffic.
        # Percent-encode the DOI before it goes into the URL: the preflight
        # regex admits URL-significant characters (?, #, &, spaces), so an
        # unencoded DOI could inject a query/fragment into the request or make
        # a legitimate DOI containing such a character resolve to the wrong
        # resource. safe='/' keeps the slash that separates DOI prefix and
        # suffix, which CrossRef expects literally in the path.
        query_url = self.API_BASE_URL + urllib.parse.quote(doi, safe='/')
        async with self.session.head(  # type: ignore[union-attr]
                query_url,
                headers=self.headers,
                raise_for_status=False,
                timeout=ClientTimeout(total=self.timeout_sec)) as response:
            # CrossRef usually sends these rate-limit headers, but not always
            # (and not on every response type). Read them defensively so a
            # missing/odd header never costs us the DOI's status: fall back to
            # the conservative public-pool default (5 requests / 1 s), matching
            # the _min_interval set in __init__. Header format is 'numeric s'.
            limit = response.headers.get('X-Rate-Limit-Limit', '5')
            timewindow = response.headers.get('X-Rate-Limit-Interval', '1s')
            timewindow = timewindow.rstrip('s').strip() or '1'
            return {
                'max_queries':  limit,
                'seconds':  timewindow,
                'status': response.status}

    async def __worker(self,
                       name: str,
                       queue: asyncio.Queue) -> None:
        """Worker coroutine to process DOI checks from the queue.

        Waits for API request results and enforces rate limiting.

        Args:
            name: Worker identifier for debugging purposes.
            queue: Async queue containing DOIs to check.
        """
        # DO NOT REMOVE 'while True'. Without that the queue is stopped
        # after the first iteration.
        while True:
            doi = await queue.get()
            try:
                api_response = await self.__api_send_head_request(doi)
                if api_response['status'] == 200:
                    logging.debug("DOI %s is valid", doi)
                    self.valid_doi_list.append(doi)
                elif api_response['status'] == 404:
                    logging.debug("DOI %s does not exist!", doi)
                    self.invalid_doi_list.append(doi)
                else:
                    if not self.quiet:
                        print(f"Unexpected API response: {api_response['status']}")
                await self.__rate_limit_wait(
                    int(api_response['max_queries']),
                    int(api_response['seconds']))
            except Exception:
                logging.exception("Failed to check DOI %s", doi)
            finally:
                if self.pbar_doi is not None:
                    self.pbar_doi.update(1)
                queue.task_done()

    async def __distribute_work(self,
                                doi_list: list) -> None:
        """Start a queue and spawn workers to work in parallel.

        Args:
            doi_list: List of DOI strings to check.
        """
        queue: asyncio.Queue = asyncio.Queue()
        for entry in doi_list:
            if self._is_valid_doi_format(entry):
                queue.put_nowait(entry)
            else:
                logging.warning("DOI '%s' fails basic format check — skipping API call.", entry)
                self.invalid_doi_list.append(entry)

        await self.__create_session()
        tasks = []
        try:
            for i in range(int(self.NUM_API_WORKERS)):
                task = asyncio.create_task(self.__worker(f'worker-{i}', queue))
                tasks.append(task)
            await queue.join()
        finally:
            for task in tasks:
                task.cancel()
            await self.__close_session()
            await asyncio.gather(*tasks, return_exceptions=True)

    def check_dois(self) -> None:
        """Check the DOIs in the queue and show a progress bar.

        Synchronous wrapper for the async DOI checking process.
        """
        dois_to_check = self.db.get_dois_to_check()
        if not dois_to_check:
            logging.debug('No DOIs to check.')
            return
        num_doi = len(dois_to_check)
        if not self.quiet:
            print(f"{num_doi} DOI{'s' if num_doi != 1 else ''} to check:")
        self.pbar_doi = tqdm(total=num_doi, disable=self.quiet or not sys.stdout.isatty())
        try:
            asyncio.run(self.__distribute_work(dois_to_check))
        finally:
            self.pbar_doi.close()
        # executemany needs a list of tuples:
        if self.valid_doi_list:
            self.db.save_valid_dois([(doi, ) for doi in self.valid_doi_list])
        if self.invalid_doi_list:
            self.db.log_invalid_dois([(doi, ) for doi in self.invalid_doi_list])
