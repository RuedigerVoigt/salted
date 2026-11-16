#!/usr/bin/python3

"""
Input Parser for salted
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026 Rüdiger Voigt and contributors
Released under the Apache License 2.0
"""

import html.entities
import logging
import re
import urllib.parse
from typing import Final

from bs4 import BeautifulSoup  # type: ignore

from salted import err

logger = logging.getLogger(__name__)

# Detected silently: logging at import time would run logging.basicConfig()
# on the root logger of a program that imports salted, so its own later
# basicConfig() call would do nothing. log_html_backend() reports the result
# once a check starts.
try:
    import lxml  # type: ignore[import-untyped]
    _BS_PARSER = 'lxml'
except ImportError:
    _BS_PARSER = 'html.parser'


def log_html_backend() -> None:
    """Log which HTML parser backend BeautifulSoup uses.

    Info level, not warning: lxml is only an optimization, and html.parser
    handles every file correctly.
    """
    if _BS_PARSER == 'lxml':
        logger.info("lxml %s available — using it as HTML parser backend.",
                    lxml.__version__)
    else:
        logger.info('lxml not installed — using html.parser. Install '
                    '"salted[lxml]" for faster HTML parsing.')

# BibTeX support is optional. Unlike lxml - which only swaps the HTML
# backend for a faster one - pybtex has no fallback: without it a .bib
# file cannot be read at all. So this import stays silent. Warning here
# would nag the majority who never check a .bib file, while the ones who
# do are told at the point where such a file is actually encountered.
try:
    from pybtex.database import parse_string  # type: ignore
    PYBTEX_AVAILABLE = True
except ImportError:
    PYBTEX_AVAILABLE = False

# The message is defined once: the run aborts with it when a .bib file
# was named explicitly, and it is written into the report when one was
# merely found while scanning a folder.
MISSING_PYBTEX_MSG: Final[str] = (
    'BibTeX support requires the optional dependency pybtex, which is not '
    'installed. Install it with: pip install "salted[bibtex]"')
# The quotes are part of the command, not decoration: zsh (the default
# shell on macOS) treats the brackets as a filename pattern and aborts
# with 'no matches found' before pip runs. Double quotes work in every
# shell, single quotes would break the Windows command prompt.
# a future version of pybtex might get type hints, see:
# https://bitbucket.org/pybtex-devs/pybtex/issues/141/type-annotations

# Markdown code and HTML comments: a link written inside code is an
# example, not a link, and one inside a comment is not rendered at all.
# Fences follow CommonMark: up to three spaces of indentation, at least
# three backticks or tildes; a backtick fence's info string cannot contain
# a backtick. The closing fence uses the same character and is at least as
# long.
_MD_FENCE_OPEN: Final = re.compile(r' {0,3}(?P<fence>`{3,}(?=[^`]*$)|~{3,})')
_MD_FENCE_CLOSE: Final = re.compile(r' {0,3}(?P<fence>`{3,}|~{3,})[ \t]*$')
# A line starting with '<!--' opens an HTML block (CommonMark type 2) that
# ends with the line containing '-->'. Every line of it is raw HTML.
_MD_COMMENT_BLOCK: Final = re.compile(r' {0,3}<!--')
_MD_BLANK_LINE: Final = re.compile(r'(\n[ \t]*\n)')
# Inline: a run of backticks (a code span delimiter) or a comment opener.
_MD_INLINE_TOKEN: Final = re.compile(r'`+|<!--')


def _strip_code_and_comment_blocks(text: str) -> str:
    """Blank out fenced code blocks and HTML comment blocks.

    The line structure is kept. A line-by-line scan rather than one regex:
    it is linear for every input, including an unclosed fence or comment,
    which runs to the end of the document, as it does in a renderer.
    Whichever block starts first wins: a fence inside a comment is part of
    the comment, and '<!--' inside a fence is code.
    """
    out = []
    fence = ''
    comment = False
    for line in text.splitlines(keepends=True):
        bare = line.rstrip('\r\n')
        if comment:
            comment = '-->' not in bare
        elif fence:
            closing = _MD_FENCE_CLOSE.match(bare)
            if (closing is not None and closing['fence'][0] == fence[0]
                    and len(closing['fence']) >= len(fence)):
                fence = ''
        elif (opening := _MD_FENCE_OPEN.match(bare)) is not None:
            fence = opening['fence']
        elif _MD_COMMENT_BLOCK.match(bare):
            # '<!-->' and '<!--->' are complete comments, and contain '-->'.
            comment = '-->' not in bare
        else:
            out.append(line)
            continue
        out.append('\n')
    return ''.join(out)


