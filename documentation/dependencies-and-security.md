# Dependencies and Security

## Runtime Dependencies

| Package | Purpose |
|---|---|
| [aiohttp](https://docs.aiohttp.org/) | Async HTTP client used to send HEAD/GET requests when checking links |
| [aiodns](https://github.com/saghul/aiodns) | Async DNS resolver, required by aiohttp for non-blocking hostname lookups |
| [beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/) | Parses HTML files to extract hyperlinks from `<a href>` tags |
| [Jinja2](https://jinja.palletsprojects.com/) | Template engine for rendering check results (CLI and Markdown output) |
| [tqdm](https://tqdm.github.io/) | Displays progress bars during link checking |
| [userprovided](https://github.com/RuedigerVoigt/userprovided) | URL normalization and validation to deduplicate links before checking |
| [compatibility](https://github.com/RuedigerVoigt/compatibility) | Checks that the running Python version meets requirements at startup |

SALTED uses Python's built-in `sqlite3` module for the cache — no additional database library is required.

## Optional Dependencies

Neither is installed by `pip install salted`. They differ in kind: one only makes salted faster, the other decides whether a file format can be read at all.

| Package | Extra | Purpose |
|---|---|---|
| [lxml](https://lxml.de/) | `salted[lxml]` | High-performance HTML parsing backend for BeautifulSoup — faster and more lenient with malformed HTML than the built-in `html.parser`. **Has a fallback:** without it salted uses `html.parser` and everything still works. Requires `>=6.1.1` (fixes CVE-2026-41066, needed for Python 3.14 compatibility). |
| [pybtex](https://pybtex.org/) | `salted[bibtex]` | Parses BibTeX files to extract URL and DOI fields. **Has no fallback:** without it a `.bib` file cannot be read at all. |

`pip install "salted[all]"` installs both. Keep the double quotes: zsh (the default shell on macOS) reads the brackets as a filename pattern and aborts before pip runs.

Because `pybtex` is optional, its own dependencies — `latexcodec` and `PyYAML` — are no longer part of a default install either.

### What happens without `pybtex`

A missing BibTeX dependency is never silent, because an unchecked file that is reported as fine would hide dead links in exactly the pipeline meant to catch them:

* A `.bib` file named directly with `-i` stops the run with `MissingOptionalDependencyError`, naming the install command. On the command line this is reported as a plain error message and exit code 1, without a traceback.
* A `.bib` file found while scanning a folder does not abort the run — the other files are still checked — but it is listed in the report's FILE ACCESS ERRORS section and counted as unchecked.
* With `--raise_for_dead_links`, unchecked `.bib` files fail the run even when every URL that *was* checked is fine. This is not special-cased for BibTeX: any file salted could not read fails such a run.

## Dependency Graph

[Dependency Graph](dependency-graph.md)