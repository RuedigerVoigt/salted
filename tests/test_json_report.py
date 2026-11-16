#!/usr/bin/python3

"""
Tests for the JSON report (salted/json_report.py, --report_format json)
~~~~~~~~~~~~~~~~~~~~~
Smart, Asynchronous Link Tester with Database backend (SALTED)
Source: https://github.com/RuedigerVoigt/salted
(c) 2026: Released under the Apache License 2.0

Every report is checked against the published schema,
documentation/report-schema-1.json. The check is hand-written (no jsonschema
dependency) but reads that file, so the schema and the tests cannot drift
apart.
"""

import json
import os
import pathlib
import re
import sys
from unittest.mock import AsyncMock, patch

import pytest

import salted
from salted import command_line, err, json_report

SCHEMA_FILE = (pathlib.Path(__file__).parent.parent
               / 'documentation' / 'report-schema-1.json')
SCHEMA = json.loads(SCHEMA_FILE.read_text(encoding='utf-8'))

_TYPES = {'object': dict, 'array': list, 'string': str, 'boolean': bool,
          'integer': int}


def schema_errors(instance, schema=SCHEMA, path='$') -> list:
    """Validate instance against the subset of JSON Schema the file uses.

    Supported: $ref (to $defs), type, const, enum, pattern, minimum,
    required, properties, items, allOf with if/then. A keyword the schema
    uses but this function does not know fails the test, so the check can
    never silently skip part of the schema.
    """
    known = {'$schema', '$id', 'title', 'description', '$defs', '$ref',
             'type', 'const', 'enum', 'pattern', 'minimum', 'required',
             'properties', 'items', 'allOf', 'if', 'then'}
    unknown = set(schema) - known
    assert not unknown, f'schema keyword(s) not supported by the test: {unknown}'

    if '$ref' in schema:
        return schema_errors(
            instance, SCHEMA['$defs'][schema['$ref'].split('/')[-1]], path)
    problems = []
    expected = _TYPES.get(schema.get('type'))
    if expected is not None:
        # bool is a subclass of int in Python, not in JSON.
        if not isinstance(instance, expected) or (
                expected is int and isinstance(instance, bool)):
            return [f'{path}: expected {schema["type"]}, got {instance!r}']
    if 'const' in schema and instance != schema['const']:
        problems.append(f'{path}: expected {schema["const"]!r}')
    if 'enum' in schema and instance not in schema['enum']:
        problems.append(f'{path}: {instance!r} not in {schema["enum"]}')
    if 'pattern' in schema and not re.search(schema['pattern'], instance):
        problems.append(f'{path}: {instance!r} does not match the pattern')
    if 'minimum' in schema and instance < schema['minimum']:
        problems.append(f'{path}: {instance!r} < {schema["minimum"]}')
    if isinstance(instance, dict):
        problems += [f'{path}: missing {key!r}'
                     for key in schema.get('required', ())
                     if key not in instance]
        for key, sub in schema.get('properties', {}).items():
            if key in instance:
                problems += schema_errors(instance[key], sub, f'{path}.{key}')
    if isinstance(instance, list) and 'items' in schema:
        for index, item in enumerate(instance):
            problems += schema_errors(item, schema['items'], f'{path}[{index}]')
    for rule in schema.get('allOf', ()):
        if not schema_errors(instance, rule['if'], path):
            problems += schema_errors(instance, rule['then'], path)
    return problems


def assert_valid(report: dict) -> None:
    problems = schema_errors(report)
    assert not problems, '\n'.join(problems)


class TestSchemaFile:
    """The published schema and the code describe the same report."""

    def test_kinds_match(self):
        kinds = SCHEMA['$defs']['finding']['properties']['kind']['enum']
        assert kinds == list(json_report.KINDS)

    def test_every_kind_has_its_required_fields(self):
        rules = SCHEMA['$defs']['finding']['allOf']
        assert [rule['if']['properties']['kind']['const']
                for rule in rules] == list(json_report.KINDS)

    def test_reason_codes_match(self):
        codes = (SCHEMA['properties']['result']['properties']['reasons']
                 ['items']['properties']['code']['enum'])
        assert codes == list(json_report.REASON_CODES)

    def test_statistics_keys_match(self):
        required = SCHEMA['properties']['statistics']['required']
        assert required == list(json_report.statistics_from({}))

    def test_schema_version_matches_the_file(self):
        assert re.search(SCHEMA['properties']['schema_version']['pattern'],
                         json_report.SCHEMA_VERSION)
        major = json_report.SCHEMA_VERSION.split('.')[0]
        assert SCHEMA_FILE.name == f'report-schema-{major}.json'


