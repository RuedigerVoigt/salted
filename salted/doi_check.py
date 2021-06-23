#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Check DOI via the API
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2021 Rüdiger Voigt
Released under the Apache License 2.0
"""
import asyncio
import logging
from typing import Final, Optional

import aiohttp
from tqdm.asyncio import tqdm  # type: ignore

from salted import database_io
from salted import _version


class DoiCheck:
    """Interact with the API to check DOIs."""
    # pylint: disable=too-few-public-methods

    API_BASE_URL: Final[str] = 'https://api.crossref.org/works/'
    NUM_API_WORKERS: Final[int] = 5

    def __init__(self,
                 db_io: database_io.DatabaseIO) -> None:

        self.db = db_io

        # Do NOT conceal the user agent for API requests.
        # The providers of the API explicitly ask that bots identify themselves
        # with an user agent, a project URL and a mailto address.
        # Requests of polite bots get directed to a separate pool of machines.
        # See: https://github.com/CrossRef/rest-api-doc
        self.headers = {'User-Agent': (
            f"salted/{_version.__version__} " +
            "(https://github.com/RuedigerVoigt/salted; " +
            "mailto:projects@ruediger-voigt.eu)")}

        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout_sec = 3

        self.pbar_doi: tqdm = None

        self.valid_doi_list: list = list()
        self.invalid_doi_list: list = list()

    async def __create_session(self) -> None:
        self.session = aiohttp.ClientSession(loop=asyncio.get_running_loop())

    async def __close_session(self) -> None:
        "Close the session object once it is no longer needed."
        if self.session:
            await self.session.close()

    async def __rate_limit_wait(self,
                                max_queries: int,
                                seconds: int
                                ) -> None:
        """Sleep long enough to keep the number of API requests within
        the rate limit. Always taking into account the newest values provided
        by the server."""

        if max_queries < 1:
            raise ValueError('Parameter "max_queries" must be an integer > 0.')
        if max_queries < 1:
            raise ValueError('Parameter "seconds" must be an integer > 0.')
        # Keep it at 90% to always be below the limit. This is still fast,
        # given that standard for that API is 50 requests/second.
        # Input is a positive int != 0 and round rounds up, so the smallest
        # amount this can take is 1:
        max_queries = round(max_queries * 0.9)
        # In a specified number of seconds, there is maximum number of queries.
        # As the work is distributed over multiple workers, the wait time has
        # to be multiplied by their number:
        time_to_sleep = float((seconds / max_queries) * self.NUM_API_WORKERS)
        logging.debug(f"wait time per worker for {max_queries} queries /" +
                      f" {seconds} s: {time_to_sleep}")
        await asyncio.sleep(time_to_sleep)
        return None

    async def __api_send_head_request(self,
                                      doi: str) -> dict:
        """Send a HTTP Head request to the server and return the status code
           (tells us if the DOI exists or not) plus information about the rate
           limit."""
        logging.debug("Sending head request to Crossref API: check %s", doi)
        # The HTTP HEAD method requests the headers, but not the page's body.
        # Requesting this way reduces load on the server and network traffic.
        query_url = self.API_BASE_URL + doi
        async with self.session.get(  # type: ignore
                query_url,
                headers=self.headers,
                raise_for_status=False,
                timeout=self.timeout_sec) as response:
            # format is 'numeric s'
            timewindow = response.headers['X-Rate-Limit-Interval']
            timewindow = timewindow.rstrip('s').strip()
            return {
                'max_queries':  response.headers['X-Rate-Limit-Limit'],
                'seconds':  timewindow,
                'status': response.status}

    async def __worker(self,
                       name: str,
                       queue: asyncio.Queue) -> None:
        """Worker: wait for the result of the API request and then wait long
           enough to stay within the rate limit."""
        # DO NOT REMOVE 'while True'. Without that the queue is stopped
        # after the first iteration.
        while True:
            doi = await queue.get()
            api_response = await self.__api_send_head_request(doi)
            if api_response['status'] == 200:
                logging.debug("DOI %s is valid", doi)
                self.valid_doi_list.append(doi)
            elif api_response['status'] == 404:
                logging.debug("DOI %s does not exist!", doi)
                self.invalid_doi_list.append(doi)
            else:
                print(f"Unexpected API response: {api_response['status']}")
            await self.__rate_limit_wait(
                int(api_response['max_queries']),
                int(api_response['seconds']))
            self.pbar_doi.update(1)
            queue.task_done()

    async def __distribute_work(self,
                                doi_list: list) -> None:
        """Start a queue and spawn workers to work in parallel."""
        queue: asyncio.Queue = asyncio.Queue()
        for entry in doi_list:
            queue.put_nowait(entry)

        await self.__create_session()

        tasks = []
        for i in range(int(self.NUM_API_WORKERS)):
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

    def check_dois(self) -> None:
        "Check the DOI in the queue and show a progress bar."
        dois_to_check = self.db.get_dois_to_check()
        if not dois_to_check:
            logging.debug('No DOIs to check.')
            return
        num_doi = len(dois_to_check)
        print(f"{num_doi} DOI to check:")
        self.pbar_doi = tqdm(total=num_doi)

        asyncio.run(self.__distribute_work(dois_to_check))
        # executemany needs a list of tuples:
        if self.valid_doi_list:
            self.db.save_valid_dois([(doi, ) for doi in self.valid_doi_list])
        if self.invalid_doi_list:
            self.db.log_invalid_dois([(doi, ) for doi in self.invalid_doi_list])