def _is_escaped(text: str, position: int, floor: int) -> bool:
    """Tell whether the character at position follows a backslash escape.

    An odd number of backslashes escapes it, an even number are escaped
    backslashes. Backslashes before floor belong to a span already closed,
    in which a backslash is literal, so they do not count.
    """
    count = 0
    while position - count > floor and text[position - count - 1] == '\\':
        count += 1
    return count % 2 == 1


def _comment_end(paragraph: str, position: int) -> int | None:
    """Return where an inline HTML comment opened at position ends.

    CommonMark: '<!-->', '<!--->', or '<!--' up to the next '-->'. Without
    a '-->' the opener is literal text.
    """
    after = position + 4
    if paragraph.startswith('>', after):
        return after + 1
    if paragraph.startswith('->', after):
        return after + 2
    close = paragraph.find('-->', after)
    return None if close == -1 else close + 3


def _strip_inline_code_and_comments(paragraph: str) -> str:
    """Blank out `code spans` and <!-- comments --> within one paragraph.

    A span opens with a run of backticks and closes with the next run of the
    same length; a run without a partner is literal text. A backslash
    escapes the first backtick of an opening run, as it escapes a '<!--'.
    Inside a span a backslash is literal, so a closing run is never
    escaped. Whichever of a span and a comment opens first wins and hides
    the delimiters of the other.

    Pairing the runs by length keeps this linear - a lazy regex would
    rescan the paragraph for every unmatched run, quadratic on a crafted
    file. So does the comment search: once a '-->' is missing, it is missing
    for every later opener as well.
    """
    tokens = [(m.start(), m.end())
              for m in _MD_INLINE_TOKEN.finditer(paragraph)]
    closers = _closing_runs(paragraph, tokens)
    spans = []
    covered = 0
    comments_can_close = True
    for index, (start, end) in enumerate(tokens):
        if start < covered:
            continue                  # inside a span or comment
        escaped = _is_escaped(paragraph, start, covered)
        if paragraph[start] == '<':
            if escaped or not comments_can_close:
                continue
            close = _comment_end(paragraph, start)
            comments_can_close = close is not None
        else:
            start += escaped          # an escaped backtick is literal
            close = _code_span_end(tokens, closers, index, end - start)
        if close is not None:
            spans.append((start, close))
            covered = close
    return _blank_spans(paragraph, spans)


def _closing_runs(paragraph: str, tokens: list) -> dict[int, list[int]]:
    """Map each length to a stack of the backtick runs that could close.

    The stacks hold indices into tokens, with the smallest on top.
    """
    closers: dict[int, list[int]] = {}
    for index in range(len(tokens) - 1, -1, -1):
        start, end = tokens[index]
        if paragraph[start] == '`':
            closers.setdefault(end - start, []).append(index)
    return closers


def _code_span_end(tokens: list,
                   closers: dict[int, list[int]],
                   index: int,
                   length: int) -> int | None:
    """Return where the span opened by the run at index ends, if it closes.

    The span closes with the next run of the same length. An escaped run
    one backtick long has the length 0 and opens nothing.
    """
    candidates = closers.get(length, [])
    # Drop this run and any earlier one: each index is popped once.
    while candidates and candidates[-1] <= index:
        candidates.pop()
    return tokens[candidates.pop()][1] if candidates else None


def _blank_spans(paragraph: str, spans: list) -> str:
    """Replace each (start, end) span of the paragraph with a blank."""
    if not spans:
        return paragraph
    pieces = []
    position = 0
    for start, end in spans:
        pieces.append(paragraph[position:start])
        pieces.append(' ')
        position = end
    pieces.append(paragraph[position:])
    return ''.join(pieces)


