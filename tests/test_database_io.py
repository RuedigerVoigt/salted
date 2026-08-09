#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Tests for database_io module
~~~~~~~~~~~~~~~~~~~~~
Smart, Asynchronous Link Tester with Database backend (SALTED)
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2025: Released under the Apache License 2.0
"""

import pathlib

from salted import database_io, memory_instance


class TestDatabaseIOInitialization:
    """Test DatabaseIO initialization"""

    def test_initialization_without_cache_file(self):
        """Test initialization without cache file"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)
        assert db_io.cursor is not None
        assert db_io.cache_file_path is None
        mem_inst.tear_down_in_memory_db()

    def test_initialization_with_cache_file(self):
        """Test initialization with cache file path"""
        mem_inst = memory_instance.MemoryInstance()
        cache_path = pathlib.Path("test_cache.sqlite")
        db_io = database_io.DatabaseIO(mem_inst, cache_file=cache_path)
        assert db_io.cursor is not None
        assert db_io.cache_file_path == cache_path.resolve()
        mem_inst.tear_down_in_memory_db()

    def test_initialization_with_cache_file_as_string(self):
        """Test initialization with cache file as string"""
        mem_inst = memory_instance.MemoryInstance()
        cache_path = "test_cache.sqlite"
        db_io = database_io.DatabaseIO(mem_inst, cache_file=cache_path)
        assert db_io.cursor is not None
        assert db_io.cache_file_path == pathlib.Path(cache_path).resolve()
        mem_inst.tear_down_in_memory_db()


class TestSaveFoundLinks:
    """Test saving found links"""

    def test_save_found_links_empty_list(self):
        """Test saving empty list of links"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)
        db_io.save_found_links([])
        mem_inst.tear_down_in_memory_db()

    def test_save_found_links_with_data(self):
        """Test saving links to database"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        links = [
            ('test.html', 'example.com', 'http://example.com', 'http://example.com', 'Link Text'),
            ('test.html', 'example.org', 'http://example.org', 'http://example.org', 'Another Link')
        ]
        db_io.save_found_links(links)

        # Verify links were saved
        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT COUNT(*) FROM queue')
        count = cursor.fetchone()[0]
        assert count == 2
        mem_inst.tear_down_in_memory_db()


class TestSaveFoundDois:
    """Test saving found DOIs"""

    def test_save_found_dois_empty_list(self):
        """Test saving empty list of DOIs"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)
        result = db_io.save_found_dois([])
        assert result is None
        mem_inst.tear_down_in_memory_db()

    def test_save_found_dois_with_data(self):
        """Test saving DOIs to database"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        dois = [
            ('test.bib', '10.1234/test1', 'Test Article 1'),
            ('test.bib', '10.1234/test2', 'Test Article 2')
        ]
        result = db_io.save_found_dois(dois)
        assert result is None

        # Verify DOIs were saved
        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT COUNT(*) FROM queue_doi')
        count = cursor.fetchone()[0]
        assert count == 2
        mem_inst.tear_down_in_memory_db()


class TestUrlsToCheck:
    """Test retrieving URLs to check"""

    def test_urls_to_check_empty_queue(self):
        """Test getting URLs when queue is empty"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)
        urls = db_io.urls_to_check()
        assert urls == []
        mem_inst.tear_down_in_memory_db()

    def test_urls_to_check_with_data(self):
        """Test getting URLs from queue"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        links = [
            ('test.html', 'example.com', 'http://example.com', 'http://example.com', 'Link'),
            ('test.html', 'example.org', 'http://example.org', 'http://example.org', 'Link')
        ]
        db_io.save_found_links(links)

        urls = db_io.urls_to_check()
        assert len(urls) == 2
        mem_inst.tear_down_in_memory_db()

    def test_urls_to_check_distinct(self):
        """Test that duplicate URLs are returned only once"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        links = [
            ('test1.html', 'example.com', 'http://example.com', 'http://example.com', 'Link 1'),
            ('test2.html', 'example.com', 'http://example.com', 'http://example.com', 'Link 2')
        ]
        db_io.save_found_links(links)

        urls = db_io.urls_to_check()
        assert len(urls) == 1
        mem_inst.tear_down_in_memory_db()


class TestGetDoisToCheck:
    """Test retrieving DOIs to check"""

    def test_get_dois_to_check_empty_queue(self):
        """Test getting DOIs when queue is empty"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)
        dois = db_io.get_dois_to_check()
        assert dois is None
        mem_inst.tear_down_in_memory_db()

    def test_get_dois_to_check_with_data(self):
        """Test getting DOIs from queue"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        dois = [
            ('test.bib', '10.1234/test1', 'Test Article 1'),
            ('test.bib', '10.1234/test2', 'Test Article 2')
        ]
        db_io.save_found_dois(dois)

        dois_to_check = db_io.get_dois_to_check()
        assert len(dois_to_check) == 2
        assert '10.1234/test1' in dois_to_check
        assert '10.1234/test2' in dois_to_check
        mem_inst.tear_down_in_memory_db()


class TestLogUrlIsFine:
    """Test logging valid URLs"""

    def test_log_url_is_fine(self):
        """Test logging a valid URL"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        db_io.log_url_is_fine('http://example.com')

        # Verify URL was logged
        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT COUNT(*) FROM validUrls')
        count = cursor.fetchone()[0]
        assert count == 1

        cursor.execute('SELECT normalizedUrl FROM validUrls')
        url = cursor.fetchone()[0]
        assert url == 'http://example.com'
        mem_inst.tear_down_in_memory_db()


