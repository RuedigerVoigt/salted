#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit Tests for URL Checking functionality in SALTED
Focuses on testing previously untested components with mocking.
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import pytest
import aiohttp
from aiohttp import ClientSession, ClientResponse, ClientTimeout

from salted import url_check, database_io, memory_instance


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
        """Test client error codes (403, 404, 410)."""
        test_cases = [
            (403, "Forbidden"),
            (404, "Not Found"),
            (410, "Gone")
        ]
        
        for status_code, description in test_cases:
            with patch.object(url_checker, 'head_request', return_value=status_code):
                await url_checker.validate_url("https://broken.com")
                
                mock_db.log_error.assert_called_with("https://broken.com", status_code)
                mock_db.reset_mock()

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
        """Test unexpected exception handling (logs but doesn't crash)."""
        with patch.object(url_checker, 'head_request', side_effect=ValueError("Unexpected error")):
            with patch('salted.url_check.logging.exception') as mock_log:
                await url_checker.validate_url("https://unexpected.com")
                
                # Should log exception but not crash
                mock_log.assert_called_once()
                assert "https://unexpected.com" in str(mock_log.call_args)


class TestWorkerRecommendation:
    """Test worker recommendation logic (already tested but adding edge cases)."""

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


class TestCheckUrlsAsync:
    """Test async check_urls_async method"""

    @pytest.mark.asyncio
    async def test_check_urls_async_no_urls(self):
        """Test check_urls_async when there are no URLs to check"""
        mock_db = Mock(spec=database_io.DatabaseIO)
        mock_db.urls_to_check = Mock(return_value=None)

        url_checker = url_check.UrlCheck(
            user_agent="test",
            db=mock_db,
            workers=4,
            timeout_sec=5
        )

        # Should return early without error (no exception raised)
        await url_checker.check_urls_async()

    @pytest.mark.asyncio
    @patch('salted.url_check.tqdm')
    async def test_check_urls_async_with_urls(self, mock_tqdm):
        """Test check_urls_async with URLs to process"""
        mock_db = Mock(spec=database_io.DatabaseIO)
        mock_db.urls_to_check = Mock(return_value=[
            ('https://example.com',),
            ('https://test.com',)
        ])

        url_checker = url_check.UrlCheck(
            user_agent="test",
            db=mock_db,
            workers=4,
            timeout_sec=5
        )

        # Mock the distribute_work method to avoid actual async execution
        url_checker._UrlCheck__distribute_work = AsyncMock()

        await url_checker.check_urls_async()

        # Verify progress bar was created
        assert mock_tqdm.called

        # Verify async distribute_work was called
        url_checker._UrlCheck__distribute_work.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
