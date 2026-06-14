#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit Tests for URL Checking functionality in SALTED
Focuses on testing previously untested components with mocking.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import pytest
import aiohttp
from aiohttp import ClientResponse

from salted import url_check, database_io


@pytest.fixture
def mock_db():
    """Create a mock database for testing."""
    mock_db = MagicMock(spec=database_io.DatabaseIO)
    return mock_db


@pytest.fixture
def url_checker(mock_db):
    """Create a UrlCheck instance with mocked database."""
    return url_check.UrlCheck(
        user_agent="test-agent/1.0",
        db=mock_db,
        workers='automatic',
        timeout_sec=10,
        ignore_urls={"https://ignored.com"}
    )


class TestHeadRequestFallback:
    """Test our HEAD → GET fallback logic (the performance fix)."""

    @pytest.mark.asyncio
    async def test_head_request_success(self, url_checker):
        """Test successful HEAD request (no fallback needed)."""
        mock_response = AsyncMock(spec=ClientResponse)
        mock_response.status = 200

        with patch.object(url_checker, 'session') as mock_session:
            mock_session.head.return_value.__aenter__.return_value = mock_response

            status = await url_checker.head_request("https://example.com")

            assert status == 200
            mock_session.head.assert_called_once()
            mock_session.get.assert_not_called()  # No fallback needed

    @pytest.mark.asyncio
    async def test_head_request_405_fallback(self, url_checker):
        """Test HEAD returns 405 → falls back to GET (our fix!)."""
        mock_head_response = AsyncMock(spec=ClientResponse)
        mock_head_response.status = 405  # Method Not Allowed

        mock_get_response = AsyncMock(spec=ClientResponse)
        mock_get_response.status = 200  # GET works fine

        with patch.object(url_checker, 'session') as mock_session:
            mock_session.head.return_value.__aenter__.return_value = mock_head_response
            mock_session.get.return_value.__aenter__.return_value = mock_get_response

            status = await url_checker.head_request("https://no-head-support.com")

            assert status == 200
            mock_session.head.assert_called_once()
            mock_session.get.assert_called_once()  # Fallback triggered
            # Ensure fallback counter was incremented
            assert url_checker.cnt['neededFullRequest'] == 1

    @pytest.mark.asyncio
    async def test_head_request_405_fallback_also_fails(self, url_checker):
        """Test HEAD returns 405 → GET fallback also returns error."""
        mock_head_response = AsyncMock(spec=ClientResponse)
        mock_head_response.status = 405

        mock_get_response = AsyncMock(spec=ClientResponse)
        mock_get_response.status = 404  # GET also fails

        with patch.object(url_checker, 'session') as mock_session:
            mock_session.head.return_value.__aenter__.return_value = mock_head_response
            mock_session.get.return_value.__aenter__.return_value = mock_get_response

            status = await url_checker.head_request("https://broken.com")

            assert status == 404
            mock_session.head.assert_called_once()
            mock_session.get.assert_called_once()


    @pytest.mark.asyncio
    async def test_head_request_other_error_no_fallback(self, url_checker):
        """Test HEAD returns non-405 error → no fallback."""
        mock_response = AsyncMock(spec=ClientResponse)
        mock_response.status = 404  # Not found, but not method not allowed

        with patch.object(url_checker, 'session') as mock_session:
            mock_session.head.return_value.__aenter__.return_value = mock_response

            status = await url_checker.head_request("https://not-found.com")

            assert status == 404
            mock_session.head.assert_called_once()
            mock_session.get.assert_not_called()  # No fallback for 404


def _response(status, location=None):
    """Build a mock response with a real headers dict."""
    response = MagicMock()
    response.status = status
    response.headers = {'Location': location} if location else {}
    return response


def _mock_get_sequence(mock_session, responses):
    """Make consecutive session.get() calls yield the given responses."""
    managers = []
    for response in responses:
        manager = MagicMock()
        manager.__aenter__ = AsyncMock(return_value=response)
        manager.__aexit__ = AsyncMock(return_value=False)
        managers.append(manager)
    mock_session.get.side_effect = managers


