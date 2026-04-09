# Changelog for salted

## Version 2.0.0 (upcoming)

* Breaking Changes:
  * `--raise_for_dead_links` no longer accepts a string argument (`True`/`False`/`yes`/`no`). Use the bare flag `--raise_for_dead_links` to enable and `--no-raise_for_dead_links` to explicitly disable. Default is off (no exception raised). Scripts using `--raise_for_dead_links True` must be updated.
* New features:
  * Add `-q`/`--quiet` flag to suppress progress messages — useful for CI pipelines where only the final report should appear on stdout
  * Add `--ignore_domains` CLI argument and `ignore_domains` config key (under `[BEHAVIOR]`): comma-separated list of hostnames whose URLs are skipped without checking. Invalid entries are logged as warnings and dropped. Matching is exact (e.g. `example.com` does not match `sub.example.com`).
  * Invalid DOIs (CrossRef returns 404) are now stored and shown in reports under a dedicated "INVALID DOIs" section, grouped by source file. A basic preflight format check (`10.NNNN/suffix`) is applied before any API call is made, so obviously malformed entries (typos, broken strings) are flagged immediately without hitting the network. Validated DOIs are cached permanently — `dont_check_again_within_hours` applies to URLs only.
  * BibTeX (`.bib`) support now fully working — URL and DOI fields are extracted and checked; `.bib` files are included under `--file_types tex`
  * Mailto links are now parsed and listed in the report. Each address is checked for basic format validity (not empty, has email address format), but no DNS lookup or delivery verification is performed. The mailto section only appears in the report when mailto links are actually present.
  * Improved documentation
* Security:
  * Updated dependencies
  * [Document direct and indirect dependencies](documentation/dependencies-and-security.md)
  * Add basic SSRF preflight check: any URL whose host resolves to a loopback address (127.0.0.0/8, ::1, `localhost`), an RFC1918 private range (10.x, 172.16.x, 192.168.x), or a link-local address (169.254.0.0/16 including the cloud-metadata endpoint, fe80::/10, `.local` hostnames) is blocked before a network request is made and logged as an exception in the report. (Requires userprovided ≥ 2.3.0).
  * Enable `autoescape=True` on Jinja2 `Environment` for user-provided templates to prevent XSS (CWE-94); built-in CLI/Markdown templates explicitly set `autoescape=False` as they output plain text
* Bug Fixes:
  * Fix files with non-UTF-8 encoding (e.g. Latin-1) causing a file access error on Windows — salted now tries UTF-8 first and falls back to Latin-1
  * Fix `--file_types` having no effect on directory scans
  * Fix BibTeX URL and DOI extraction silently failing due to wrong field name casing (`'Url'`/`'Doi'` → `'url'`/`'doi'`)
  * Fix `AttributeError` in `CacheReader.overwrite_cache_file()` when caching is disabled
  * Fix DOI checks using GET instead of HEAD against the CrossRef API
  * Fix `base_url` trailing slash not being normalized

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