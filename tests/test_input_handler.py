#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Tests for input handler functionality
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2025: Released under the Apache License 2.0
"""

import pathlib
import pytest
from unittest.mock import Mock, patch, mock_open

from salted.input_handler import InputHandler
from salted import database_io


class TestInputHandlerInitialization:
    """Test InputHandler initialization"""

    def test_initialization(self):
        """Test basic initialization"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        assert handler.db == db_mock
        assert handler.cnt is not None
        assert handler.parser is not None


class TestReadFileContent:
    """Test file content reading with various error conditions"""

    def test_read_file_content_success(self):
        """Test successful file reading"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        test_content = "<html><a href='http://example.com'>link</a></html>"

        mock_stat = Mock()
        mock_stat.st_size = 1024
        with patch.object(pathlib.Path, 'stat', return_value=mock_stat):
            with patch('builtins.open', mock_open(read_data=test_content)):
                content = handler.read_file_content(pathlib.Path('test.html'))

        assert content == test_content
        db_mock.log_file_access_error.assert_not_called()

    def test_read_file_content_utf8(self, tmp_path):
        """A valid UTF-8 file is read correctly."""
        f = tmp_path / "test.html"
        f.write_bytes("Héllo Wörld".encode('utf-8'))
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)
        content = handler.read_file_content(f)
        assert content == "Héllo Wörld"
        db_mock.log_file_access_error.assert_not_called()

    def test_read_file_content_latin1_fallback(self, tmp_path):
        """A Latin-1 encoded file is read via fallback without logging an error."""
        f = tmp_path / "test.html"
        f.write_bytes("Héllo Wörld".encode('latin-1'))
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)
        content = handler.read_file_content(f)
        assert content == "Héllo Wörld"
        db_mock.log_file_access_error.assert_not_called()

    def test_read_file_content_file_not_found(self):
        """Test handling FileNotFoundError"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        with patch.object(pathlib.Path, 'stat', side_effect=FileNotFoundError()):
            content = handler.read_file_content(pathlib.Path('missing.html'))

        assert content is None
        db_mock.log_file_access_error.assert_called_once()
        assert 'file not found' in str(db_mock.log_file_access_error.call_args)

    def test_read_file_content_permission_error(self):
        """Test handling PermissionError"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        mock_stat = Mock()
        mock_stat.st_size = 1024
        with patch.object(pathlib.Path, 'stat', return_value=mock_stat):
            with patch('builtins.open', side_effect=PermissionError()):
                content = handler.read_file_content(pathlib.Path('forbidden.html'))

        assert content is None
        db_mock.log_file_access_error.assert_called_once()
        assert 'permission error' in str(db_mock.log_file_access_error.call_args)

    def test_read_file_content_timeout_error(self):
        """Test handling TimeoutError"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        mock_stat = Mock()
        mock_stat.st_size = 1024
        with patch.object(pathlib.Path, 'stat', return_value=mock_stat):
            with patch('builtins.open', side_effect=TimeoutError()):
                content = handler.read_file_content(pathlib.Path('slow.html'))

        assert content is None
        db_mock.log_file_access_error.assert_called_once()
        assert 'system timeout' in str(db_mock.log_file_access_error.call_args)

    def test_read_file_content_blocking_io_error(self):
        """Test handling BlockingIOError"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        mock_stat = Mock()
        mock_stat.st_size = 1024
        with patch.object(pathlib.Path, 'stat', return_value=mock_stat):
            with patch('builtins.open', side_effect=BlockingIOError()):
                content = handler.read_file_content(pathlib.Path('blocked.html'))

        assert content is None
        db_mock.log_file_access_error.assert_called_once()
        assert 'blocking IO' in str(db_mock.log_file_access_error.call_args)

    def test_read_file_content_unexpected_exception(self):
        """Test handling unexpected exceptions"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        mock_stat = Mock()
        mock_stat.st_size = 1024
        with patch.object(pathlib.Path, 'stat', return_value=mock_stat):
            with patch('builtins.open', side_effect=RuntimeError('Unexpected error')):
                content = handler.read_file_content(pathlib.Path('error.html'))

        assert content is None
        db_mock.log_file_access_error.assert_called_once()
        assert 'Unexpected error' in str(db_mock.log_file_access_error.call_args)