class TestSchemaCheck:
    """The hand-written check rejects what the schema rejects."""

    def _minimal(self) -> dict:
        return {
            'schema_version': '1.0',
            'tool': {'name': 'salted', 'version': '2.0.0'},
            'generated_at': '2026-11-16T12:00:00Z',
            'searchpath': 'docs',
            'result': {'fails_run': False, 'raise_for_dead_links': False,
                       'reasons': []},
            'statistics': json_report.statistics_from({}),
            'findings': [],
        }

    def test_minimal_report_is_valid(self):
        assert_valid(self._minimal())

    @pytest.mark.parametrize('change', [
        lambda r: r.pop('findings'),
        lambda r: r.update(schema_version='2.0'),
        lambda r: r['statistics'].update(links_found=True),
        lambda r: r['statistics'].update(links_found=-1),
        lambda r: r['result']['reasons'].append({'code': 'x', 'count': 1}),
        lambda r: r['findings'].append({'kind': 'nope', 'fails_run': True,
                                        'file': 'a'}),
        lambda r: r['findings'].append({'kind': 'dead_link',
                                        'fails_run': True, 'file': 'a',
                                        'url': 'u', 'normalized_url': 'u'}),
        lambda r: r['findings'].append({'kind': 'mailto', 'fails_run': False,
                                        'file': 'a', 'url': 'u',
                                        'valid': True, 'link_text': None}),
    ])
    def test_invalid_report_is_rejected(self, change):
        report = self._minimal()
        change(report)
        assert schema_errors(report)


@pytest.fixture
def site(tmp_path):
    """A folder with one finding of every kind."""
    root = tmp_path / 'site'
    (root / 'blog').mkdir(parents=True)
    (root / 'blog' / 'page.html').write_text(
        '<a href="https://dead.example/">Grüße</a>'
        '<a href="https://moved.example/">moved</a>'
        '<a href="https://slow.example/">slow</a>'
        '<a href="https://fine.example/">fine</a>'
        '<a href="http://:8080/">no host</a>'
        '<a href="missing.html">gone</a>'
        '<a href="../../outside.html">outside</a>'
        '<a href="mailto:someone@example.com">mail</a>'
        '<a href="mailto:">empty</a>',
        encoding='utf-8')
    (root / 'refs.bib').write_text(
        '@article{a, title={A}, doi={not-a-doi}}\n'
        '@article{b, title={B}, doi={doi:10.1000/182}}\n',
        encoding='utf-8')
    (root / 'big.html').write_text('x' * (2 * 1024 * 1024), encoding='utf-8')
    return root


async def _responses(url):
    """Stand-in for UrlCheck.head_request."""
    codes = {'https://dead.example/': 404, 'https://moved.example/': 301,
             'https://fine.example/': 200}
    if url == 'https://slow.example/':
        raise TimeoutError
    return codes[url]


@pytest.fixture
def network():
    with patch('salted.url_check.UrlCheck.head_request',
               new_callable=AsyncMock, side_effect=_responses), \
            patch('salted.url_check.ip_check.is_potential_ssrf_target',
                  return_value=False):
        yield


def _checker(tmp_path, **settings) -> salted.Salted:
    checker = salted.Salted()
    checker.cache_file = tmp_path / 'cache.sqlite3'
    checker.report_format = 'json'
    checker.write_to = tmp_path / 'report.json'
    checker.max_file_size_mb = 1
    checker.domain_delay = 0
    checker.quiet = True
    for name, value in settings.items():
        setattr(checker, name, value)
    return checker


def _run(tmp_path, site, **settings) -> dict:
    checker = _checker(tmp_path, **settings)
    checker.check(site)
    return json.loads(pathlib.Path(checker.write_to).read_text(encoding='utf-8'))


