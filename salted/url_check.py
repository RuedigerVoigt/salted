#!/usr/bin/python3

"""
Hyperlink checks for salted.
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026 Rüdiger Voigt and contributors
Released under the Apache License 2.0
"""
import asyncio
import logging
import sys
import urllib.parse
from collections import Counter
from typing import Final

import aiohttp
from aiohttp import ClientTimeout
from tqdm.asyncio import tqdm  # type: ignore
from userprovided import ip as ip_check

from salted import database_io, err
from salted.rate_limiter import DomainRateLimiter


class UrlCheck:
    """Interact with the network to check URLs."""
    # pylint: disable=too-many-instance-attributes

    MAX_REDIRECTS: Final[int] = 3
    REDIRECT_CODES: Final[tuple] = (301, 302, 303, 307, 308)

    def __init__(self,
                 user_agent: str,
                 db: database_io.DatabaseIO,
                 workers: int | str = 'automatic',
                 timeout_sec: int = 5,
                 ignore_urls: set | None = None,
                 domain_delay: float = 0.25,
                 ignore_domains: set | None = None,
                 quiet: bool = False
                 ) -> None:
        """Initialize the URL checker.

        Args:
            user_agent: HTTP User-Agent header value to send with requests.
            db: Database I/O handler for logging results.
            workers: Number of async worker coroutines, or 'automatic' to
                auto-size based on URL count.
            timeout_sec: Request timeout in seconds.
            ignore_urls: Set of URLs to skip during checking.
            domain_delay: Minimum delay in seconds between requests to the
                same domain. Set to 0 to disable.
            ignore_domains: Set of hostnames to skip entirely.
            quiet: If True, suppress progress messages.
        """
        # pylint: disable=too-many-arguments
        self.headers: dict = dict()
        if user_agent:
            self.headers = {'User-Agent': user_agent}

        self.db = db
        self.timeout = int(timeout_sec)
        self.ignore_urls = ignore_urls if ignore_urls else set()
        self.ignore_domains = ignore_domains if ignore_domains else set()

        self.num_workers: int | str = workers
        self.quiet = quiet

        self.cnt: Counter = Counter()

        self.pbar_links: tqdm | None = None

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
            ValueError: If num_checks is less than 1, or if a user-set
                number of workers is below 1. Zero workers would leave the
                queue without consumers and block forever on queue.join().
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
            if recommendation < 1:
                raise ValueError(
                    "num_workers must be a positive integer (>= 1) "
                    "or 'automatic'.")
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
                return await self.__get_with_safe_redirects(url)
            return response.status

    async def __get_with_safe_redirects(self,
                                        url: str) -> int:
        """Send a GET request, following redirects with a check per hop.

        aiohttp's automatic redirect handling does not re-check redirect
        targets, so a malicious server could bounce the request to a
        private or internal address that the SSRF preflight on the
        original URL never saw. Therefore redirects are followed manually
        (up to MAX_REDIRECTS) and every target is run through the SSRF
        preflight before it is requested.

        Args:
            url: The URL to request.

        Returns:
            HTTP status code of the final response. A redirect without a
            Location header returns that redirect's status code.

        Raises:
            err.RedirectBlockedException: If a redirect target fails the
                SSRF preflight or uses a non-HTTP scheme.
            err.TooManyRedirectsException: If the chain exceeds
                MAX_REDIRECTS redirects.
        """
        current_url = url
        for _ in range(self.MAX_REDIRECTS + 1):
            async with self.session.get(
                    current_url,
                    headers=self.headers,
                    raise_for_status=False,
                    allow_redirects=False,
                    timeout=ClientTimeout(total=self.timeout)) as response:
                if response.status not in self.REDIRECT_CODES:
                    return response.status
                location = response.headers.get('Location')
                if not location:
                    # Redirect without a target: report the status itself.
                    return response.status
                # Location may be relative (RFC 9110 allows it).
                next_url = urllib.parse.urljoin(current_url, location)
                scheme = urllib.parse.urlparse(next_url).scheme
                if scheme not in ('http', 'https'):
                    raise err.RedirectBlockedException(
                        f"Blocked: redirect to unsupported scheme ({scheme})")
                if ip_check.is_potential_ssrf_target(next_url):
                    raise err.RedirectBlockedException(
                        'Blocked: redirect to private/internal target')
                current_url = next_url
        raise err.TooManyRedirectsException(
            f"More than {self.MAX_REDIRECTS} redirects")

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

        if urllib.parse.urlparse(url).hostname in self.ignore_domains:
            self.cnt['ignored_domains'] += 1
            return

        if ip_check.is_potential_ssrf_target(url):
            self.db.log_exception(url, 'Blocked: private/internal target')
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
            elif response_code in (404, 410):
                self.db.log_error(url, response_code)
            elif response_code == 403:
                # 403 is ambiguous: often bot/WAF blocking rather than a dead
                # link. Report as an inconclusive exception, not a hard error.
                self.db.log_exception(url, 'Forbidden (403) - may be bot detection')
            elif response_code == 429:
                self.db.log_exception(url, 'Rate Limit (429)')
            else:
                self.db.log_exception(url, f"Other ({response_code})")
        # Log but do not raise. Raising leads to the worker not returning
        # and the application does not finish the loop.
        except err.RedirectBlockedException as exc:
            self.db.log_exception(url, str(exc))
        except err.TooManyRedirectsException:
            self.db.log_exception(url, 'Too many redirects')
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
        except Exception as exc:
            logging.exception('Exception. URL %s', url, exc_info=True)
            self.db.log_exception(url, f"Unexpected error ({type(exc).__name__})")

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
            if self.pbar_links is not None:
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
        try:
            for i in range(int(self.num_workers)):
                task = asyncio.create_task(self.__worker(f'worker-{i}', queue))
                tasks.append(task)
            await queue.join()
        finally:
            for task in tasks:
                task.cancel()
            await self.__close_session()
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
        if not self.quiet:
            print(f"{num_checks} URLs to check with {self.num_workers} workers:")
        self.pbar_links = tqdm(total=num_checks, disable=self.quiet or not sys.stdout.isatty())
        try:
            asyncio.run(self.__distribute_work(urls_to_check))
        finally:
            self.pbar_links.close()
