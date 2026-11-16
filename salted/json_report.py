#!/usr/bin/python3

"""
JSON report for tools and AI agents
~~~~~~~~~~~~~~~~~~~~~
Smart, Asynchronous Link Tester with Database backend (SALTED)
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026 Rüdiger Voigt and contributors
Released under the Apache License 2.0

The schema is documented in documentation/json-report.md and published as
JSON Schema in documentation/report-schema-1.json. Its version follows the
rules given there: a new field or a new kind raises the minor version;
removing, renaming or retyping a field, or changing its meaning, raises the
major version.
"""

import contextlib
import datetime
import json
import logging
import os
import pathlib
import sys
import tempfile
from collections.abc import Callable
from typing import Any, Final

from salted import memory_instance
from salted.database_io import MALFORMED_URL_REASON

logger = logging.getLogger(__name__)

SCHEMA_VERSION: Final[str] = '1.0'

# Every kind a finding can have, in the order the report lists them. The
# published schema enumerates the same kinds; a test keeps the two in step.
KINDS: Final[tuple] = (
    'dead_link', 'malformed_url', 'internal_link', 'file_access_error',
    'malformed_doi', 'permanent_redirect', 'exception', 'outdated_doi_link',
    'mailto')

# Why a run fails --raise_for_dead_links, in the order the CLI message names
# them (Salted._failure_message).
REASON_CODES: Final[tuple] = (
    'dead_links', 'malformed_links', 'malformed_dois', 'unreadable_files')

# Keys of the statistics object, mapped from the statistics the text
# templates receive. A missing value counts as 0, so a run that found no
# files still gets a complete object.
_STATISTICS: Final[tuple] = (
    ('links_found', 'num_links'),
    ('distinct_urls', 'num_distinct'),
    ('served_from_cache', 'num_cached'),
    ('urls_checked', 'num_checked'),
    ('urls_fine', 'num_fine'),
    ('needed_full_request', 'needed_full_request'),
    ('runtime_seconds', 'time_to_check'),
    ('dois_found', 'num_dois'),
    ('malformed_dois', 'num_malformed_dois'),
    ('confirmed_dois', 'num_confirmed_dois'),
    ('internal_links_checked', 'num_internal_checked'),
    ('internal_links_fine', 'num_internal_fine'),
)


class PathDisplay:
    """Turn a stored, absolute file path into the form the report shows.

    Paths are given relative to the checked folder, always with forward
    slashes, so a report reads the same on every operating system. With a
    base_url, that URL is put in front instead. Unlike the text reports,
    nothing is stripped: the JSON escapes every control character.
    """

    def __init__(self, base: str, base_url: str | None = None) -> None:
        """Initialize the path display.

        Args:
            base: The checked folder (its parent for a single file).
            base_url: Optional URL that replaces that folder.
        """
        self.base = base
        self.base_url = base_url.rstrip('/') if base_url else None

    def __call__(self, file_path: str) -> str:
        """Return file_path relative to the base, or under base_url.

        Args:
            file_path: The path as stored in the database.
        """
        try:
            relative = pathlib.Path(file_path).relative_to(self.base)
        except ValueError:
            # Not below the checked folder (not expected): left as it is.
            return file_path
        if self.base_url:
            return f'{self.base_url}/{relative.as_posix()}'
        return relative.as_posix()


def statistics_from(text_statistics: dict) -> dict:
    """Map the statistics of the text report to the JSON statistics object.

    Args:
        text_statistics: The statistics passed to the text templates. May be
            partial; missing counts are 0.

    Returns:
        The statistics object with its documented keys.
    """
    result: dict[str, Any] = {
        key: int(text_statistics.get(source, 0) or 0)
        for key, source in _STATISTICS}
    result['check_internal_links'] = bool(
        text_statistics.get('check_internal_links', False))
    return result


def _finding(**fields: Any) -> dict:
    """Build a finding. Fields that do not apply are left out, not null."""
    return {key: value for key, value in fields.items() if value is not None}


# One query per kind, written out in full: no SQL is assembled at runtime.
# Links are reported per occurrence (a row of the queue), joined with the
# result logged for their normalized form.
_SQL_DEAD_LINKS: Final = '''
    SELECT q.filePath, q.url, q.normalizedUrl, q.linktext, e.error
    FROM queue AS q JOIN errors AS e ON q.normalizedUrl = e.normalizedUrl
    ORDER BY q.filePath, q.url;'''