def _of_kind(report: dict, kind: str) -> list:
    return [f for f in report['findings'] if f['kind'] == kind]


@pytest.mark.usefixtures('network')
class TestReportContent:
    """A run with one finding of every kind."""

    def test_report_matches_the_schema(self, tmp_path, site):
        assert_valid(_run(tmp_path, site))

    def test_every_kind_is_reported(self, tmp_path, site):
        report = _run(tmp_path, site)
        assert {f['kind'] for f in report['findings']} == set(json_report.KINDS)

    def test_findings_are_ordered_by_kind(self, tmp_path, site):
        kinds = [f['kind'] for f in _run(tmp_path, site)['findings']]
        assert kinds == sorted(kinds, key=json_report.KINDS.index)

    def test_dead_link(self, tmp_path, site):
        [dead] = _of_kind(_run(tmp_path, site), 'dead_link')
        assert dead == {
            'kind': 'dead_link', 'fails_run': True, 'file': 'blog/page.html',
            'url': 'https://dead.example/',
            'normalized_url': 'https://dead.example/',
            'link_text': 'Grüße', 'http_status': 404}

    def test_redirect_and_exception_do_not_fail(self, tmp_path, site):
        report = _run(tmp_path, site)
        [redirect] = _of_kind(report, 'permanent_redirect')
        assert redirect['http_status'] == 301
        assert redirect['fails_run'] is False
        [exception] = _of_kind(report, 'exception')
        assert exception['reason'] == 'Timeout'
        assert exception['fails_run'] is False

    def test_malformed_url(self, tmp_path, site):
        [malformed] = _of_kind(_run(tmp_path, site), 'malformed_url')
        assert malformed['url'] == 'http://:8080/'
        assert malformed['fails_run'] is True
        assert 'normalized_url' not in malformed

    def test_internal_links(self, tmp_path, site):
        findings = _of_kind(_run(tmp_path, site), 'internal_link')
        by_url = {f['url']: f for f in findings}
        assert by_url['missing.html']['fails_run'] is True
        assert by_url['../../outside.html']['fails_run'] is False
        assert 'outside' in by_url['../../outside.html']['reason']

    def test_file_access_error(self, tmp_path, site):
        [unreadable] = _of_kind(_run(tmp_path, site), 'file_access_error')
        assert unreadable['file'] == 'big.html'
        assert unreadable['fails_run'] is True

    def test_dois(self, tmp_path, site):
        report = _run(tmp_path, site)
        [malformed] = _of_kind(report, 'malformed_doi')
        assert malformed['doi'] == 'not-a-doi'
        assert malformed['file'] == 'refs.bib'
        [outdated] = _of_kind(report, 'outdated_doi_link')
        assert outdated['suggestion'] == 'https://doi.org/10.1000/182'
        assert outdated['fails_run'] is False

    def test_mailto(self, tmp_path, site):
        mails = {f['url']: f for f in _of_kind(_run(tmp_path, site), 'mailto')}
        assert mails['mailto:someone@example.com']['valid'] is True
        assert mails['mailto:someone@example.com']['address'] == \
            'someone@example.com'
        # No address: the field is absent, never null or empty.
        assert 'address' not in mails['mailto:']
        assert mails['mailto:']['valid'] is False

    def test_no_field_is_null(self, tmp_path, site):
        report = _run(tmp_path, site)
        assert all(value is not None
                   for finding in report['findings']
                   for value in finding.values())

    def test_result_and_statistics(self, tmp_path, site):
        report = _run(tmp_path, site)
        assert report['result'] == {
            'fails_run': True, 'raise_for_dead_links': False,
            'reasons': [{'code': 'dead_links', 'count': 2},
                        {'code': 'malformed_links', 'count': 1},
                        {'code': 'malformed_dois', 'count': 1},
                        {'code': 'unreadable_files', 'count': 1}]}
        assert report['statistics']['urls_checked'] == 4
        assert report['statistics']['urls_fine'] == 1
        assert report['statistics']['check_internal_links'] is True

    def test_metadata(self, tmp_path, site):
        report = _run(tmp_path, site)
        assert report['schema_version'] == json_report.SCHEMA_VERSION
        assert report['tool'] == {'name': 'salted',
                                  'version': salted.__version__}
        assert report['searchpath'] == str(site)

    def test_base_url_replaces_the_folder(self, tmp_path, site):
        report = _run(tmp_path, site, base_url='https://www.example.com/')
        [dead] = _of_kind(report, 'dead_link')
        assert dead['file'] == 'https://www.example.com/blog/page.html'


