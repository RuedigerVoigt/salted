#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Find Files for salted
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2021: Rüdiger Voigt
Released under the Apache License 2.0
"""

import logging
import pathlib
from typing import Final, List, Optional


class FileFinder:
    """Methods to find files in supported formats."""

    SUPPORTED_SUFFIX: Final[set] = {".htm", ".html", '.md', '.tex', '.bib'}

    def __init__(self) -> None:
        return

    def is_supported_format(self,
                            filepath: pathlib.Path) -> bool:
        """Check if the file format is supported.

        Uses the filename suffix to determine support.

        Args:
            filepath: Path to the file to check.

        Returns:
            True if the file format is supported, False otherwise.
        """
        return bool(filepath.suffix in self.SUPPORTED_SUFFIX)

    def find_files_by_extensions(
            self,
            path_to_base_folder: pathlib.Path,
            suffixes: Optional[set] = None) -> List[pathlib.Path]:
        """Find all files with specific file type suffixes.

        Searches the base folder and all its subfolders recursively.

        Args:
            path_to_base_folder: Base directory to search from.
            suffixes: Set of file suffixes to search for (e.g., {".html", ".md"}).
                If None, searches for all supported formats.

        Returns:
            List of resolved Path objects matching the specified suffixes.
        """
        # self undefined at time of definition. Therefore fallback here:
        if not suffixes:
            suffixes = self.SUPPORTED_SUFFIX

        files_to_check = []
        path_to_check = pathlib.Path(path_to_base_folder)
        all_files = path_to_check.glob('**/*')
        for candidate in all_files:
            if candidate.suffix in suffixes:
                files_to_check.append(candidate.resolve())
        logging.debug('Found %s files', len(files_to_check))
        return files_to_check

    def find_html_files(self,
                        path_to_base_folder: pathlib.Path
                        ) -> List[pathlib.Path]:
        """Find all HTML files in the base folder and its subfolders.

        Args:
            path_to_base_folder: Base directory to search from.

        Returns:
            List of resolved Path objects for HTML files (.htm, .html).
        """
        return self.find_files_by_extensions(
            path_to_base_folder,
            {".htm", ".html"})

    def find_markdown_files(self,
                            path_to_base_folder: pathlib.Path
                            ) -> List[pathlib.Path]:
        """Find all markdown files in the base folder and its subfolders.

        Args:
            path_to_base_folder: Base directory to search from.

        Returns:
            List of resolved Path objects for Markdown files (.md).
        """
        return self.find_files_by_extensions(
            path_to_base_folder,
            {".md"})

    def find_tex_files(self,
                       path_to_base_folder: pathlib.Path
                       ) -> List[pathlib.Path]:
        """Find all TeX files in the base folder and its subfolders.

        Args:
            path_to_base_folder: Base directory to search from.

        Returns:
            List of resolved Path objects for TeX files (.tex).
        """
        return self.find_files_by_extensions(
            path_to_base_folder,
            {".tex"})
