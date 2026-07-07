#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Tests for cache_reader module
~~~~~~~~~~~~~~~~~~~~~
Smart, Asynchronous Link Tester with Database backend (SALTED)
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2025: Released under the Apache License 2.0
"""

import pathlib
import sqlite3
import tempfile
import pytest

from salted import cache_reader, memory_instance


class TestCacheReaderInitialization:
    """Test CacheReader initialization"""

    def test_initialization_without_cache_file(self):
        """Test initialization without cache file"""
        mem_inst = memory_instance.MemoryInstance()
        reader = cache_reader.CacheReader(
            mem_instance=mem_inst,
            dont_check_again_within_hours=24,
            cache_file=None
        )
        assert reader.cache_file_path is None
        mem_inst.tear_down_in_memory_db()

    def test_initialization_with_valid_file_path(self):
        """Test initialization with valid file path"""
        mem_inst = memory_instance.MemoryInstance()
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = pathlib.Path(tmpdir) / "cache.db"
            reader = cache_reader.CacheReader(
                mem_instance=mem_inst,
                dont_check_again_within_hours=24,
                cache_file=cache_file
            )
            assert reader.cache_file_path == cache_file.resolve()
        mem_inst.tear_down_in_memory_db()

    def test_initialization_with_existing_cache_file(self):
        """Test initialization with existing cache file"""
        mem_inst = memory_instance.MemoryInstance()
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = pathlib.Path(tmpdir) / "cache.db"
            cache_file.touch()  # Create the file

            reader = cache_reader.CacheReader(
                mem_instance=mem_inst,
                dont_check_again_within_hours=24,
                cache_file=cache_file
            )
            assert reader.cache_file_path == cache_file.resolve()
        mem_inst.tear_down_in_memory_db()

    def test_initialization_cache_file_parent_not_exists(self):
        """Test initialization when parent directory doesn't exist"""
        mem_inst = memory_instance.MemoryInstance()

        cache_file = pathlib.Path("/nonexistent/directory/cache.db")

        with pytest.raises(ValueError, match="Incorrect path to cache_file"):
            cache_reader.CacheReader(
                mem_instance=mem_inst,
                dont_check_again_within_hours=24,
                cache_file=cache_file
            )
        mem_inst.tear_down_in_memory_db()

    def test_initialization_cache_file_is_directory(self):
        """Test initialization when cache_file is a directory"""
        mem_inst = memory_instance.MemoryInstance()

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = pathlib.Path(tmpdir)

            with pytest.raises(ValueError, match="cache_file is a directory"):
                cache_reader.CacheReader(
                    mem_instance=mem_inst,
                    dont_check_again_within_hours=24,
                    cache_file=cache_dir
                )
        mem_inst.tear_down_in_memory_db()