# GFM extended autolinks: a bare http(s):// or www. link, at the start of a
# line or after whitespace, '*', '_', '~' or '('. It ends at whitespace or
# '<'. Inside an HTML attribute (href="https://...") it follows a quote, so
# it is not one.
_GFM_AUTOLINK: Final = re.compile(
    r"(?<![^\s*_~(])(?P<url>(?:https?://|www\.)[^\s<]*)", flags=re.IGNORECASE)
# A valid domain: segments of letters, digits, '_' and '-' with at least one
# period. The last two segments have no underscore.
_GFM_DOMAIN: Final = re.compile(r"[\w-]+(?:\.[\w-]+)+")


def gfm_autolink(candidate: str) -> str | None:
    """Trim a bare URL as GFM does, or return None if it is not a link.

    Trailing punctuation (?!.,:*_~) is not part of the link, nor is a closing
    parenthesis without an opening one, nor an entity reference (&hl;) at
    the end. The link needs a valid domain: 'http://localhost' is no link.

    Args:
        candidate: Text matched by _GFM_AUTOLINK.

    Returns:
        The link as written, trimmed, or None.
    """
    # Works on an end index with running counts: re-slicing and re-counting
    # for each character would be quadratic on a crafted 'x/)))))...'.
    end = len(candidate)
    unmatched = candidate.count(')') - candidate.count('(')
    while True:
        before = end
        while end and candidate[end - 1] in '?!.,:*_~':
            end -= 1
        if end and candidate[end - 1] == ')' and unmatched > 0:
            end -= 1
            unmatched -= 1
        elif end and candidate[end - 1] == ';':
            start = end - 1
            while start and candidate[start - 1].isascii() \
                    and candidate[start - 1].isalnum():
                start -= 1
            if start and start < end - 1 and candidate[start - 1] == '&':
                end = start - 1          # drop an entity such as '&hl;'
        if end == before:
            break
    url = candidate[:end]
    rest = url.split('://', 1)[1] if '://' in url else url
    domain = _GFM_DOMAIN.match(rest)
    if domain is None or '_' in ''.join(domain[0].split('.')[-2:]):
        return None
    return url


def _bare_urls(text: str) -> list:
    """Return the GFM extended autolinks in text as [url, linktext] pairs.

    A www. link is checked as http://www...., as GFM renders it.
    """
    links = []
    for match in _GFM_AUTOLINK.finditer(text):
        url = gfm_autolink(match['url'])
        if url is not None:
            links.append([f'http://{url}' if url[:4].lower() == 'www.'
                          else url, url])
    return links


# In a link destination, CommonMark turns a backslash before ASCII
# punctuation into that character and decodes entity and numeric character
# references. Both in one pass from left to right: in '\&amp;' the
# backslash escapes the '&', so the result is '&amp;', not '&'.
_MD_ESCAPE_OR_REFERENCE: Final = re.compile(
    r'\\(?P<escaped>[!-/:-@\[-`{-~])'
    r'|(?P<reference>&(?:#[xX][0-9a-fA-F]{1,6}|#[0-9]{1,7}'
    r'|[A-Za-z][A-Za-z0-9]{1,31});)')
# Whitespace and control characters, which a decoded reference can produce.
_MD_UNSAFE_IN_URL: Final = re.compile(r'[\x00-\x20\x7f-\x9f]')


def _decode_reference(reference: str) -> str:
    """Decode a character reference such as '&amp;' or '&#x41;'.

    CommonMark: a numeric reference that is no valid code point, and
    U+0000, become U+FFFD. A name that HTML does not define stays as it is.
    Only names with the closing ';' are looked up: html.unescape would
    also decode the 'amp' in '&ampx;', which CommonMark leaves alone.
    """
    if reference[1] != '#':
        return html.entities.html5.get(reference[1:], reference)
    digits = reference[2:-1]
    code = int(digits[1:], 16) if digits[0] in 'xX' else int(digits)
    if code == 0 or code > 0x10FFFF or 0xD800 <= code <= 0xDFFF:
        return '\ufffd'
    return chr(code)


