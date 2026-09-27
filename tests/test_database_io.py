#!/usr/bin/python3

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
        db_io.save_found_dois([])
        assert db_io.count_dois() == 0
        mem_inst.tear_down_in_memory_db()

    def test_save_found_dois_with_data(self):
        """Test saving DOIs to database"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)
        db_io.save_found_dois([
            ('test.bib', '10.1234/test1', 'Test Article 1', 1),
            ('test.bib', '10.1234/test2', 'Test Article 2', 1),
        ])
        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT COUNT(*) FROM foundDois')
        assert cursor.fetchone()[0] == 2
        mem_inst.tear_down_in_memory_db()


class TestDoiCounts:
    """Counts of found, malformed and confirmed DOIs."""

    def test_counts_are_case_insensitive_and_distinct(self):
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)
        db_io.save_found_dois([
            ('a.bib', '10.1234/ABC', 'A', 1),
            ('b.bib', '10.1234/abc', 'B', 1),
            ('b.bib', 'nonsense', 'C', 0),
            ('c.bib', 'NONSENSE', 'D', 0),
        ])
        assert db_io.count_dois() == 2
        assert db_io.count_malformed_dois() == 1
        assert db_io.count_confirmed_dois() == 0
        mem_inst.tear_down_in_memory_db()

    def test_confirmed_doi_matches_any_case(self):
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)
        db_io.save_found_dois([('a.bib', '10.1038/NATURE14539', 'A', 1)])
        mem_inst.get_cursor().execute(
            "INSERT INTO validDois (doi) VALUES ('10.1038/nature14539')")
        assert db_io.count_confirmed_dois() == 1
        mem_inst.tear_down_in_memory_db()


class TestConfirmDoisFromLinks:
    """A doi.org link that answered as fine confirms its DOI."""

    @staticmethod
    def _queue(db_io, url, hostname):
        db_io.save_found_links([('page.html', hostname, url, url, 'text')])

    @staticmethod
    def _confirmed(mem_inst):
        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT doi FROM validDois ORDER BY doi')
        return [row[0] for row in cursor.fetchall()]

    def test_fine_doi_link_confirms_the_doi_in_lower_case(self):
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)
        url = 'https://doi.org/10.1038/NATURE14539'
        self._queue(db_io, url, 'doi.org')
        db_io.log_url_is_fine(url)
        db_io.confirm_dois_from_links()
        assert self._confirmed(mem_inst) == ['10.1038/nature14539']
        mem_inst.tear_down_in_memory_db()

    def test_percent_encoded_doi_is_decoded(self):
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)
        url = 'https://dx.doi.org/10.1175/1520-0469(1963)020%3C0130:DNF%3E2.0.CO;2'
        self._queue(db_io, url, 'dx.doi.org')
        db_io.log_url_is_fine(url)
        db_io.confirm_dois_from_links()
        assert self._confirmed(mem_inst) == [
            '10.1175/1520-0469(1963)020<0130:dnf>2.0.co;2']
        mem_inst.tear_down_in_memory_db()

    def test_unchecked_or_dead_link_confirms_nothing(self):
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)
        self._queue(db_io, 'https://doi.org/10.1234/dead', 'doi.org')
        db_io.log_error('https://doi.org/10.1234/dead', 404)
        db_io.confirm_dois_from_links()
        assert self._confirmed(mem_inst) == []
        mem_inst.tear_down_in_memory_db()

    def test_other_hosts_and_malformed_paths_confirm_nothing(self):
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)
        for url, host in [('https://example.com/10.1234/x', 'example.com'),
                          ('https://doi.org/help.html', 'doi.org')]:
            self._queue(db_io, url, host)
            db_io.log_url_is_fine(url)
        db_io.confirm_dois_from_links()
        assert self._confirmed(mem_inst) == []
        mem_inst.tear_down_in_memory_db()

    def test_calling_twice_stores_the_doi_once(self):
        mem_inst = memory_instance.MemoryInstance()
        mem_inst.generate_indices()
        db_io = database_io.DatabaseIO(mem_inst)
        url = 'https://doi.org/10.1234/x'
        self._queue(db_io, url, 'doi.org')
        db_io.log_url_is_fine(url)
        db_io.confirm_dois_from_links()
        db_io.confirm_dois_from_links()
        assert self._confirmed(mem_inst) == ['10.1234/x']
        mem_inst.tear_down_in_memory_db()


class TestLogOutdatedDoiLinks:
    """Test saving DOIs written in an outdated form."""

    def test_rows_are_saved_and_empty_list_is_fine(self):
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)
        db_io.log_outdated_doi_links([])
        db_io.log_outdated_doi_links([
            ('a.bib', 'doi:10.1234/x', 'https://doi.org/10.1234/x', 'K')])
        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT * FROM outdatedDoiLinks')
        assert cursor.fetchall() == [
            ('a.bib', 'doi:10.1234/x', 'https://doi.org/10.1234/x', 'K')]
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

    def test_urls_to_check_skips_malformed_urls(self):
        """A link logged as malformed is never handed to the URL checker"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        links = [
            ('test.md', None, 'http://:8080/', 'http://:8080/', 'Broken'),
            ('test.md', 'example.com', 'http://example.com', 'http://example.com', 'Fine')
        ]
        db_io.save_found_links(links)
        db_io.log_malformed_url('http://:8080/')

        assert db_io.urls_to_check() == [('http://example.com',)]
        mem_inst.tear_down_in_memory_db()


