# Dependencies and Security

## Runtime Dependencies

| Package | Purpose |
|---|---|
| [aiohttp](https://docs.aiohttp.org/) | Async HTTP client used to send HEAD/GET requests when checking links |
| [aiodns](https://github.com/saghul/aiodns) | Async DNS resolver, required by aiohttp for non-blocking hostname lookups |
| [beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/) | Parses HTML files to extract hyperlinks from `<a href>` tags |
| [lxml](https://lxml.de/) | **Optional.** High-performance HTML parsing backend for BeautifulSoup — faster and more lenient with malformed HTML than the built-in `html.parser`. Install with `pip install salted[lxml]`. Falls back to `html.parser` if not available. Requires `>=6.1.0` (fixes CVE-2026-41066, needed for Python 3.14 compatibility). |
| [Jinja2](https://jinja.palletsprojects.com/) | Template engine for rendering check results (CLI and Markdown output) |
| [pybtex](https://pybtex.org/) | Parses BibTeX files to extract URL and DOI fields |
| [tqdm](https://tqdm.github.io/) | Displays progress bars during link checking |
| [userprovided](https://github.com/RuedigerVoigt/userprovided) | URL normalization and validation to deduplicate links before checking |
| [compatibility](https://github.com/RuedigerVoigt/compatibility) | Checks that the running Python version meets requirements at startup |

SALTED uses Python's built-in `sqlite3` module for the cache — no additional database library is required.

## Dependency Graph

[Dependency Graph](dependency-graph.md)