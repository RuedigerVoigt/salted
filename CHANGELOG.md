# Changelog for salted

## Version 2.0.0 (upcoming)

* Breaking Changes:
  * Drop support for Python 3.10 (EOL October 2026). Supported versions are now Python 3.11 to 3.14.
  * `--raise_for_dead_links` no longer accepts a string argument (`True`/`False`/`yes`/`no`). Use the bare flag `--raise_for_dead_links` to enable and `--no-raise_for_dead_links` to explicitly disable. Default is off (no exception raised). Scripts using `--raise_for_dead_links True` must be updated.
* New features:
  * **Internal links in HTML files are now checked** (closes #1): relative paths (`../about/index.html`), root-relative paths (`/contact.html`), same-directory references, and fragments (`#section`, `page.html#intro`) are resolved against the file's location on disk and verified to exist. Fragment links additionally require a matching `id` attribute (or `<a name>`) in the target HTML document. Broken internal links appear in a new report section and count as dead links for `--raise_for_dead_links`. Disable via `--no-check_internal_links` or `check_internal_links = False` under `[BEHAVIOR]`. Security containment: the checked folder is a strict boundary — a link resolving outside it (path traversal, symlink escape) is never probed on disk and is reported as "not checked" (never as broken, so it cannot fail CI); backslash paths and UNC-style `//host/share` forms are rejected outright to prevent SMB requests on Windows. Internal links in Markdown/TeX sources and `src` attributes remain out of scope.
  * When `base_url` is not set, report output now shows file paths **relative to the checked folder** (e.g. `blog/post.html`) instead of the full absolute filesystem path. Set `base_url` to rewrite paths to URLs as before.
  * Add configurable file size limit (`--max_file_size_mb`, config key `max_file_size_mb` under `[BEHAVIOR]`, default: 20 MB). Files exceeding the limit are skipped and reported as errors, preventing accidental loading of oversized binary or data files that carry a supported extension.
  * Add `--config <path>` CLI argument to load an alternative configuration file instead of the default `salted-linkcheck.ini` in the current working directory.
  * Config file errors now fail loudly with a clear message instead of being silently ignored. A config file that is unreadable (e.g. a permission error) or corrupted (not valid INI) now raises `ConfigFileError`; previously such files were silently skipped and defaults used. An explicitly provided `--config` file that is missing, unreadable, or corrupted stops the CLI with a non-zero exit code. (Unknown config sections now also raise `ConfigFileError` rather than `ValueError`.)
  * Add `-q`/`--quiet` flag to suppress progress messages — useful for CI pipelines where only the final report should appear on stdout
  * Add `--ignore_domains` CLI argument and `ignore_domains` config key (under `[BEHAVIOR]`): comma-separated list of hostnames whose URLs are skipped without checking. Invalid entries are logged as warnings and dropped. Matching is exact (e.g. `example.com` does not match `sub.example.com`).
  * `lxml` is now an optional dependency (`pip install salted[lxml]`). If installed, it is used as the BeautifulSoup HTML parser backend (faster, more lenient with malformed HTML). Falls back to Python's built-in `html.parser` if not available. salted logs which parser is active at startup.
  * Invalid DOIs (CrossRef returns 404) are now stored and shown in reports under a dedicated "INVALID DOIs" section, grouped by source file. A basic preflight format check (`10.NNNN/suffix`) is applied before any API call is made, so obviously malformed entries (typos, broken strings) are flagged immediately without hitting the network. Validated DOIs are cached permanently — `dont_check_again_within_hours` applies to URLs only.
  * BibTeX (`.bib`) support now fully working — URL and DOI fields are extracted and checked; `.bib` files are included under `--file_types tex`
  * Add `--check_dois` / `--no-check_dois` CLI flag and `check_dois` config key (under `[BEHAVIOR]`): set to `False` to skip DOI validation entirely (default: `True`).
  * Add `--mailto` CLI argument and `mailto` config key (under `[BEHAVIOR]`): a contact e-mail address included in the CrossRef API User-Agent to opt into the polite pool (higher rate limits, dedicated infrastructure). Optional but recommended when checking DOIs. A warning is logged if no address is configured.
  * Mailto links are now parsed and listed in the report. Each address is checked for basic format validity (not empty, has email address format), but no DNS lookup or delivery verification is performed. The mailto section only appears in the report when mailto links are actually present.
  * Improved documentation
* Security:
  * Updated dependencies; bumped minimum lxml to 6.1.0 to address CVE-2026-41066 (XXE in `iterparse`/`ETCompatXMLParser`)
  * [Document direct and indirect dependencies](documentation/dependencies-and-security.md)
  * The disk cache now stores only validated URLs and DOIs. Previously the whole in-memory database was copied to `salted-cache.sqlite3`, persisting absolute local file paths, link text, and e-mail addresses that are never read back — a leak if the cache file is shared or committed.
  * Add basic SSRF preflight check: any URL whose host resolves to a loopback address (127.0.0.0/8, ::1, `localhost`), an RFC1918 private range (10.x, 172.16.x, 192.168.x), or a link-local address (169.254.0.0/16 including the cloud-metadata endpoint, fe80::/10, `.local` hostnames) is blocked before a network request is made and logged as an exception in the report. (Requires userprovided ≥ 2.3.0).
  * Enable `autoescape=True` on Jinja2 `Environment` for user-provided templates to prevent XSS (CWE-94); built-in CLI/Markdown templates explicitly set `autoescape=False` as they output plain text
  * Report templates are now rendered in a Jinja2 `SandboxedEnvironment` (CWE-94). A template is loaded from a configurable path, so it can originate in the folder being checked — i.e. from untrusted input. A plain `Environment` lets a template walk the object graph of any variable it receives (`value.__class__.__mro__` → `__subclasses__()`) and reach arbitrary code execution. `autoescape` does not prevent this: it escapes the *result* of an expression, not what the expression is allowed to evaluate.
  * Path settings from an **auto-discovered** config file are now confined to that file's own folder. A `salted-linkcheck.ini` merely found in the working directory can ship with the content being checked, so `template_searchpath`, `write_to`, and `cache_file` may no longer point outside the directory holding it; a value that does stops the run with a `ConfigFileError`. This closes an arbitrary file read (via `template_searchpath` + `template_name`, which rendered any readable file into the report) and an arbitrary file write (via `write_to`) — neither of which the template sandbox addresses, because the loader and the output file are chosen outside the template language. The restriction does not apply to a file named with `--config`, to values given on the command line, or to attributes set through the library API: a project can still ship a config pointing at its own template folder.
  * `template_name` must now end in `.jinja`. Jinja2 renders a file that contains no template syntax as its own content, so any other name turned `template_name` into a file-read primitive that copied an arbitrary readable file (an SSH key, a `.env` file) into the report.
  * The HTTP GET fallback (triggered on 405 Method Not Allowed) follows at most 3 redirects and now validates every redirect target against the SSRF preflight before requesting it. Redirects to private/internal addresses or non-HTTP schemes are blocked and reported in the results; overlong redirect chains are reported as "Too many redirects".
  * Fix a denial-of-service risk in the TeX parser (ReDoS): the optional-argument part of the `\href` pattern used a greedy `.*`, so a `.tex` file containing many `\href[` without a closing bracket forced the regex engine into quadratic backtracking — roughly 0.6 seconds at 96 KB but 73 seconds at 1 MB, while files up to `max_file_size_mb` (20 MB by default) are accepted. A crafted or accidentally malformed document could stall a check for hours. The optional argument is now matched by a length-bounded character class that cannot span lines, which makes the scan linear.
  * DOIs are now percent-encoded before being placed in the CrossRef API URL. Previously a DOI read from a `.bib` file was concatenated onto the query URL raw, so URL-significant characters (`?`, `#`, `&`, spaces) could inject a query string or fragment into the request, and a legitimate DOI containing such a character resolved to the wrong resource (a false "invalid DOI"). The slash separating DOI prefix and suffix is preserved.
* Robustness:
  * The disk cache is now written atomically. Previously the existing cache file was deleted and then rebuilt in place, so an interruption mid-write (crash, error, or power loss) could leave no cache at all. The new cache is built in a sibling temporary file and moved into place with `os.replace`, so any existing cache stays intact on failure.
* Bug Fixes:
  * Fix files with an uppercase extension (`INDEX.HTML`, `Notes.Md`) being skipped and their links never checked: file type matching is now case-insensitive.
  * Fix links with an uppercase scheme (`HTTP://…`, `MAILTO:…`) being discarded as unsupported — schemes are case-insensitive per RFC 3986. Matching the parsed scheme also keeps look-alikes such as `httpfoo://host` out of the queue.
  * Fix Markdown links whose URL contains balanced parentheses (e.g. Wikipedia `..._(programming_language)`) being truncated at the first `)`, which produced false dead-link reports.
  * Fix TeX `\href` links being lost when a line held both an `\href` and a later `[...]` construct. The greedy optional-argument pattern consumed everything up to the last bracket on the line, so the first link on such a line was never extracted and went unchecked. (Same root cause as the ReDoS fix listed under Security.)
  * Fix URLs raising an unexpected exception being dropped from the report; the `validate_url` catch-all now records them via `log_exception`.
  * Fix files with non-UTF-8 encoding (e.g. Latin-1) causing a file access error on Windows — salted now tries UTF-8 first and falls back to Latin-1
  * Fix `--file_types` having no effect on directory scans
  * Fix BibTeX URL and DOI extraction silently failing due to wrong field name casing (`'Url'`/`'Doi'` → `'url'`/`'doi'`)
  * Fix `AttributeError` in `CacheReader.overwrite_cache_file()` when caching is disabled
  * Fix DOI checks using GET instead of HEAD against the CrossRef API
  * Fix a leaked in-memory SQLite connection (`ResourceWarning: unclosed database`) when `check()` exited early or raised (e.g. `DeadLinksException` with `raise_for_dead_links`). The database is now always torn down via `try`/`finally`.
  * Fix CLI integer options `--num_workers`, `--timeout`, and `--dont_check_again_within_hours` silently ignoring an explicit `0` (they used a truthy check). `--dont_check_again_within_hours 0` (force a recheck) is now honored; `--num_workers 0` and `--timeout 0` are rejected with an error instead of being ignored — a timeout of 0 would disable the timeout entirely and let a never-responding server occupy a worker forever. Negative values are also rejected.
  * Fix DOIs being silently dropped from the report when the CrossRef response lacked the `X-Rate-Limit-*` headers. These headers are now read defensively (with a conservative fallback), so a DOI's 200/404 status is always recorded regardless of rate-limit header presence.
  * HTTP 403 (Forbidden) is no longer reported as a dead link. Because 403 is frequently bot/WAF blocking rather than a broken link, it is now logged as an inconclusive exception ("Forbidden (403) - may be bot detection") instead of a hard error, reducing false positives.
  * Fix `base_url` trailing slash not being normalized
  * Fix a config file setting `base_url = None` being read as the literal string `"None"`, which silently rewrote every report path to `None/…`. The literal `"None"` and empty values are now treated as unset. The example `salted-linkcheck.ini` no longer ships `base_url = None`.
  * Fix `num_workers = 0` in a config file hanging salted forever (zero workers, queue never processed). Invalid values (non-numeric, empty, or below 1) now raise `ConfigFileError` at startup; a worker count below 1 set via the library API raises `ValueError`.
  * Fix the URL cache not being saved when `raise_for_dead_links` found dead links: the cache is now written before `DeadLinksException` is raised, so a failing CI run no longer rechecks all URLs on the next attempt.
  * Centralize parameter validation: the same rules now apply whether a value is set on the CLI or in a config file, and error messages name the source. Malformed typed config values (e.g. `timeout = five`) raise `ConfigFileError` instead of a bare traceback. Out-of-range values that previously misbehaved silently are now rejected: negative `timeout` or `dont_check_again_within_hours`, unknown `file_types`, `max_file_size_mb` below 1, and negative `domain_delay`.
* Internal:
  * Replaced flake8 with [ruff](https://docs.astral.sh/ruff/) for linting (config under `[tool.ruff]` in `pyproject.toml`). Keeps the previous coverage (pycodestyle E/W, pyflakes F, mccabe complexity ≤ 10, line length 127) and adds pyupgrade (UP), flake8-bugbear (B), isort (I), flake8-async (ASYNC), and ruff-native (RUF) rules. The CI workflow lints the library only and still hard-fails only on syntax errors and undefined names; everything else is advisory.
  * Modernized all type hints to PEP 604 (`X | Y`) and PEP 585 (`list`/`dict`/`set` builtins), dropping the corresponding `typing.Optional`/`Union`/`List`/`Dict`/`Set` imports. No runtime or API change (Python 3.10+ already required).
  * Removed the unused async variants `UrlCheck.check_urls_async` and `DoiCheck.check_dois_async` — they were never reachable through the documented API.
  * Removed the dead `doi` column from the in-memory `queue` table — it was never written or read (DOIs live in the separate `queue_doi` table).
  * Refactor `command_line.main()` into a parser builder plus table-driven override helpers (no behavior change).
  * De-duplicated the async scaffolding shared by `UrlCheck` and `DoiCheck`: session lifecycle, the worker loop, and work distribution now live in a common base class (`salted/checker_base.py`, `AsyncCheckerBase`); each checker only implements how a single item is checked and how the queue is filled (no behavior change).
  * CI now also tests against the Python 3.15 beta (Linux, Windows, and macOS) as an experimental, allowed-to-fail matrix entry to catch breakage early.

## Version 1.0.1 (2025-11-04)

* Bug Fixes:
  * Fix `python -m salted` not working - module was missing entry point that calls the CLI
  * Fix path handling bug where trailing backslashes in quoted paths (e.g., `"C:\path\"`) caused the closing quote to be included in the path, resulting in FileNotFoundError
  * Check this behavior with new tests.
* Improvements:
  * Add feedback message when cached URLs/DOIs can be skipped to speed up tests (e.g., "Skipped 238 cached URLs (still valid in cache)")

## Version 1.0.0 (2025-11-03)

* Supported Python versions:
  * Drop support for Python 3.8 and 3.9 (EOL).
  * Add support for Python 3.10 to 3.14.
* New features:
  * [Presets for custom user agents](https://github.com/RuedigerVoigt/salted#handling-problematic-servers).
  * [Per-domain rate limiting](https://github.com/RuedigerVoigt/salted#parameters--initializing) - enforces configurable delay between requests to the same domain (default: 250ms). Prevents hammering servers and reduces rate limit errors.
  * React on missing configfile.
* Build system / packaging improvements:
  * Migrate from legacy `setup.py` to modern `pyproject.toml` packaging standard.
  * Migrate pytest configuration from `pytest.ini` to `pyproject.toml`.
  * Switch to [poetry](https://python-poetry.org/).
* Quality:
  * Ensure with an automatic workflow that coverage is 95% or higher.
  * Convert all docstrings to Google style.
* Dependency updates:
  * Update versions of dependencies to ensure compatibility with Python 3.14.
  * Update [userprovided](https://github.com/RuedigerVoigt/userprovided) from 2.0.0 to 2.1.0 (adds `extract_domain()` function).
  * Remove unused `sqlalchemy` dependency - salted uses Python's built-in `sqlite3` module.
* Security:
  * Run pip-audit with every push to the repository and with all pull requests.



## Version 0.7.2 beta (2021-07-22)

* New features:
  * New command line parameter `ignore_urls` (same command in the `BEHAVIOR` section of a configfile). Accepts URLs (in the form of comma separated string), that will not be checked. This is useful as some websites always return an error code if you do not use a browser.

## Version 0.7.1 beta (2021-07-20)

* Bugfix: If called via the CLI without a searchpath, the searchpath now correctly defaults to the current working directory.
* Tests for Python 3.10 now run with Beta 4 instead of Beta 3.

## Version 0.7.0 beta (2021-07-16)

* New features:
  * **Salted can be called within a Python script as a library, or as a standalone script via the command line! Both ways support using a configuration file.**
  * Check a specific file instead of all supported files within a folder.
  * Markdown reports now contain links (instead of bare URLs).
* **BREAKING CHANGES:**
  *  The function `check_links()` has been renamed to `check`  and the parameter `path_to_base_folder` is now named `searchpath`.
  * If a configfile is present, it overwrites the default settings. however, if salted is used standalone via the command line interface (CLI), arguments on the CLI overwrite the corresponding values in a config file.
  * Salted uses head requests as a fast and light query type to check an URL. Some servers do not like head requests. Therefore, salted tried a full request each time a head requests did return an error. This behavior has been tested using a large collection of URLs. In this collection 607 URls answered a head request with an error code. Only in 5 cases a follow up with a full requests yielded a different result. In the face of this insignificant effect, the functionality for doing a second (full) request has been removed.
* New dependencies:
  * Updated versions of multiple dependencies.
  * Added the [`pybtext`](https://pypi.org/project/pybtex/) as a dependency to parse BibTeX files. (next release)
  * Added sqlalchemy as a dependency.
* Improved code tests:
    * Automatic tests now also run with `Python 3.10 beta 3`.
    * Although the code is designed to be platform independent, tests now also run in a MacOS and a Windows container to be sure there are no issues.


## Version 0.6.1 beta (January 22, 2021)

* Log file access errors (like missing permissions) and list them in reports.
* Add time stamp to reports.
* New dependency: [`compatibility`](https://github.com/RuedigerVoigt/compatibility) (`>=0.8.0`) is added. This warns you if you use `salted` with an untested or unsupported version of Python. As a sister project of `salted` development is coordinated.

## Version 0.6.0 beta (January 08, 2021)

* Add basic support for checking links in Markdown and LaTeX (.tex) files:
    * Relative ('local') links are not yet supported in any format.
    * Markdown : The pandoc version as well as GitHub flavored markdown are supported.
    * LaTeX : Salted recognizes `\url{url}` as well as `\href{url}{text}`, but the hyperref option `baseurl` is ignored.
* Add some automatic tests with the pytest framework.

## Version 0.5.4 beta (December 18, 2020)

* Salted sets the HTTP header 'User-Agent' to `salted/<version>`. Users can overwrite this by setting a custom user agent.
* Require lxml version >= 4.6.2 (released 2020-11-26) as it fixes a vulnerability *and* works with Python 3.9.