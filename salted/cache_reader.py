#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Read a cache file.
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2021 Rüdiger Voigt
Released under the Apache License 2.0
"""

import logging
import pathlib
import sqlite3
from typing import Optional, Union

from salted import memory_instance


class CacheReader:
    """Handle the cache file"""

    def __init__(self,
                 mem_instance: memory_instance.MemoryInstance,
                 dont_check_again_within_hours: int,
                 cache_file: Union[pathlib.Path, str] = None) -> None:

        self.cache_file_path: Optional[pathlib.Path] = None

        if not cache_file:
            logging.debug('No path to cache file provided.')
            return

        self.mem_instance = mem_instance
        self.cursor = mem_instance.get_cursor()

        self.dont_check_again_within_hours = dont_check_again_within_hours

        self.cache_file_path = pathlib.Path(cache_file).resolve()
        logging.debug('Absolute path to cache file: %s', self.cache_file_path)
        self.__check_cache_file_path()

    def __check_cache_file_path(self) -> None:
        """Check if the given path is valid in order to fail if it is not
           before the linkcheck runs.
           Raise ValueError if the path is a directory or if parent
           folders do not exists."""

        if not self.cache_file_path:
            raise RuntimeError('check_cache_file path called without path set')

        if self.cache_file_path.exists() and self.cache_file_path.is_file():
            return

        # Established that the file does not exist, but check if it can
        # exist before returning False.
        if not self.cache_file_path.parent.is_dir():
            raise ValueError('Incorrect path to cache_file. ' +
                             'Parameter cache_file must be the path to ' +
                             'a file and parent directories must exist.')
        if self.cache_file_path.is_dir():
            raise ValueError('Parameter cache_file is a directory, ' +
                             'but must include file name!')

    def load_disk_cache(self) -> None:
        """If there is a cache file open it, read the valid URLs and
           load them into the in-memory instance of sqlite."""

        if not self.cache_file_path:
            return

        valid_urls = list()
        valid_dois = list()

        try:
            logging.debug('Trying to load disk cache')
            disk_cache = sqlite3.connect(
                self.cache_file_path,
                isolation_level=None  # reenable autocommit
            )
            disk_cache_cursor = disk_cache.cursor()
            disk_cache_cursor.execute('''
                SELECT
                normalizedUrl, lastValid
                FROM validUrls
                WHERE lastValid > (strftime('%s','now') - (? * 3600));''',
                [self.dont_check_again_within_hours])
            valid_urls = disk_cache_cursor.fetchall()

            disk_cache_cursor.execute('SELECT doi, lastSeen FROM validDois;')
            valid_dois = disk_cache_cursor.fetchall()

        except Exception:
            logging.debug('No cache file or could not read it.', exc_info=True)
        finally:
            disk_cache.close()

        if valid_urls:
            self.cursor.executemany('''
                INSERT INTO validUrls
                (normalizedUrl, lastValid)
                VALUES (?, ?);''', valid_urls)

        if valid_dois:
            self.cursor.executemany(
                'INSERT INTO validDois (doi, lastSeen) VALUES (?, ?);',
                valid_dois)

    def overwrite_cache_file(self) -> None:
        """Write the current in-memory database into a file.
           Overwrite any file in the given path."""

        self.cache_file_path.unlink(missing_ok=True)  # type: ignore[union-attr]

        if self.cache_file_path:
            new_cache_file = sqlite3.connect(self.cache_file_path)
            with new_cache_file:
                self.mem_instance.conn.backup(new_cache_file, name='main')
            new_cache_file.close()
