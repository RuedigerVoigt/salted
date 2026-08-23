#!/usr/bin/python3

"""
Tests for the internal link checker (salted/internal_link_check.py).

Uses a real temporary directory (tmp_path) because the checker's security
containment is about actual filesystem path resolution.
"""

import pytest

import salted
from salted import database_io, memory_instance, parameter_rules
from salted.input_handler import InputHandler
from salted.internal_link_check import InternalLinkCheck


@pytest.fixture
def site(tmp_path):
    """A small static site inside a jail directory, with a file outside."""
    root = tmp_path / 'site'
    root.mkdir()
    (root / 'index.html').write_text(
        '<html><body><h1 id="intro">Hi</h1><a name="legacy"></a></body></html>',
        encoding='utf-8')
    (root / 'style.css').write_text('body {}', encoding='utf-8')
    sub = root / 'blog'
    sub.mkdir()
    (sub / 'post.html').write_text(
        '<html><body><p id="section-1">text</p></body></html>',
        encoding='utf-8')
    # A file OUTSIDE the jail that exists — must never be confirmed.
    (tmp_path / 'secret.txt').write_text('secret', encoding='utf-8')
    return root


@pytest.fixture
def checker(site):
    return InternalLinkCheck(root=site)


class TestClassification:
    """is_internal_link must only accept scheme-less, host-less links."""

    @pytest.mark.parametrize('url', [
        'page.html',
        '../up.html',
        '/rooted/page.html',
        '#fragment',
        'page.html#intro',
        'folder/',
        'image.png?v=2',
    ])
    def test_internal_forms(self, url):
        assert InternalLinkCheck.is_internal_link(url) is True

    @pytest.mark.parametrize('url', [
        'http://example.com',
        'https://example.com/page',
        'mailto:foo@example.com',
        'tel:+123456',
        'javascript:alert(1)',
        'ftp://example.com/file',
        'file:///etc/passwd',
        # Protocol-relative: a host, so external.
        '//example.com/page',
        # Windows drive letter is parsed as a scheme.
        'C:/Users/someone/file.html',
        '',
        '   ',
    ])
    def test_external_or_invalid_forms(self, url):
        assert InternalLinkCheck.is_internal_link(url) is False


class TestResolution:
    """Existing targets pass; missing targets are broken."""

    def test_same_directory_file_exists(self, site, checker):
        assert checker.check_link(site / 'index.html', 'style.css') is None

    def test_subdirectory_file_exists(self, site, checker):
        assert checker.check_link(site / 'index.html', 'blog/post.html') is None

    def test_relative_up_and_down(self, site, checker):
        assert checker.check_link(
            site / 'blog' / 'post.html', '../index.html') is None

    def test_root_relative_path(self, site, checker):
        assert checker.check_link(
            site / 'blog' / 'post.html', '/index.html') is None

    def test_missing_target_is_error(self, site, checker):
        reason, is_error = checker.check_link(site / 'index.html', 'gone.html')
        assert is_error == 1
        assert 'does not exist' in reason

    def test_directory_link_with_trailing_slash(self, site, checker):
        assert checker.check_link(site / 'index.html', 'blog/') is None

    def test_missing_directory_is_error(self, site, checker):
        reason, is_error = checker.check_link(site / 'index.html', 'nope/')
        assert is_error == 1

    def test_directory_without_trailing_slash(self, site, checker):
        assert checker.check_link(site / 'index.html', 'blog') is None

    def test_percent_encoded_path(self, site, checker):
        (site / 'my page.html').write_text('<html></html>', encoding='utf-8')
        assert checker.check_link(site / 'index.html', 'my%20page.html') is None

    def test_query_string_is_ignored(self, site, checker):
        assert checker.check_link(site / 'index.html', 'style.css?v=2') is None

    def test_counters(self, site, checker):
        checker.check_link(site / 'index.html', 'style.css')
        checker.check_link(site / 'index.html', 'gone.html')
        assert checker.cnt['internal_checked'] == 2
        assert checker.cnt['internal_fine'] == 1
        assert checker.cnt['internal_broken'] == 1