class TestHandleFoundUrls:
    """Test URL handling and normalization"""

    def test_handle_found_urls_http_links(self):
        """Test handling of HTTP/HTTPS links"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        url_list = [
            ['https://example.com/page', 'Example'],
            ['http://test.org/path', 'Test']
        ]

        handler.handle_found_urls(pathlib.Path('test.html'), url_list)

        assert handler.cnt['links_found'] == 2
        db_mock.save_found_links.assert_called_once()

        # Check that links were saved with correct format
        saved_links = db_mock.save_found_links.call_args[0][0]
        assert len(saved_links) == 2
        assert saved_links[0][1] == 'example.com'  # hostname
        assert saved_links[0][2] == 'https://example.com/page'  # original URL

    def test_handle_found_urls_with_query_params(self):
        """Test URL normalization with query parameters"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        url_list = [
            ['https://example.com/page?b=2&a=1', 'Link']
        ]

        handler.handle_found_urls(pathlib.Path('test.html'), url_list)

        assert handler.cnt['links_found'] == 1
        saved_links = db_mock.save_found_links.call_args[0][0]
        # Normalized URL should have sorted query params
        assert 'a=1' in saved_links[0][3]  # normalized URL

    @patch('salted.input_handler.userprovided.url.normalize_url')
    def test_handle_found_urls_query_key_conflict(self, mock_normalize):
        """Test handling QueryKeyConflict during normalization"""
        from userprovided.err import QueryKeyConflict

        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        # First call raises exception, second call succeeds
        mock_normalize.side_effect = [
            QueryKeyConflict('Duplicate keys'),
            'https://example.com/normalized'
        ]

        url_list = [['https://example.com/page?key=1&key=2', 'Duplicate']]

        handler.handle_found_urls(pathlib.Path('test.html'), url_list)

        # Should call normalize twice: once normally, once with do_not_change_query_part
        assert mock_normalize.call_count == 2
        assert handler.cnt['links_found'] == 1

    def test_handle_found_urls_mailto_links(self):
        """Test handling of mailto links (currently just logged)"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        url_list = [
            ['mailto:test@example.com', 'Email']
        ]

        handler.handle_found_urls(pathlib.Path('test.html'), url_list)

        # Mailto links are not yet implemented, so no links should be found
        assert handler.cnt['links_found'] == 0
        db_mock.save_found_links.assert_not_called()

    def test_handle_found_urls_unsupported_scheme(self):
        """Test handling of unsupported URL schemes"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        url_list = [
            ['ftp://example.com/file', 'FTP Link'],
            ['file:///local/path', 'Local File']
        ]

        handler.handle_found_urls(pathlib.Path('test.html'), url_list)

        assert handler.cnt['unsupported_scheme'] == 2
        assert handler.cnt['links_found'] == 0
        db_mock.save_found_links.assert_not_called()

    def test_handle_found_urls_empty_list(self):
        """Test handling empty URL list"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        handler.handle_found_urls(pathlib.Path('test.html'), [])

        db_mock.save_found_links.assert_not_called()


class TestHandleFoundDois:
    """Test DOI handling"""

    def test_handle_found_dois_small_list(self):
        """Test handling small DOI list (less than 50)"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        doi_list = [
            ['10.1234/test1', 'entry1'],
            ['10.1234/test2', 'entry2']
        ]

        handler.handle_found_dois(pathlib.Path('refs.bib'), doi_list)

        # Should save all DOIs in one call for small lists
        db_mock.save_found_dois.assert_called_once()
        saved_dois = db_mock.save_found_dois.call_args[0][0]
        assert len(saved_dois) == 2

    def test_handle_found_dois_large_list(self):
        """Test handling large DOI list (batched processing)"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        # Create a list of 125 DOIs (more than 50)
        doi_list = [[f'10.1234/test{i}', f'entry{i}'] for i in range(125)]

        handler.handle_found_dois(pathlib.Path('refs.bib'), doi_list)

        # Should be called multiple times (batches of 50)
        assert db_mock.save_found_dois.call_count >= 2

    def test_handle_found_dois_empty_list(self):
        """Test handling empty DOI list"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        result = handler.handle_found_dois(pathlib.Path('refs.bib'), [])

        assert result is None
        db_mock.save_found_dois.assert_not_called()

    def test_handle_found_dois_none(self):
        """Test handling None DOI list"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        result = handler.handle_found_dois(pathlib.Path('refs.bib'), None)

        assert result is None
        db_mock.save_found_dois.assert_not_called()


class TestScanFiles:
    """Test file scanning functionality"""

    @patch('salted.input_handler.tqdm')
    def test_scan_files_html(self, mock_tqdm):
        """Test scanning HTML files"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        mock_tqdm.return_value = [pathlib.Path('test.html')]

        test_content = '<html><a href="http://example.com">Link</a></html>'

        with patch.object(handler, 'read_file_content', return_value=test_content):
            with patch.object(handler.parser, 'extract_links_from_html') as mock_extract:
                mock_extract.return_value = [['http://example.com', 'Link']]

                handler.scan_files([pathlib.Path('test.html')])

        mock_extract.assert_called_once()
        assert handler.cnt['links_found'] > 0

    @patch('salted.input_handler.tqdm')
    def test_scan_files_markdown(self, mock_tqdm):
        """Test scanning Markdown files"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        mock_tqdm.return_value = [pathlib.Path('test.md')]

        test_content = '[Link](http://example.com)'

        with patch.object(handler, 'read_file_content', return_value=test_content):
            with patch.object(handler.parser, 'extract_links_from_markdown') as mock_extract:
                mock_extract.return_value = [['http://example.com', 'Link']]

                handler.scan_files([pathlib.Path('test.md')])

        mock_extract.assert_called_once()

    @patch('salted.input_handler.tqdm')
    def test_scan_files_tex(self, mock_tqdm):
        """Test scanning TeX files"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        mock_tqdm.return_value = [pathlib.Path('test.tex')]

        test_content = r'\url{http://example.com}'

        with patch.object(handler, 'read_file_content', return_value=test_content):
            with patch.object(handler.parser, 'extract_links_from_tex') as mock_extract:
                mock_extract.return_value = [['http://example.com', '']]

                handler.scan_files([pathlib.Path('test.tex')])

        mock_extract.assert_called_once()

    @patch('salted.input_handler.tqdm')
    def test_scan_files_bib(self, mock_tqdm):
        """Test scanning BibTeX files"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        mock_tqdm.return_value = [pathlib.Path('test.bib')]

        test_content = '@article{test, url={http://example.com}, doi={10.1234/test}}'

        with patch.object(handler, 'read_file_content', return_value=test_content):
            with patch.object(handler.parser, 'extract_links_from_bib') as mock_extract:
                mock_extract.return_value = (
                    [['http://example.com', 'test']],
                    [['10.1234/test', 'test']]
                )

                handler.scan_files([pathlib.Path('test.bib')])

        mock_extract.assert_called_once()

    @patch('salted.input_handler.tqdm')
    def test_scan_files_bib_parse_error_is_logged(self, mock_tqdm):
        """BibTeX parse failure logs a file access error with a clear message."""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        mock_tqdm.return_value = [pathlib.Path('broken.bib')]

        with patch.object(handler, 'read_file_content', return_value='not valid bibtex @@@'):
            with patch.object(handler.parser, 'extract_links_from_bib',
                              side_effect=Exception('unexpected EOF')):
                handler.scan_files([pathlib.Path('broken.bib')])

        db_mock.log_file_access_error.assert_called_once()
        call_args = str(db_mock.log_file_access_error.call_args)
        assert 'broken.bib' in call_args
        assert 'BibTeX parse error' in call_args

    @patch('salted.input_handler.tqdm')
    def test_scan_files_bib_parse_error_continues_to_next_file(self, mock_tqdm):
        """Scanning continues to the next file after a BibTeX parse error."""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        mock_tqdm.return_value = [
            pathlib.Path('broken.bib'),
            pathlib.Path('good.bib'),
        ]

        good_content = '@article{ok, url={http://example.com}}'

        def fake_read(path):
            return 'bad content' if path.name == 'broken.bib' else good_content

        def fake_parse(content):
            if content == 'bad content':
                raise Exception('unexpected EOF')
            return ([['http://example.com', 'ok']], [])

        with patch.object(handler, 'read_file_content', side_effect=fake_read):
            with patch.object(handler.parser, 'extract_links_from_bib',
                              side_effect=fake_parse):
                handler.scan_files([pathlib.Path('broken.bib'), pathlib.Path('good.bib')])

        db_mock.log_file_access_error.assert_called_once()
        db_mock.save_found_links.assert_called_once()

    @patch('salted.input_handler.tqdm')
    def test_scan_files_unreadable_file(self, mock_tqdm):
        """Test scanning when file cannot be read"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        mock_tqdm.return_value = [pathlib.Path('test.html')]

        with patch.object(handler, 'read_file_content', return_value=None):
            with patch.object(handler.parser, 'extract_links_from_html') as mock_extract:
                handler.scan_files([pathlib.Path('test.html')])

        # Should skip the file and not try to extract links
        mock_extract.assert_not_called()

    def test_scan_files_empty_list(self):
        """Test scanning with empty file list"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        result = handler.scan_files([])

        assert result is None

    @patch('salted.input_handler.tqdm')
    def test_scan_files_invalid_extension(self, mock_tqdm):
        """Test scanning file with invalid extension"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        mock_tqdm.return_value = [pathlib.Path('test.xyz')]

        with patch.object(handler, 'read_file_content', return_value='content'):
            with pytest.raises(RuntimeError, match='Invalid extension'):
                handler.scan_files([pathlib.Path('test.xyz')])

    @patch('salted.input_handler.tqdm')
    def test_scan_files_oversized_file_is_skipped(self, mock_tqdm, tmp_path):
        """scan_files skips files that exceed the size limit."""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock, max_file_size_mb=1)

        large_file = tmp_path / "large.html"
        large_file.write_bytes(b'x' * (2 * 1024 * 1024))  # 2 MB > 1 MB limit

        mock_tqdm.return_value = [large_file]
        handler.scan_files([large_file])

        db_mock.log_file_access_error.assert_called_once()
        error_msg = db_mock.log_file_access_error.call_args[0][1]
        assert 'file too large' in error_msg
        db_mock.save_found_links.assert_not_called()

    @patch('salted.input_handler.tqdm')
    def test_scan_files_resets_counter(self, mock_tqdm):
        """Test that link counter is reset on each scan"""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)

        mock_tqdm.return_value = [pathlib.Path('test.html')]

        # Set counter to non-zero value
        handler.cnt['links_found'] = 100

        test_content = '<html><a href="http://example.com">Link</a></html>'

        with patch.object(handler, 'read_file_content', return_value=test_content):
            with patch.object(handler.parser, 'extract_links_from_html') as mock_extract:
                mock_extract.return_value = []  # No links found

                handler.scan_files([pathlib.Path('test.html')])

        # Should be reset to 0 (counter starts fresh for each scan)
        assert handler.cnt['links_found'] == 0