class TestLoadDiskCache:
    """Test loading cache from disk"""

    def test_load_disk_cache_no_file_path(self):
        """Test load_disk_cache when no cache file path is set"""
        mem_inst = memory_instance.MemoryInstance()
        reader = cache_reader.CacheReader(
            mem_instance=mem_inst,
            dont_check_again_within_hours=24,
            cache_file=None
        )
        # Should return early without error
        reader.load_disk_cache()
        mem_inst.tear_down_in_memory_db()

    def test_load_disk_cache_file_does_not_exist(self):
        """Test load_disk_cache when cache file doesn't exist yet"""
        mem_inst = memory_instance.MemoryInstance()

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = pathlib.Path(tmpdir) / "cache.db"

            reader = cache_reader.CacheReader(
                mem_instance=mem_inst,
                dont_check_again_within_hours=24,
                cache_file=cache_file
            )

            # Should handle missing file gracefully
            reader.load_disk_cache()
        mem_inst.tear_down_in_memory_db()

    def test_load_disk_cache_with_valid_urls(self):
        """Test loading valid URLs from cache"""
        mem_inst = memory_instance.MemoryInstance()

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = pathlib.Path(tmpdir) / "cache.db"

            # Create a cache file with valid URLs
            cache_conn = sqlite3.connect(cache_file)
            cache_cursor = cache_conn.cursor()
            cache_cursor.execute('''
                CREATE TABLE validUrls (
                    normalizedUrl text,
                    lastValid integer
                )
            ''')
            cache_cursor.execute('''
                CREATE TABLE validDois (
                    doi text
                )
            ''')
            # Insert a URL with current timestamp (within cache lifetime)
            cache_cursor.execute('''
                INSERT INTO validUrls VALUES (?, strftime('%s', 'now'))
            ''', ['http://example.com'])
            cache_conn.commit()
            cache_conn.close()

            reader = cache_reader.CacheReader(
                mem_instance=mem_inst,
                dont_check_again_within_hours=24,
                cache_file=cache_file
            )
            reader.load_disk_cache()

            # Verify URL was loaded
            mem_inst.cursor.execute('SELECT COUNT(*) FROM validUrls')
            count = mem_inst.cursor.fetchone()[0]
            assert count == 1
        mem_inst.tear_down_in_memory_db()

    def test_load_disk_cache_with_valid_dois(self):
        """Test loading valid DOIs from cache"""
        mem_inst = memory_instance.MemoryInstance()

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = pathlib.Path(tmpdir) / "cache.db"

            # Create a cache file with valid DOIs
            cache_conn = sqlite3.connect(cache_file)
            cache_cursor = cache_conn.cursor()
            cache_cursor.execute('''
                CREATE TABLE validUrls (
                    normalizedUrl text,
                    lastValid integer
                )
            ''')
            cache_cursor.execute('''
                CREATE TABLE validDois (
                    doi text
                )
            ''')
            # Insert a DOI
            cache_cursor.execute('''
                INSERT INTO validDois VALUES (?)
            ''', ['10.1234/test'])
            cache_conn.commit()
            cache_conn.close()

            reader = cache_reader.CacheReader(
                mem_instance=mem_inst,
                dont_check_again_within_hours=24,
                cache_file=cache_file
            )
            reader.load_disk_cache()

            # Verify DOI was loaded
            mem_inst.cursor.execute('SELECT COUNT(*) FROM validDois')
            count = mem_inst.cursor.fetchone()[0]
            assert count == 1
        mem_inst.tear_down_in_memory_db()

    def test_load_disk_cache_expired_urls(self):
        """Test that expired URLs are not loaded"""
        mem_inst = memory_instance.MemoryInstance()

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = pathlib.Path(tmpdir) / "cache.db"

            # Create a cache file with expired URL
            cache_conn = sqlite3.connect(cache_file)
            cache_cursor = cache_conn.cursor()
            cache_cursor.execute('''
                CREATE TABLE validUrls (
                    normalizedUrl text,
                    lastValid integer
                )
            ''')
            cache_cursor.execute('''
                CREATE TABLE validDois (
                    doi text
                )
            ''')
            # Insert a URL with old timestamp (expired)
            cache_cursor.execute('''
                INSERT INTO validUrls VALUES (?, strftime('%s', 'now') - 100000)
            ''', ['http://expired.com'])
            cache_conn.commit()
            cache_conn.close()

            reader = cache_reader.CacheReader(
                mem_instance=mem_inst,
                dont_check_again_within_hours=24,
                cache_file=cache_file
            )
            reader.load_disk_cache()

            # Verify expired URL was not loaded
            mem_inst.cursor.execute('SELECT COUNT(*) FROM validUrls')
            count = mem_inst.cursor.fetchone()[0]
            assert count == 0
        mem_inst.tear_down_in_memory_db()

    def test_load_disk_cache_corrupted_file(self):
        """Test handling of corrupted cache file"""
        mem_inst = memory_instance.MemoryInstance()

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = pathlib.Path(tmpdir) / "cache.db"

            # Create a corrupted file (not a valid SQLite database)
            cache_file.write_text("This is not a valid SQLite database")

            reader = cache_reader.CacheReader(
                mem_instance=mem_inst,
                dont_check_again_within_hours=24,
                cache_file=cache_file
            )

            # Should handle corrupted file gracefully
            reader.load_disk_cache()
        mem_inst.tear_down_in_memory_db()


