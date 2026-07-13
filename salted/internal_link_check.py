#!/usr/bin/python3

"""
Check internal links against the local filesystem.
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026 Rüdiger Voigt and contributors
Released under the Apache License 2.0
"""

import logging
import pathlib
import urllib.parse
from collections import Counter

from bs4 import BeautifulSoup  # type: ignore

from salted.parser import _BS_PARSER


class InternalLinkCheck:
    """Resolve internal links on disk and verify their targets exist.

    Internal links (relative paths, root-relative paths, and fragment
    references) are resolved against the checked file's location and the
    checked folder ("site root"). Security containment: the checked folder
    is treated as a jail — a link whose resolved target lies outside it is
    never touched on disk (no existence probe, no read). This prevents a
    crafted document from using salted as a file-existence oracle or from
    making it open arbitrary files. Backslash paths and anything with a
    scheme or host (including UNC-style ``//host/share`` forms, which
    would trigger SMB requests on Windows) are rejected before any
    filesystem access.
    """

    # Findings with these prefixes are broken links (isError=1); everything
    # else stored is an unverifiable note (isError=0) and must not fail CI.

    def __init__(self,
                 root: pathlib.Path,
                 max_file_size_mb: int = 20) -> None:
        """Initialize the internal link checker.

        Args:
            root: The checked folder. Targets must resolve inside it.
            max_file_size_mb: Maximum size of an HTML file that is opened
                for fragment (#id) verification. Larger targets are not
                read; their fragments count as unverifiable, not broken.
        """
        self.root = root.resolve()
        self.max_bytes = max_file_size_mb * 1024 * 1024
        self.cnt: Counter = Counter()
        # Cache of fragment anchors per resolved HTML file. None means the
        # file could not be parsed/read — fragments count as unverifiable.
        self._anchor_cache: dict[pathlib.Path, set[str] | None] = {}

    @staticmethod
    def is_internal_link(url: str) -> bool:
        """Return True if the link is an internal (same-site) reference.

        Internal means: no scheme and no host. This excludes http(s),
        mailto, tel, javascript, file, protocol-relative ``//host/...``
        links, and Windows drive references like ``C:/...`` (urlparse
        reads the drive letter as a scheme).

        Args:
            url: The link exactly as written in the document.
        """
        if not url or not url.strip():
            return False
        try:
            parsed = urllib.parse.urlparse(url)
        except ValueError:
            return False
        return parsed.scheme == '' and parsed.netloc == ''

    def check_link(self,
                   source_file: pathlib.Path,
                   link: str) -> tuple[str, int] | None:
        """Check a single internal link found in source_file.

        Args:
            source_file: The file the link was found in. Must be inside
                the checked folder.
            link: The link exactly as written in the document.

        Returns:
            None if the link is fine. Otherwise a tuple (reason, is_error):
            is_error is 1 for a broken link and 0 for a link that cannot
            be verified (e.g. it resolves outside the checked folder).
        """
        self.cnt['internal_checked'] += 1
        finding = self._evaluate(source_file, link)
        if finding is None:
            self.cnt['internal_fine'] += 1
        elif finding[1] == 1:
            self.cnt['internal_broken'] += 1
        else:
            self.cnt['internal_unverifiable'] += 1
        return finding

    def _evaluate(self,
                  source_file: pathlib.Path,
                  link: str) -> tuple[str, int] | None:
        """Resolve and verify the link. See check_link for the contract."""
        # Backslashes are not valid URL path separators and — passed to
        # pathlib on Windows — could form UNC paths (\\host\share) whose
        # mere existence check triggers an SMB network request.
        if '\\' in link:
            return ('invalid link: contains a backslash', 1)

        try:
            parsed = urllib.parse.urlparse(link)
            path_part = urllib.parse.unquote(parsed.path)
        except ValueError:
            return ('invalid link: cannot be parsed', 1)

        if '\x00' in path_part or any(ord(c) < 32 for c in path_part):
            return ('invalid link: contains control characters', 1)

        # Fragment-only (#section) and query-only links refer to the
        # source file itself.
        if not path_part:
            return self._check_fragment(source_file, parsed.fragment)

        resolved = self._resolve_in_jail(source_file, path_part)
        if isinstance(resolved, tuple):
            return resolved
        return self._check_target(resolved, path_part, parsed.fragment)

    def _resolve_in_jail(self,
                         source_file: pathlib.Path,
                         path_part: str) -> pathlib.Path | tuple[str, int]:
        """Resolve the link path and enforce the jail boundary.

        Returns:
            The resolved path if it lies inside the checked folder,
            otherwise a (reason, is_error) finding. The jail check runs
            BEFORE any filesystem probe; resolve() follows symlinks, so a
            symlink escaping the tree is caught here too.
        """
        if path_part.startswith('/'):
            # Root-relative: resolve against the checked folder. A UNC-style
            # '//host/share' never gets here (urlparse puts the host into
            # netloc, so is_internal_link already rejected it).
            candidate = self.root / path_part.lstrip('/')
        else:
            candidate = source_file.parent / path_part

        try:
            resolved = candidate.resolve()
        except (OSError, ValueError, RuntimeError):
            return ('invalid link: path cannot be resolved', 1)

        if not resolved.is_relative_to(self.root):
            return ('not checked: resolves outside the checked folder', 0)
        return resolved

    def _check_target(self,
                      resolved: pathlib.Path,
                      path_part: str,
                      fragment: str) -> tuple[str, int] | None:
        """Verify the jailed target exists (and its fragment, if any)."""
        try:
            if path_part.endswith('/'):
                # Directory reference: the directory itself must exist.
                if not resolved.is_dir():
                    return ('target folder does not exist', 1)
                return None
            if resolved.is_dir():
                return None
            if not resolved.is_file():
                return ('target file does not exist', 1)
        except OSError:
            return ('invalid link: target path not accessible', 1)

        if fragment:
            return self._check_fragment(resolved, fragment)
        return None

    def _check_fragment(self,
                        target: pathlib.Path,
                        fragment: str) -> tuple[str, int] | None:
        """Verify that a #fragment exists as an anchor in the target file.

        Only HTML targets are verified. Non-HTML targets, unreadable or
        oversized files count as unverifiable — never as broken.

        Args:
            target: Resolved path of the file the fragment points into.
                Callers guarantee it is inside the checked folder.
            fragment: The fragment identifier without the leading '#'.
        """
        if not fragment:
            # A bare '#' (or fragment-only link on the file itself) always
            # "works" in a browser.
            return None
        # Browsers scroll to the top for '#top' even without a matching
        # element (HTML spec fallback).
        if fragment == 'top':
            return None
        if target.suffix.lower() not in ('.htm', '.html'):
            return None
        anchors = self._collect_anchors(target)
        if anchors is None:
            return (f"fragment '#{fragment}' not verifiable "
                    '(target could not be parsed)', 0)
        if urllib.parse.unquote(fragment) in anchors:
            return None
        return (f"fragment '#{fragment}' not found in target", 1)

    def _collect_anchors(self,
                         target: pathlib.Path) -> set[str] | None:
        """Return all anchor names (id attributes and <a name>) in a file.

        Results are cached per file. Returns None if the file cannot be
        read or exceeds the size limit.
        """
        if target in self._anchor_cache:
            return self._anchor_cache[target]

        anchors: set[str] | None = None
        try:
            if target.stat().st_size <= self.max_bytes:
                try:
                    content = target.read_text(encoding='utf-8')
                except UnicodeDecodeError:
                    content = target.read_text(encoding='latin-1')
                soup = BeautifulSoup(content, _BS_PARSER)
                anchors = {str(tag['id']) for tag in soup.find_all(id=True)}
                anchors.update(
                    str(tag['name'])
                    for tag in soup.find_all('a', attrs={'name': True}))
            else:
                logging.warning(
                    'File too large for fragment verification: %s', target)
        except OSError as exc:
            logging.warning('Cannot read %s for fragment verification: %s',
                            target, exc)

        self._anchor_cache[target] = anchors
        return anchors
