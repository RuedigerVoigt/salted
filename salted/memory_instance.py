#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Provide the sqlite3 in memory instance
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2021 Rüdiger Voigt
Released under the Apache License 2.0
"""

import logging
import sqlite3


class MemoryInstance():
    "Handles the in memory instance of the database"
    def __init__(self) -> None:
        "Initialize the in memory instance of sqlite"
        logging.debug('Initializing in memory database.')
        self.conn = sqlite3.connect(
            ':memory:',
            isolation_level=None  # reenable autocommit
            )
        self.cursor = self.conn.cursor()
        self.create_schema()

    def get_cursor(self) -> sqlite3.Cursor:
        """Returns a valid cursor. Is used by the report generator that
           directly accesses the database outside this class.
           If user reuse the object a new database is created and in that case
           the old cursor is invalid."""
        return self.cursor

    def tear_down_in_memory_db(self) -> None:
        """If there is an active in memory instance, close the connection.
           All data not stored elsewhere will be lost."""
        if self.conn:
            logging.debug("tear down in memory instance")
            self.conn.close()

    def create_schema(self) -> None:
        """Create the SQLite database schema. """
        # Table 'queue': URLs to be tested
        self.cursor.execute('''
            CREATE TABLE queue (
            filePath text,
            doi text,
            hostname text,
            url text,
            normalizedUrl text,
            linktext text);''')
        # Table 'queue_doi': DOIs to be tested
        self.cursor.execute('''
            CREATE TABLE queue_doi (
            filePath text,
            doi text,
            description text);''')
        # Table 'errors': invalid hyperlinks
        self.cursor.execute('''
            CREATE TABLE errors (
            normalizedUrl text,
            error integer);''')
        # Table 'fileAccessErrors': paths of files that could not be read
        self.cursor.execute('''
            CREATE TABLE fileAccessErrors (
                filePath text,
                problem text
                );''')
        # Table 'permanentRedirects': permanent redirects that were encountered
        self.cursor.execute('''
            CREATE TABLE permanentRedirects (
                normalizedUrl text,
                error integer);''')
        # Table 'exceptions': exception sthat occured by crawling
        # like network timeouts, et cetera
        self.cursor.execute('''
            CREATE TABLE exceptions (
            normalizedUrl text,
            reason text);''')
        # table 'validUrls': cache for URls
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS validUrls (
            normalizedUrl text,
            lastValid integer);''')
        # table 'validDois': cache for DOI
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS validDois (
            doi text,
            lastSeen integer);''')

        logging.debug("Created database schema.")

    def generate_indices(self) -> None:
        """Add indices to the in memory database. This is not done on creation
           for performance reasons."""
        # While adding links to the database the index is not needed,
        # but would be updated with every insert. It is faster to create it
        # once the table has it contents.
        logging.debug('Generating indices')
        self.cursor.execute('''
            CREATE INDEX IF NOT EXISTS index_timestamp
            ON validUrls (lastValid);''')
        self.cursor.execute('''
            CREATE INDEX IF NOT EXISTS index_normalized_url
            ON queue (normalizedUrl);''')
        self.cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS index_valid_doi
            ON validDois (doi);''')

    def generate_db_views(self) -> None:
        """ Generate Views for Analytics and Output Generating."""
        # Separate function to execute after all links have been checked
        # and the respective tables are stable."""
        logging.debug('Generating database views')
        self.cursor.execute('''
            CREATE VIEW IF NOT EXISTS v_errorCountByFile AS
            SELECT COUNT(*) AS numErrors, filePath
            FROM queue
            WHERE normalizedUrl IN (
            SELECT normalizedUrl FROM errors
            ) GROUP BY filePath;''')
        self.cursor.execute('''
            CREATE VIEW IF NOT EXISTS v_redirectCountByFile AS
            SELECT COUNT(*) AS numRedirects, filePath
            FROM queue
            WHERE normalizedUrl IN (
            SELECT normalizedUrl FROM permanentRedirects
            ) GROUP BY filePath;''')
        self.cursor.execute('''
            CREATE VIEW IF NOT EXISTS v_exceptionCountByFile AS
            SELECT COUNT(*) AS numExceptions, filePath
            FROM queue
            WHERE normalizedUrl IN (
            SELECT normalizedUrl FROM exceptions
            ) GROUP BY filePath;''')

        self.cursor.execute('''
            CREATE VIEW IF NOT EXISTS v_errorsByFile AS
            SELECT queue.filePath,
            queue.url,
            queue.linktext,
            errors.error AS httpCode
            FROM queue
            INNER JOIN errors
            ON queue.normalizedUrl = errors.normalizedUrl;''')

        self.cursor.execute('''
            CREATE VIEW IF NOT EXISTS v_redirectsByFile AS
            SELECT queue.filePath,
            queue.url,
            queue.linktext,
            permanentRedirects.error AS httpCode
            FROM queue
            INNER JOIN permanentRedirects
            ON queue.normalizedUrl = permanentRedirects.normalizedUrl;''')

        self.cursor.execute('''
            CREATE VIEW IF NOT EXISTS v_exceptionsByFile AS
            SELECT queue.filePath,
            queue.url,
            queue.linktext,
            exceptions.reason
            FROM queue
            INNER JOIN exceptions
            ON queue.normalizedUrl = exceptions.normalizedUrl;''')

        logging.debug('Created Views for analytics and output generating.')