def markdown_destination(raw: str) -> str:
    """Return the URL a Markdown link destination stands for.

    Backslash escapes and character references are decoded, as a renderer
    does: '[x](https://e.example/a\\(b\\))' points to '/a(b)', and '&amp;'
    in a query is an '&'. Whitespace and control characters, a space in
    '<...>' or a decoded '&#32;', are then percent-encoded, as the renderer
    does when it writes the href: that is what a browser requests.

    Args:
        raw: The destination as written, without its angle brackets.

    Returns:
        The URL to check.
    """
    decoded = _MD_ESCAPE_OR_REFERENCE.sub(
        lambda m: m['escaped'] or _decode_reference(m['reference']), raw)
    return _MD_UNSAFE_IN_URL.sub(
        lambda m: ''.join(f'%{byte:02X}' for byte in m[0].encode('utf-8')),
        decoded)


def _inline_target(match: re.Match) -> str:
    """Return the URL of an inline link, from either form of its target."""
    if match['pointy'] is None:
        return markdown_destination(match['url'])
    return markdown_destination(match['pointy'].strip())


def strip_markdown_code_and_comments(text: str) -> str:
    """Remove code and HTML comments from Markdown.

    Removes fenced code blocks, inline code spans and HTML comments: none
    of them renders as a link. Indented code blocks are left alone: telling
    them from an indented list continuation needs a full Markdown parser.

    Args:
        text: Markdown file content.

    Returns:
        The text with code and comments replaced by blanks.
    """
    text = _strip_code_and_comment_blocks(text)
    # A code span or inline comment cannot cross a paragraph, so a stray
    # backtick cannot eat the links of the following paragraphs.
    parts = _MD_BLANK_LINE.split(text)
    return ''.join(part if index % 2 else _strip_inline_code_and_comments(part)
                   for index, part in enumerate(parts))


