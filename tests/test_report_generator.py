#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Tests for report_generator module
~~~~~~~~~~~~~~~~~~~~~
Smart, Asynchronous Link Tester with Database backend (SALTED)
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2025: Released under the Apache License 2.0
"""

import pytest
import tempfile
import pathlib

from salted import report_generator, memory_instance


class TestReportGeneratorInitialization:
    """Test ReportGenerator initialization"""

    def test_initialization_defaults(self):
        """Test initialization with defaults"""
        mem_inst = memory_instance.MemoryInstance()
        gen = report_generator.ReportGenerator(mem_inst)

        assert gen.show_redirects is True
        assert gen.show_exceptions is True
        assert gen.replace_path_by_url is None
        mem_inst.tear_down_in_memory_db()

    def test_initialization_custom_flags(self):
        """Test initialization with custom flags"""
        mem_inst = memory_instance.MemoryInstance()
        gen = report_generator.ReportGenerator(
            mem_inst,
            show_redirects=False,
            show_exceptions=False
        )

        assert gen.show_redirects is False
        assert gen.show_exceptions is False
        mem_inst.tear_down_in_memory_db()


class TestRewritePath:
    """Test path rewriting functionality"""

    def test_rewrite_path_success(self):
        """Test successful path rewriting"""
        mem_inst = memory_instance.MemoryInstance()
        gen = report_generator.ReportGenerator(mem_inst)

        gen.replace_path_by_url = {
            'path_to_be_replaced': '/local/path',
            'replace_with_url': 'http://example.com'
        }

        result = gen.rewrite_path('/local/path/file.html')
        assert result == 'http://example.com/file.html'
        mem_inst.tear_down_in_memory_db()

    def test_rewrite_path_missing_path_to_replace(self):
        """Test rewrite_path raises error when path_to_be_replaced is missing"""
        mem_inst = memory_instance.MemoryInstance()
        gen = report_generator.ReportGenerator(mem_inst)

        gen.replace_path_by_url = {
            'path_to_be_replaced': None,
            'replace_with_url': 'http://example.com'
        }

        with pytest.raises(ValueError, match="not knowing what"):
            gen.rewrite_path('/local/path/file.html')
        mem_inst.tear_down_in_memory_db()

    def test_rewrite_path_missing_replace_with_url(self):
        """Test rewrite_path raises error when replace_with_url is missing"""
        mem_inst = memory_instance.MemoryInstance()
        gen = report_generator.ReportGenerator(mem_inst)

        gen.replace_path_by_url = {
            'path_to_be_replaced': '/local/path',
            'replace_with_url': None
        }

        with pytest.raises(ValueError, match="not knowing with what"):
            gen.rewrite_path('/local/path/file.html')
        mem_inst.tear_down_in_memory_db()


class TestGenerateAccessErrorList:
    """Test generating access error list"""

    def test_generate_access_error_list_no_errors(self):
        """Test when there are no file access errors"""
        mem_inst = memory_instance.MemoryInstance()
        gen = report_generator.ReportGenerator(mem_inst)

        result = gen.generate_access_error_list()
        assert result is None
        mem_inst.tear_down_in_memory_db()

    def test_generate_access_error_list_with_errors(self):
        """Test when there are file access errors"""
        mem_inst = memory_instance.MemoryInstance()
        gen = report_generator.ReportGenerator(mem_inst)

        # Add some file access errors
        cursor = mem_inst.get_cursor()
        cursor.execute('''
            INSERT INTO fileAccessErrors VALUES (?, ?)
        ''', ['/path/file1.html', 'File not found'])
        cursor.execute('''
            INSERT INTO fileAccessErrors VALUES (?, ?)
        ''', ['/path/file2.html', 'Permission denied'])

        result = gen.generate_access_error_list()
        assert result is not None
        assert len(result) == 2
        assert result[0]['path'] == '/path/file1.html'
        assert result[0]['problem'] == 'File not found'
        assert result[1]['path'] == '/path/file2.html'
        assert result[1]['problem'] == 'Permission denied'
        mem_inst.tear_down_in_memory_db()


class TestGenerateErrorList:
    """Test generating error list"""

    def test_generate_error_list_no_errors(self):
        """Test when there are no errors"""
        mem_inst = memory_instance.MemoryInstance()
        mem_inst.generate_db_views()
        gen = report_generator.ReportGenerator(mem_inst)

        result = gen.generate_error_list()
        assert result is None
        mem_inst.tear_down_in_memory_db()

    def test_generate_error_list_with_errors(self):
        """Test when there are errors"""
        mem_inst = memory_instance.MemoryInstance()
        mem_inst.generate_db_views()
        gen = report_generator.ReportGenerator(mem_inst)

        # Add some links to the queue
        cursor = mem_inst.get_cursor()
        cursor.execute('''
            INSERT INTO queue VALUES (?, ?, ?, ?, ?, ?)
        ''', ['test.html', None, 'example.com', 'http://example.com/404', 'http://example.com/404', 'Link'])

        # Add an error
        cursor.execute('''
            INSERT INTO errors VALUES (?, ?)
        ''', ['http://example.com/404', 404])

        result = gen.generate_error_list()
        assert result is not None
        assert len(result) == 1
        assert result[0]['path'] == 'test.html'
        assert result[0]['num_errors'] == 1
        mem_inst.tear_down_in_memory_db()


class TestGenerateRedirectList:
    """Test generating redirect list"""

    def test_generate_redirect_list_no_redirects(self):
        """Test when there are no redirects"""
        mem_inst = memory_instance.MemoryInstance()
        mem_inst.generate_db_views()
        gen = report_generator.ReportGenerator(mem_inst)

        result = gen.generate_redirect_list()
        assert result is None
        mem_inst.tear_down_in_memory_db()

    def test_generate_redirect_list_with_redirects(self):
        """Test when there are redirects"""
        mem_inst = memory_instance.MemoryInstance()
        mem_inst.generate_db_views()
        gen = report_generator.ReportGenerator(mem_inst)

        # Add some links to the queue
        cursor = mem_inst.get_cursor()
        cursor.execute('''
            INSERT INTO queue VALUES (?, ?, ?, ?, ?, ?)
        ''', ['test.html', None, 'example.com', 'http://example.com/old', 'http://example.com/old', 'Link'])

        # Add a redirect
        cursor.execute('''
            INSERT INTO permanentRedirects VALUES (?, ?)
        ''', ['http://example.com/old', 301])

        result = gen.generate_redirect_list()
        assert result is not None
        assert len(result) == 1
        assert result[0]['path'] == 'test.html'
        assert result[0]['num_redirects'] == 1
        mem_inst.tear_down_in_memory_db()

    def test_generate_redirect_list_with_path_rewriting(self):
        """Test redirect list with path rewriting enabled"""
        mem_inst = memory_instance.MemoryInstance()
        mem_inst.generate_db_views()
        gen = report_generator.ReportGenerator(mem_inst)

        gen.replace_path_by_url = {
            'path_to_be_replaced': 'test',
            'replace_with_url': 'http://example.com'
        }

        # Add some links to the queue
        cursor = mem_inst.get_cursor()
        cursor.execute('''
            INSERT INTO queue VALUES (?, ?, ?, ?, ?, ?)
        ''', ['test.html', None, 'example.com', 'http://example.com/old', 'http://example.com/old', 'Link'])

        # Add a redirect
        cursor.execute('''
            INSERT INTO permanentRedirects VALUES (?, ?)
        ''', ['http://example.com/old', 301])

        result = gen.generate_redirect_list()
        assert result is not None
        assert result[0]['path'] == 'http://example.com.html'
        mem_inst.tear_down_in_memory_db()


class TestGenerateExceptionList:
    """Test generating exception list"""

    def test_generate_exception_list_no_exceptions(self):
        """Test when there are no exceptions"""
        mem_inst = memory_instance.MemoryInstance()
        mem_inst.generate_db_views()
        gen = report_generator.ReportGenerator(mem_inst)

        result = gen.generate_exception_list()
        assert result is None
        mem_inst.tear_down_in_memory_db()

    def test_generate_exception_list_with_exceptions(self):
        """Test when there are exceptions"""
        mem_inst = memory_instance.MemoryInstance()
        mem_inst.generate_db_views()
        gen = report_generator.ReportGenerator(mem_inst)

        # Add some links to the queue
        cursor = mem_inst.get_cursor()
        cursor.execute('''
            INSERT INTO queue VALUES (?, ?, ?, ?, ?, ?)
        ''', ['test.html', None, 'example.com', 'http://example.com/timeout', 'http://example.com/timeout', 'Link'])

        # Add an exception
        cursor.execute('''
            INSERT INTO exceptions VALUES (?, ?)
        ''', ['http://example.com/timeout', 'Connection timeout'])

        result = gen.generate_exception_list()
        assert result is not None
        assert len(result) == 1
        assert result[0]['path'] == 'test.html'
        assert result[0]['num_exceptions'] == 1
        mem_inst.tear_down_in_memory_db()

    def test_generate_exception_list_with_path_rewriting(self):
        """Test exception list with path rewriting enabled"""
        mem_inst = memory_instance.MemoryInstance()
        mem_inst.generate_db_views()
        gen = report_generator.ReportGenerator(mem_inst)

        gen.replace_path_by_url = {
            'path_to_be_replaced': 'test',
            'replace_with_url': 'http://example.com'
        }

        # Add some links to the queue
        cursor = mem_inst.get_cursor()
        cursor.execute('''
            INSERT INTO queue VALUES (?, ?, ?, ?, ?, ?)
        ''', ['test.html', None, 'example.com', 'http://example.com/timeout', 'http://example.com/timeout', 'Link'])

        # Add an exception
        cursor.execute('''
            INSERT INTO exceptions VALUES (?, ?)
        ''', ['http://example.com/timeout', 'Connection timeout'])

        result = gen.generate_exception_list()
        assert result is not None
        assert result[0]['path'] == 'http://example.com.html'
        mem_inst.tear_down_in_memory_db()


class TestGenerateErrorListWithPathRewriting:
    """Test error list generation with path rewriting"""

    def test_generate_error_list_with_path_rewriting(self):
        """Test error list with path rewriting enabled"""
        mem_inst = memory_instance.MemoryInstance()
        mem_inst.generate_db_views()
        gen = report_generator.ReportGenerator(mem_inst)

        gen.replace_path_by_url = {
            'path_to_be_replaced': 'test',
            'replace_with_url': 'http://example.com'
        }

        # Add some links to the queue
        cursor = mem_inst.get_cursor()
        cursor.execute('''
            INSERT INTO queue VALUES (?, ?, ?, ?, ?, ?)
        ''', ['test.html', None, 'example.com', 'http://example.com/404', 'http://example.com/404', 'Link'])

        # Add an error
        cursor.execute('''
            INSERT INTO errors VALUES (?, ?)
        ''', ['http://example.com/404', 404])

        result = gen.generate_error_list()
        assert result is not None
        assert result[0]['path'] == 'http://example.com.html'
        mem_inst.tear_down_in_memory_db()
