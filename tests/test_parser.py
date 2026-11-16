#!/usr/bin/python3

"""
Tests for parser module
~~~~~~~~~~~~~~~~~~~~~
Smart, Asynchronous Link Tester with Database backend (SALTED)
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2025: Released under the Apache License 2.0
"""

import time

import pytest

from salted.parser import Parser


class TestHtmlParsing:
    """Test HTML link extraction"""

    def test_extract_links_from_html_with_valid_links(self):
        """Test extracting links from valid HTML"""
        parser = Parser()
        html = '<a href="http://example.com">Example</a><a href="http://test.com">Test</a>'
        links = parser.extract_links_from_html(html)
        assert len(links) == 2
        assert ['http://example.com', 'Example'] in links
        assert ['http://test.com', 'Test'] in links

    def test_extract_links_from_html_without_href(self):
        """Test HTML with anchor tags but no href attribute"""
        parser = Parser()
        html = '<a>No href here</a><a name="anchor">Named anchor</a>'
        links = parser.extract_links_from_html(html)
        # Should skip anchors without href and return empty list
        assert links == []

    def test_extract_links_from_html_empty(self):
        """Test empty HTML"""
        parser = Parser()
        html = '<html><body></body></html>'
        links = parser.extract_links_from_html(html)
        assert links == []

    def test_extract_links_from_html_uppercase_tags(self):
        """Uppercase <A HREF=...> tags (e.g. Chrome bookmark exports) are matched."""
        parser = Parser()
        html = '<A HREF="https://example.com/">link</A>'
        links = parser.extract_links_from_html(html)
        assert links == [['https://example.com/', 'link']]


class TestBaseHref:
    """find_base_href returns what a <base href> sets, if anything."""

    @pytest.mark.parametrize('html', [
        '<html><head></head><body><a href="x.html">x</a></body></html>',
        '<head><base target="_blank"></head>',   # no href: changes no URL
        '<head><base href=""></head>',
        '<head><base href="   "></head>',
        '<p>mentions &lt;base href="/x/"&gt; as text</p>',
    ])
    def test_no_base_href(self, html):
        assert Parser.find_base_href(html) is None

    @pytest.mark.parametrize('html, expected', [
        ('<head><base href="/assets/"></head>', '/assets/'),
        ('<HEAD><BASE HREF=" sub/ "></HEAD>', 'sub/'),
        ('<base href="https://example.com/docs/">', 'https://example.com/docs/'),
        # The first <base> with an href wins (HTML spec).
        ('<base target="_top"><base href="/a/"><base href="/b/">', '/a/'),
    ])
    def test_base_href_found(self, html, expected):
        assert Parser.find_base_href(html) == expected


class TestBibtexParsing:
    """Test BibTeX parsing with missing fields"""

    def test_extract_links_from_bib_with_url_only(self):
        """Test BibTeX entry with URL but no DOI"""
        parser = Parser()
        bib = """
        @article{test2024,
            title = {Test Article},
            author = {Test Author},
            Url = {http://example.com}
        }
        """
        result = parser.extract_links_from_bib(bib)
        url_list, doi_list = result

        assert len(url_list) == 1
        assert url_list[0][0] == 'http://example.com'
        assert 'test2024' in url_list[0][1]
        assert len(doi_list) == 0

    def test_extract_links_from_bib_with_doi_only(self):
        """Test BibTeX entry with DOI but no URL"""
        parser = Parser()
        bib = """
        @article{test2024,
            title = {Test Article},
            author = {Test Author},
            Doi = {10.1234/test}
        }
        """
        result = parser.extract_links_from_bib(bib)
        url_list, doi_list = result

        assert len(url_list) == 0
        assert len(doi_list) == 1
        assert doi_list[0][0] == '10.1234/test'
        assert 'test2024' in doi_list[0][1]

    def test_extract_links_from_bib_without_url_or_doi(self):
        """Test BibTeX entry with neither URL nor DOI (KeyError handling)"""
        parser = Parser()
        bib = """
        @article{test2024,
            title = {Test Article},
            author = {Test Author},
            year = {2024}
        }
        """
        result = parser.extract_links_from_bib(bib)
        url_list, doi_list = result

        # Should handle missing fields gracefully
        assert len(url_list) == 0
        assert len(doi_list) == 0

    def test_extract_links_from_bib_with_both_url_and_doi(self):
        """Test BibTeX entry with both URL and DOI"""
        parser = Parser()
        bib = """
        @article{test2024,
            title = {Test Article},
            Url = {http://example.com},
            Doi = {10.1234/test}
        }
        """
        result = parser.extract_links_from_bib(bib)
        url_list, doi_list = result

        assert len(url_list) == 1
        assert len(doi_list) == 1

    def test_extract_links_from_bib_doi_with_whitespace(self):
        """Test that DOIs are stripped of whitespace"""
        parser = Parser()
        bib = """
        @article{test2024,
            Doi = {  10.1234/test  }
        }
        """
        result = parser.extract_links_from_bib(bib)
        _url_list, doi_list = result

        # DOI should be stripped of whitespace
        assert doi_list[0][0] == '10.1234/test'