class Parser:
    """Methods to extract hyperlinks and mail addresses from different formats."""

    def __init__(self) -> None:
        """Compile regex patterns for URL extraction from all supported formats."""
        # Specification: https://www.ctan.org/pkg/hyperref
        self.pattern_latex_url = re.compile(
            r"\\url\{(?P<url>[^{]*?)\}",
            flags=re.MULTILINE | re.IGNORECASE)
        # The optional argument is deliberately matched by a *bounded*
        # character class rather than '.*'. Two reasons:
        #   Performance: with '.*' every '\href[' that has no closing
        #   bracket makes the engine scan ahead and backtrack, which is
        #   quadratic in the line length — a crafted .tex file well within
        #   max_file_size_mb could stall a run for hours. An unbounded
        #   class such as '[^]]*' does not help here; only the length
        #   bound makes each attempt constant work and the scan linear.
        #   Correctness: '.*' is greedy, so a line holding an href plus a
        #   later '[...]' swallowed everything up to the last bracket and
        #   the first link was lost.
        # Excluding newlines keeps the argument on one line, as '.' did.
        # The limit applies to the *optional argument only* — the URL and
        # the link text are matched by unbounded groups, so URLs of any
        # length are still extracted in full. Even a stacked option list
        # ("page=42,pdfremotestartview=FitBH,pdfnewwindow=true,...") stays
        # under 150 characters, so 500 is ample headroom; an \href whose
        # optional argument exceeded it would be skipped, and a skipped
        # link is an unchecked link. The headroom is free: on documents
        # that are not the pathological unclosed-bracket case the bound
        # never comes into play (measured: no difference at 20 MB).
        # The group stays capturing — extract_links_from_tex() reads the
        # url and linktext as match[1] and match[2].
        self.pattern_latex_href = re.compile(
            r"\\href(\[[^]\r\n]{0,500}\]){0,1}\{(?P<url>[^}]*)\}\{(?P<linktext>[^}]*?)\}",
            flags=re.MULTILINE | re.IGNORECASE)

        # Specs:
        # https://pandoc.org/MANUAL.html
        # https://daringfireball.net/projects/markdown/syntax
        # https://github.github.com/gfm/
        # The url group allows balanced parentheses so links such as
        # Wikipedia's `..._(programming_language)` are not truncated at the
        # first ')'. It still stops at whitespace (a following "title") or
        # the link's closing ')'.
        # The link text may hold one level of balanced brackets, which is
        # what an image inside a link needs: [![badge](img)](target). With
        # '[^\[]*' the match began at the image's '[' and swallowed it, so
        # the image's URL was never checked.
        # The target is either plain or in angle brackets: [t](<url>). The
        # bracketed form (CommonMark, Pandoc) may hold spaces and unbalanced
        # parentheses, but no line break and no unescaped '<' or '>'. A plain
        # target cannot start with '<', so a broken bracketed one is no link.
        # A backslash escapes the character after it: '\)' and '\>' do not
        # end the target, and an escaped parenthesis needs no partner. Each
        # alternative starts with a different character, which keeps the
        # match free of backtracking; a backslash before whitespace or the
        # end is literal.
        self.pattern_md_link = re.compile(
            r"\[(?P<linktext>[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*)\]"
            r"\((?:<(?P<pointy>(?:[^<>\n\\]|\\[^\n])*)>"
            r"|(?!<)(?P<url>(?:[^\s()\\]|\\\S|\\(?!\S)"
            r"|\((?:[^\s()\\]|\\\S)*\))*))"
            r"[\s\)]+",
            flags=re.MULTILINE | re.IGNORECASE)
        # Autolinks as CommonMark defines them: <scheme:...> with a scheme of
        # 2-32 characters and no space, control character or angle bracket,
        # or <user@example.com>, which renders as a mailto: link. Anything
        # else in angle brackets is HTML (<br/>, <a name="x">) or a
        # placeholder (<path>), and is not a link.
        self.pattern_md_link_pointy = re.compile(
            r"<(?:(?P<url>[A-Za-z][A-Za-z0-9+.\-]{1,31}:[^\x00-\x20<>]*)"
            r"|(?P<email>[A-Za-z0-9.!#$%&'*+/=?^_`{|}~\-]+@[A-Za-z0-9]"
            r"(?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?"
            r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?)*))>")
        # Opening tag of an HTML anchor written in Markdown. Bounded, so an
        # unclosed '<a ' cannot make the scan rescan the rest of the file.
        self.pattern_html_anchor = re.compile(r"<a\s[^<>]{0,4096}>",
                                              flags=re.IGNORECASE)
        # Reference links ([text][label], [label][], [label]) take their URL
        # from a definition line '[label]: url "title"', so extracting the
        # definitions finds every reference link, however it is used.
        # '[^1]: ...' defines a footnote (Pandoc, GFM), not a link. A label
        # has at most 999 characters (CommonMark), which also keeps the
        # pattern linear.
        self.pattern_md_reference = re.compile(
            r"^ {0,3}\[(?!\^)(?P<label>[^\]\n]{1,999})\]:[ \t]*"
            r"(?:<(?P<pointy>(?:[^>\n\\]|\\[^\n])*)>|(?P<url>\S+))",
            flags=re.MULTILINE)

    @staticmethod
    def extract_links_from_html(file_content: str) -> list:
        """Extract all links from a HTML file.

        Args:
            file_content: HTML file content as a string.

        Returns:
            List of [url, linktext] pairs extracted from anchor tags.
        """
        matches = []
        soup = BeautifulSoup(file_content, _BS_PARSER)
        for link in soup.find_all('a'):
            href = link.get('href')
            if href:
                matches.append([href, link.text])
        return matches

    @staticmethod
    def find_base_href(file_content: str) -> str | None:
        """Return the href of a HTML document's <base> element, if any.

        A <base href> changes what every relative link and every #fragment
        in the document points to. Only the first <base> with an href counts
        (HTML spec); one without an href, or with an empty one, changes
        nothing.

        Args:
            file_content: HTML file content as a string.

        Returns:
            The stripped href, or None if the document sets none.
        """
        # Cheap pre-check: most documents have no <base>, and parsing every
        # file a second time would cost noticeable time on large sites.
        if '<base' not in file_content.lower():
            return None
        tag = BeautifulSoup(file_content, _BS_PARSER).find('base', href=True)
        if tag is None:
            return None
        return str(tag['href']).strip() or None

    def extract_links_from_markdown(self,
                                    file_content: str) -> list:
        """Extract all links from a Markdown file.

        Supports inline links and images ([text](url)), reference link
        definitions ([label]: url) and <url> syntax. Links in fenced code
        blocks, in `code spans` and in HTML comments are left out.

        Args:
            file_content: Markdown file content as a string.

        Returns:
            List of [url, linktext] pairs extracted from the markdown.
        """
        matches: list = []

        def take(pattern: re.Pattern, text: str, build) -> str:
            """Collect pattern's links and blank them out of text.

            Blanking stops a later pattern from finding the same link
            again, as '[r]: <url>' would match the <url> syntax too.
            """
            def collect(match: re.Match) -> str:
                for link in build(match):
                    if link[0]:
                        matches.append(link)
                return ' '
            return pattern.sub(collect, text)

        def inline(match: re.Match) -> list:
            """The link, then any image inside its text: [![x](img)](url)."""
            nested = [[_inline_target(inner), inner['linktext']] for inner in
                      self.pattern_md_link.finditer(match['linktext'])]
            return [[_inline_target(match), match['linktext']], *nested]

        text = strip_markdown_code_and_comments(file_content)
        text = take(self.pattern_md_link, text, inline)
        text = take(self.pattern_md_reference, text,
                    lambda m: [[markdown_destination(
                        m['url'] if m['url'] is not None
                        else m['pointy']), m['label']]])
        text = take(self.pattern_md_link_pointy, text,
                    lambda m: [[m['url'], m['url']] if m['url'] is not None
                               else [f"mailto:{m['email']}", m['email']]])
        # Markdown allows raw HTML, and READMEs use it for links (often
        # around an image). Parsed only if the text has an <a at all.
        if self.pattern_html_anchor.search(text):
            matches.extend(self.extract_links_from_html(text))
        # Last: every link syntax above is blanked out by now, so a bare
        # URL found here is not one of them found a second time.
        matches.extend(_bare_urls(text))
        return matches

    def extract_links_from_tex(self,
                               file_content: str) -> list:
        """Extract all links from a TeX file.

        Supports \\url{url} and \\href{url}{text} commands.

        Args:
            file_content: TeX file content as a string.

        Returns:
            List of [url, linktext] pairs extracted from hyperref commands.
        """
        matches = []
        # extract class \href{url}{text} links
        href_in_file = re.findall(self.pattern_latex_href, file_content)
        for match in href_in_file:
            # The RegEx returns the optional element as first element.
            # (Empty, but still in the return if it is not in the string.)
            matches.append([match[1], match[2]])
        # extract \url{url} links
        url_in_file = re.findall(self.pattern_latex_url, file_content)
        for url in url_in_file:
            matches.append([url, url])
        return matches

    @staticmethod
    def extract_links_from_bib(file_content: str) -> list:
        """Extract all URLs and DOIs from a BibTeX file.

        Args:
            file_content: BibTeX file content as a string.

        Returns:
            List containing two lists:
                - First list: [[url, text], [url, text]] where text is the
                  bibtex entry key and field name.
                - Second list: [[doi, text], [doi, text]] where text is the
                  bibtex entry key and field name.

        Raises:
            err.MissingOptionalDependencyError: If pybtex is not installed.
        """
        if not PYBTEX_AVAILABLE:
            raise err.MissingOptionalDependencyError(MISSING_PYBTEX_MSG)
        url_list = []
        doi_list = []
        bib_data = parse_string(file_content, bib_format='bibtex')
        for entry in bib_data.entries:
            # Neither the URL, nor the DOI field is required by BiBTeX.
            # pybtex throws a KeyError if the field does not exist.
            try:
                url = bib_data.entries[entry].fields['url']
                url_list.append([url, f"Key: {entry}, Field: url"])
            except KeyError:
                pass

            try:
                doi = bib_data.entries[entry].fields['doi']
                doi_list.append([doi.strip(), f"Key: {entry}, Field: doi"])
            except KeyError:
                pass

        return [url_list, doi_list]

    @staticmethod
    def extract_mails_from_mailto(mailto_link: str) -> list:
        """Extract mail addresses from a mailto link.

        A single mailto link can contain multiple mail addresses in the
        path component (the ``to`` field), separated by commas.
        Query parameters (subject, cc, bcc, …) are intentionally ignored.

        Args:
            mailto_link: The mailto URL string to parse.

        Returns:
            List of raw address strings found in the ``to`` field.
            Empty list if the link is empty or cannot be parsed.
        """
        try:
            parsed = urllib.parse.urlparse(mailto_link)
            to_part = urllib.parse.unquote(parsed.path)
            if not to_part:
                return []
            return [addr.strip() for addr in to_part.split(',') if addr.strip()]
        except Exception:
            return []