@pytest.mark.usefixtures('network')
class TestUrlIsTheTarget:
    """'url' is the target as salted read it, not the source spelling.

    The documentation promised the text 'exactly as written', which a
    Markdown escape, a 'www.' link or an HTML entity made untrue.
    """

    def test_url_after_markdown_and_html_rules(self, tmp_path):
        root = tmp_path / 'docs'
        root.mkdir()
        (root / 'readme.md').write_text(
            '[q](https://dead.example/?x=1&amp;y=2) '
            '[p](<https://dead.example/a b>) see www.dead.example/w\n'
            '<a href="https://dead.example/?h=1&amp;i=2">h</a>\n',
            encoding='utf-8')
        with patch('salted.url_check.UrlCheck.head_request',
                   new_callable=AsyncMock, return_value=404) as head, \
                patch('salted.url_check.ip_check.is_potential_ssrf_target',
                      return_value=False):
            report = _run(tmp_path, root)
        assert_valid(report)
        # The decoded target is what is requested, not the spelling.
        assert sorted(call.args[0] for call in head.await_args_list) == [
            'http://www.dead.example/w', 'https://dead.example/?h=1&i=2',
            'https://dead.example/?x=1&y=2', 'https://dead.example/a%20b']
        assert {(f['url'], f['link_text'])
                for f in _of_kind(report, 'dead_link')} == {
            ('https://dead.example/?x=1&y=2', 'q'),
            ('https://dead.example/a%20b', 'p'),
            ('http://www.dead.example/w', 'www.dead.example/w'),
            ('https://dead.example/?h=1&i=2', 'h')}


class TestRobustness:
    """Always valid JSON, written completely or not at all."""

    def test_file_is_ascii_with_escapes(self, tmp_path, site):
        _run(tmp_path, site)
        raw = (tmp_path / 'report.json').read_bytes()
        assert raw.isascii()
        # Non-ASCII characters are escaped, not dropped.
        assert b'Gr\\u00fc\\u00dfe' in raw
        assert raw.endswith(b'}\n')

    def test_control_characters_are_escaped(self):
        # The HTML parser drops some control characters itself; any that
        # reach the report are kept, but escaped, so printing it cannot
        # inject terminal sequences.
        text = json_report.serialize({'link_text': 'red \x1b[31m\x00'})
        assert '\x1b' not in text and '\x00' not in text
        assert '\\u001b[31m\\u0000' in text
        assert json.loads(text) == {'link_text': 'red \x1b[31m\x00'}

    def test_nan_is_refused(self):
        with pytest.raises(ValueError):
            json_report.serialize({'value': float('nan')})

    def test_failed_run_writes_the_report_first(self, tmp_path, site):
        checker = _checker(tmp_path, raise_for_dead_links=True)
        with pytest.raises(err.DeadLinksException):
            checker.check(site)
        report = json.loads((tmp_path / 'report.json').read_text('utf-8'))
        assert report['result']['raise_for_dead_links'] is True
        assert report['result']['fails_run'] is True

    def test_stdout_carries_only_the_json(self, tmp_path, site, capsys):
        # Not quiet: the progress messages must not end up in the JSON.
        checker = _checker(tmp_path, write_to='cli', quiet=False)
        checker.check(site)
        captured = capsys.readouterr()
        assert_valid(json.loads(captured.out))
        assert 'Scanning files for links' in captured.err

    def test_failed_write_keeps_the_previous_report(self, tmp_path, site,
                                                    monkeypatch):
        (tmp_path / 'report.json').write_text('previous', encoding='utf-8')
        monkeypatch.setattr(json_report.os, 'replace',
                            lambda *_: (_ for _ in ()).throw(OSError('disk')))
        with pytest.raises(OSError, match='disk'):
            _run(tmp_path, site)
        assert (tmp_path / 'report.json').read_text('utf-8') == 'previous'
        # The temporary file is gone as well.
        assert sorted(p.name for p in tmp_path.iterdir()) == [
            'cache.sqlite3', 'report.json', 'site']

    @pytest.mark.skipif(sys.platform == 'win32',
                        reason='POSIX permissions')
    def test_file_gets_the_usual_permissions(self, tmp_path, site):
        _run(tmp_path, site)
        umask = os.umask(0)
        os.umask(umask)
        mode = (tmp_path / 'report.json').stat().st_mode & 0o777
        assert mode == 0o666 & ~umask

    def test_run_without_files_still_writes_a_report(self, tmp_path):
        empty = tmp_path / 'empty'
        empty.mkdir()
        (empty / 'notes.txt').write_text('no links', encoding='utf-8')
        report = _run(tmp_path, empty)
        assert_valid(report)
        assert report['findings'] == []
        assert report['result']['fails_run'] is False
        assert report['statistics']['links_found'] == 0


