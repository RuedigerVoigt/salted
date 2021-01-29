#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Check DOI via the API
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2021: Released under the Apache License 2.0
"""
import asyncio
import logging

import aiohttp
from tqdm.asyncio import tqdm  # type: ignore


class DoiCheck:
    """Interact with the API to check DOIs."""

    API_BASE_URL = 'https://api.crossref.org/works/'
    NUM_API_WORKERS = 4 # TO DO: rate limiter!

    def __init__(self,
                 db_io) -> None:

        self.db = db_io

        # Do NOT conceal the user agent for API requests.
        # There is no UA block and this makes it easier to report problems.
        self.headers = {'User-Agent': 'salted / 0.7'}

        self.session = None
        self.timeout_sec = 3

        # Very reasonable defaults for the rate limit (10% of the default
        # values of the API) until HTTP headers give the actual limit:
        self.max_queries = 5
        self.timewindow = 1

        self.pbar_doi: tqdm = None

        self.valid_doi_list = list()

    async def __create_session(self):
        self.session = aiohttp.ClientSession(loop=asyncio.get_running_loop())

    async def __close_session(self):
        "Close the session object once it is no longer needed."
        if self.session:
            await self.session.close()

    async def __api_send_head_request(self,
                                      doi: str) -> dict:
        """Send a HTTP Head request to the server and return the status code
           (tells us if the DOI exists or not) plus information about the rate
           limit."""
        # The HTTP HEAD method requests the headers, but not the page's body.
        # Requesting this way reduces load on the server and network traffic.
        query_url = self.API_BASE_URL + doi
        async with self.session.get(
            query_url,
            headers=self.headers,
            raise_for_status=False,
            timeout=self.timeout_sec) as response:
                return {'status': response.status,
                        'max_queries': response.headers['X-Rate-Limit-Limit'],
                        'timewindow': response.headers['X-Rate-Limit-Interval']}

    async def __worker(self,
                       name: str,
                       queue: asyncio.Queue) -> None:
        doi = await queue.get()
        api_response = await self.__api_send_head_request(doi)
        if api_response['status'] == 200:
            self.valid_doi_list.append(doi)
        elif api_response['status'] == '404':
            print('DOI does not exist!')
        else:
            print('Unexpected API response!')
        # TO DO: remove with rate limiter
        await asyncio.sleep(0.25)
        # TO DO
        # api_response['max_queries']
        # api_response['timewindow']
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

    def __get_dois_to_check(self):
        "Check the database if there are any DOI to validate."
        # TO DO
        # FOR TESTS
        dois_to_check = ['10.1016/j.jebo.2014.12.018', '10.1017/S0020818309990191']
        return dois_to_check

    def __store_valid_doi(self) -> None:
        "Store valid DOIs in the database"
        # TO DO
        return

    def check_dois(self) -> None:
        dois_to_check = self.__get_dois_to_check()
        if not dois_to_check:
            logging.debug('No DOIs to check.')
            return
        num_doi = len(dois_to_check)
        print(f"{num_doi} DOI to check:")
        self.pbar_doi = tqdm(total=num_doi)

        asyncio.run(self.__distribute_work(dois_to_check))

        print(self.valid_doi_list)
