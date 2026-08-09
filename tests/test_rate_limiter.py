#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Tests for the domain-based rate limiter
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2025: Released under the Apache License 2.0
"""

import asyncio
import time
import pytest

from salted.rate_limiter import DomainRateLimiter


class TestRateLimiterBasics:
    """Test basic rate limiter functionality"""

    @pytest.mark.asyncio
    async def test_initialization_defaults(self):
        """Test rate limiter initializes with correct defaults"""
        limiter = DomainRateLimiter()
        assert limiter.delay_seconds == 0.25
        assert limiter.drop_subdomain is True
        assert len(limiter.last_request_time) == 0

    @pytest.mark.asyncio
    async def test_initialization_custom_values(self):
        """Test rate limiter with custom values"""
        limiter = DomainRateLimiter(delay_seconds=0.5, drop_subdomain=False)
        assert limiter.delay_seconds == 0.5
        assert limiter.drop_subdomain is False

    @pytest.mark.asyncio
    async def test_disabled_rate_limiter(self):
        """Test that rate limiter with delay=0 does not delay"""
        limiter = DomainRateLimiter(delay_seconds=0.0)

        start = time.time()
        for i in range(5):
            await limiter.wait_if_needed(f'https://example.com/page{i}')
        elapsed = time.time() - start

        # Should complete almost instantly
        assert elapsed < 0.1
        # Disabled: wait_if_needed returns before recording anything
        assert len(limiter.last_request_time) == 0


class TestDomainExtraction:
    """Test domain extraction logic"""

    @pytest.mark.asyncio
    async def test_extract_domain_basic(self):
        """Test basic domain extraction"""
        limiter = DomainRateLimiter()

        domain = limiter._get_domain_key('https://www.example.com/path')
        assert domain == 'example.com'  # drop_subdomain=True by default

    @pytest.mark.asyncio
    async def test_extract_domain_with_subdomain_kept(self):
        """Test domain extraction without dropping subdomain"""
        limiter = DomainRateLimiter(drop_subdomain=False)

        domain = limiter._get_domain_key('https://www.example.com/path')
        assert domain == 'www.example.com'

    @pytest.mark.asyncio
    async def test_extract_domain_multi_part_tld(self):
        """Test extraction with multi-part TLD"""
        limiter = DomainRateLimiter()

        domain = limiter._get_domain_key('https://www.example.co.uk/path')
        assert domain == 'example.co.uk'

    @pytest.mark.asyncio
    async def test_extract_domain_with_port(self):
        """Test extraction removes port"""
        limiter = DomainRateLimiter(drop_subdomain=False)

        domain = limiter._get_domain_key('https://example.com:8080/path')
        assert domain == 'example.com'

    @pytest.mark.asyncio
    async def test_extract_domain_invalid_url(self):
        """Test extraction with invalid URL"""
        limiter = DomainRateLimiter()

        with pytest.raises(ValueError):
            limiter._get_domain_key('')


class TestRateLimitingBehavior:
    """Test actual rate limiting behavior"""

    @pytest.mark.asyncio
    async def test_first_request_no_delay(self):
        """Test first request to a domain has no delay"""
        limiter = DomainRateLimiter(delay_seconds=1.0)

        start = time.time()
        await limiter.wait_if_needed('https://example.com/page1')
        elapsed = time.time() - start

        # First request should be instant
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_second_request_delayed(self):
        """Test second request to same domain is delayed"""
        limiter = DomainRateLimiter(delay_seconds=0.5)

        await limiter.wait_if_needed('https://example.com/page1')

        start = time.time()
        await limiter.wait_if_needed('https://example.com/page2')
        elapsed = time.time() - start

        # Should wait approximately 0.5s
        assert 0.4 < elapsed < 0.6

    @pytest.mark.asyncio
    async def test_different_domains_no_delay(self):
        """Test requests to different domains are not delayed"""
        limiter = DomainRateLimiter(delay_seconds=1.0)

        start = time.time()
        await limiter.wait_if_needed('https://example.com/page')
        await limiter.wait_if_needed('https://different.org/page')
        await limiter.wait_if_needed('https://another.net/page')
        elapsed = time.time() - start

        # Should be instant for different domains
        assert elapsed < 0.1
        assert len(limiter.last_request_time) == 3

    @pytest.mark.asyncio
    async def test_same_domain_different_subdomains_shared_limit(self):
        """Test that subdomains share rate limit when drop_subdomain=True"""
        limiter = DomainRateLimiter(delay_seconds=0.5, drop_subdomain=True)

        await limiter.wait_if_needed('https://www.example.com/page1')

        start = time.time()
        await limiter.wait_if_needed('https://api.example.com/page2')
        elapsed = time.time() - start

        # Should be delayed because both resolve to 'example.com'
        assert 0.4 < elapsed < 0.6
        assert len(limiter.last_request_time) == 1

    @pytest.mark.asyncio
    async def test_same_domain_different_subdomains_separate_limit(self):
        """Test that subdomains have separate limits when drop_subdomain=False"""
        limiter = DomainRateLimiter(delay_seconds=0.5, drop_subdomain=False)

        await limiter.wait_if_needed('https://www.example.com/page1')

        start = time.time()
        await limiter.wait_if_needed('https://api.example.com/page2')
        elapsed = time.time() - start

        # Should NOT be delayed because they're different subdomains
        assert elapsed < 0.1
        assert len(limiter.last_request_time) == 2

    @pytest.mark.asyncio
    async def test_wait_after_delay_passes(self):
        """Test that waiting long enough resets the delay"""
        limiter = DomainRateLimiter(delay_seconds=0.2)

        await limiter.wait_if_needed('https://example.com/page1')
        await asyncio.sleep(0.3)  # Wait longer than delay

        start = time.time()
        await limiter.wait_if_needed('https://example.com/page2')
        elapsed = time.time() - start

        # Should be instant because enough time has passed
        assert elapsed < 0.1


class TestConcurrency:
    """Test concurrent access from several coroutines (not threads)"""

    @pytest.mark.asyncio
    async def test_concurrent_requests_different_domains(self):
        """Test concurrent requests to different domains"""
        limiter = DomainRateLimiter(delay_seconds=0.3)

        urls = [
            'https://example1.com/page',
            'https://example2.com/page',
            'https://example3.com/page',
            'https://example4.com/page',
        ]

        start = time.time()
        await asyncio.gather(*[limiter.wait_if_needed(url) for url in urls])
        elapsed = time.time() - start

        # Should all complete quickly (no delays for different domains)
        assert elapsed < 0.2
        assert len(limiter.last_request_time) == 4

    @pytest.mark.asyncio
    async def test_concurrent_requests_same_domain(self):
        """Test concurrent requests to same domain are serialized"""
        limiter = DomainRateLimiter(delay_seconds=0.2)

        urls = [
            'https://example.com/page1',
            'https://example.com/page2',
            'https://example.com/page3',
        ]

        start = time.time()
        await asyncio.gather(*[limiter.wait_if_needed(url) for url in urls])
        elapsed = time.time() - start

        # Should take approximately delay * (n-1) seconds
        # 3 requests with 0.2s delay = ~0.4s total
        assert 0.3 < elapsed < 0.5
        assert len(limiter.last_request_time) == 1


class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_invalid_url_gracefully_handled(self):
        """Test that invalid URLs don't crash the rate limiter"""
        limiter = DomainRateLimiter()

        # Should not raise exception, just skip rate limiting
        await limiter.wait_if_needed('')

        assert len(limiter.last_request_time) == 0

    @pytest.mark.asyncio
    async def test_negative_delay_treated_as_disabled(self):
        """Test negative delay is treated as disabled"""
        limiter = DomainRateLimiter(delay_seconds=-1.0)

        start = time.time()
        await limiter.wait_if_needed('https://example.com/page1')
        await limiter.wait_if_needed('https://example.com/page2')
        elapsed = time.time() - start

        # Should be instant
        assert elapsed < 0.1
        # Negative delay disables the limiter, so nothing is recorded
        assert len(limiter.last_request_time) == 0