_SQL_REDIRECTS: Final = '''
    SELECT q.filePath, q.url, q.normalizedUrl, q.linktext, r.error
    FROM queue AS q
    JOIN permanentRedirects AS r ON q.normalizedUrl = r.normalizedUrl
    ORDER BY q.filePath, q.url;'''
# Malformed links are logged as exceptions with a fixed reason (see
# DatabaseIO.log_malformed_url), but they fail a run, unlike a timeout.
_SQL_EXCEPTIONS: Final = '''
    SELECT q.filePath, q.url, q.normalizedUrl, q.linktext, x.reason
    FROM queue AS q JOIN exceptions AS x ON q.normalizedUrl = x.normalizedUrl
    WHERE (x.reason = ?) = ?
    ORDER BY q.filePath, q.url;'''


def _dead_links(cursor: Any, display: Callable[[str], str]) -> list:
    cursor.execute(_SQL_DEAD_LINKS)
    return [_finding(kind='dead_link', fails_run=True, file=display(path),
                     url=url, normalized_url=normalized, link_text=text,
                     http_status=code)
            for path, url, normalized, text, code in cursor.fetchall()]


def _malformed_urls(cursor: Any, display: Callable[[str], str]) -> list:
    cursor.execute(_SQL_EXCEPTIONS, [MALFORMED_URL_REASON, True])
    # normalized_url is left out: a malformed link has no normalized form.
    return [_finding(kind='malformed_url', fails_run=True, file=display(path),
                     url=url, link_text=text, reason=reason)
            for path, url, _, text, reason in cursor.fetchall()]


def _internal_links(cursor: Any, display: Callable[[str], str]) -> list:
    cursor.execute('''
        SELECT filePath, url, linktext, reason, isError
        FROM internalLinkFindings ORDER BY filePath, isError DESC, url;''')
    return [_finding(kind='internal_link', fails_run=bool(is_error),
                     file=display(path), url=url, link_text=text,
                     reason=reason)
            for path, url, text, reason, is_error in cursor.fetchall()]


def _file_access_errors(cursor: Any, display: Callable[[str], str]) -> list:
    cursor.execute('''SELECT filePath, problem FROM fileAccessErrors
                      ORDER BY filePath;''')
    return [_finding(kind='file_access_error', fails_run=True,
                     file=display(path), reason=problem)
            for path, problem in cursor.fetchall()]


def _malformed_dois(cursor: Any, display: Callable[[str], str]) -> list:
    cursor.execute('''SELECT filePath, doi, description FROM foundDois
                      WHERE wellFormed = 0 ORDER BY filePath, doi;''')
    return [_finding(kind='malformed_doi', fails_run=True, file=display(path),
                     doi=doi, reason=description)
            for path, doi, description in cursor.fetchall()]


def _redirects(cursor: Any, display: Callable[[str], str]) -> list:
    cursor.execute(_SQL_REDIRECTS)
    return [_finding(kind='permanent_redirect', fails_run=False,
                     file=display(path), url=url, normalized_url=normalized,
                     link_text=text, http_status=code)
            for path, url, normalized, text, code in cursor.fetchall()]


def _exceptions(cursor: Any, display: Callable[[str], str]) -> list:
    cursor.execute(_SQL_EXCEPTIONS, [MALFORMED_URL_REASON, False])
    return [_finding(kind='exception', fails_run=False, file=display(path),
                     url=url, normalized_url=normalized, link_text=text,
                     reason=reason)
            for path, url, normalized, text, reason in cursor.fetchall()]


def _outdated_doi_links(cursor: Any, display: Callable[[str], str]) -> list:
    cursor.execute('''SELECT filePath, found, recommended, description
                      FROM outdatedDoiLinks ORDER BY filePath, found;''')
    return [_finding(kind='outdated_doi_link', fails_run=False,
                     file=display(path), url=found, suggestion=recommended,
                     reason=description)
            for path, found, recommended, description in cursor.fetchall()]