class TestSafeRedirects:
    """The GET fallback follows redirects with an SSRF check per hop."""

    @pytest.mark.asyncio
    async def test_redirect_chain_followed_to_final_status(self, url_checker):
        """Redirects are still followed; the final status is returned."""
        with patch.object(url_checker, 'session') as mock_session:
            _mock_get_sequence(mock_session, [
                _response(301, 'https://example.com/new'),
                _response(200),
            ])
            status = await url_checker._UrlCheck__get_with_safe_redirects(
                'https://example.com/old')
            assert status == 200
            assert mock_session.get.call_count == 2
            # Hops are requested manually, never auto-followed by aiohttp:
            for call in mock_session.get.call_args_list:
                assert call.kwargs['allow_redirects'] is False

    @pytest.mark.asyncio
    async def test_relative_redirect_resolved(self, url_checker):
        """A relative Location header is resolved against the current URL."""
        with patch.object(url_checker, 'session') as mock_session:
            _mock_get_sequence(mock_session, [
                _response(302, '/new'),
                _response(200),
            ])
            await url_checker._UrlCheck__get_with_safe_redirects(
                'https://example.com/old')
            second_call_url = mock_session.get.call_args_list[1].args[0]
            assert second_call_url == 'https://example.com/new'

    @pytest.mark.asyncio
    async def test_redirect_to_private_target_blocked(self, url_checker):
        """A redirect into private/internal address space must be blocked."""
        with patch.object(url_checker, 'session') as mock_session:
            _mock_get_sequence(mock_session, [
                _response(302, 'http://169.254.169.254/latest/meta-data/'),
            ])
            with pytest.raises(url_check.err.RedirectBlockedException,
                               match='private/internal'):
                await url_checker._UrlCheck__get_with_safe_redirects(
                    'https://example.com/')
            # The blocked target must never be requested.
            assert mock_session.get.call_count == 1

    @pytest.mark.asyncio
    async def test_redirect_to_non_http_scheme_blocked(self, url_checker):
        """A redirect to a non-HTTP scheme must be blocked."""
        with patch.object(url_checker, 'session') as mock_session:
            _mock_get_sequence(mock_session, [
                _response(302, 'file:///etc/passwd'),
            ])
            with pytest.raises(url_check.err.RedirectBlockedException,
                               match='scheme'):
                await url_checker._UrlCheck__get_with_safe_redirects(
                    'https://example.com/')
            assert mock_session.get.call_count == 1

    @pytest.mark.asyncio
    async def test_too_many_redirects_raises(self, url_checker):
        """A chain longer than MAX_REDIRECTS raises instead of looping."""
        with patch.object(url_checker, 'session') as mock_session:
            _mock_get_sequence(mock_session, [
                _response(301, f'https://example.com/{i}') for i in range(5)
            ])
            with pytest.raises(url_check.err.TooManyRedirectsException):
                await url_checker._UrlCheck__get_with_safe_redirects(
                    'https://example.com/')
            assert mock_session.get.call_count == url_check.UrlCheck.MAX_REDIRECTS + 1

    @pytest.mark.asyncio
    async def test_redirect_without_location_returns_status(self, url_checker):
        """A redirect without a Location header reports its own status."""
        with patch.object(url_checker, 'session') as mock_session:
            _mock_get_sequence(mock_session, [_response(301)])
            status = await url_checker._UrlCheck__get_with_safe_redirects(
                'https://example.com/')
            assert status == 301

    @pytest.mark.asyncio
    async def test_blocked_redirect_logged_as_exception(self, url_checker, mock_db):
        """validate_url reports a blocked redirect in the database."""
        with patch.object(
                url_checker, 'head_request',
                side_effect=url_check.err.RedirectBlockedException(
                    'Blocked: redirect to private/internal target')):
            await url_checker.validate_url('https://example.com/')
            mock_db.log_exception.assert_called_with(
                'https://example.com/',
                'Blocked: redirect to private/internal target')

    @pytest.mark.asyncio
    async def test_too_many_redirects_logged_as_exception(self, url_checker, mock_db):
        """validate_url reports an overlong redirect chain in the database."""
        with patch.object(
                url_checker, 'head_request',
                side_effect=url_check.err.TooManyRedirectsException()):
            await url_checker.validate_url('https://example.com/')
            mock_db.log_exception.assert_called_with(
                'https://example.com/', 'Too many redirects')