class TestSecurityContainment:
    """Links must never cause probes or reads outside the checked folder."""

    def test_traversal_out_of_tree_is_not_probed(self, site, checker):
        # ../secret.txt EXISTS on disk — but outside the jail. The checker
        # must not confirm its existence: unverifiable, not fine/broken.
        reason, is_error = checker.check_link(
            site / 'index.html', '../secret.txt')
        assert is_error == 0
        assert 'outside' in reason

    def test_deep_traversal_out_of_tree(self, site, checker):
        reason, is_error = checker.check_link(
            site / 'index.html', '../../../../../../etc/passwd')
        assert is_error == 0
        assert 'outside' in reason

    def test_root_relative_cannot_escape(self, site, checker):
        # Root-relative paths resolve against the jail, and '..' segments
        # that climb out of it must be caught after resolution.
        reason, is_error = checker.check_link(
            site / 'index.html', '/../secret.txt')
        assert is_error == 0
        assert 'outside' in reason

    def test_backslashes_rejected_before_fs_access(self, site, checker):
        # Backslash forms could build UNC paths (\\host\share) whose
        # existence check triggers SMB traffic on Windows.
        reason, is_error = checker.check_link(
            site / 'index.html', '..\\secret.txt')
        assert is_error == 1
        assert 'backslash' in reason

    def test_unc_style_link_is_not_internal(self):
        # urlparse puts the host of '//host/share' into netloc.
        assert InternalLinkCheck.is_internal_link('//host/share/file') is False

    def test_control_characters_rejected(self, site, checker):
        reason, is_error = checker.check_link(
            site / 'index.html', 'page%00.html')
        assert is_error == 1

    def test_symlink_escape_is_caught(self, site, checker, tmp_path):
        # Windows only permits symlinks with Developer Mode or elevation.
        # Skipping on os.name == 'nt' outright would retire this test on the
        # whole Windows leg, so it is attempted and skipped only where the
        # OS actually refuses.
        escape = site / 'escape.txt'
        try:
            escape.symlink_to(tmp_path / 'secret.txt')
        except (OSError, NotImplementedError) as exc:
            pytest.skip(f'this OS does not allow creating a symlink: {exc}')
        reason, is_error = checker.check_link(site / 'index.html', 'escape.txt')
        assert is_error == 0
        assert 'outside' in reason

    def test_windows_device_name_is_not_fine(self, site, checker):
        result = checker.check_link(site / 'index.html', 'NUL')
        # Never "fine": devices are neither regular files nor directories
        # inside the jail. (Resolution details differ per platform.)
        assert result is not None


class TestFragments:
    """#fragment links require a matching anchor in the target HTML."""

    def test_fragment_only_link_with_existing_id(self, site, checker):
        assert checker.check_link(site / 'index.html', '#intro') is None

    def test_fragment_only_link_missing_id(self, site, checker):
        reason, is_error = checker.check_link(site / 'index.html', '#nope')
        assert is_error == 1
        assert '#nope' in reason

    def test_fragment_in_other_file(self, site, checker):
        assert checker.check_link(
            site / 'index.html', 'blog/post.html#section-1') is None

    def test_fragment_in_other_file_missing(self, site, checker):
        reason, is_error = checker.check_link(
            site / 'index.html', 'blog/post.html#missing')
        assert is_error == 1

    def test_a_name_anchor_found(self, site, checker):
        assert checker.check_link(site / 'index.html', '#legacy') is None

    def test_bare_hash_is_fine(self, site, checker):
        assert checker.check_link(site / 'index.html', '#') is None

    def test_hash_top_is_fine_without_element(self, site, checker):
        # Browsers scroll to the top for '#top' even without an anchor.
        assert checker.check_link(site / 'index.html', '#top') is None

    def test_fragment_on_non_html_target_not_verified(self, site, checker):
        # Cannot verify anchors in CSS — not an error.
        assert checker.check_link(site / 'index.html', 'style.css#foo') is None

    def test_oversized_target_is_unverifiable_not_broken(self, site):
        checker = InternalLinkCheck(root=site, max_file_size_mb=1)
        big = site / 'big.html'
        big.write_text('<html>' + 'x' * (2 * 1024 * 1024), encoding='utf-8')
        finding = checker.check_link(site / 'index.html', 'big.html#x')
        assert finding is not None
        assert finding[1] == 0

    def test_anchor_cache_is_used(self, site, checker):
        checker.check_link(site / 'index.html', '#intro')
        checker.check_link(site / 'index.html', '#legacy')
        assert len(checker._anchor_cache) == 1