class TestMailtoParsing:
    """Test mailto link extraction"""

    def test_extract_mails_from_mailto(self):
        """Test mailto extraction returns the address."""
        parser = Parser()
        result = parser.extract_mails_from_mailto('mailto:test@example.com')
        assert result == ['test@example.com']

    def test_extract_mails_from_mailto_multiple(self):
        """Test mailto with multiple addresses returns all of them."""
        parser = Parser()
        result = parser.extract_mails_from_mailto('mailto:test1@example.com,test2@example.com')
        assert result == ['test1@example.com', 'test2@example.com']


class TestMarkdownParsing:
    """Test Markdown link extraction edge cases"""

    def test_extract_links_from_markdown_mixed_formats(self):
        """Test Markdown with both standard and pointy bracket links"""
        parser = Parser()
        markdown = """
        [Link 1](http://example.com)
        <http://pointy.com>
        [Link 2](http://test.com)
        """
        links = parser.extract_links_from_markdown(markdown)

        assert len(links) == 3
        # Check that both formats are captured
        urls = [link[0] for link in links]
        assert 'http://example.com' in urls
        assert 'http://pointy.com' in urls
        assert 'http://test.com' in urls

    def test_extract_links_from_markdown_url_with_parentheses(self):
        """A URL containing balanced parentheses (e.g. Wikipedia) must not
        be truncated at the first ')'."""
        parser = Parser()
        url = 'https://en.wikipedia.org/wiki/Python_(programming_language)'
        links = parser.extract_links_from_markdown(f'[Py]({url})')

        assert links == [[url, 'Py']]


class TestMarkdownLinkedImages:
    """A linked image (a README badge) holds two URLs; both are checked."""

    def test_badge(self):
        markdown = ('[![Downloads](https://img.example/badge)]'
                    '(https://target.example/project)')
        assert Parser().extract_links_from_markdown(markdown) == [
            ['https://target.example/project',
             '![Downloads](https://img.example/badge)'],
            ['https://img.example/badge', 'Downloads']]

    def test_brackets_in_link_text(self):
        assert Parser().extract_links_from_markdown(
            '[see [1] here](https://t.example/)') == [
                ['https://t.example/', 'see [1] here']]

    def test_brackets_before_a_link(self):
        assert Parser().extract_links_from_markdown(
            '[note] and [link](https://t.example/)') == [
                ['https://t.example/', 'link']]

    def test_unclosed_brackets_are_not_quadratic(self):
        parser = Parser()

        def measure(count: int) -> float:
            payload = ('[a' + '[b]' * 20) * count
            start = time.perf_counter()
            parser.extract_links_from_markdown(payload)
            return time.perf_counter() - start

        measure(100)
        small = measure(2000)
        large = measure(4000)

        assert large < 2, f"parsing took {large:.1f}s"
        assert large < small * 3 + 0.05, (
            f"scaling looks quadratic: {small:.3f}s -> {large:.3f}s")