def _mailto_links(cursor: Any, display: Callable[[str], str]) -> list:
    cursor.execute('''SELECT filePath, url, address, valid FROM mailtoLinks
                      ORDER BY filePath, url;''')
    return [_finding(kind='mailto', fails_run=False, file=display(path),
                     url=url, address=address or None, valid=bool(valid))
            for path, url, address, valid in cursor.fetchall()]


# In the order of KINDS.
_COLLECTORS: Final = (
    _dead_links, _malformed_urls, _internal_links, _file_access_errors,
    _malformed_dois, _redirects, _exceptions, _outdated_doi_links,
    _mailto_links)


def collect_findings(mem: memory_instance.MemoryInstance,
                     display: Callable[[str], str]) -> list:
    """Return every finding of the run as one flat list.

    One entry per occurrence: a dead link that stands in three files is
    three findings. Strings are taken from the database unchanged - 'url'
    is the link target as the parsers read it, which is not always its
    spelling in the file (documentation/json-report.md lists the rules).

    Args:
        mem: The in-memory database of the run.
        display: Turns a stored file path into the reported one.

    Returns:
        The findings, ordered by kind (see KINDS) and then by file.
    """
    cursor = mem.get_cursor()
    findings: list = []
    for collect in _COLLECTORS:
        findings.extend(collect(cursor, display))
    return findings


def build_report(mem: memory_instance.MemoryInstance,
                 *,
                 version: str,
                 searchpath: str,
                 statistics: dict,
                 failure_counts: dict,
                 raise_for_dead_links: bool,
                 display: Callable[[str], str]) -> dict:
    """Assemble the JSON report of a run.

    Args:
        mem: The in-memory database of the run.
        version: The salted version.
        searchpath: The file or folder checked, as given by the user.
        statistics: The statistics object (see statistics_from).
        failure_counts: Count per entry of REASON_CODES.
        raise_for_dead_links: Whether this run fails on these findings.
        display: Turns a stored file path into the reported one.

    Returns:
        The report, ready for json.dumps.
    """
    reasons = [{'code': code, 'count': failure_counts[code]}
               for code in REASON_CODES if failure_counts.get(code)]
    return {
        'schema_version': SCHEMA_VERSION,
        'tool': {'name': 'salted', 'version': version},
        'generated_at': datetime.datetime.now(datetime.UTC).strftime(
            '%Y-%m-%dT%H:%M:%SZ'),
        'searchpath': searchpath,
        'result': {
            # True if these findings fail a --raise_for_dead_links run,
            # whether or not this run used it.
            'fails_run': bool(reasons),
            'raise_for_dead_links': raise_for_dead_links,
            'reasons': reasons,
        },
        'statistics': statistics,
        'findings': collect_findings(mem, display),
    }


def serialize(report: dict) -> str:
    """Serialize the report.

    ASCII only, so it is valid on every console encoding (a Windows console
    may not be UTF-8); every other character is escaped. Control characters
    are escaped as well, so printing the report cannot inject terminal
    sequences.

    Args:
        report: The report from build_report.

    Returns:
        The JSON text, ending in a newline.
    """
    return json.dumps(report, ensure_ascii=True, allow_nan=False,
                      indent=2) + '\n'


def write_report(report: dict,
                 write_to: str | pathlib.Path) -> None:
    """Write the report to stdout or, atomically, to a file.

    A file is written to a temporary file in the same folder and moved into
    place, so a reader never sees a half-written report, and a failure
    leaves an earlier report untouched.

    Args:
        report: The report from build_report.
        write_to: 'cli' for stdout, otherwise the path of the report file.

    Raises:
        OSError: If the file cannot be written.
    """
    text = serialize(report)
    if write_to == 'cli':
        sys.stdout.write(text)
        sys.stdout.flush()
        return

    target = pathlib.Path(write_to).resolve()
    handle, temporary = tempfile.mkstemp(
        dir=target.parent, prefix=f'.{target.name}.', suffix='.tmp')
    try:
        with os.fdopen(handle, 'w', encoding='utf-8', newline='\n') as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        # mkstemp creates the file readable by its owner only. A report
        # gets the permissions any other new file would get.
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(temporary, 0o666 & ~umask)
        os.replace(temporary, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temporary)
        raise
    logger.info('Wrote JSON report to file: %s', target)