class TestValidateUrlStatusCodes:
    """Test HTTP status code categorization and database logging."""

    @pytest.mark.asyncio
    async def test_validate_url_success_codes(self, url_checker, mock_db):
        """Test successful response codes (200, 302, 303, 307)."""
        test_cases = [
            (200, "OK"),
            (302, "Found"),
            (303, "See Other"),
            (307, "Temporary Redirect")
        ]

        for status_code, description in test_cases:
            with patch.object(url_checker, 'head_request', return_value=status_code):
                await url_checker.validate_url("https://example.com")

                mock_db.log_url_is_fine.assert_called_with("https://example.com")
                assert url_checker.cnt['fine'] > 0
                mock_db.reset_mock()

    @pytest.mark.asyncio
    async def test_validate_url_permanent_redirects(self, url_checker, mock_db):
        """Test permanent redirect codes (301, 308)."""
        test_cases = [
            (301, "Moved Permanently"),
            (308, "Permanent Redirect")
        ]

        for status_code, description in test_cases:
            with patch.object(url_checker, 'head_request', return_value=status_code):
                await url_checker.validate_url("https://moved.com")

                mock_db.log_redirect.assert_called_with("https://moved.com", status_code)
                mock_db.reset_mock()

    @pytest.mark.asyncio
    async def test_validate_url_client_errors(self, url_checker, mock_db):
        """Test client error codes that mean a dead link (404, 410)."""
        test_cases = [
            (404, "Not Found"),
            (410, "Gone")
        ]

        for status_code, description in test_cases:
            with patch.object(url_checker, 'head_request', return_value=status_code):
                await url_checker.validate_url("https://broken.com")

                mock_db.log_error.assert_called_with("https://broken.com", status_code)
                mock_db.reset_mock()

    @pytest.mark.asyncio
    async def test_validate_url_forbidden_is_exception_not_error(self, url_checker, mock_db):
        """403 is inconclusive (often bot/WAF blocking), so it is logged as an
        exception rather than a hard dead-link error."""
        with patch.object(url_checker, 'head_request', return_value=403):
            await url_checker.validate_url("https://forbidden.com")

            mock_db.log_exception.assert_called_with(
                "https://forbidden.com", 'Forbidden (403) - may be bot detection')
            mock_db.log_error.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_url_rate_limit(self, url_checker, mock_db):
        """Test rate limiting (429)."""
        with patch.object(url_checker, 'head_request', return_value=429):
            await url_checker.validate_url("https://rate-limited.com")

            mock_db.log_exception.assert_called_with("https://rate-limited.com", 'Rate Limit (429)')

    @pytest.mark.asyncio
    async def test_validate_url_other_status_codes(self, url_checker, mock_db):
        """Test unknown/other status codes (500, 503, etc.)."""
        test_cases = [500, 502, 503, 999]

        for status_code in test_cases:
            with patch.object(url_checker, 'head_request', return_value=status_code):
                await url_checker.validate_url("https://server-error.com")

                mock_db.log_exception.assert_called_with(
                    "https://server-error.com",
                    f"Other ({status_code})"
                )
                mock_db.reset_mock()

    @pytest.mark.asyncio
    async def test_validate_url_ignored_urls(self, url_checker, mock_db):
        """Test that ignored URLs are skipped."""
        await url_checker.validate_url("https://ignored.com")

        assert url_checker.cnt['ignored_urls'] == 1
        assert url_checker.cnt['checked_urls'] == 0
        mock_db.log_url_is_fine.assert_not_called()


