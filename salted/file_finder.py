#!/usr/bin/python3

"""
Find Files for salted
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026 Rüdiger Voigt and contributors
Released under the Apache License 2.0
"""

import logging
import pathlib
from typing import Final

from userprovided.parameters import separated_string_to_set


def separated_paths_to_set(raw: str | None) -> set[str] | None:
    """Parse a comma-separated list of file system paths into a set.

    Thin wrapper around the shared parser used for the other list-valued
    options. That parser treats a backslash as an escape character, which
    is right for URLs but destroys Windows paths: 'C:\\docs\\drafts' would
    arrive as 'C:docsdrafts'. Doubling the backslashes first makes them
    literal while keeping everything else the parser does - quoting (so a
    path containing a comma can be written as "C:\\my, folder"), trimming,
    dropping empty entries, and collapsing duplicates.

    Args:
        raw: The comma-separated string, or None.

    Returns:
        Set of path strings, or None if raw is None.
    """
    if raw is None:
        return None
    return separated_string_to_set(raw.replace('\\', '\\\\'))


class FileFinder:
    """Methods to find files in supported formats."""

    SUPPORTED_SUFFIX: Final[set] = {".htm", ".html", '.md', '.tex', '.bib'}

    def __init__(self) -> None:
        """Initialize the FileFinder with the set of supported file suffixes."""
        return

    def is_supported_format(self,
                            filepath: pathlib.Path) -> bool:
        """Check if the file format is supported.

        Uses the filename suffix to determine support. The comparison is
        case-insensitive: 'INDEX.HTML' and 'notes.MD' are as valid as their
        lowercase spellings, and both occur in the wild - especially on
        Windows and macOS, whose filesystems do not distinguish the case.
        Treating them as unsupported silently left their links unchecked.

        Args:
            filepath: Path to the file to check.

        Returns:
            True if the file format is supported, False otherwise.
        """
        return bool(filepath.suffix.lower() in self.SUPPORTED_SUFFIX)

    @staticmethod
    def resolve_exclusions(entries: set | None) -> set[pathlib.Path]:
        """Resolve user-supplied exclusion entries into comparable paths.

        An entry may be a file or a folder, given as an absolute path or as
        a path relative to the directory salted was called from (the current
        working directory, *not* the searchpath): that is where the user
        typed the path, so it is the folder they can see.

        Both sides of the later comparison are resolved - here and in
        find_files_by_extensions - so symlinks, '..' segments, and (on
        Windows) the spelling of an existing name cannot make an exclusion
        miss the file it names.

        Args:
            entries: Paths to exclude, as strings or Path objects.

        Returns:
            Set of resolved Path objects. Entries that cannot be resolved at
            all are logged as a warning and dropped.
        """
        if not entries:
            return set()
        resolved: set[pathlib.Path] = set()
        for entry in entries:
            text = str(entry).strip().strip('"').strip("'")
            if not text:
                continue
            try:
                candidate = pathlib.Path(text).resolve()
            except (OSError, ValueError, RuntimeError):
                logging.warning(
                    "Cannot resolve excluded path '%s' - ignored.", entry)
                continue
            if not candidate.exists():
                # Not an error: the exclusion simply matches nothing. Say so,
                # as a typo here silently checks files meant to be skipped.
                logging.warning(
                    "Excluded path '%s' does not exist. Note that a relative "
                    "path is resolved against the current working directory.",
                    entry)
            resolved.add(candidate)
        return resolved

    @staticmethod
    def is_excluded(filepath: pathlib.Path,
                    exclusions: set[pathlib.Path] | None) -> bool:
        """Check whether a resolved path is covered by an exclusion.

        Args:
            filepath: A *resolved* path to test.
            exclusions: Resolved exclusions from resolve_exclusions().

        Returns:
            True if the path is an excluded file, is an excluded folder, or
            lies within one. A single is_relative_to covers all three, as a
            path is relative to itself.
        """
        if not exclusions:
            return False
        return any(filepath.is_relative_to(excluded) for excluded in exclusions)

    def find_files_by_extensions(
            self,
            path_to_base_folder: pathlib.Path,
            suffixes: set | None = None,
            exclude: set[pathlib.Path] | None = None) -> list[pathlib.Path]:
        """Find all files with specific file type suffixes.

        Searches the base folder and all its subfolders recursively.

        Matching is case-insensitive, so a folder holding 'INDEX.HTML' or
        'Notes.Md' is searched as expected.

        Args:
            path_to_base_folder: Base directory to search from.
            suffixes: Set of file suffixes to search for (e.g., {".html", ".md"}).
                If None, searches for all supported formats.
            exclude: Resolved paths (files or folders) to leave out, as
                returned by resolve_exclusions(). If None, nothing is excluded.

        Returns:
            List of resolved Path objects matching the specified suffixes.
        """
        # self undefined at time of definition. Therefore fallback here:
        if not suffixes:
            suffixes = self.SUPPORTED_SUFFIX
        # Normalize here too: a caller may pass '.HTML'.
        wanted = {suffix.lower() for suffix in suffixes}

        files_to_check = []
        num_excluded = 0
        path_to_check = pathlib.Path(path_to_base_folder)
        all_files = path_to_check.glob('**/*')
        for candidate in all_files:
            if candidate.suffix.lower() in wanted:
                resolved = candidate.resolve()
                if self.is_excluded(resolved, exclude):
                    num_excluded += 1
                    continue
                files_to_check.append(resolved)
        logging.debug('Found %s files', len(files_to_check))
        if num_excluded:
            logging.debug('Left out %s excluded files', num_excluded)
        return files_to_check