class TestSaveValidDois:
    """Test saving valid DOIs"""

    def test_save_valid_dois(self):
        """Test saving valid DOIs to cache"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        valid_dois = [
            ('10.1234/test1',),
            ('10.1234/test2',)
        ]
        db_io.save_valid_dois(valid_dois)

        # Verify DOIs were saved
        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT COUNT(*) FROM validDois')
        count = cursor.fetchone()[0]
        assert count == 2
        mem_inst.tear_down_in_memory_db()

    def test_save_valid_dois_ignore_duplicates(self):
        """Test that duplicate DOIs are ignored"""
        mem_inst = memory_instance.MemoryInstance()
        mem_inst.generate_indices()  # Generate indices for UNIQUE constraint
        db_io = database_io.DatabaseIO(mem_inst)

        valid_dois = [
            ('10.1234/test1',),
            ('10.1234/test1',)  # duplicate
        ]
        db_io.save_valid_dois(valid_dois)

        # Verify only one DOI was saved
        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT COUNT(*) FROM validDois')
        count = cursor.fetchone()[0]
        assert count == 1
        mem_inst.tear_down_in_memory_db()


class TestSaveMailtoLinks:
    """Test saving mailto links"""

    def test_save_mailto_links_empty_list_returns_early(self):
        """save_mailto_links with empty list hits the early return."""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)
        db_io.save_mailto_links([])  # should not raise and should not insert
        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT COUNT(*) FROM mailtoLinks')
        assert cursor.fetchone()[0] == 0
        mem_inst.tear_down_in_memory_db()

    def test_save_mailto_links_with_data(self):
        """save_mailto_links stores entries correctly."""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)
        db_io.save_mailto_links([
            ('index.html', 'mailto:alice@example.com', 'alice@example.com', 1),
        ])
        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT COUNT(*) FROM mailtoLinks')
        assert cursor.fetchone()[0] == 1
        mem_inst.tear_down_in_memory_db()


class TestLogInvalidDois:
    """Test logging invalid DOIs"""

    def test_log_invalid_dois(self):
        """Test that invalid DOIs are stored in the invalidDois table."""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        db_io.log_invalid_dois([('10.1234/invalid',), ('10.5678/also-bad',)])

        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT doi FROM invalidDois ORDER BY doi;')
        rows = cursor.fetchall()
        assert len(rows) == 2
        assert rows[0][0] == '10.1234/invalid'
        assert rows[1][0] == '10.5678/also-bad'
        mem_inst.tear_down_in_memory_db()

    def test_log_invalid_dois_empty_list(self):
        """Empty list must not insert any rows."""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        db_io.log_invalid_dois([])

        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT COUNT(*) FROM invalidDois;')
        assert cursor.fetchone()[0] == 0
        mem_inst.tear_down_in_memory_db()


class TestLogError:
    """Test logging errors"""

    def test_log_error(self):
        """Test logging an error"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        db_io.log_error('http://example.com/404', 404)

        # Verify error was logged
        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT COUNT(*) FROM errors')
        count = cursor.fetchone()[0]
        assert count == 1

        cursor.execute('SELECT * FROM errors')
        error = cursor.fetchone()
        assert error[0] == 'http://example.com/404'
        assert error[1] == 404
        mem_inst.tear_down_in_memory_db()


