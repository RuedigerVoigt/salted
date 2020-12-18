#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Network interactions for salted.
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020: Released under the Apache License 2.0
"""
import asyncio
from collections import Counter
import logging

import aiohttp

from salted import database_io


class NetworkInteraction:
    """Interacts with the network to check hyperlinks."""

    def __init__(self,
                 db: database_io.DatabaseIO,
                 timeout_sec: int,
                 user_agent: str) -> None:
        self.db = db
        self.timeout_sec = timeout_sec

        self.headers: dict = dict()
        if user_agent:
            self.headers = {'User-Agent': user_agent}

        self.session = aiohttp.ClientSession(loop=asyncio.get_running_loop())

        self.cnt: Counter = Counter()

    async def close_session(self):
        """Close the session object once it is no longer needed"""
        if self.session:
            await self.session.close()

    async def head_request(self,
                           url: str) -> int:
        """The HTTP HEAD method requests the headers, but not the body of
           a page. Requesting this way reduces load on the server and
           reduces network traffic."""
        async with self.session.get(url,
                                    headers=self.headers,
                                    raise_for_status=False,
                                    timeout=self.timeout_sec) as response:
            return response.status

    async def full_request(self,
                           url: str) -> int:
        """ Some servers do not understand or block a HTTP HEAD request.
            In those cases this function can try a full request.
            This carries the risk of encountering very large pages.
            Therefore the read is limited."""

        async with self.session.get(url,
                                    headers=self.headers,
                                    raise_for_status=False,
                                    timeout=self.timeout_sec) as response:
            await response.content.read(100)

        return response.status

    async def check_url(self,
                        url: str,
                        request_type: str) -> None:
        """Check the URL by using a HTTP HEAD request (or if necessary a full
           request with limited data read) to check the link and log the result
           to the database. """
        # pylint: disable=too-many-branches
        try:
            if request_type == 'head':
                response_code = await self.head_request(url)
            elif request_type == 'full':
                response_code = await self.full_request(url)
                self.cnt['neededFullRequest'] += 1

            if response_code in (200, 302, 303, 307):
                self.cnt['fine'] += 1
                self.db.log_url_is_fine(url)
            elif response_code in (301, 308):
                self.db.log_redirect(url, response_code)
            elif response_code == 403:
                if request_type == 'head':
                    await self.check_url(url, 'full')
                else:
                    self.db.log_error(url, 403)
            elif response_code in (404, 410):
                self.db.log_error(url, response_code)
            elif response_code == 429:
                self.db.log_exception(url, 'Rate Limit (429)')
            else:
                if request_type == 'head':
                    await self.check_url(url, 'full')
                else:
                    self.db.log_exception(url, f"Other ({response_code})")
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
            raise
