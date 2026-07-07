#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Tests for DOI checking functionality
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2025: Released under the Apache License 2.0
"""

import asyncio
import aiohttp
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from salted.doi_check import DoiCheck
from salted import database_io


class TestDoiCheckInitialization:
    """Test DOI checker initialization"""

    def test_initialization(self):
        """Test basic initialization"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        doi_checker = DoiCheck(db_mock)

        assert doi_checker.db == db_mock
        assert doi_checker.session is None
        assert doi_checker.timeout_sec == 3
        assert doi_checker.valid_doi_list == []
        assert doi_checker.invalid_doi_list == []

    def test_user_agent_header(self):
        """Test that user agent header is properly set"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        doi_checker = DoiCheck(db_mock)

        assert 'User-Agent' in doi_checker.headers
        assert 'salted' in doi_checker.headers['User-Agent']
        assert 'github.com' in doi_checker.headers['User-Agent']
        assert 'mailto:' not in doi_checker.headers['User-Agent']  # mailto is optional; omitted when not configured

    def test_api_base_url_constant(self):
        """Test API base URL is set correctly"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        doi_checker = DoiCheck(db_mock)

        assert doi_checker.API_BASE_URL == 'https://api.crossref.org/works/'

    def test_num_workers_constant(self):
        """Test number of workers is set correctly"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        doi_checker = DoiCheck(db_mock)

        assert doi_checker.NUM_API_WORKERS == 5


class TestRateLimitWait:
    """Test rate limit waiting logic"""

    @pytest.mark.asyncio
    async def test_rate_limit_wait_calculates_correctly(self):
        """Test rate limit wait time calculation"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        doi_checker = DoiCheck(db_mock)

        # Simulate a request was just sent so the full interval is slept.
        doi_checker._last_send = asyncio.get_event_loop().time()

        # With 50 req/s at 90%: interval = 1 / round(45) ≈ 0.022s
        import time
        start = time.time()
        await doi_checker._DoiCheck__rate_limit_wait(50, 1)
        elapsed = time.time() - start

        assert 0.01 < elapsed < 0.05

    @pytest.mark.asyncio
    async def test_rate_limit_wait_invalid_max_queries_zero(self):
        """Test rate limit with invalid max_queries raises error"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        doi_checker = DoiCheck(db_mock)

        with pytest.raises(ValueError) as exc_info:
            await doi_checker._DoiCheck__rate_limit_wait(0, 1)

        assert 'max_queries' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_rate_limit_wait_invalid_seconds_zero(self):
        """Test rate limit with invalid seconds raises error"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        doi_checker = DoiCheck(db_mock)

        with pytest.raises(ValueError) as exc_info:
            await doi_checker._DoiCheck__rate_limit_wait(50, 0)

        assert 'seconds' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_rate_limit_wait_uses_90_percent(self):
        """Test that rate limiter uses 90% of max to stay safe"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        doi_checker = DoiCheck(db_mock)

        # Simulate a request was just sent so the full interval is slept.
        doi_checker._last_send = asyncio.get_event_loop().time()

        # With 100 req/s at 90%: interval = 1 / round(90) ≈ 0.011s
        import time
        start = time.time()
        await doi_checker._DoiCheck__rate_limit_wait(100, 1)
        elapsed = time.time() - start

        assert 0.005 < elapsed < 0.03


class TestSessionManagement:
    """Test session creation and closing"""

    @pytest.mark.asyncio
    async def test_create_session(self):
        """Test session creation"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        doi_checker = DoiCheck(db_mock)

        await doi_checker._DoiCheck__create_session()

        assert isinstance(doi_checker.session, aiohttp.ClientSession)
        assert not doi_checker.session.closed

        # Cleanup
        await doi_checker._DoiCheck__close_session()

    @pytest.mark.asyncio
    async def test_close_session_when_exists(self):
        """Test closing an existing session actually closes it"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        doi_checker = DoiCheck(db_mock)

        await doi_checker._DoiCheck__create_session()
        await doi_checker._DoiCheck__close_session()

        assert doi_checker.session.closed

    @pytest.mark.asyncio
    async def test_close_session_when_none(self):
        """Test closing when session is None doesn't error"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        doi_checker = DoiCheck(db_mock)

        # Should not raise an error
        await doi_checker._DoiCheck__close_session()