class TestPathDisplay:
    """File paths: relative, forward slashes, or under base_url."""

    def test_relative_with_forward_slashes(self, tmp_path):
        display = json_report.PathDisplay(str(tmp_path))
        assert display(str(tmp_path / 'a' / 'b.html')) == 'a/b.html'

    def test_base_url(self, tmp_path):
        display = json_report.PathDisplay(str(tmp_path), 'https://x.example/')
        assert display(str(tmp_path / 'a' / 'b.html')) == \
            'https://x.example/a/b.html'

    def test_path_outside_the_folder_is_left_alone(self, tmp_path):
        display = json_report.PathDisplay(str(tmp_path / 'site'))
        other = str(tmp_path / 'other.html')
        assert display(other) == other


class TestSettings:
    """report_format is validated like every other setting."""

    def test_default_is_text(self):
        assert salted.Salted().report_format == 'text'

    @pytest.mark.parametrize('value, expected', [
        ('json', 'json'), (' JSON ', 'json'), ('text', 'text')])
    def test_valid_attribute(self, value, expected):
        checker = salted.Salted()
        checker.report_format = value
        checker.check_parameters()
        assert checker.report_format == expected

    def test_invalid_attribute(self):
        checker = salted.Salted()
        checker.report_format = 'xml'
        with pytest.raises(err.InvalidSettingError, match='report_format'):
            checker.check_parameters()

    def test_config_file(self, tmp_path, monkeypatch):
        (tmp_path / 'salted-linkcheck.ini').write_text(
            '[TEMPLATE]\nreport_format = json\n', encoding='utf-8')
        monkeypatch.chdir(tmp_path)
        assert salted.Salted().report_format == 'json'

    def test_invalid_config_value(self, tmp_path, monkeypatch):
        (tmp_path / 'salted-linkcheck.ini').write_text(
            '[TEMPLATE]\nreport_format = yaml\n', encoding='utf-8')
        monkeypatch.chdir(tmp_path)
        with pytest.raises(err.ConfigFileError, match='report_format'):
            salted.Salted()

    @pytest.mark.parametrize('setting, value', [
        ('template_name', 'default.md.jinja'),
        ('template_searchpath', 'my/templates')])
    def test_template_settings_conflict_with_json(self, setting, value):
        checker = salted.Salted()
        checker.report_format = 'json'
        setattr(checker, setting, value)
        with pytest.raises(err.InvalidSettingError, match='uses no template'):
            checker.check_parameters()

    def test_cli_option(self):
        parser = command_line._build_arg_parser()
        args = parser.parse_args(['--report_format', 'json'])
        checker = salted.Salted()
        command_line._apply_mapped_overrides(checker, args, parser)
        assert checker.report_format == 'json'

    def test_cli_rejects_unknown_format(self, capsys):
        parser = command_line._build_arg_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(['--report_format', 'xml'])
        assert 'report_format' in capsys.readouterr().err

    def test_unusable_write_to_fails_before_checking(self, tmp_path, site):
        checker = _checker(tmp_path,
                           write_to=tmp_path / 'missing' / 'report.json')
        with patch('salted.url_check.UrlCheck.head_request',
                   new_callable=AsyncMock) as head:
            with pytest.raises(err.InvalidSettingError, match='does not exist'):
                checker.check(site)
        head.assert_not_awaited()