class TestLogRedirect:
    """Test logging redirects"""

    def test_log_redirect(self):
        """Test logging a permanent redirect"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        db_io.log_redirect('http://example.com/old', 301)

        # Verify redirect was logged
        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT COUNT(*) FROM permanentRedirects')
        count = cursor.fetchone()[0]
        assert count == 1

        cursor.execute('SELECT * FROM permanentRedirects')
        redirect = cursor.fetchone()
        assert redirect[0] == 'http://example.com/old'
        assert redirect[1] == 301
        mem_inst.tear_down_in_memory_db()


class TestLogException:
    """Test logging exceptions"""

    def test_log_exception(self):
        """Test logging an exception"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        db_io.log_exception('http://example.com', 'Connection timeout')

        # Verify exception was logged
        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT COUNT(*) FROM exceptions')
        count = cursor.fetchone()[0]
        assert count == 1

        cursor.execute('SELECT * FROM exceptions')
        exception = cursor.fetchone()
        assert exception[0] == 'http://example.com'
        assert exception[1] == 'Connection timeout'
        mem_inst.tear_down_in_memory_db()


class TestLogFileAccessError:
    """Test logging file access errors"""

    def test_log_file_access_error(self):
        """Test logging a file access error"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        db_io.log_file_access_error('/path/to/file.txt', 'Permission denied')

        # Verify error was logged
        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT COUNT(*) FROM fileAccessErrors')
        count = cursor.fetchone()[0]
        assert count == 1

        cursor.execute('SELECT * FROM fileAccessErrors')
        error = cursor.fetchone()
        assert error[0] == '/path/to/file.txt'
        assert error[1] == 'Permission denied'
        mem_inst.tear_down_in_memory_db()

    def test_count_file_access_errors(self):
        """The count drives whether unreadable files fail the run"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        assert db_io.count_file_access_errors() == 0

        db_io.log_file_access_error('/a.html', 'permission error')
        db_io.log_file_access_error('/b.bib', 'BibTeX parse error: bad token')

        assert db_io.count_file_access_errors() == 2
        mem_inst.tear_down_in_memory_db()


class TestDelLinksThatCanBeSkipped:
    """Test deleting links that can be skipped"""

    def test_del_links_that_can_be_skipped_no_cache(self):
        """Test when no cached URLs exist"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        links = [
            ('test.html', 'example.com', 'http://example.com', 'http://example.com', 'Link')
        ]
        db_io.save_found_links(links)

        num_remaining = db_io.del_links_that_can_be_skipped()
        assert num_remaining == 1
        mem_inst.tear_down_in_memory_db()

    def test_del_links_that_can_be_skipped_with_cache(self):
        """Test when cached URLs exist"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        # Add URLs to queue
        links = [
            ('test.html', 'example.com', 'http://example.com', 'http://example.com', 'Link 1'),
            ('test.html', 'example.org', 'http://example.org', 'http://example.org', 'Link 2')
        ]
        db_io.save_found_links(links)

        # Mark one URL as valid (cached)
        db_io.log_url_is_fine('http://example.com')

        num_remaining = db_io.del_links_that_can_be_skipped()
        assert num_remaining == 1

        # Verify correct URL remains
        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT normalizedUrl FROM queue')
        urls = cursor.fetchall()
        assert urls[0][0] == 'http://example.org'
        mem_inst.tear_down_in_memory_db()


class TestDelDoisThatCanBeSkipped:
    """Test deleting DOIs that can be skipped"""

    def test_del_dois_that_can_be_skipped_no_cache(self):
        """Test when no cached DOIs exist"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        dois = [
            ('test.bib', '10.1234/test1', 'Test Article 1')
        ]
        db_io.save_found_dois(dois)

        db_io.del_dois_that_can_be_skipped()

        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT COUNT(*) FROM queue_doi')
        count = cursor.fetchone()[0]
        assert count == 1
        mem_inst.tear_down_in_memory_db()

    def test_del_dois_that_can_be_skipped_with_cache(self):
        """Test when cached DOIs exist"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        # Add DOIs to queue
        dois = [
            ('test.bib', '10.1234/test1', 'Test Article 1'),
            ('test.bib', '10.1234/test2', 'Test Article 2')
        ]
        db_io.save_found_dois(dois)

        # Mark one DOI as valid (cached)
        db_io.save_valid_dois([('10.1234/test1',)])

        db_io.del_dois_that_can_be_skipped()

        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT COUNT(*) FROM queue_doi')
        count = cursor.fetchone()[0]
        assert count == 1

        # Verify correct DOI remains
        cursor.execute('SELECT doi FROM queue_doi')
        dois = cursor.fetchall()
        assert dois[0][0] == '10.1234/test2'
        mem_inst.tear_down_in_memory_db()


class TestCountErrors:
    """Test counting errors"""

    def test_count_errors_empty(self):
        """Test counting errors when none exist"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        count = db_io.count_errors()
        assert count == 0
        mem_inst.tear_down_in_memory_db()

    def test_count_errors_with_data(self):
        """Test counting errors when they exist"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        db_io.log_error('http://example.com/404', 404)
        db_io.log_error('http://example.com/410', 410)

        count = db_io.count_errors()
        assert count == 2
        mem_inst.tear_down_in_memory_db()