class TestMarkdownAngleBracketTargets:
    """[text](<url>): the bracketed target of CommonMark and Pandoc.

    It was read with the brackets, so the link counted as unsupported and
    was never checked.
    """

    @pytest.mark.parametrize('markdown, url, text', [
        ('[r](<https://example.com/report.pdf>)',
         'https://example.com/report.pdf', 'r'),
        # Spaces are allowed and percent-encoded, as a renderer does.
        ('[r](<https://example.com/annual report.pdf>)',
         'https://example.com/annual%20report.pdf', 'r'),
        ('[r](<https://example.com/a(b.pdf> "Title")',
         'https://example.com/a(b.pdf', 'r'),
        ('![img](< https://example.com/my pic.png >)',
         'https://example.com/my%20pic.png', 'img'),
    ])
    def test_target_without_brackets(self, markdown, url, text):
        assert Parser().extract_links_from_markdown(markdown) == [[url, text]]

    def test_badge_with_bracketed_targets(self):
        markdown = '[![b](<https://img.example/b a>)](<https://t.example/p q>)'
        assert [link[0] for link in
                Parser().extract_links_from_markdown(markdown)] == [
                    'https://t.example/p%20q', 'https://img.example/b%20a']

    @pytest.mark.parametrize('markdown', [
        '[r](<>)',                                # empty target
        '[r](<https://example.com/\nsplit>)',     # no line break inside
    ])
    def test_no_link(self, markdown):
        assert Parser().extract_links_from_markdown(markdown) == []


class TestMarkdownDestinationDecoding:
    """A destination means what a renderer makes of it, not its spelling.

    '&amp;' and '\\(' were requested as written, which is another URL.
    """

    @pytest.mark.parametrize('markdown, url', [
        ('[a](https://e.example/a?x=1&amp;y=2)', 'https://e.example/a?x=1&y=2'),
        (r'[a](https://e.example/a\(b\))', 'https://e.example/a(b)'),
        # An escaped parenthesis needs no partner and ends nothing.
        (r'[a](https://e.example/a\)b)', 'https://e.example/a)b'),
        (r'[a](https://e.example/x_(a\)b))', 'https://e.example/x_(a)b)'),
        # One pass: the backslash escapes the '&', so no entity is left.
        (r'[a](https://e.example/a\&amp;b)', 'https://e.example/a&amp;b'),
        # Only ASCII punctuation can be escaped; elsewhere '\' is literal.
        (r'[a](https://e.example/a\b)', 'https://e.example/a\\b'),
        (r'[a](https://e.example/a\ ) tail', 'https://e.example/a\\'),
        (r'[a](https://e.example/a\\)', 'https://e.example/a\\'),
        ('[a](https://e.example/&copy;&#65;&#x42;)', 'https://e.example/©AB'),
        # Not a reference: an unknown name, or no closing ';'.
        ('[a](https://e.example/&ampx;&nosuch;&amp)',
         'https://e.example/&ampx;&nosuch;&amp'),
        # No valid code point, and U+0000, become U+FFFD.
        ('[a](https://e.example/&#0;&#x110000;&#xD800;)',
         'https://e.example/���'),
        # Decoded whitespace and control characters are percent-encoded.
        ('[a](https://e.example/a&#32;b&#x1b;&#x9b;&Tab;)',
         'https://e.example/a%20b%1B%C2%9B%09'),
        ('[a](<https://e.example/a b&amp;c\\>d>)',
         'https://e.example/a%20b&c>d'),
        ('[r]: https://e.example/a?x=1&amp;y=2', 'https://e.example/a?x=1&y=2'),
        (r'[r]: https://e.example/a\_b', 'https://e.example/a_b'),
        ('[r]: <https://e.example/a b>', 'https://e.example/a%20b'),
    ])
    def test_destination_is_decoded(self, markdown, url):
        assert [link[0] for link in
                Parser().extract_links_from_markdown(markdown)] == [url]

    @pytest.mark.parametrize('markdown', [
        # The escaped '>' does not close the target, so there is no link
        # target and no definition. What is left is an autolink, in which
        # a backslash is literal.
        r'[a](<https://e.example/a\>)',
        r'[r]: <https://e.example/a\>',
    ])
    def test_escaped_angle_bracket_does_not_close(self, markdown):
        assert Parser().extract_links_from_markdown(markdown) == [
            ['https://e.example/a\\', 'https://e.example/a\\']]

    def test_unclosed_bracket_is_no_definition(self):
        # A plain target cannot start with '<'; it was read as one.
        assert Parser().extract_links_from_markdown(
            '[r]: <https://e.example/a') == []

    @pytest.mark.parametrize('payload', [
        lambda n: '[a](https://e.example/' + '\\(' * n,
        lambda n: '[a](https://e.example/' + '(\\)' * n,
        lambda n: '[a](<https://e.example/' + '\\>' * n,
    ])
    def test_escapes_are_not_quadratic(self, payload):
        parser = Parser()

        def measure(n: int) -> float:
            text = payload(n)
            start = time.perf_counter()
            parser.extract_links_from_markdown(text)
            return time.perf_counter() - start

        measure(1000)
        small = measure(50000)
        large = measure(100000)

        assert large < 2, f"parsing took {large:.1f}s"
        assert large < small * 3 + 0.05, (
            f"scaling looks quadratic: {small:.3f}s -> {large:.3f}s")


