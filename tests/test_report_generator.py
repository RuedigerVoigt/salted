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
import pathlib

from jinja2.exceptions import SecurityError

from salted import err, report_generator, memory_instance


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