class TestConvertDoiUrlsToDois:
    """Test converting doi.org URLs from the URL queue to the DOI queue."""

    def test_convert_doi_urls_no_doi_urls(self):
        """Returns 0 when no doi.org URLs are in the queue."""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)
        db_io.save_found_links([
            ('test.html', 'example.com', 'http://example.com', 'http://example.com', 'Link')
        ])
        result = db_io.convert_doi_urls_to_dois()
        assert result == 0
        mem_inst.tear_down_in_memory_db()

    def test_convert_doi_urls_valid_doi(self):
        """Valid doi.org URL is moved to queue_doi and removed from queue."""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)
        db_io.save_found_links([
            ('refs.bib', 'doi.org', 'https://doi.org/10.1234/test', 'https://doi.org/10.1234/test', 'Smith2020')
        ])
        result = db_io.convert_doi_urls_to_dois()
        assert result == 1
        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT doi, filePath, description FROM queue_doi')
        row = cursor.fetchone()
        assert row[0] == '10.1234/test'
        assert row[1] == 'refs.bib'
        assert row[2] == 'Smith2020'
        cursor.execute("SELECT COUNT(*) FROM queue WHERE hostname = 'doi.org'")
        assert cursor.fetchone()[0] == 0
        mem_inst.tear_down_in_memory_db()

    def test_convert_doi_urls_invalid_doi_path(self):
        """doi.org URL with non-DOI path is left in queue and triggers a warning."""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)
        db_io.save_found_links([
            ('page.html', 'doi.org', 'https://doi.org/not-a-doi', 'https://doi.org/not-a-doi', 'Bad')
        ])
        result = db_io.convert_doi_urls_to_dois()
        assert result == 0
        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT COUNT(*) FROM queue_doi')
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT COUNT(*) FROM queue WHERE hostname = 'doi.org'")
        assert cursor.fetchone()[0] == 1
        mem_inst.tear_down_in_memory_db()

    def test_convert_doi_urls_linktext_fallback(self):
        """Uses URL as description when linktext is None."""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)
        db_io.save_found_links([
            ('refs.bib', 'doi.org', 'https://doi.org/10.5678/abc', 'https://doi.org/10.5678/abc', None)
        ])
        db_io.convert_doi_urls_to_dois()
        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT description FROM queue_doi')
        row = cursor.fetchone()
        assert row[0] == 'https://doi.org/10.5678/abc'
        mem_inst.tear_down_in_memory_db()


class TestDelLinksThatCanBeSkippedQuiet:
    """Test quiet=True suppresses output in del_links_that_can_be_skipped."""

    def test_quiet_true_suppresses_print(self):
        """No output when quiet=True even if URLs are skipped."""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst, quiet=True)
        db_io.save_found_links([
            ('test.html', 'example.com', 'http://example.com', 'http://example.com', 'Link')
        ])
        db_io.log_url_is_fine('http://example.com')
        result = db_io.del_links_that_can_be_skipped()
        assert result == 0
        mem_inst.tear_down_in_memory_db()


class TestDelDoisThatCanBeSkippedQuiet:
    """Test quiet=True suppresses output in del_dois_that_can_be_skipped."""

    def test_quiet_true_suppresses_print(self):
        """No output when quiet=True even if DOIs are skipped."""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst, quiet=True)
        db_io.save_found_dois([('refs.bib', '10.1234/test', 'Test')])
        db_io.save_valid_dois([('10.1234/test',)])
        db_io.del_dois_that_can_be_skipped()
        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT COUNT(*) FROM queue_doi')
        assert cursor.fetchone()[0] == 0
        mem_inst.tear_down_in_memory_db()


class TestListErrors:
    """Test listing errors"""

    def test_list_errors_none_exist(self):
        """Test listing errors when none exist"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        errors = db_io.list_errors(404)
        assert errors == []
        mem_inst.tear_down_in_memory_db()

    def test_list_errors_specific_code(self):
        """Test listing errors for a specific error code"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        db_io.log_error('http://example.com/404', 404)
        db_io.log_error('http://example.org/404', 404)
        db_io.log_error('http://example.net/410', 410)

        errors_404 = db_io.list_errors(404)
        assert len(errors_404) == 2

        errors_410 = db_io.list_errors(410)
        assert len(errors_410) == 1
        assert errors_410[0][0] == 'http://example.net/410'
        mem_inst.tear_down_in_memory_db()