class TestInputHandlerIntegration:
    """Internal links from HTML files are routed to the checker."""

    def _handler(self, site):
        mem = memory_instance.MemoryInstance()
        db = database_io.DatabaseIO(mem)
        checker = InternalLinkCheck(root=site)
        handler = InputHandler(db, quiet=True, internal_checker=checker)
        return mem, db, handler, checker

    def test_broken_internal_link_is_logged(self, site):
        mem, db, handler, checker = self._handler(site)
        try:
            handler.handle_found_urls(
                site / 'index.html', [['gone.html', 'broken link']])
            assert db.count_internal_link_errors() == 1
        finally:
            mem.tear_down_in_memory_db()

    def test_fine_internal_link_not_logged(self, site):
        mem, db, handler, checker = self._handler(site)
        try:
            handler.handle_found_urls(
                site / 'index.html', [['style.css', 'stylesheet']])
            assert db.count_internal_link_errors() == 0
            assert checker.cnt['internal_fine'] == 1
        finally:
            mem.tear_down_in_memory_db()

    def test_unverifiable_link_does_not_count_as_error(self, site):
        mem, db, handler, checker = self._handler(site)
        try:
            handler.handle_found_urls(
                site / 'index.html', [['../secret.txt', 'escape']])
            # Stored as a finding, but not as an error (no CI failure).
            assert db.count_internal_link_errors() == 0
            assert checker.cnt['internal_unverifiable'] == 1
        finally:
            mem.tear_down_in_memory_db()

    def test_markdown_source_not_internally_checked(self, site):
        # Issue #1 scope: internal resolution only for HTML sources.
        mem, db, handler, checker = self._handler(site)
        try:
            handler.handle_found_urls(
                site / 'readme.md', [['gone.html', 'md link']])
            assert checker.cnt['internal_checked'] == 0
            assert handler.cnt['unsupported_scheme'] == 1
        finally:
            mem.tear_down_in_memory_db()

    def test_without_checker_internal_links_are_skipped(self, site):
        mem = memory_instance.MemoryInstance()
        db = database_io.DatabaseIO(mem)
        handler = InputHandler(db, quiet=True)
        try:
            handler.handle_found_urls(
                site / 'index.html', [['gone.html', 'link']])
            assert handler.cnt['unsupported_scheme'] == 1
        finally:
            mem.tear_down_in_memory_db()

    def test_external_links_still_queued(self, site):
        mem, db, handler, checker = self._handler(site)
        try:
            handler.handle_found_urls(
                site / 'index.html',
                [['https://example.com', 'ext'], ['style.css', 'int']])
            assert len(db.urls_to_check()) == 1
            assert checker.cnt['internal_checked'] == 1
        finally:
            mem.tear_down_in_memory_db()


class TestConfiguration:
    """The check_internal_links switch is wired through config and rules."""

    def test_default_is_enabled(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        checker = salted.Salted()
        assert checker.check_internal_links is True

    def test_config_file_can_disable(self, tmp_path, monkeypatch):
        cfg = tmp_path / 'salted-linkcheck.ini'
        cfg.write_text('[BEHAVIOR]\ncheck_internal_links = False\n',
                       encoding='utf-8')
        monkeypatch.chdir(tmp_path)
        checker = salted.Salted()
        assert checker.check_internal_links is False

    def test_parameter_rule_accepts_boolean_spellings(self):
        assert parameter_rules.validate(
            'check_internal_links', 'yes', 'in test') is True
        assert parameter_rules.validate(
            'check_internal_links', 'off', 'in test') is False

    def test_parameter_rule_rejects_garbage(self):
        with pytest.raises(ValueError, match='check_internal_links'):
            parameter_rules.validate(
                'check_internal_links', 'maybe', 'in test')