class TestApiSendHeadRequest:
    """Test API request sending"""

    @pytest.mark.asyncio
    async def test_api_send_head_request_success(self):
        """Test successful API request"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        doi_checker = DoiCheck(db_mock)

        # Mock the session and response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {
            'X-Rate-Limit-Limit': '50',
            'X-Rate-Limit-Interval': '1s'
        }

        doi_checker.session = AsyncMock()
        doi_checker.session.head = MagicMock(return_value=mock_response)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        result = await doi_checker._DoiCheck__api_send_head_request('10.1234/test')

        assert result['status'] == 200
        assert result['max_queries'] == '50'
        assert result['seconds'] == '1'

    @pytest.mark.asyncio
    async def test_api_send_head_request_missing_rate_limit_headers(self):
        """Missing CrossRef rate-limit headers must not lose the DOI status.

        Regression: the headers used to be read with [] indexing, so an absent
        header raised KeyError before the status was returned, and the worker's
        broad except silently dropped the DOI. Now they fall back to defaults.
        """
        db_mock = Mock(spec=database_io.DatabaseIO)
        doi_checker = DoiCheck(db_mock)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {}  # CrossRef omitted the rate-limit headers

        doi_checker.session = AsyncMock()
        doi_checker.session.head = MagicMock(return_value=mock_response)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        result = await doi_checker._DoiCheck__api_send_head_request('10.1234/test')

        # Status is still returned; rate-limit values fall back to defaults.
        assert result['status'] == 200
        assert result['max_queries'] == '5'
        assert result['seconds'] == '1'

    @pytest.mark.asyncio
    @pytest.mark.parametrize("doi, expected_url", [
        # A plain DOI is unchanged: the slash and dot are already URL-safe.
        ('10.1234/test.doi',
         'https://api.crossref.org/works/10.1234/test.doi'),
        # '?' would otherwise start a query string on the CrossRef request.
        ('10.5555/foo?rows=1000',
         'https://api.crossref.org/works/10.5555/foo%3Frows%3D1000'),
        # '#' would otherwise be treated as a fragment and dropped, so the
        # server would look up the wrong (truncated) DOI.
        ('10.1000/abc#frag',
         'https://api.crossref.org/works/10.1000/abc%23frag'),
        # A space and an '&' are encoded rather than passed through raw.
        ('10.1234/a b&c',
         'https://api.crossref.org/works/10.1234/a%20b%26c'),
    ])
    async def test_api_send_head_request_percent_encodes_doi(
            self, doi, expected_url):
        """The DOI is percent-encoded before it goes into the query URL.

        URL-significant characters (?, #, &, spaces) that the preflight regex
        admits must not be able to inject a query/fragment into the request or
        make a legitimate DOI resolve to the wrong resource. The slash that
        separates DOI prefix and suffix is preserved (CrossRef expects it
        literally in the path).
        """
        db_mock = Mock(spec=database_io.DatabaseIO)
        doi_checker = DoiCheck(db_mock)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {
            'X-Rate-Limit-Limit': '50',
            'X-Rate-Limit-Interval': '1s'
        }

        doi_checker.session = AsyncMock()
        mock_head = MagicMock(return_value=mock_response)
        doi_checker.session.head = mock_head
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        await doi_checker._DoiCheck__api_send_head_request(doi)

        assert mock_head.call_args[0][0] == expected_url


class TestWorker:
    """Test worker functionality"""

    @pytest.mark.asyncio
    async def test_worker_valid_doi(self):
        """Test worker processing valid DOI"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        doi_checker = DoiCheck(db_mock)
        doi_checker.pbar_doi = Mock()
        doi_checker.pbar_doi.update = Mock()

        # Mock the API request to return valid DOI
        async def mock_api_request(doi):
            return {
                'status': 200,
                'max_queries': '50',
                'seconds': '1'
            }

        doi_checker._DoiCheck__api_send_head_request = mock_api_request
        doi_checker._DoiCheck__rate_limit_wait = AsyncMock()

        # Create a queue with one DOI
        queue = asyncio.Queue()
        queue.put_nowait('10.1234/valid')

        # Run worker for one iteration
        worker_task = asyncio.create_task(
            doi_checker._DoiCheck__worker('test-worker', queue)
        )

        # Wait for the queue to be processed
        await queue.join()

        # Cancel the worker
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

        # Check that DOI was added to valid list
        assert '10.1234/valid' in doi_checker.valid_doi_list
        assert len(doi_checker.invalid_doi_list) == 0

    @pytest.mark.asyncio
    async def test_worker_invalid_doi(self):
        """Test worker processing invalid DOI (404)"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        doi_checker = DoiCheck(db_mock)
        doi_checker.pbar_doi = Mock()
        doi_checker.pbar_doi.update = Mock()

        # Mock the API request to return 404
        async def mock_api_request(doi):
            return {
                'status': 404,
                'max_queries': '50',
                'seconds': '1'
            }

        doi_checker._DoiCheck__api_send_head_request = mock_api_request
        doi_checker._DoiCheck__rate_limit_wait = AsyncMock()

        queue = asyncio.Queue()
        queue.put_nowait('10.1234/invalid')

        worker_task = asyncio.create_task(
            doi_checker._DoiCheck__worker('test-worker', queue)
        )

        await queue.join()

        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

        # Check that DOI was added to invalid list
        assert '10.1234/invalid' in doi_checker.invalid_doi_list
        assert len(doi_checker.valid_doi_list) == 0

    @pytest.mark.asyncio
    async def test_worker_unexpected_status(self, capsys):
        """Test worker handling unexpected API status code"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        doi_checker = DoiCheck(db_mock)
        doi_checker.pbar_doi = Mock()
        doi_checker.pbar_doi.update = Mock()

        # Mock the API request to return unexpected status
        async def mock_api_request(doi):
            return {
                'status': 500,  # Unexpected status
                'max_queries': '50',
                'seconds': '1'
            }

        doi_checker._DoiCheck__api_send_head_request = mock_api_request
        doi_checker._DoiCheck__rate_limit_wait = AsyncMock()

        queue = asyncio.Queue()
        queue.put_nowait('10.1234/unexpected')

        worker_task = asyncio.create_task(
            doi_checker._DoiCheck__worker('test-worker', queue)
        )

        await queue.join()

        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

        # Check that unexpected status message was printed
        captured = capsys.readouterr()
        assert 'Unexpected API response: 500' in captured.out

    @pytest.mark.asyncio
    async def test_worker_classifies_despite_missing_headers(self):
        """End-to-end: a 404 with no rate-limit headers is still classified
        invalid via the real __api_send_head_request (not silently dropped)."""
        db_mock = Mock(spec=database_io.DatabaseIO)
        doi_checker = DoiCheck(db_mock)
        doi_checker.pbar_doi = Mock()
        doi_checker.pbar_doi.update = Mock()

        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.headers = {}  # no rate-limit headers
        doi_checker.session = AsyncMock()
        doi_checker.session.head = MagicMock(return_value=mock_response)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        # Use the real __api_send_head_request, but skip actual sleeping.
        doi_checker._DoiCheck__rate_limit_wait = AsyncMock()

        queue = asyncio.Queue()
        queue.put_nowait('10.1234/missing-headers')
        worker_task = asyncio.create_task(
            doi_checker._DoiCheck__worker('test-worker', queue))
        await queue.join()
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

        assert '10.1234/missing-headers' in doi_checker.invalid_doi_list
        assert doi_checker.valid_doi_list == []


class TestCheckDois:
    """Test main check_dois method"""

    def test_check_dois_no_dois(self):
        """Test check_dois when there are no DOIs to check"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        db_mock.get_dois_to_check = Mock(return_value=None)

        doi_checker = DoiCheck(db_mock)

        # Should return early without error
        doi_checker.check_dois()

        # Database should not be called to save anything
        db_mock.save_valid_dois.assert_not_called()
        db_mock.log_invalid_dois.assert_not_called()

    def test_check_dois_empty_list(self):
        """Test check_dois when DOI list is empty"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        db_mock.get_dois_to_check = Mock(return_value=[])

        doi_checker = DoiCheck(db_mock)

        # Should return early without error
        doi_checker.check_dois()

        # Database should not be called to save anything
        db_mock.save_valid_dois.assert_not_called()
        db_mock.log_invalid_dois.assert_not_called()

    @patch('salted.doi_check.tqdm')
    def test_check_dois_with_dois(self, mock_tqdm):
        """Test check_dois with DOIs to process"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        db_mock.get_dois_to_check = Mock(return_value=['10.1234/test1', '10.1234/test2'])
        db_mock.save_valid_dois = Mock()
        db_mock.log_invalid_dois = Mock()

        doi_checker = DoiCheck(db_mock)

        # Mock the distribute_work method to avoid actual async execution
        doi_checker._DoiCheck__distribute_work = AsyncMock()

        # Simulate some valid and invalid DOIs
        doi_checker.valid_doi_list = ['10.1234/test1']
        doi_checker.invalid_doi_list = ['10.1234/test2']

        doi_checker.check_dois()

        # Verify progress bar was created
        assert mock_tqdm.called

        # Verify async distribute_work was called
        doi_checker._DoiCheck__distribute_work.assert_called_once()

        # Verify database was updated
        db_mock.save_valid_dois.assert_called_once()
        db_mock.log_invalid_dois.assert_called_once()

    @patch('salted.doi_check.tqdm')
    def test_check_dois_only_valid(self, mock_tqdm):
        """Test check_dois with only valid DOIs"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        db_mock.get_dois_to_check = Mock(return_value=['10.1234/test1'])
        db_mock.save_valid_dois = Mock()
        db_mock.log_invalid_dois = Mock()

        doi_checker = DoiCheck(db_mock)
        # Mock the distribute_work method to avoid actual async execution
        doi_checker._DoiCheck__distribute_work = AsyncMock()
        doi_checker.valid_doi_list = ['10.1234/test1']

        doi_checker.check_dois()

        # Only valid DOIs should be saved
        db_mock.save_valid_dois.assert_called_once()
        db_mock.log_invalid_dois.assert_not_called()

    @patch('salted.doi_check.tqdm')
    def test_check_dois_only_invalid(self, mock_tqdm):
        """Test check_dois with only invalid DOIs"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        db_mock.get_dois_to_check = Mock(return_value=['10.1234/invalid'])
        db_mock.save_valid_dois = Mock()
        db_mock.log_invalid_dois = Mock()

        doi_checker = DoiCheck(db_mock)
        # Mock the distribute_work method to avoid actual async execution
        doi_checker._DoiCheck__distribute_work = AsyncMock()
        doi_checker.invalid_doi_list = ['10.1234/invalid']

        doi_checker.check_dois()

        # Only invalid DOIs should be logged
        db_mock.save_valid_dois.assert_not_called()
        db_mock.log_invalid_dois.assert_called_once()


class TestDistributeWork:
    """Test __distribute_work method with real async execution"""

    @pytest.mark.asyncio
    async def test_distribute_work_with_dois(self):
        """Test that __distribute_work actually runs workers and processes DOIs"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        doi_checker = DoiCheck(db_mock)

        # Mock the API request to return valid DOI responses
        async def mock_api_request(doi):
            return {
                'status': 200,
                'max_queries': '50',
                'seconds': '1'
            }

        doi_checker._DoiCheck__api_send_head_request = mock_api_request
        doi_checker._DoiCheck__rate_limit_wait = AsyncMock()

        # Mock tqdm for progress bar
        doi_checker.pbar_doi = Mock()
        doi_checker.pbar_doi.update = Mock()

        # Test with a small list of DOIs
        dois = ['10.1234/test1', '10.1234/test2', '10.1234/test3']

        await doi_checker._DoiCheck__distribute_work(dois)

        # Verify all DOIs were processed
        assert len(doi_checker.valid_doi_list) == 3
        assert '10.1234/test1' in doi_checker.valid_doi_list
        assert '10.1234/test2' in doi_checker.valid_doi_list
        assert '10.1234/test3' in doi_checker.valid_doi_list
        assert len(doi_checker.invalid_doi_list) == 0

        # Verify session was created (it's closed but object remains)
        assert doi_checker.session is not None

    @pytest.mark.asyncio
    async def test_distribute_work_with_mixed_results(self):
        """Test __distribute_work with both valid and invalid DOIs"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        doi_checker = DoiCheck(db_mock)

        # Mock the API request to return mixed responses
        async def mock_api_request(doi):
            if doi.startswith('10.1234/valid'):
                return {
                    'status': 200,
                    'max_queries': '50',
                    'seconds': '1'
                }
            else:
                return {
                    'status': 404,
                    'max_queries': '50',
                    'seconds': '1'
                }

        doi_checker._DoiCheck__api_send_head_request = mock_api_request
        doi_checker._DoiCheck__rate_limit_wait = AsyncMock()

        doi_checker.pbar_doi = Mock()
        doi_checker.pbar_doi.update = Mock()

        dois = ['10.1234/valid1', '10.1234/notfound', '10.1234/valid2']

        await doi_checker._DoiCheck__distribute_work(dois)

        # Verify results were categorized correctly
        assert len(doi_checker.valid_doi_list) == 2
        assert '10.1234/valid1' in doi_checker.valid_doi_list
        assert '10.1234/valid2' in doi_checker.valid_doi_list
        assert len(doi_checker.invalid_doi_list) == 1
        assert '10.1234/notfound' in doi_checker.invalid_doi_list

    @pytest.mark.asyncio
    async def test_distribute_work_task_cancellation(self):
        """Test that __distribute_work properly cancels and gathers tasks"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        doi_checker = DoiCheck(db_mock)

        # Mock the API request
        async def mock_api_request(doi):
            return {
                'status': 200,
                'max_queries': '50',
                'seconds': '1'
            }

        doi_checker._DoiCheck__api_send_head_request = mock_api_request
        doi_checker._DoiCheck__rate_limit_wait = AsyncMock()

        doi_checker.pbar_doi = Mock()
        doi_checker.pbar_doi.update = Mock()

        # Run with just one DOI to test task cancellation logic
        dois = ['10.1234/test']

        await doi_checker._DoiCheck__distribute_work(dois)

        # Should complete without errors even with task cancellation
        assert len(doi_checker.valid_doi_list) == 1


class TestDoiFormatCheck:
    """Test the preflight DOI format check."""

    def test_valid_doi_passes(self):
        """Standard DOIs pass the format check."""
        valid = [
            '10.1234/something',
            '10.12345/suffix',
            '10.1000/xyz123',
            '10.1038/nature12345',
        ]
        for doi in valid:
            assert DoiCheck._is_valid_doi_format(doi), f"Expected valid: {doi}"

    def test_invalid_doi_rejected(self):
        """Malformed DOIs are rejected before hitting the API."""
        invalid = [
            '',
            'not-a-doi',
            '10.123/too-short-registrant',  # registrant must be ≥4 digits
            '10.1234',                       # missing slash and suffix
            '10.1234/',                      # missing suffix
            'doi:10.1234/something',         # has prefix that breaks the pattern
        ]
        for doi in invalid:
            assert not DoiCheck._is_valid_doi_format(doi), f"Expected invalid: {doi}"

    @pytest.mark.asyncio
    async def test_malformed_doi_skips_api(self):
        """A malformed DOI is added to invalid_doi_list without any API call."""
        db_mock = Mock(spec=database_io.DatabaseIO)
        doi_checker = DoiCheck(db_mock)
        doi_checker.pbar_doi = Mock()
        doi_checker.pbar_doi.update = Mock()

        with patch.object(doi_checker, '_DoiCheck__api_send_head_request') as mock_api:
            await doi_checker._DoiCheck__distribute_work(['not-a-doi'])

        mock_api.assert_not_called()
        assert 'not-a-doi' in doi_checker.invalid_doi_list

    @pytest.mark.asyncio
    async def test_valid_doi_reaches_api(self):
        """A well-formed DOI is sent to the CrossRef API."""
        db_mock = Mock(spec=database_io.DatabaseIO)
        doi_checker = DoiCheck(db_mock)
        doi_checker.pbar_doi = Mock()
        doi_checker.pbar_doi.update = Mock()

        async def mock_api(doi):
            return {'status': 200, 'max_queries': '50', 'seconds': '1'}

        doi_checker._DoiCheck__api_send_head_request = mock_api
        doi_checker._DoiCheck__rate_limit_wait = AsyncMock()

        await doi_checker._DoiCheck__distribute_work(['10.1234/valid'])

        assert '10.1234/valid' in doi_checker.valid_doi_list
        assert doi_checker.invalid_doi_list == []
