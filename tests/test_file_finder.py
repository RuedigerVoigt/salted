#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for file discovery and the exclusion of files and folders
~~~~~~~~~~~~~~~~~~~~~
Smart, Asynchronous Link Tester with Database backend (SALTED)
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026: Released under the Apache License 2.0
"""

import pathlib

from salted.file_finder import FileFinder, separated_paths_to_set


def build_tree(root: pathlib.Path) -> None:
    """Create a small tree with two nested folders and five files."""
    (root / 'docs').mkdir(parents=True)
    (root / 'docs' / 'drafts').mkdir()
    (root / 'vendor').mkdir()
    (root / 'index.html').write_text('x', encoding='utf-8')
    (root / 'docs' / 'guide.html').write_text('x', encoding='utf-8')
    (root / 'docs' / 'notes.md').write_text('x', encoding='utf-8')
    (root / 'docs' / 'drafts' / 'wip.html').write_text('x', encoding='utf-8')
    (root / 'vendor' / 'bundled.html').write_text('x', encoding='utf-8')


class TestSeparatedPathsToSet:
    """Paths are parsed with backslashes taken literally, not as escapes."""

    def test_none_returns_none(self):
        assert separated_paths_to_set(None) is None

    def test_basic_split_and_trim(self):
        assert separated_paths_to_set(' docs/drafts , build ') == {
            'docs/drafts', 'build'}

    def test_windows_paths_survive(self):
        """The shared parser would read a backslash as an escape character.

        Regression guard: 'C:\\Users\\rv\\docs' must not become
        'C:Usersrvdocs'.
        """
        assert separated_paths_to_set(r'C:\Users\rv\docs, .\build') == {
            r'C:\Users\rv\docs', r'.\build'}

    def test_trailing_backslash_survives(self):
        assert separated_paths_to_set('C:\\docs\\') == {'C:\\docs\\'}

    def test_quoted_path_may_contain_a_comma(self):
        assert separated_paths_to_set(r'"C:\my, folder", other') == {
            r'C:\my, folder', 'other'}

    def test_empty_entries_are_dropped(self):
        assert separated_paths_to_set('docs,,  , build') == {'docs', 'build'}


class TestResolveExclusions:
    """Entries become resolved paths, relative ones against the CWD."""

    def test_empty_input_yields_empty_set(self):
        assert FileFinder.resolve_exclusions(None) == set()
        assert FileFinder.resolve_exclusions(set()) == set()

    def test_absolute_path_is_kept(self, tmp_path):
        target = tmp_path / 'docs'
        target.mkdir()
        assert FileFinder.resolve_exclusions({str(target)}) == {
            target.resolve()}

    def test_relative_path_resolves_against_cwd(self, tmp_path, monkeypatch):
        """Relative means: relative to where salted was called from."""
        (tmp_path / 'docs').mkdir()
        monkeypatch.chdir(tmp_path)

        assert FileFinder.resolve_exclusions({'docs'}) == {
            (tmp_path / 'docs').resolve()}

    def test_relative_path_is_not_resolved_against_the_searchpath(
            self, tmp_path, monkeypatch):
        """A same-named folder below the searchpath must not be hit."""
        called_from = tmp_path / 'called_from'
        called_from.mkdir()
        searchpath = tmp_path / 'searchpath'
        (searchpath / 'docs').mkdir(parents=True)
        monkeypatch.chdir(called_from)

        resolved = FileFinder.resolve_exclusions({'docs'})

        assert (searchpath / 'docs').resolve() not in resolved

    def test_dot_segments_are_normalized(self, tmp_path, monkeypatch):
        (tmp_path / 'docs' / 'drafts').mkdir(parents=True)
        monkeypatch.chdir(tmp_path / 'docs')

        assert FileFinder.resolve_exclusions({'../docs/drafts'}) == {
            (tmp_path / 'docs' / 'drafts').resolve()}

    def test_surrounding_quotes_and_whitespace_are_stripped(self, tmp_path,
                                                            monkeypatch):
        (tmp_path / 'docs').mkdir()
        monkeypatch.chdir(tmp_path)

        assert FileFinder.resolve_exclusions({' "docs" '}) == {
            (tmp_path / 'docs').resolve()}

    def test_blank_entries_are_dropped(self, tmp_path, monkeypatch):
        (tmp_path / 'docs').mkdir()
        monkeypatch.chdir(tmp_path)

        assert FileFinder.resolve_exclusions({'docs', '', '  ', '""'}) == {
            (tmp_path / 'docs').resolve()}

    def test_unresolvable_entry_is_dropped_with_a_warning(self, monkeypatch,
                                                          caplog):
        """A path the operating system refuses must not stop the run."""
        def refuse(self, *args, **kwargs):
            raise OSError('nope')

        monkeypatch.setattr(pathlib.Path, 'resolve', refuse)

        assert FileFinder.resolve_exclusions({'whatever'}) == set()
        assert 'Cannot resolve' in caplog.text

    def test_nonexistent_entry_is_kept_but_warned_about(self, tmp_path,
                                                        monkeypatch, caplog):
        """A typo must not pass silently, but it is not fatal either."""
        monkeypatch.chdir(tmp_path)

        resolved = FileFinder.resolve_exclusions({'typo'})

        assert resolved == {(tmp_path / 'typo').resolve()}
        assert 'does not exist' in caplog.text


class TestIsExcluded:
    """A path is excluded if it is, or lies below, an excluded path."""

    def test_no_exclusions_means_not_excluded(self, tmp_path):
        assert FileFinder.is_excluded(tmp_path / 'a.html', set()) is False
        assert FileFinder.is_excluded(tmp_path / 'a.html', None) is False

    def test_excluded_file_matches_itself(self, tmp_path):
        target = tmp_path / 'a.html'
        assert FileFinder.is_excluded(target, {target}) is True

    def test_file_inside_excluded_folder_matches(self, tmp_path):
        assert FileFinder.is_excluded(
            tmp_path / 'docs' / 'deep' / 'a.html', {tmp_path / 'docs'}) is True

    def test_excluded_folder_matches_itself(self, tmp_path):
        assert FileFinder.is_excluded(
            tmp_path / 'docs', {tmp_path / 'docs'}) is True

    def test_sibling_with_shared_name_prefix_does_not_match(self, tmp_path):
        """'docs-old' must not be swallowed by an exclusion of 'docs'."""
        assert FileFinder.is_excluded(
            tmp_path / 'docs-old' / 'a.html', {tmp_path / 'docs'}) is False


class TestFindFilesWithExclusions:
    """find_files_by_extensions leaves out what the exclusions cover."""

    def test_without_exclusions_everything_is_found(self, tmp_path):
        build_tree(tmp_path)
        found = FileFinder().find_files_by_extensions(tmp_path)
        assert len(found) == 5

    def test_excluded_folder_removes_its_whole_subtree(self, tmp_path):
        build_tree(tmp_path)
        found = FileFinder().find_files_by_extensions(
            tmp_path, exclude={(tmp_path / 'docs').resolve()})

        assert {p.name for p in found} == {'index.html', 'bundled.html'}

    def test_excluded_file_removes_only_that_file(self, tmp_path):
        build_tree(tmp_path)
        found = FileFinder().find_files_by_extensions(
            tmp_path, exclude={(tmp_path / 'docs' / 'notes.md').resolve()})

        assert {p.name for p in found} == {
            'index.html', 'guide.html', 'wip.html', 'bundled.html'}

    def test_several_exclusions_combine(self, tmp_path):
        build_tree(tmp_path)
        found = FileFinder().find_files_by_extensions(
            tmp_path,
            exclude={(tmp_path / 'vendor').resolve(),
                     (tmp_path / 'docs' / 'drafts').resolve()})

        assert {p.name for p in found} == {
            'index.html', 'guide.html', 'notes.md'}

    def test_exclusions_combine_with_the_suffix_filter(self, tmp_path):
        build_tree(tmp_path)
        found = FileFinder().find_files_by_extensions(
            tmp_path,
            suffixes={'.html'},
            exclude={(tmp_path / 'vendor').resolve()})

        assert {p.name for p in found} == {
            'index.html', 'guide.html', 'wip.html'}

    def test_exclusion_outside_the_searchpath_changes_nothing(self, tmp_path):
        build_tree(tmp_path)
        found = FileFinder().find_files_by_extensions(
            tmp_path, exclude={(tmp_path.parent / 'elsewhere').resolve()})

        assert len(found) == 5

    def test_excluding_the_searchpath_itself_leaves_nothing(self, tmp_path):
        build_tree(tmp_path)
        found = FileFinder().find_files_by_extensions(
            tmp_path, exclude={tmp_path.resolve()})

        assert found == []