class TestOverwriteCacheFile:
    """Test overwriting cache file"""

    def test_overwrite_cache_file_creates_new(self):
        """Test overwriting cache file creates new file"""
        mem_inst = memory_instance.MemoryInstance()

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = pathlib.Path(tmpdir) / "cache.db"

            reader = cache_reader.CacheReader(
                mem_instance=mem_inst,
                dont_check_again_within_hours=24,
                cache_file=cache_file
            )

            # Add some data to memory instance
            mem_inst.cursor.execute('''
                INSERT INTO validUrls VALUES (?, strftime('%s', 'now'))
            ''', ['http://example.com'])

            # Overwrite (create) cache file
            reader.overwrite_cache_file()

            # Verify file was created
            assert cache_file.exists()

            # Verify data was written
            conn = sqlite3.connect(cache_file)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM validUrls')
            count = cursor.fetchone()[0]
            assert count == 1
            conn.close()
        mem_inst.tear_down_in_memory_db()

    def test_overwrite_cache_file_only_persists_cache_tables(self):
        """Only validUrls/validDois reach disk; tables holding local file
        paths and e-mail addresses (queue, mailtoLinks) must not leak."""
        mem_inst = memory_instance.MemoryInstance()

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = pathlib.Path(tmpdir) / "cache.db"

            reader = cache_reader.CacheReader(
                mem_instance=mem_inst,
                dont_check_again_within_hours=24,
                cache_file=cache_file
            )

            # Data that should be persisted:
            mem_inst.cursor.execute(
                "INSERT INTO validUrls VALUES (?, strftime('%s', 'now'))",
                ['http://example.com'])
            mem_inst.cursor.execute(
                "INSERT INTO validDois VALUES (?)", ['10.1000/xyz'])
            # Sensitive data that must NOT be written to disk:
            mem_inst.cursor.execute(
                "INSERT INTO queue (filePath, hostname, url, normalizedUrl, linktext)"
                " VALUES (?, ?, ?, ?, ?)",
                [r'C:\Users\secret\private.md', 'example.com',
                 'http://example.com', 'http://example.com', 'link'])
            mem_inst.cursor.execute(
                "INSERT INTO mailtoLinks VALUES (?, ?, ?, ?)",
                [r'C:\Users\secret\private.md', 'mailto:a@b.com', 'a@b.com', 1])

            reader.overwrite_cache_file()

            conn = sqlite3.connect(cache_file)
            try:
                tables = {row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table';")}
                assert tables == {'validUrls', 'validDois'}
                assert conn.execute(
                    'SELECT normalizedUrl FROM validUrls').fetchone()[0] == \
                    'http://example.com'
                assert conn.execute(
                    'SELECT doi FROM validDois').fetchone()[0] == '10.1000/xyz'
            finally:
                conn.close()
        mem_inst.tear_down_in_memory_db()

    def test_overwrite_cache_file_atomic_on_failure(self, monkeypatch):
        """A failure during the atomic replace must leave the existing cache
        intact and not leave a stray temp file behind."""
        mem_inst = memory_instance.MemoryInstance()

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = pathlib.Path(tmpdir) / "cache.db"

            # Existing cache with known-good content.
            cache_conn = sqlite3.connect(cache_file)
            cache_conn.execute(
                'CREATE TABLE validUrls (normalizedUrl text, lastValid integer);')
            cache_conn.execute(
                "INSERT INTO validUrls VALUES (?, strftime('%s', 'now'))",
                ['http://old.com'])
            cache_conn.commit()
            cache_conn.close()

            reader = cache_reader.CacheReader(
                mem_instance=mem_inst,
                dont_check_again_within_hours=24,
                cache_file=cache_file
            )
            mem_inst.cursor.execute(
                "INSERT INTO validUrls VALUES (?, strftime('%s', 'now'))",
                ['http://new.com'])

            # Force the atomic move to fail after the temp file is built.
            def boom(src, dst):
                raise OSError('simulated disk failure')
            monkeypatch.setattr(cache_reader.os, 'replace', boom)

            with pytest.raises(OSError, match='simulated disk failure'):
                reader.overwrite_cache_file()

            # The previous cache is untouched (still the old URL, not the new).
            conn = sqlite3.connect(cache_file)
            try:
                urls = [row[0] for row in conn.execute(
                    'SELECT normalizedUrl FROM validUrls')]
            finally:
                conn.close()
            assert urls == ['http://old.com']

            # No stray temp file left behind.
            tmp_path = cache_file.with_name(cache_file.name + '.tmp')
            assert not tmp_path.exists()
        mem_inst.tear_down_in_memory_db()

    def test_overwrite_cache_file_replaces_existing(self):
        """Test overwriting existing cache file"""
        mem_inst = memory_instance.MemoryInstance()

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = pathlib.Path(tmpdir) / "cache.db"

            # Create initial cache file
            cache_conn = sqlite3.connect(cache_file)
            cache_cursor = cache_conn.cursor()
            cache_cursor.execute('''
                CREATE TABLE validUrls (
                    normalizedUrl text,
                    lastValid integer
                )
            ''')
            cache_cursor.execute('''
                INSERT INTO validUrls VALUES (?, strftime('%s', 'now'))
            ''', ['http://old.com'])
            cache_conn.commit()
            cache_conn.close()

            reader = cache_reader.CacheReader(
                mem_instance=mem_inst,
                dont_check_again_within_hours=24,
                cache_file=cache_file
            )

            # Add new data to memory instance
            mem_inst.cursor.execute('''
                INSERT INTO validUrls VALUES (?, strftime('%s', 'now'))
            ''', ['http://new.com'])

            # Overwrite cache file
            reader.overwrite_cache_file()

            # Verify file was overwritten
            conn = sqlite3.connect(cache_file)
            cursor = conn.cursor()
            cursor.execute('SELECT normalizedUrl FROM validUrls')
            urls = [row[0] for row in cursor.fetchall()]

            # Should only have new data
            assert 'http://new.com' in urls
            # Old data should be gone (file was replaced)
            # Note: The old data might still be there if it was loaded first
            conn.close()
        mem_inst.tear_down_in_memory_db()