class TestLogMalformedUrl:
    """Test logging links that cannot be requested"""

    def test_logged_once_per_url(self):
        """The same malformed link in several files yields one exception"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        links = [
            ('a.md', None, 'http://:8080/', 'http://:8080/', 'Broken'),
            ('b.md', None, 'http://:8080/', 'http://:8080/', 'Broken')
        ]
        db_io.save_found_links(links)
        db_io.log_malformed_url('http://:8080/')
        db_io.log_malformed_url('http://:8080/')

        cursor = mem_inst.get_cursor()
        cursor.execute('SELECT * FROM exceptions')
        assert cursor.fetchall() == [
            ('http://:8080/', database_io.MALFORMED_URL_REASON)]
        # One report row per occurrence, not per occurrence and exception
        mem_inst.generate_db_views()
        cursor.execute('SELECT filePath FROM v_exceptionsByFile ORDER BY filePath')
        assert cursor.fetchall() == [('a.md',), ('b.md',)]
        mem_inst.tear_down_in_memory_db()

    def test_count_malformed_urls(self):
        """Only malformed links are counted, not network exceptions"""
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)

        assert db_io.count_malformed_urls() == 0
        db_io.log_malformed_url('http://:8080/')
        db_io.log_malformed_url('http://:8080/')
        db_io.log_malformed_url('http://example.com:99999/')
        db_io.log_exception('http://example.com', 'Connection timeout')
        assert db_io.count_malformed_urls() == 2
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


class TestCountDistinctAndCachedUrls:
    """Counts used for the statistics at the top of the report."""

    def test_counts_distinct_normalized_urls(self):
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)
        db_io.save_found_links([
            ('a.html', 'example.com', 'http://example.com#x', 'http://example.com', 'A'),
            ('b.html', 'example.com', 'http://example.com', 'http://example.com', 'B'),
            ('b.html', 'example.org', 'http://example.org', 'http://example.org', 'C'),
        ])
        assert db_io.count_distinct_urls() == 2
        assert db_io.count_cached_urls() == 0
        mem_inst.tear_down_in_memory_db()

    def test_cached_url_counted_once_however_often_linked(self):
        mem_inst = memory_instance.MemoryInstance()
        db_io = database_io.DatabaseIO(mem_inst)
        db_io.save_found_links([
            ('a.html', 'example.com', 'http://example.com', 'http://example.com', 'A'),
            ('b.html', 'example.com', 'http://example.com', 'http://example.com', 'B'),
            ('b.html', 'example.org', 'http://example.org', 'http://example.org', 'C'),
        ])
        db_io.log_url_is_fine('http://example.com')
        assert db_io.count_cached_urls() == 1
        db_io.del_links_that_can_be_skipped()
        assert db_io.count_cached_urls() == 0
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