class TestMarkdownAutolinks:
    """<...> is a link only in the CommonMark autolink forms."""

    @pytest.mark.parametrize('markdown, expected', [
        ('<https://auto.example/a?b=1>', ['https://auto.example/a?b=1',
                                          'https://auto.example/a?b=1']),
        ('<HTTP://AUTO.EXAMPLE/>', ['HTTP://AUTO.EXAMPLE/',
                                    'HTTP://AUTO.EXAMPLE/']),
        ('<ftp://files.example/x>', ['ftp://files.example/x',
                                     'ftp://files.example/x']),
        ('<user@mail.example>', ['mailto:user@mail.example',
                                 'user@mail.example']),
    ])
    def test_autolink(self, markdown, expected):
        assert Parser().extract_links_from_markdown(markdown) == [expected]

    @pytest.mark.parametrize('markdown', [
        '<br/>', '<a name="intro">', '</div>', '<path>', '<path to folder>',
        '<https://with space.example/>', '<C:\\files\\x>',
        '<span>\nhttps-ish: across\nlines</span>',
        '<x:>',                          # scheme of one character
    ])
    def test_not_an_autolink(self, markdown):
        assert Parser().extract_links_from_markdown(markdown) == []


class TestMarkdownBareUrls:
    """GFM extended autolinks: bare http(s):// and www. links.

    Most cases are the examples of the GFM spec, section 6.9.
    """

    @pytest.mark.parametrize('markdown, url', [
        ('www.commonmark.org', 'http://www.commonmark.org'),
        ('Visit www.commonmark.org/help for more information.',
         'http://www.commonmark.org/help'),
        ('Visit www.commonmark.org.', 'http://www.commonmark.org'),
        ('Visit www.commonmark.org/a.b.', 'http://www.commonmark.org/a.b'),
        ('www.google.com/search?q=Markup+(business)',
         'http://www.google.com/search?q=Markup+(business)'),
        ('www.google.com/search?q=Markup+(business)))',
         'http://www.google.com/search?q=Markup+(business)'),
        ('(www.google.com/search?q=Markup+(business))',
         'http://www.google.com/search?q=Markup+(business)'),
        ('www.google.com/search?q=(business))+ok',
         'http://www.google.com/search?q=(business))+ok'),
        ('www.google.com/search?q=commonmark&hl=en',
         'http://www.google.com/search?q=commonmark&hl=en'),
        ('www.google.com/search?q=commonmark&hl;',
         'http://www.google.com/search?q=commonmark'),
        ('www.commonmark.org/he<lp', 'http://www.commonmark.org/he'),
        ('http://commonmark.org', 'http://commonmark.org'),
        ('(Visit https://encrypted.google.com/search?q=Markup+(business))',
         'https://encrypted.google.com/search?q=Markup+(business)'),
        ('*https://emphasis.example/*', 'https://emphasis.example/'),
        ('Port https://host.example:8080/x, then', 'https://host.example:8080/x'),
        ('WWW.UPPER.EXAMPLE', 'http://WWW.UPPER.EXAMPLE'),
        ('www.x_y.commonmark.org', 'http://www.x_y.commonmark.org'),
    ])
    def test_bare_url(self, markdown, url):
        assert [link[0] for link in
                Parser().extract_links_from_markdown(markdown)] == [url]

    @pytest.mark.parametrize('markdown', [
        'http://localhost:8080/x',        # no period in the domain
        'www.commonmark.org_x',           # underscore in the last segments
        'xhttps://glued.example/',        # not after whitespace or (*_~
        'https://',
        'see `https://code.example/`',
        '<img src="https://attr.example/logo.png">',
    ])
    def test_not_a_bare_url(self, markdown):
        assert Parser().extract_links_from_markdown(markdown) == []

    @pytest.mark.parametrize('markdown', [
        '[text](https://once.example/)',
        '<https://once.example/>',
        '[r]: https://once.example/',
        '<a href="https://once.example/">https://once.example/</a>',
        '[https://once.example/](https://once.example/)',
    ])
    def test_link_syntax_is_not_found_twice(self, markdown):
        assert [link[0] for link in
                Parser().extract_links_from_markdown(markdown)] == [
                    'https://once.example/']

    @pytest.mark.parametrize('tail', [
        lambda n: ')' * n,
        lambda n: '.)' * n,
        lambda n: '&a;' * n,
        lambda n: ('x' * 50 + ';)') * (n // 50),
    ])
    def test_trimming_is_not_quadratic(self, tail):
        parser = Parser()

        def measure(n: int) -> float:
            payload = 'https://trim.example/' + tail(n)
            start = time.perf_counter()
            parser.extract_links_from_markdown(payload)
            return time.perf_counter() - start

        measure(1000)
        small = measure(50000)
        large = measure(100000)

        assert large < 2, f"trimming took {large:.1f}s"
        assert large < small * 3 + 0.05, (
            f"scaling looks quadratic: {small:.3f}s -> {large:.3f}s")

    @pytest.mark.parametrize('markdown, url', [
        ('https://e.example/a&amp;&hl;', 'https://e.example/a'),
        ('https://e.example/x;', 'https://e.example/x;'),   # no '&'
        ('https://e.example/&;', 'https://e.example/&;'),   # empty name
        ('https://e.example/(a)).', 'https://e.example/(a)'),
    ])
    def test_trailing_entities_and_parentheses(self, markdown, url):
        assert [link[0] for link in
                Parser().extract_links_from_markdown(markdown)] == [url]

    def test_link_text_is_the_url_as_written(self):
        assert Parser().extract_links_from_markdown('see www.text.example') == [
            ['http://www.text.example', 'www.text.example']]


class TestMarkdownRawHtml:
    """HTML anchors written into Markdown are links too."""

    def test_anchor_is_extracted(self):
        markdown = ('# Title\n\n<a href="https://html.example/">'
                    '<img src="logo.png"> Logo</a> and [md](https://md.example/)')
        assert Parser().extract_links_from_markdown(markdown) == [
            ['https://md.example/', 'md'],
            ['https://html.example/', ' Logo']]

    def test_uppercase_anchor_across_lines(self):
        markdown = '<A\n  HREF="https://html.example/">x</A>'
        assert Parser().extract_links_from_markdown(markdown) == [
            ['https://html.example/', 'x']]

    @pytest.mark.parametrize('markdown', [
        '<a name="intro"></a>',               # an anchor without href
        '<abbr title="x">X</abbr>',
        '`<a href="https://code.example/">x</a>`',
        '```html\n<a href="https://code.example/">x</a>\n```',
    ])
    def test_no_link(self, markdown):
        assert Parser().extract_links_from_markdown(markdown) == []

    def test_unclosed_anchors_are_not_quadratic(self):
        parser = Parser()

        def measure(count: int) -> float:
            payload = '<a ' * count
            start = time.perf_counter()
            parser.extract_links_from_markdown(payload)
            return time.perf_counter() - start

        measure(1000)
        small = measure(50000)
        large = measure(100000)

        assert large < 2, f"parsing took {large:.1f}s"
        assert large < small * 3 + 0.05, (
            f"scaling looks quadratic: {small:.3f}s -> {large:.3f}s")


class TestMarkdownReferenceLinks:
    """Reference links take their URL from a '[label]: url' definition."""

    @pytest.mark.parametrize('markdown', [
        '[text][r]\n\n[r]: https://ref.example/',
        '[r][]\n\n[r]: https://ref.example/ "Title"',
        '[r]\n\n  [r]: <https://ref.example/>',
        'Used nowhere\n\n[r]:https://ref.example/',
    ])
    def test_definition_is_extracted_once(self, markdown):
        assert Parser().extract_links_from_markdown(markdown) == [
            ['https://ref.example/', 'r']]

    @pytest.mark.parametrize('markdown', [
        '[^1]: A footnote, https://ref.example/',   # footnote
        # 4 spaces start an indented code block. Those are not recognized
        # yet, so the URL is still found - but as a bare URL.
        '    [r]: https://ref.example/',
        'Text [r]: https://ref.example/',    # not at the start of a line
    ])
    def test_not_a_definition(self, markdown):
        # Found as a bare URL (its own link text), not via the label 'r'.
        assert Parser().extract_links_from_markdown(markdown) == [
            ['https://ref.example/', 'https://ref.example/']]

    def test_empty_destination_is_no_link(self):
        assert Parser().extract_links_from_markdown('[r]: <>') == []


class TestMarkdownCode:
    """Links written inside code are examples, not links."""

    @pytest.mark.parametrize('markdown', [
        'Use `[x](https://code.example/)` literally.',
        'Use ``a ` [x](https://code.example/) b`` here.',
        '```\n[x](https://code.example/)\n```',
        '```python\n<https://code.example/>\n```\n',
        '~~~\n[r]: https://code.example/\n~~~',
        # A longer closing fence closes; a shorter one does not.
        '````\n```\n[x](https://code.example/)\n```````\n',
        # An unclosed fence runs to the end of the document.
        'Text\n```\n[x](https://code.example/)\n',
    ])
    def test_code_is_skipped(self, markdown):
        assert Parser().extract_links_from_markdown(markdown) == []

    @pytest.mark.parametrize('markdown', [
        # A stray backtick is literal text, and cannot open a span that
        # swallows the next paragraph.
        'A ` stray backtick.\n\n[x](https://after.example/)',
        'Mismatched `` run` then [x](https://after.example/)',
        '```\ncode\n```\n[x](https://after.example/)',
        '~~~\ncode\n```\n~~~\n[x](https://after.example/)',
        '`a` [x](https://after.example/) `b`',
        '\r\n```\r\ncode\r\n```\r\n[x](https://after.example/)',
    ])
    def test_link_outside_code_is_kept(self, markdown):
        assert Parser().extract_links_from_markdown(markdown) == [
            ['https://after.example/', 'x']]

    @pytest.mark.parametrize('markdown', [
        # An escaped backtick is literal and opens no span.
        r'\` [x](https://after.example/) \`',
        r'\`\` [x](https://after.example/) ``',
        # Inside a span a backslash is literal: `foo\` is the whole span.
        r'`foo\` [x](https://after.example/) `',
        # A backslash inside an earlier span escapes nothing after it.
        r'`a\` `b` [x](https://after.example/)',
    ])
    def test_escaped_backtick_opens_no_span(self, markdown):
        assert Parser().extract_links_from_markdown(markdown) == [
            ['https://after.example/', 'x']]

    @pytest.mark.parametrize('markdown', [
        # An escaped backslash leaves the backtick unescaped.
        r'\\`[x](https://code.example/)`',
        # The escape takes one backtick off the run: '``' opens.
        r'\```[x](https://code.example/)``',
    ])
    def test_escape_that_still_opens_a_span(self, markdown):
        assert Parser().extract_links_from_markdown(markdown) == []

    @pytest.mark.parametrize('payload', [
        # Runs of growing length never find a partner: a lazy regex
        # rescans the paragraph for each of them.
        lambda n: ' '.join('`' * k for k in range(1, n)),
        lambda n: '` ' * (n * n // 4),
        lambda n: '```\n' * (n * n // 8),
        lambda n: '\\` ' * (n * n // 4),
        lambda n: '\\' * (n * n // 4) + '`',
    ])
    def test_crafted_input_is_not_quadratic(self, payload):
        parser = Parser()

        def measure(n: int) -> float:
            text = payload(n)
            start = time.perf_counter()
            parser.extract_links_from_markdown(text)
            return time.perf_counter() - start

        measure(100)
        small = measure(400)
        large = measure(800)   # about 4x the input of small

        assert large < 2, f"parsing took {large:.1f}s"
        # Linear would be ~4x, quadratic ~16x.
        assert large < small * 8 + 0.05, (
            f"scaling looks quadratic: {small:.3f}s -> {large:.3f}s")


class TestMarkdownHtmlComments:
    """A link inside an HTML comment is not rendered, so it is no link."""

    @pytest.mark.parametrize('markdown', [
        '<!-- https://comment.example/gone -->',
        '<!-- [x](https://comment.example/gone) -->',
        '<!--\n[r]: https://comment.example/gone\n-->',
        # A comment block runs across blank lines up to the '-->' line,
        # and that whole line is part of it.
        '<!--\n<https://comment.example/a>\n\n[x](https://comment.example/b)'
        '\n--> https://comment.example/c',
        # Unclosed at the start of a line, it runs to the end, as a fence.
        'Text\n\n<!--\n[x](https://comment.example/gone)\n',
        '   <!-- indented --> https://comment.example/gone',
        'Inline <!-- [x](https://comment.example/gone) --> comment',
        'Across <!-- a line\n[x](https://comment.example/gone) --> break',
    ])
    def test_comment_is_skipped(self, markdown):
        assert Parser().extract_links_from_markdown(markdown) == []

    @pytest.mark.parametrize('markdown', [
        'Inline <!-- note --> [x](https://after.example/)',
        # '<!-->' and '<!--->' are complete comments.
        'a <!--> [x](https://after.example/)',
        'a <!---> [x](https://after.example/)',
        # Unclosed inside a paragraph, '<!--' is literal text.
        'a <!-- unclosed [x](https://after.example/)',
        # An inline comment cannot cross a paragraph.
        'a <!-- open\n\n[x](https://after.example/) -->',
        '\\<!-- escaped [x](https://after.example/) -->',
        # A code span that opens first hides the comment delimiters.
        '`<!--` [x](https://after.example/) `-->`',
        'a `x <!--` [x](https://after.example/) --> b',
        # A comment that opens first hides a backtick.
        'a <!-- ` --> [x](https://after.example/) `',
        # Inside a fence, '<!--' is code and opens no comment.
        '```\n<!--\n```\n[x](https://after.example/)',
        # A comment block hides the fence that would hide the link.
        '<!--\n```\n-->\n[x](https://after.example/)',
        '<!-- one -->\n[x](https://after.example/)',
    ])
    def test_link_outside_comment_is_kept(self, markdown):
        assert Parser().extract_links_from_markdown(markdown) == [
            ['https://after.example/', 'x']]

    @pytest.mark.parametrize('payload', [
        lambda n: 'x <!--' * (n * n // 4),
        lambda n: 'x <!-- -->' * (n * n // 8),
        lambda n: '<!--\n' * (n * n // 8),
    ])
    def test_crafted_input_is_not_quadratic(self, payload):
        parser = Parser()

        def measure(n: int) -> float:
            text = payload(n)
            start = time.perf_counter()
            parser.extract_links_from_markdown(text)
            return time.perf_counter() - start

        measure(100)
        small = measure(400)
        large = measure(800)   # about 4x the input of small

        assert large < 2, f"parsing took {large:.1f}s"
        assert large < small * 8 + 0.05, (
            f"scaling looks quadratic: {small:.3f}s -> {large:.3f}s")


class TestTexParsing:
    """Test TeX link extraction edge cases"""

    def test_extract_links_from_tex_with_optional_href_params(self):
        """Test TeX with optional parameters in href"""
        parser = Parser()
        tex = r"""
        \href[optional]{http://example.com}{Link Text}
        \href{http://test.com}{Another Link}
        """
        links = parser.extract_links_from_tex(tex)

        assert len(links) == 2
        urls = [link[0] for link in links]
        assert 'http://example.com' in urls
        assert 'http://test.com' in urls

    def test_extract_links_from_tex_mixed_commands(self):
        """Test TeX with both url and href commands"""
        parser = Parser()
        tex = r"""
        \url{http://url-example.com}
        \href{http://href-example.com}{Link}
        """
        links = parser.extract_links_from_tex(tex)

        assert len(links) == 2
        urls = [link[0] for link in links]
        assert 'http://url-example.com' in urls
        assert 'http://href-example.com' in urls

    def test_href_optional_argument_does_not_span_the_line(self):
        """The optional [...] argument must not swallow later href commands.

        With a greedy '.*' the optional group ate everything up to the last
        ']' on the line, so the first href here was misparsed.
        """
        parser = Parser()
        tex = r"\href[a]{http://one.example}{One} [x] \href[b]{http://two.example}{Two}"
        links = parser.extract_links_from_tex(tex)

        urls = [link[0] for link in links]
        assert urls == ['http://one.example', 'http://two.example']

    def test_href_optional_argument_length_is_bounded(self):
        """An over-long '[...]' is not treated as the optional argument.

        The bound is what keeps the scan linear, so it is part of the
        contract: past 500 characters the bracket group no longer counts
        as hyperref's optional argument. Real option lists are an order of
        magnitude shorter than this.
        """
        parser = Parser()

        at_limit = "\\href[" + ('x' * 500) + "]{http://example.com}{Text}"
        assert parser.extract_links_from_tex(at_limit) == [
            ['http://example.com', 'Text']]

        over_limit = "\\href[" + ('x' * 501) + "]{http://example.com}{Text}"
        assert parser.extract_links_from_tex(over_limit) == []

    def test_long_urls_are_not_truncated_by_the_optional_argument_bound(self):
        """The length bound must constrain the option list, never the URL.

        URLs can legitimately be long (OAuth2 redirects, presigned S3
        links, map permalinks). They are matched by an unbounded group, so
        neither form of \\href nor \\url may truncate or drop them.
        """
        parser = Parser()
        long_url = 'https://example.com/?token=' + ('a' * 4000)

        assert parser.extract_links_from_tex(
            "\\href{" + long_url + "}{Text}") == [[long_url, 'Text']]
        assert parser.extract_links_from_tex(
            "\\href[page=3]{" + long_url + "}{Text}") == [[long_url, 'Text']]
        assert parser.extract_links_from_tex(
            "\\url{" + long_url + "}") == [[long_url, long_url]]

    def test_realistic_long_urls_survive_extraction(self):
        """Long but standard-conformant URLs are extracted verbatim."""
        parser = Parser()
        urls = [
            # OAuth2 authorization redirect with PKCE and state
            'https://login.example.com/oauth2/authorize?response_type=code'
            '&client_id=' + ('a' * 40) + '&redirect_uri=https%3A%2F%2Fapp.example.com%2Fcb'
            '&scope=read%20write%20profile&state=' + ('b' * 128)
            + '&code_challenge=' + ('c' * 43) + '&code_challenge_method=S256',
            # Presigned S3 object URL
            'https://bucket.s3.eu-central-1.amazonaws.com/path/to/object.pdf'
            '?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=' + ('d' * 60)
            + '&X-Amz-Date=20260725T000000Z&X-Amz-Expires=3600'
            '&X-Amz-SignedHeaders=host&X-Amz-Signature=' + ('e' * 64),
        ]
        for url in urls:
            assert parser.extract_links_from_tex(
                "\\href{" + url + "}{cite}") == [[url, 'cite']], url

    def test_unclosed_href_optional_argument_is_not_quadratic(self):
        """A crafted .tex file must not stall the parser (ReDoS guard).

        '\\href[' without a closing bracket used to make the engine scan
        ahead and backtrack for every occurrence, which is quadratic:
        ~0.6 s at 96 KB and ~73 s at 1 MB, while the default file size
        limit is 20 MB.

        Scaling is asserted rather than raw duration: doubling the input
        must not quadruple the time. That catches a pattern that is still
        quadratic even on a machine slow enough to pass a fixed timeout.
        """
        parser = Parser()

        def measure(count: int) -> float:
            payload = "\\href[" * count
            start = time.perf_counter()
            assert parser.extract_links_from_tex(payload) == []
            return time.perf_counter() - start

        # Warm up so the first call does not carry one-off costs.
        measure(1000)
        small = measure(20000)   # 120 KB
        large = measure(40000)   # 240 KB

        assert large < 2, f"parsing 240 KB took {large:.1f}s"
        # Linear would be ~2x, the old quadratic pattern ~4x. Allow ample
        # headroom for timer noise on loaded CI machines.
        assert large < small * 3 + 0.05, (
            f"scaling looks quadratic: {small:.3f}s -> {large:.3f}s")

    def test_unclosed_href_optional_argument_across_lines(self):
        """The multi-line form of the ReDoS payload must stay cheap too.

        A character class that excludes ']' but not newlines would pass
        the single-line test above while still backtracking across the
        whole file here.
        """
        parser = Parser()
        payload = ("\\href[" + "\n") * 20000

        start = time.perf_counter()
        assert parser.extract_links_from_tex(payload) == []
        duration = time.perf_counter() - start

        assert duration < 2, f"parsing took {duration:.1f}s - pattern may backtrack"
