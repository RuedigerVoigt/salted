#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Tests for report_generator module
~~~~~~~~~~~~~~~~~~~~~
Smart, Asynchronous Link Tester with Database backend (SALTED)
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2025: Released under the Apache License 2.0
"""

import contextlib
import io
import re
import sys
import pytest
import pathlib

from jinja2.exceptions import SecurityError

from salted import err, report_generator, memory_instance


class _FakeTTY(io.StringIO):
    """A stdout replacement that claims to be a terminal."""

    def isatty(self) -> bool:
        return True


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

    def test_rewrite_path_no_config_raises(self):
        """rewrite_path raises when replace_path_by_url is None."""
        mem_inst = memory_instance.MemoryInstance()
        gen = report_generator.ReportGenerator(mem_inst)
        # replace_path_by_url is None by default
        with pytest.raises(ValueError, match="No path replacement configured"):
            gen.rewrite_path('/local/path/file.html')
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


class TestDisplayPathRelativeMode:
    """Path display relative to the search root when no base_url is set."""

    def test_display_path_relative(self):
        """With path_to_be_replaced set but no URL, paths are made relative."""
        mem_inst = memory_instance.MemoryInstance()
        gen = report_generator.ReportGenerator(mem_inst)
        base = pathlib.Path('/local/site')
        gen.replace_path_by_url = {
            'path_to_be_replaced': str(base),
            'replace_with_url': None,
        }
        fp = base / 'blog' / 'page.html'
        assert gen._display_path(str(fp)) == str(pathlib.Path('blog/page.html'))
        mem_inst.tear_down_in_memory_db()

    def test_display_path_url_takes_precedence(self):
        """When a base_url is set, _display_path rewrites to the URL."""
        mem_inst = memory_instance.MemoryInstance()
        gen = report_generator.ReportGenerator(mem_inst)
        gen.replace_path_by_url = {
            'path_to_be_replaced': '/local',
            'replace_with_url': 'https://example.com',
        }
        assert gen._display_path('/local/page.html') == 'https://example.com/page.html'
        mem_inst.tear_down_in_memory_db()

    def test_display_path_no_mapping_unchanged(self):
        """No mapping configured → path returned unchanged."""
        mem_inst = memory_instance.MemoryInstance()
        gen = report_generator.ReportGenerator(mem_inst)
        assert gen._display_path('/local/page.html') == '/local/page.html'
        mem_inst.tear_down_in_memory_db()

    def test_display_path_outside_base_unchanged(self):
        """A path not under the base is left untouched (no crash)."""
        mem_inst = memory_instance.MemoryInstance()
        gen = report_generator.ReportGenerator(mem_inst)
        gen.replace_path_by_url = {
            'path_to_be_replaced': str(pathlib.Path('/local/site')),
            'replace_with_url': None,
        }
        outside = str(pathlib.Path('/other/place/file.html'))
        assert gen._display_path(outside) == outside
        mem_inst.tear_down_in_memory_db()

    def test_error_list_shows_relative_paths(self):
        """generate_error_list yields relative paths when no base_url is set."""
        mem_inst = memory_instance.MemoryInstance()
        mem_inst.generate_db_views()
        gen = report_generator.ReportGenerator(mem_inst)
        base = pathlib.Path('/local/site')
        gen.replace_path_by_url = {
            'path_to_be_replaced': str(base),
            'replace_with_url': None,
        }
        fp = str(base / 'blog' / 'page.html')
        cursor = mem_inst.get_cursor()
        cursor.execute(
            'INSERT INTO queue (filePath, hostname, url, normalizedUrl, linktext)'
            ' VALUES (?, ?, ?, ?, ?)',
            [fp, 'example.com', 'http://example.com/404',
             'http://example.com/404', 'Link'])
        cursor.execute(
            'INSERT INTO errors VALUES (?, ?)', ['http://example.com/404', 404])
        result = gen.generate_error_list()
        assert result is not None
        assert result[0]['path'] == str(pathlib.Path('blog/page.html'))
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
            INSERT INTO queue (filePath, hostname, url, normalizedUrl, linktext)
            VALUES (?, ?, ?, ?, ?)
        ''', ['test.html', 'example.com', 'http://example.com/404', 'http://example.com/404', 'Link'])

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
            INSERT INTO queue (filePath, hostname, url, normalizedUrl, linktext)
            VALUES (?, ?, ?, ?, ?)
        ''', ['test.html', 'example.com', 'http://example.com/old', 'http://example.com/old', 'Link'])

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
            INSERT INTO queue (filePath, hostname, url, normalizedUrl, linktext)
            VALUES (?, ?, ?, ?, ?)
        ''', ['test.html', 'example.com', 'http://example.com/old', 'http://example.com/old', 'Link'])

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
            INSERT INTO queue (filePath, hostname, url, normalizedUrl, linktext)
            VALUES (?, ?, ?, ?, ?)
        ''', ['test.html', 'example.com', 'http://example.com/timeout', 'http://example.com/timeout', 'Link'])

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
            INSERT INTO queue (filePath, hostname, url, normalizedUrl, linktext)
            VALUES (?, ?, ?, ?, ?)
        ''', ['test.html', 'example.com', 'http://example.com/timeout', 'http://example.com/timeout', 'Link'])

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
            INSERT INTO queue (filePath, hostname, url, normalizedUrl, linktext)
            VALUES (?, ?, ?, ?, ?)
        ''', ['test.html', 'example.com', 'http://example.com/404', 'http://example.com/404', 'Link'])

        # Add an error
        cursor.execute('''
            INSERT INTO errors VALUES (?, ?)
        ''', ['http://example.com/404', 404])

        result = gen.generate_error_list()
        assert result is not None
        assert result[0]['path'] == 'http://example.com.html'
        mem_inst.tear_down_in_memory_db()


class TestGenerateMailtoList:
    """Test generate_mailto_list with path rewriting."""

    def test_generate_mailto_list_with_path_rewriting(self):
        """generate_mailto_list rewrites file paths when replace_path_by_url is set."""
        mem_inst = memory_instance.MemoryInstance()
        gen = report_generator.ReportGenerator(mem_inst)
        gen.replace_path_by_url = {
            'path_to_be_replaced': '/local',
            'replace_with_url': 'https://example.com',
        }
        cursor = mem_inst.get_cursor()
        cursor.execute(
            'INSERT INTO mailtoLinks VALUES (?, ?, ?, ?)',
            ('/local/index.html', 'mailto:a@b.com', 'a@b.com', 1))
        result = gen.generate_mailto_list()
        assert result is not None
        assert result[0]['path'] == 'https://example.com/index.html'
        mem_inst.tear_down_in_memory_db()


class TestGenerateInvalidDoiList:
    """Test generate_invalid_doi_list."""

    def test_no_invalid_dois_returns_none(self):
        """Returns None when no invalid DOIs were recorded."""
        mem_inst = memory_instance.MemoryInstance()
        gen = report_generator.ReportGenerator(mem_inst)
        assert gen.generate_invalid_doi_list() is None
        mem_inst.tear_down_in_memory_db()

    def test_invalid_doi_joined_with_source_file(self):
        """Invalid DOI is joined with queue_doi to find its source file."""
        mem_inst = memory_instance.MemoryInstance()
        cursor = mem_inst.get_cursor()
        cursor.execute(
            'INSERT INTO queue_doi (filePath, doi, description) VALUES (?, ?, ?)',
            ('refs.bib', '10.1234/bad', 'Smith2020'))
        cursor.execute(
            'INSERT INTO invalidDois (doi) VALUES (?)',
            ('10.1234/bad',))
        gen = report_generator.ReportGenerator(mem_inst)
        result = gen.generate_invalid_doi_list()
        assert result is not None
        assert len(result) == 1
        assert result[0]['doi'] == '10.1234/bad'
        assert result[0]['path'] == 'refs.bib'
        assert result[0]['description'] == 'Smith2020'
        mem_inst.tear_down_in_memory_db()

    def test_invalid_doi_appears_in_multiple_files(self):
        """Same invalid DOI in two files produces one entry per file."""
        mem_inst = memory_instance.MemoryInstance()
        cursor = mem_inst.get_cursor()
        cursor.execute(
            'INSERT INTO queue_doi VALUES (?, ?, ?)', ('file1.bib', '10.1234/bad', 'A'))
        cursor.execute(
            'INSERT INTO queue_doi VALUES (?, ?, ?)', ('file2.bib', '10.1234/bad', 'B'))
        cursor.execute('INSERT INTO invalidDois (doi) VALUES (?)', ('10.1234/bad',))
        gen = report_generator.ReportGenerator(mem_inst)
        result = gen.generate_invalid_doi_list()
        assert result is not None
        assert len(result) == 2
        paths = {r['path'] for r in result}
        assert paths == {'file1.bib', 'file2.bib'}
        mem_inst.tear_down_in_memory_db()

    def test_path_rewriting_applied(self):
        """File paths are rewritten when replace_path_by_url is set."""
        mem_inst = memory_instance.MemoryInstance()
        cursor = mem_inst.get_cursor()
        cursor.execute(
            'INSERT INTO queue_doi VALUES (?, ?, ?)',
            ('/local/refs.bib', '10.1234/bad', 'X'))
        cursor.execute('INSERT INTO invalidDois (doi) VALUES (?)', ('10.1234/bad',))
        gen = report_generator.ReportGenerator(mem_inst)
        gen.replace_path_by_url = {
            'path_to_be_replaced': '/local',
            'replace_with_url': 'https://example.com',
        }
        result = gen.generate_invalid_doi_list()
        assert result[0]['path'] == 'https://example.com/refs.bib'
        mem_inst.tear_down_in_memory_db()


class TestGenerateInternalLinkList:
    """Test generate_internal_link_list."""

    @staticmethod
    def _log(cursor, file_path, url, linktext, reason, is_error):
        cursor.execute('''
            INSERT INTO internalLinkFindings
            (filePath, url, linktext, reason, isError)
            VALUES (?, ?, ?, ?, ?);''',
            (file_path, url, linktext, reason, is_error))

    def test_no_findings_returns_none(self):
        """Returns None when no internal link findings were recorded."""
        mem_inst = memory_instance.MemoryInstance()
        gen = report_generator.ReportGenerator(mem_inst)
        assert gen.generate_internal_link_list() is None
        mem_inst.tear_down_in_memory_db()

    def test_findings_grouped_by_file(self):
        """Findings are grouped per file with a count and detail rows."""
        mem_inst = memory_instance.MemoryInstance()
        cursor = mem_inst.get_cursor()
        self._log(cursor, 'index.html', 'gone.html', 'broken',
                  'target file does not exist', 1)
        self._log(cursor, 'index.html', '#nope', 'frag',
                  "fragment '#nope' not found in target", 1)
        gen = report_generator.ReportGenerator(mem_inst)
        result = gen.generate_internal_link_list()
        assert result is not None
        assert len(result) == 1
        assert result[0]['path'] == 'index.html'
        assert result[0]['num_findings'] == 2
        assert len(result[0]['findings']) == 2
        mem_inst.tear_down_in_memory_db()

    def test_errors_sorted_before_unverifiable(self):
        """Within a file, broken links (isError=1) come before notes (0)."""
        mem_inst = memory_instance.MemoryInstance()
        cursor = mem_inst.get_cursor()
        self._log(cursor, 'p.html', '../out.txt', 'escape',
                  'not checked: resolves outside the checked folder', 0)
        self._log(cursor, 'p.html', 'gone.html', 'broken',
                  'target file does not exist', 1)
        gen = report_generator.ReportGenerator(mem_inst)
        result = gen.generate_internal_link_list()
        # findings row layout: (url, linktext, reason, isError)
        assert result[0]['findings'][0][3] == 1
        assert result[0]['findings'][1][3] == 0
        mem_inst.tear_down_in_memory_db()

    def test_path_rewriting_applied(self):
        """File paths are rewritten when replace_path_by_url is set."""
        mem_inst = memory_instance.MemoryInstance()
        cursor = mem_inst.get_cursor()
        self._log(cursor, '/local/index.html', 'gone.html', 'x',
                  'target file does not exist', 1)
        gen = report_generator.ReportGenerator(mem_inst)
        gen.replace_path_by_url = {
            'path_to_be_replaced': '/local',
            'replace_with_url': 'https://example.com',
        }
        result = gen.generate_internal_link_list()
        assert result[0]['path'] == 'https://example.com/index.html'
        mem_inst.tear_down_in_memory_db()


class TestReportSanitizing:
    """Values from checked documents must not control the report."""

    ESC = '\x1b'

    @staticmethod
    def _report(template_name, rows, findings=()):
        """Render a report over seeded error rows and return the output."""
        mem = memory_instance.MemoryInstance()
        cur = mem.get_cursor()
        if rows:
            cur.executemany(
                'INSERT INTO queue (filePath, hostname, url, normalizedUrl, '
                'linktext) VALUES (?,?,?,?,?);', rows)
            cur.executemany('INSERT INTO errors VALUES (?, ?);',
                            [(r[3], 404) for r in rows])
        for finding in findings:
            cur.execute(
                'INSERT INTO internalLinkFindings (filePath, url, linktext, '
                'reason, isError) VALUES (?,?,?,?,?);', finding)
        mem.generate_db_views()
        gen = report_generator.ReportGenerator(mem)
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                gen.generate_report(
                    statistics={'num_links': len(rows), 'num_checked': len(rows),
                                'timestamp': 'now', 'time_to_check': 1,
                                'checks_per_second': 1, 'num_fine': 0,
                                'needed_full_request': 0,
                                'percentage_full_request': 0,
                                'check_dois': False, 'num_valid_dois': 0,
                                'num_invalid_dois': 0,
                                'check_internal_links': True,
                                'num_internal_checked': len(findings),
                                'num_internal_fine': 0},
                    template={'searchpath': None, 'name': template_name},
                    write_to='cli', replace_path_by_url=None)
        finally:
            mem.tear_down_in_memory_db()
        return buf.getvalue()

    # ---- control characters (all templates) ----

    def test_strip_control_characters_keeps_tab_only(self):
        """Only the control characters go; tab is normal text and stays.

        Note what remains: removing the ESC byte leaves the rest of the
        sequence ('[32m') as ordinary text. That is deliberate - the
        sequence is inert once ESC is gone, and the leftover is a visible
        hint that the document contained something odd. Stripping whole
        sequences would risk eating text that merely looks like one.
        """
        cleaned = report_generator.strip_control_characters(
            'a\x1b[32mb\rc\nd\te\x00f\x7fg')
        assert cleaned == 'a[32mbcd\tefg'

    @pytest.mark.parametrize('template_name',
                             ['default.cli.jinja', 'default.md.jinja'])
    def test_escape_sequences_never_reach_the_report(self, template_name):
        """A document must not be able to write terminal escapes.

        Unfiltered, '\\x1b[2K\\x1b[32m...' erases the report line and prints
        a green success message inside the list of broken links.
        """
        payload = f'{self.ESC}[2K{self.ESC}[32mAll links OK{self.ESC}[0m'
        out = self._report(
            template_name,
            [('doc.html', 'e.example', f'https://e.example/{self.ESC}[31mx',
              f'https://e.example/{self.ESC}[31mx', payload)])

        assert '\x1b' not in out
        assert '\r' not in out
        # The text itself is still reported, only the escapes are gone.
        assert 'All links OK' in out

    def test_carriage_return_cannot_split_a_report_line(self):
        out = self._report(
            'default.cli.jinja',
            [('doc.html', 'e.example', 'https://e.example/1',
              'https://e.example/1', 'harmless\rOVERWRITTEN')])

        assert 'harmlessOVERWRITTEN' in out

    def test_control_characters_in_a_file_path_are_stripped(self):
        """File names may contain control characters on most filesystems."""
        out = self._report(
            'default.cli.jinja',
            [(f'do{self.ESC}[31mc.html', 'e.example', 'https://e.example/1',
              'https://e.example/1', 'text')])

        assert '\x1b' not in out

    # ---- markdown escaping ----

    def test_markdown_cell_escapes_structural_characters(self):
        assert report_generator.markdown_cell('a|b') == r'a\|b'
        assert report_generator.markdown_cell('[x](y)') == r'\[x\](y)'
        assert report_generator.markdown_cell('<img>') == r'\<img\>'
        assert report_generator.markdown_cell('a`b') == 'a\\`b'
        # The backslash is escaped first, not twice.
        assert report_generator.markdown_cell('a\\b') == r'a\\b'

    def test_markdown_url_encodes_link_breaking_characters(self):
        assert report_generator.markdown_url(
            'https://e.example/Python_(programming_language)'
        ) == 'https://e.example/Python_%28programming_language%29'

    def test_pipe_in_link_text_cannot_forge_table_cells(self):
        """An unescaped pipe would end the cell and inject further columns."""
        out = self._report(
            'default.md.jinja',
            [('doc.html', 'e.example', 'https://e.example/1',
              'https://e.example/1', 'x|**0 errors**|all fine|')])

        assert r'x\|\*\*0 errors\*\*\|all fine\|' in out

    def test_parenthesis_in_url_does_not_break_the_markdown_link(self):
        """Wikipedia-style URLs are legitimate and must render as links."""
        url = 'https://e.example/Python_(programming_language)'
        out = self._report(
            'default.md.jinja',
            [('doc.html', 'e.example', url, url, 'Python')])

        # The link target carries encoded parentheses, so it cannot end early.
        assert '(https://e.example/Python_%28programming_language%29)' in out

    def test_raw_html_from_a_markdown_source_is_neutralised(self):
        """Markdown and TeX link text is not tag-stripped by a parser."""
        out = self._report(
            'default.md.jinja',
            [('doc.md', 'e.example', 'https://e.example/1',
              'https://e.example/1', '<img src=x onerror=alert(1)>')])

        assert r'\<img src=x onerror=alert(1)\>' in out
        # No angle bracket survives unescaped, which is what a renderer
        # would otherwise turn back into a live tag.
        assert not re.search(r'(?<!\\)<img', out)

    def test_internal_link_findings_are_escaped_too(self):
        out = self._report(
            'default.md.jinja', [],
            findings=[('doc.html', 'a|b.html', 'text|more',
                       'target file does not exist', 1)])

        assert r'a\|b.html' in out
        assert r'text\|more' in out


class TestTemplateSecurity:
    """External templates are untrusted input: sandboxed and name-checked."""

    @staticmethod
    def _render(tmp_path, template_body, name='evil.jinja'):
        """Render a template from disk and return its output."""
        mem_inst = memory_instance.MemoryInstance()
        mem_inst.generate_db_views()
        gen = report_generator.ReportGenerator(mem_inst)
        template_dir = tmp_path / "templates"
        template_dir.mkdir(exist_ok=True)
        (template_dir / name).write_text(template_body, encoding='utf-8')
        try:
            gen.generate_report(
                statistics={'num_links': 1},
                template={'searchpath': str(template_dir), 'name': name},
                write_to='cli',
                replace_path_by_url={'replace_with_url': None})
        finally:
            mem_inst.tear_down_in_memory_db()

    def test_template_cannot_reach_the_object_graph(self, tmp_path):
        """The classic SSTI first step must be blocked by the sandbox.

        A plain jinja2.Environment lets a template walk from any passed
        variable to every loaded class and from there to code execution.
        """
        with pytest.raises(SecurityError):
            self._render(
                tmp_path,
                "{{ statistics.__class__.__mro__[1].__subclasses__() | length }}")

    @pytest.mark.parametrize('payload', [
        "{{ statistics.__class__.__mro__[1].__subclasses__() }}",
        "{{ statistics.__init__.__globals__ }}",
        "{{ ''.__class__.__mro__[1].__subclasses__() }}",
        "{{ self.__init__.__globals__ }}",
        "{{ cycler.__init__.__globals__ }}",
        "{{ namespace.__init__.__globals__ }}",
    ])
    def test_known_sandbox_escape_routes_are_blocked(self, tmp_path, payload):
        """Common SSTI entry points must all raise rather than evaluate."""
        with pytest.raises(SecurityError):
            self._render(tmp_path, payload)

    def test_ordinary_template_expressions_still_work(self, tmp_path):
        """The sandbox must not break legitimate report templates."""
        self._render(
            tmp_path,
            "{{ statistics.num_links }} links "
            "{% for k, v in statistics.items() %}{{ k }}={{ v }}{% endfor %}",
            name='fine.jinja')

    @pytest.mark.parametrize('name', [
        'id_rsa', '.env', 'credentials', 'secrets.ini',
        'passwd', 'config.yml', 'evil.jinja.txt'])
    def test_non_template_file_names_are_refused(self, tmp_path, name):
        """template_name must not be able to point at an arbitrary file.

        Jinja renders a file without template syntax as its own content,
        so accepting any name turns template_name into a file-read
        primitive that copies the file into the report.
        """
        with pytest.raises(err.UnsafeTemplateError):
            self._render(tmp_path, "SUPERSECRET", name=name)

    def test_template_extension_is_case_insensitive(self, tmp_path):
        """A legitimate template is accepted regardless of suffix case."""
        self._render(tmp_path, "ok", name='Report.JINJA')

    def test_builtin_template_names_still_load(self):
        """The packaged templates must keep working under the sandbox."""
        mem_inst = memory_instance.MemoryInstance()
        mem_inst.generate_db_views()
        gen = report_generator.ReportGenerator(mem_inst)
        for builtin in report_generator.BUILTIN_TEMPLATES:
            gen.generate_report(
                statistics={'num_links': 0, 'num_checked': 0, 'timestamp': 'now',
                            'time_to_check': 0, 'checks_per_second': 0,
                            'num_fine': 0, 'needed_full_request': 0,
                            'percentage_full_request': 0, 'check_dois': False,
                            'num_valid_dois': 0, 'num_invalid_dois': 0,
                            'check_internal_links': False,
                            'num_internal_checked': 0, 'num_internal_fine': 0},
                template={'searchpath': None, 'name': builtin},
                write_to='cli',
                replace_path_by_url={'replace_with_url': None})
        mem_inst.tear_down_in_memory_db()


class TestGenerateReport:
    """Test report generation with different templates and outputs"""

    def test_generate_report_with_custom_template(self, tmp_path):
        """Test generating report with custom template from file system"""
        mem_inst = memory_instance.MemoryInstance()
        mem_inst.generate_db_views()
        gen = report_generator.ReportGenerator(mem_inst)

        # Create a custom template
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        template_file = template_dir / "custom.jinja"
        template_file.write_text("Statistics: {{ statistics.num_links }}")

        gen.generate_report(
            statistics={'num_links': 10},
            template={
                'searchpath': str(template_dir),
                'name': 'custom.jinja'
            },
            write_to='cli',
            replace_path_by_url={'replace_with_url': None}
        )
        mem_inst.tear_down_in_memory_db()

    def test_generate_report_write_to_file(self, tmp_path):
        """Test writing report to file"""
        mem_inst = memory_instance.MemoryInstance()
        mem_inst.generate_db_views()
        gen = report_generator.ReportGenerator(mem_inst)

        output_file = tmp_path / "report.txt"

        gen.generate_report(
            statistics={
                'timestamp': '2025-01-01 12:00h',
                'num_links': 10,
                'num_checked': 5,
                'time_to_check': 1,
                'checks_per_second': 5.0,
                'num_fine': 5,
                'needed_full_request': 0,
                'percentage_full_request': 0,
                'check_dois': True,
                'num_valid_dois': 0,
                'num_invalid_dois': 0,
            },
            template={'name': 'default.cli.jinja'},
            write_to=str(output_file),
            replace_path_by_url={'replace_with_url': None}
        )

        # Verify file was created
        assert output_file.exists()
        mem_inst.tear_down_in_memory_db()

    def test_generate_report_write_to_file_exception(self, tmp_path):
        """Test exception handling when writing to file fails (covers lines 286-289)."""
        from unittest.mock import patch, mock_open
        mem_inst = memory_instance.MemoryInstance()
        mem_inst.generate_db_views()
        gen = report_generator.ReportGenerator(mem_inst)

        full_stats = {
            'timestamp': '2026-01-01 12:00h',
            'num_links': 0, 'num_checked': 0,
            'time_to_check': 1, 'checks_per_second': 0.0,
            'num_fine': 0, 'needed_full_request': 0,
            'percentage_full_request': 0,
            'check_dois': True,
            'num_valid_dois': 0,
            'num_invalid_dois': 0,
        }

        with patch('builtins.open', mock_open()) as mocked_open:
            mocked_open.side_effect = OSError("disk full")
            with pytest.raises(OSError):
                gen.generate_report(
                    statistics=full_stats,
                    template={'name': 'default.cli.jinja'},
                    write_to='/some/report.txt',
                    replace_path_by_url={'replace_with_url': None}
                )
        mem_inst.tear_down_in_memory_db()


class TestOsc8Link:
    """Test the OSC 8 terminal hyperlink filter"""

    def test_wraps_http_url(self):
        """A http URL is wrapped as target and as visible text"""
        url = 'http://example.com/page'
        assert report_generator.osc8_link(url) == (
            f'\x1b]8;;{url}\x1b\\{url}\x1b]8;;\x1b\\')

    def test_wraps_https_url(self):
        """https is linkified as well"""
        assert report_generator.osc8_link('https://example.com').startswith(
            '\x1b]8;;https://example.com\x1b\\')

    def test_url_with_parentheses_kept_intact(self):
        """The case this feature exists for: parens must survive"""
        url = 'https://de.wikipedia.org/wiki/Normalisierung_(Datenbank)'
        result = report_generator.osc8_link(url)
        # The URL appears twice unaltered: once as target, once as text.
        assert result.count(url) == 2

    def test_visible_text_is_the_url(self):
        """Stripping the escapes must leave exactly the URL behind"""
        url = 'https://example.com/a(b)c'
        result = report_generator.osc8_link(url)
        visible = re.sub('\x1b]8;;[^\x1b]*\x1b\\\\', '', result)
        assert visible == url

    @pytest.mark.parametrize('url', [
        'ftp://example.com/file',
        'javascript:alert(1)',
        'file:///etc/passwd',
        'mailto:someone@example.com',
        'not a url at all',
        '',
    ])
    def test_other_schemes_are_not_linkified(self, url):
        """Only http(s) becomes a clickable link"""
        assert report_generator.osc8_link(url) == url

    def test_control_characters_are_stripped(self):
        """A URL must not be able to close the sequence and escape it"""
        hostile = ('https://example.com/\x1b\\'
                   '\x1b]8;;http://evil.example\x1b\\')
        result = report_generator.osc8_link(hostile)
        assert '\x1b]8;;http://evil.example' not in result
        # Exactly one opening and one closing sequence remain.
        assert result.count('\x1b]8;;') == 2

    def test_non_string_input(self):
        """Anything not a string is coerced, not linkified"""
        assert report_generator.osc8_link(42) == '42'
        assert report_generator.osc8_link(None) == 'None'

    def test_uppercase_scheme_is_linkified(self):
        """Scheme comparison is case insensitive"""
        assert report_generator.osc8_link('HTTPS://example.com').startswith(
            '\x1b]8;;')


class TestTerminalSupportsHyperlinks:
    """Test the gate deciding whether escape sequences may be written"""

    def test_not_a_tty(self, monkeypatch):
        """Redirected output must stay free of escape sequences"""
        monkeypatch.setattr(sys, 'stdout', io.StringIO())
        assert report_generator.terminal_supports_hyperlinks() is False

    def test_tty_without_term(self, monkeypatch):
        """An unset TERM is normal on Windows and must not disable links"""
        monkeypatch.setattr(sys, 'stdout', _FakeTTY())
        monkeypatch.delenv('TERM', raising=False)
        monkeypatch.delenv('NO_COLOR', raising=False)
        assert report_generator.terminal_supports_hyperlinks() is True

    def test_term_dumb(self, monkeypatch):
        """TERM=dumb explicitly means no escape sequences"""
        monkeypatch.setattr(sys, 'stdout', _FakeTTY())
        monkeypatch.setenv('TERM', 'dumb')
        monkeypatch.delenv('NO_COLOR', raising=False)
        assert report_generator.terminal_supports_hyperlinks() is False

    def test_no_color_env(self, monkeypatch):
        """NO_COLOR is honoured"""
        monkeypatch.setattr(sys, 'stdout', _FakeTTY())
        monkeypatch.delenv('TERM', raising=False)
        monkeypatch.setenv('NO_COLOR', '1')
        assert report_generator.terminal_supports_hyperlinks() is False

    def test_stdout_without_isatty(self, monkeypatch):
        """A replaced stdout lacking isatty must not raise"""
        monkeypatch.setattr(sys, 'stdout', object())
        assert report_generator.terminal_supports_hyperlinks() is False


class TestOsc8InGeneratedReport:
    """Test hyperlink emission end to end through generate_report"""

    STATS = {
        'timestamp': '2026-01-01 12:00h',
        'num_links': 1, 'num_checked': 1,
        'time_to_check': 1, 'checks_per_second': 1.0,
        'num_fine': 0, 'needed_full_request': 0,
        'percentage_full_request': 0,
        'check_dois': True,
        'num_valid_dois': 0,
        'num_invalid_dois': 0,
    }
    URL = 'https://example.com/wiki/Normalisierung_(Datenbank)'

    def _db_with_one_error(self):
        mem_inst = memory_instance.MemoryInstance()
        mem_inst.generate_db_views()
        cursor = mem_inst.get_cursor()
        cursor.execute(
            'INSERT INTO queue (filePath, hostname, url, normalizedUrl, '
            'linktext) VALUES (?, ?, ?, ?, ?)',
            ['test.html', 'example.com', self.URL, self.URL, 'Link'])
        cursor.execute(
            'INSERT INTO errors VALUES (?, ?)', [self.URL, 404])
        return mem_inst

    def test_cli_output_has_hyperlink_when_tty(self, monkeypatch, capsys):
        """On a terminal the URL is wrapped in an OSC 8 sequence"""
        monkeypatch.setattr(
            report_generator, 'terminal_supports_hyperlinks', lambda: True)
        mem_inst = self._db_with_one_error()
        gen = report_generator.ReportGenerator(mem_inst)
        gen.generate_report(
            statistics=self.STATS,
            template={'name': 'default.cli.jinja'},
            write_to='cli',
            replace_path_by_url={'replace_with_url': None})
        out = capsys.readouterr().out
        assert f'\x1b]8;;{self.URL}\x1b\\' in out
        mem_inst.tear_down_in_memory_db()

    def test_cli_output_plain_when_not_a_tty(self, capsys):
        """Piped output keeps the previous plain-text form"""
        mem_inst = self._db_with_one_error()
        gen = report_generator.ReportGenerator(mem_inst)
        gen.generate_report(
            statistics=self.STATS,
            template={'name': 'default.cli.jinja'},
            write_to='cli',
            replace_path_by_url={'replace_with_url': None})
        out = capsys.readouterr().out
        assert '\x1b' not in out
        assert self.URL in out
        mem_inst.tear_down_in_memory_db()

    def test_file_output_never_has_escapes(self, monkeypatch, tmp_path):
        """Even on a terminal, a report written to a file stays plain"""
        monkeypatch.setattr(
            report_generator, 'terminal_supports_hyperlinks', lambda: True)
        output_file = tmp_path / 'report.txt'
        mem_inst = self._db_with_one_error()
        gen = report_generator.ReportGenerator(mem_inst)
        gen.generate_report(
            statistics=self.STATS,
            template={'name': 'default.cli.jinja'},
            write_to=str(output_file),
            replace_path_by_url={'replace_with_url': None})
        content = output_file.read_text(encoding='utf-8')
        assert '\x1b' not in content
        assert self.URL in content
        mem_inst.tear_down_in_memory_db()

    def test_markdown_template_never_has_escapes(self, monkeypatch, capsys):
        """The markdown template does not use the filter"""
        monkeypatch.setattr(
            report_generator, 'terminal_supports_hyperlinks', lambda: True)
        mem_inst = self._db_with_one_error()
        gen = report_generator.ReportGenerator(mem_inst)
        gen.generate_report(
            statistics=self.STATS,
            template={'name': 'default.md.jinja'},
            write_to='cli',
            replace_path_by_url={'replace_with_url': None})
        assert '\x1b' not in capsys.readouterr().out
        mem_inst.tear_down_in_memory_db()


class _NarrowStdout(io.StringIO):
    """A stdout that only encodes a limited code page, as Windows does.

    Redirected output on Windows uses the ANSI code page rather than UTF-8,
    and io.StringIO has no encoding at all, so the real condition has to be
    modelled: writes reject what the code page cannot represent.
    """

    encoding = 'cp1252'

    def write(self, text: str) -> int:
        text.encode(self.encoding)
        return super().write(text)


# A statistics dict complete enough for the packaged templates to render.
_FULL_STATISTICS = {
    'num_links': 1, 'num_checked': 1, 'timestamp': 'now', 'time_to_check': 1,
    'checks_per_second': 1, 'num_fine': 0, 'needed_full_request': 0,
    'percentage_full_request': 0, 'check_dois': False, 'num_valid_dois': 0,
    'num_invalid_dois': 0, 'check_internal_links': False,
    'num_internal_checked': 0, 'num_internal_fine': 0,
}


class _Utf8Stdout(io.StringIO):
    """A stdout that reports UTF-8, as a real console does (PEP 528)."""

    encoding = 'utf-8'


class TestEncodableForStdout:
    """The report must survive a console that is not UTF-8."""

    def test_utf8_stdout_leaves_the_report_untouched(self, monkeypatch):
        monkeypatch.setattr(sys, 'stdout', _Utf8Stdout())
        report = 'Ünicode: 中文 Документ \U0001F600'
        assert report_generator.encodable_for_stdout(report) == report

    def test_unrepresentable_characters_become_question_marks(self,
                                                              monkeypatch):
        monkeypatch.setattr(sys, 'stdout', _NarrowStdout())
        cleaned = report_generator.encodable_for_stdout('a 中文 b')
        assert '中' not in cleaned
        assert cleaned.startswith('a ') and cleaned.endswith(' b')

    def test_characters_the_codepage_has_are_kept(self, monkeypatch):
        """cp1252 covers latin-1 text, which must not be mangled."""
        monkeypatch.setattr(sys, 'stdout', _NarrowStdout())
        assert report_generator.encodable_for_stdout('Fußnote') == 'Fußnote'

    def test_unknown_codec_does_not_raise(self, monkeypatch):
        """A mistyped PYTHONIOENCODING must not defeat the guard itself.

        The replacement pass would fail on the very same codec lookup, so
        it must not be attempted.
        """
        class _UnknownCodecStdout(io.StringIO):
            encoding = 'not-a-real-codec'

        monkeypatch.setattr(sys, 'stdout', _UnknownCodecStdout())
        report = 'Ünicode: 中文'
        assert report_generator.encodable_for_stdout(report) == report

    def test_missing_encoding_attribute_is_survivable(self, monkeypatch):
        """io.StringIO and friends have no .encoding; assume UTF-8."""
        monkeypatch.setattr(sys, 'stdout', io.StringIO())
        report = 'Ünicode: 中文'
        assert report_generator.encodable_for_stdout(report) == report

    @pytest.mark.parametrize('text', ['中文', '\U0001F600', 'Документ'])
    def test_report_prints_instead_of_raising(self, monkeypatch, text):
        """The whole point: a run must not die on a traceback.

        Link text comes out of the checked document, so any site with CJK,
        Cyrillic or emoji anchors used to end the run with
        UnicodeEncodeError as soon as stdout was redirected.
        """
        mem_inst = memory_instance.MemoryInstance()
        mem_inst.generate_db_views()
        gen = report_generator.ReportGenerator(mem_inst)
        narrow = _NarrowStdout()
        monkeypatch.setattr(sys, 'stdout', narrow)
        try:
            gen.generate_report(
                statistics=dict(_FULL_STATISTICS),
                template={'name': 'default.cli.jinja'},
                write_to='cli',
                replace_path_by_url={'replace_with_url': None})
        finally:
            mem_inst.tear_down_in_memory_db()
        assert 'RESULTS' in narrow.getvalue()


class TestC1ControlCharacters:
    """C1 holds single-character forms of the C0 escape introducers."""

    @pytest.mark.parametrize('codepoint,name', [
        (0x9b, 'CSI'), (0x9d, 'OSC'), (0x9c, 'string terminator'),
        (0x80, 'first of the range'), (0x9f, 'last of the range'),
    ])
    def test_c1_is_stripped(self, codepoint, name):
        cleaned = report_generator.strip_control_characters(
            f'a{chr(codepoint)}b')
        assert cleaned == 'ab', f'{name} (U+{codepoint:04X}) survived'

    def test_non_breaking_space_is_kept(self):
        """U+00A0 sits just past C1 and is text, not a control character."""
        assert report_generator.strip_control_characters(
            'a\u00a0b') == 'a\u00a0b'

    def test_c1_cannot_terminate_an_osc8_hyperlink(self):
        """U+009C would close the sequence and free the rest to be markup."""
        linked = report_generator.osc8_link(
            'https://example.com/\u009c\u009d8;;boom')
        assert '\u009c' not in linked
        assert '\u009d' not in linked


class TestBuiltinTemplateNameIsNotReserved:
    """A custom template named like a built-in must not be ignored."""

    @staticmethod
    def _render(tmp_path, name, body):
        mem_inst = memory_instance.MemoryInstance()
        mem_inst.generate_db_views()
        gen = report_generator.ReportGenerator(mem_inst)
        template_dir = tmp_path / 'templates'
        template_dir.mkdir(exist_ok=True)
        (template_dir / name).write_text(body, encoding='utf-8')
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                gen.generate_report(
                    statistics=dict(_FULL_STATISTICS, num_links=7),
                    template={'searchpath': str(template_dir), 'name': name},
                    write_to='cli',
                    replace_path_by_url={'replace_with_url': None})
        finally:
            mem_inst.tear_down_in_memory_db()
        return buf.getvalue()

    @pytest.mark.parametrize('name', ['default.cli.jinja', 'default.md.jinja'])
    def test_custom_file_wins_over_the_packaged_one(self, tmp_path, name):
        """Previously the packaged template was rendered without a word."""
        out = self._render(tmp_path, name, 'MARKER {{ statistics.num_links }}')
        assert 'MARKER 7' in out

    def test_builtin_still_used_when_the_folder_lacks_that_name(self,
                                                                tmp_path):
        """Setting a searchpath alone must not break the default report."""
        mem_inst = memory_instance.MemoryInstance()
        mem_inst.generate_db_views()
        gen = report_generator.ReportGenerator(mem_inst)
        empty = tmp_path / 'empty'
        empty.mkdir()
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                gen.generate_report(
                    statistics=dict(_FULL_STATISTICS),
                    template={'searchpath': str(empty),
                              'name': 'default.cli.jinja'},
                    write_to='cli',
                    replace_path_by_url={'replace_with_url': None})
        finally:
            mem_inst.tear_down_in_memory_db()
        assert 'RESULTS' in buf.getvalue()

    def test_default_searchpath_uses_the_package_loader(self):
        """The default sentinel is not read off the filesystem."""
        assert report_generator.ReportGenerator._use_builtin_template(
            {'name': 'default.cli.jinja',
             'searchpath': report_generator.DEFAULT_TEMPLATE_SEARCHPATH})

    def test_a_custom_name_is_never_treated_as_builtin(self, tmp_path):
        assert not report_generator.ReportGenerator._use_builtin_template(
            {'name': 'custom.jinja', 'searchpath': str(tmp_path)})
