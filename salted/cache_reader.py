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
from typing import Union

from salted import database_io


class CacheReader:
    """Handle the cache file"""

    def __init__(self,
                 db_object: database_io.DatabaseIO,
                 dont_check_again_within_hours: int,
                 cache_file: Union[pathlib.Path, str] = None) -> None:

        if not cache_file:
            logging.debug('No path to cache file provided.')
            return

        self.cursor = db_object.get_cursor()

        self.dont_check_again_within_hours = dont_check_again_within_hours

        self.cache_file_path = pathlib.Path(cache_file).resolve()
        logging.debug('Absolute path to cache file: %s', self.cache_file_path)
        self.__check_cache_file_path()
        self.__load_disk_cache()

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

    def __load_disk_cache(self) -> None:
        """If there is a cache file open it, read the valid URLs and
           load them into the in-memory instance of sqlite."""

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