class TestNetworkExceptionHandling:
    """Test network exception scenarios."""

    @pytest.mark.asyncio
    async def test_validate_url_timeout(self, url_checker, mock_db):
        """Test timeout exception handling."""
        with patch.object(url_checker, 'head_request', side_effect=asyncio.TimeoutError()):
            await url_checker.validate_url("https://slow.com")

            mock_db.log_exception.assert_called_with("https://slow.com", 'Timeout')

    @pytest.mark.asyncio
    async def test_validate_url_connection_error(self, url_checker, mock_db):
        """Test connection error (DNS failure, etc.)."""
        with patch.object(url_checker, 'head_request',
                          side_effect=aiohttp.client_exceptions.ClientConnectorError("connection", OSError())):
            await url_checker.validate_url("https://nonexistent.com")

            mock_db.log_exception.assert_called_with("https://nonexistent.com", 'ClientConnectorError')

    @pytest.mark.asyncio
    async def test_validate_url_response_error(self, url_checker, mock_db):
        """Test malformed HTTP response."""
        with patch.object(url_checker, 'head_request',
                          side_effect=aiohttp.client_exceptions.ClientResponseError(None, None)):
            await url_checker.validate_url("https://malformed.com")

            mock_db.log_exception.assert_called_with("https://malformed.com", 'ClientResponseError')

    @pytest.mark.asyncio
    async def test_validate_url_os_error(self, url_checker, mock_db):
        """Test OS-level network error."""
        with patch.object(url_checker, 'head_request',
                          side_effect=aiohttp.client_exceptions.ClientOSError()):
            await url_checker.validate_url("https://os-error.com")

            mock_db.log_exception.assert_called_with("https://os-error.com", 'ClientOSError')

    @pytest.mark.asyncio
    async def test_validate_url_server_disconnected(self, url_checker, mock_db):
        """Test server disconnection during request."""
        with patch.object(url_checker, 'head_request',
                          side_effect=aiohttp.client_exceptions.ServerDisconnectedError()):
            await url_checker.validate_url("https://disconnects.com")

            mock_db.log_exception.assert_called_with("https://disconnects.com", 'Server disconnected')

    @pytest.mark.asyncio
    async def test_validate_url_unexpected_exception(self, url_checker, mock_db):
        """Unexpected exceptions are logged AND recorded so the URL still
        appears in the report instead of silently vanishing."""
        with patch.object(url_checker, 'head_request', side_effect=ValueError("boom")):
            with patch('salted.url_check.logging.exception') as mock_log:
                await url_checker.validate_url("https://unexpected.com")

                # Logged for debugging (with a traceback) ...
                mock_log.assert_called_once()
                assert "https://unexpected.com" in str(mock_log.call_args)
                # ... and recorded in the database so it shows up in the report.
                mock_db.log_exception.assert_called_with(
                    "https://unexpected.com", 'Unexpected error (ValueError)')


class TestSsrfPreflight:
    """Test that private/internal targets are blocked before network requests."""

    @pytest.mark.asyncio
    async def test_loopback_ipv4_blocked(self, url_checker, mock_db):
        """127.0.0.1 must not reach the network."""
        with patch.object(url_checker, 'head_request') as mock_req:
            await url_checker.validate_url("http://127.0.0.1/secret")
            mock_req.assert_not_called()
            mock_db.log_exception.assert_called_with(
                "http://127.0.0.1/secret", 'Blocked: private/internal target')

    @pytest.mark.asyncio
    async def test_localhost_blocked(self, url_checker, mock_db):
        """localhost must not reach the network."""
        with patch.object(url_checker, 'head_request') as mock_req:
            await url_checker.validate_url("http://localhost/admin")
            mock_req.assert_not_called()
            mock_db.log_exception.assert_called_with(
                "http://localhost/admin", 'Blocked: private/internal target')

    @pytest.mark.asyncio
    async def test_cloud_metadata_endpoint_blocked(self, url_checker, mock_db):
        """169.254.169.254 (AWS/GCP metadata) must be blocked."""
        with patch.object(url_checker, 'head_request') as mock_req:
            await url_checker.validate_url("http://169.254.169.254/latest/meta-data/")
            mock_req.assert_not_called()
            mock_db.log_exception.assert_called_with(
                "http://169.254.169.254/latest/meta-data/",
                'Blocked: private/internal target')

    @pytest.mark.asyncio
    async def test_rfc1918_private_range_blocked(self, url_checker, mock_db):
        """RFC1918 addresses (10.x, 172.16.x, 192.168.x) must be blocked."""
        private_urls = [
            "http://10.0.0.1/",
            "http://172.16.0.1/",
            "http://192.168.1.1/",
        ]
        for url in private_urls:
            mock_db.reset_mock()
            with patch.object(url_checker, 'head_request') as mock_req:
                await url_checker.validate_url(url)
                mock_req.assert_not_called()
                mock_db.log_exception.assert_called_with(
                    url, 'Blocked: private/internal target')

    @pytest.mark.asyncio
    async def test_dot_local_hostname_blocked(self, url_checker, mock_db):
        """mDNS .local hostnames must be blocked."""
        with patch.object(url_checker, 'head_request') as mock_req:
            await url_checker.validate_url("http://printer.local/")
            mock_req.assert_not_called()
            mock_db.log_exception.assert_called_with(
                "http://printer.local/", 'Blocked: private/internal target')

    @pytest.mark.asyncio
    async def test_public_url_not_blocked(self, url_checker, mock_db):
        """Public URLs must still be checked normally."""
        with patch.object(url_checker, 'head_request', return_value=200):
            await url_checker.validate_url("https://example.com/page")
            mock_db.log_url_is_fine.assert_called_with("https://example.com/page")