class TestFileSizeLimit:
    """Test configurable file size limit in read_file_content."""

    def test_default_limit_is_20mb(self):
        """Default max_file_size_mb must be 20."""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock)
        assert handler.max_file_size_mb == 20

    def test_custom_limit_is_stored(self):
        """A custom max_file_size_mb value is stored correctly."""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock, max_file_size_mb=5)
        assert handler.max_file_size_mb == 5

    def test_oversized_file_returns_none_and_logs_error(self):
        """File exceeding the limit returns None and logs a descriptive error."""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock, max_file_size_mb=1)

        mock_stat = Mock()
        mock_stat.st_size = 2 * 1024 * 1024  # 2 MB > 1 MB limit

        with patch.object(pathlib.Path, 'stat', return_value=mock_stat):
            content = handler.read_file_content(pathlib.Path('large.html'))

        assert content is None
        db_mock.log_file_access_error.assert_called_once()
        error_msg = db_mock.log_file_access_error.call_args[0][1]
        assert 'file too large' in error_msg
        assert '2.0 MB' in error_msg
        assert 'limit 1 MB' in error_msg

    def test_file_within_limit_is_read(self):
        """File under the size limit is read and returned normally."""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock, max_file_size_mb=10)

        mock_stat = Mock()
        mock_stat.st_size = 1024  # 1 KB, well under limit
        test_content = "<html></html>"

        with patch.object(pathlib.Path, 'stat', return_value=mock_stat):
            with patch('builtins.open', mock_open(read_data=test_content)):
                content = handler.read_file_content(pathlib.Path('small.html'))

        assert content == test_content
        db_mock.log_file_access_error.assert_not_called()

    def test_file_at_exact_limit_is_read(self):
        """File exactly at the limit is read (limit is exclusive — > not >=)."""
        db_mock = Mock(spec=database_io.DatabaseIO)
        handler = InputHandler(db_mock, max_file_size_mb=1)

        mock_stat = Mock()
        mock_stat.st_size = 1 * 1024 * 1024  # exactly 1 MB
        test_content = "content"

        with patch.object(pathlib.Path, 'stat', return_value=mock_stat):
            with patch('builtins.open', mock_open(read_data=test_content)):
                content = handler.read_file_content(pathlib.Path('exact.html'))

        assert content == test_content
        db_mock.log_file_access_error.assert_not_called()
