#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Domain-based Rate Limiting for URL checks
~~~~~~~~~~~~~~~~~~~~~
Smart, Asynchronous Link Tester with Database backend (SALTED)
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2025: Released under the Apache License 2.0
"""

import asyncio
import logging
import time
from typing import Dict

from userprovided.url import extract_domain


class DomainRateLimiter:
    """
    Rate limiter that enforces minimum delay between requests to the same domain.
    Thread-safe for async operations using asyncio locks.

    Uses userprovided.url.extract_domain() for robust domain extraction with
    proper handling of multi-part TLDs (e.g., .co.uk, .com.au).
    """

    def __init__(self, delay_seconds: float = 0.25, drop_subdomain: bool = True):
        """
        Initialize the rate limiter.

        Args:
            delay_seconds: Minimum seconds to wait between requests to same domain.
                          Default is 0.25 (250ms) to be respectful to servers.
                          Set to 0.0 to disable rate limiting.
            drop_subdomain: If True, rate limit at the registrable domain level
                           (e.g., 'example.com' instead of 'www.example.com').
                           This means www.example.com and api.example.com share
                           the same rate limit. Default is True.
        """
        self.delay_seconds = float(delay_seconds)
        self.drop_subdomain = drop_subdomain
        self.last_request_time: Dict[str, float] = {}
        self.locks: Dict[str, asyncio.Lock] = {}
        self.global_lock = asyncio.Lock()

    def _get_domain_key(self, url: str) -> str:
        """
        Extract the domain from URL to use as rate limiting key.

        Args:
            url: Full URL string

        Returns:
            Domain string to use for rate limiting

        Raises:
            ValueError: If domain extraction fails
        """
        try:
            return extract_domain(url, drop_subdomain=self.drop_subdomain)
        except ValueError as e:
            logging.warning(f"Failed to extract domain from {url}: {e}")
            # Re-raise to let caller handle
            raise

    async def _get_domain_lock(self, domain: str) -> asyncio.Lock:
        """
        Get or create a lock for a specific domain.

        Args:
            domain: Domain string

        Returns:
            asyncio.Lock for that domain
        """
        async with self.global_lock:
            if domain not in self.locks:
                self.locks[domain] = asyncio.Lock()
            return self.locks[domain]

    async def wait_if_needed(self, url: str) -> None:
        """
        Wait if necessary to respect rate limit for the domain.
        This method is async and will sleep if needed.

        Args:
            url: The URL to check rate limit for
        """
        if self.delay_seconds <= 0:
            # Rate limiting disabled
            return

        try:
            domain = self._get_domain_key(url)
        except ValueError:
            # If we can't extract domain, skip rate limiting for this URL
            return

        if not domain:
            return

        # Get the lock for this domain to prevent race conditions
        domain_lock = await self._get_domain_lock(domain)

        async with domain_lock:
            current_time = time.time()

            if domain in self.last_request_time:
                time_since_last_request = current_time - self.last_request_time[domain]

                if time_since_last_request < self.delay_seconds:
                    sleep_time = self.delay_seconds - time_since_last_request
                    logging.debug(
                        f"Rate limiting {domain}: sleeping {sleep_time:.3f}s "
                        f"(last request {time_since_last_request:.3f}s ago)"
                    )
                    await asyncio.sleep(sleep_time)
                    current_time = time.time()  # Update after sleep

            # Record the request time
            self.last_request_time[domain] = current_time

    def get_stats(self) -> Dict:
        """
        Get statistics about tracked domains.

        Returns:
            Dictionary with statistics
        """
        return {
            'tracked_domains': len(self.last_request_time),
            'delay_seconds': self.delay_seconds,
            'drop_subdomain': self.drop_subdomain,
            'enabled': self.delay_seconds > 0
        }