class TestWorkerRecommendation:
    """Test worker recommendation logic (already tested but adding edge cases)."""

    def test_recommend_workers_zero_raises(self, url_checker):
        """Zero URLs should raise ValueError."""
        with pytest.raises(ValueError):
            url_checker._UrlCheck__recommend_num_workers(0)

    def test_recommend_workers_5000_plus(self, url_checker):
        """Test our fix: 5000+ URLs should get 64 workers."""
        assert url_checker._UrlCheck__recommend_num_workers(5001) == 64
        assert url_checker._UrlCheck__recommend_num_workers(10000) == 64

    def test_recommend_workers_boundary_conditions(self, url_checker):
        """Test exact boundary conditions."""
        assert url_checker._UrlCheck__recommend_num_workers(1) == 4
        assert url_checker._UrlCheck__recommend_num_workers(24) == 4
        assert url_checker._UrlCheck__recommend_num_workers(25) == 12
        assert url_checker._UrlCheck__recommend_num_workers(99) == 12
        assert url_checker._UrlCheck__recommend_num_workers(100) == 32
        assert url_checker._UrlCheck__recommend_num_workers(5000) == 32
        assert url_checker._UrlCheck__recommend_num_workers(5001) == 64

    def test_user_set_zero_workers_raises(self, url_checker):
        """A user-set worker count of 0 must raise instead of hanging.

        Zero workers would leave the queue without consumers and the run
        would block forever on queue.join().
        """
        url_checker.num_workers = 0
        with pytest.raises(ValueError, match="num_workers"):
            url_checker._UrlCheck__recommend_num_workers(10)

    def test_user_set_negative_workers_raises(self, url_checker):
        """A user-set negative worker count must raise instead of hanging."""
        url_checker.num_workers = -4
        with pytest.raises(ValueError, match="num_workers"):
            url_checker._UrlCheck__recommend_num_workers(10)


class TestSessionManagement:
    """Test aiohttp session creation and cleanup."""

    @pytest.mark.asyncio
    async def test_create_session(self, url_checker):
        """Test session creation."""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            await url_checker._UrlCheck__create_session()

            assert url_checker.session == mock_session
            mock_session_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_session(self, url_checker):
        """Test session cleanup."""
        mock_session = AsyncMock()
        url_checker.session = mock_session

        await url_checker._UrlCheck__close_session()

        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_session_none(self, url_checker):
        """Test closing when session is None (shouldn't crash)."""
        url_checker.session = None

        # Should not raise exception
        await url_checker._UrlCheck__close_session()


class TestIgnoreDomains:
    """Test that URLs whose hostname is in ignore_domains are skipped."""

    @pytest.mark.asyncio
    async def test_url_on_ignored_domain_is_skipped(self, mock_db):
        """URL whose hostname matches ignore_domains must not be checked."""
        checker = url_check.UrlCheck(
            user_agent="test/1.0",
            db=mock_db,
            ignore_domains={"example.com"}
        )
        with patch.object(checker, 'head_request') as mock_req:
            await checker.validate_url("https://example.com/page")
            mock_req.assert_not_called()
        assert checker.cnt['ignored_domains'] == 1

    @pytest.mark.asyncio
    async def test_url_on_other_domain_is_not_skipped(self, mock_db):
        """URL on a different domain must still be checked."""
        checker = url_check.UrlCheck(
            user_agent="test/1.0",
            db=mock_db,
            ignore_domains={"example.com"}
        )
        with patch.object(checker, 'head_request', return_value=200):
            await checker.validate_url("https://other.com/page")
        assert checker.cnt['ignored_domains'] == 0

    @pytest.mark.asyncio
    async def test_subdomain_not_matched_by_parent_domain(self, mock_db):
        """Exact hostname match: sub.example.com is not ignored by example.com."""
        checker = url_check.UrlCheck(
            user_agent="test/1.0",
            db=mock_db,
            ignore_domains={"example.com"}
        )
        with patch.object(checker, 'head_request', return_value=200):
            await checker.validate_url("https://sub.example.com/page")
        assert checker.cnt['ignored_domains'] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
