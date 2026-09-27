# Using salted as a Python library

If you want to use `salted` not as a CLI script but as a Python library, a small script is all you need:

```python
import logging
import salted

# This displays all messages of level info or above on your screen.
# You could write the log output to a file.
logging.basicConfig(level=logging.INFO)

# Initializing salted by creating an object
linkcheck = salted.Salted()

# Now you can set parameters to specific values, for example:
linkcheck.timeout = 10

# Files and folders you do not want to scan (a set of paths, each either
# absolute or relative to the current working directory):
linkcheck.exclude_paths = {'path_to_your_files/vendor', 'path_to_your_files/wip.html'}

# Salted assumes all your files are in one folder or subfolders of that.
# Simply call the check function of the instance just created:
linkcheck.check('path_to_your_files/')
```

This starts the check. By default the results will be displayed on the command line interface you are using.

`check()` takes a file or a folder and returns nothing: the result is the report, written to `write_to`. If your program needs the results in machine-readable form, write a custom template that renders them, for example as JSON (see [Style the Output and Write to File](style-salted-output.md)). You can call `check()` several times on the same object; each call starts with fresh results.

## Config file

`salted.Salted()` reads `salted-linkcheck.ini` from the **current working directory** if there is one, just like the command line tool. To read another file, pass its path: `salted.Salted(config_path='path/to/config.ini')`. Attributes you set afterwards override the values from the file.

A config file that salted finds on its own may only point inside its own folder (see [Using a Configuration File](use-a-config-file.md)). That restriction does not apply to attributes you set: your program is trusted input.

## Settings

Every setting is an attribute of the `Salted` object. The config file section is given for reference; the [config file documentation](use-a-config-file.md) describes each setting in detail.

| Attribute | Type | Default | Section | Meaning |
|---|---|---|---|---|
| `file_types` | `str` | `'supported'` | FILES | Which files to check: `'supported'`, `'html'`, `'tex'` (includes BibTeX) or `'markdown'`. |
| `exclude_paths` | `set` of paths | empty | FILES | Files and folders not to scan, absolute or relative to the current working directory. An excluded folder takes everything below it. |
| `num_workers` | `int` or `'automatic'` | `'automatic'` | BEHAVIOR | Number of parallel workers for the URL check (at least 1). |
| `timeout` | `int` | `5` | BEHAVIOR | Seconds to wait for a server (at least 1). |
| `raise_for_dead_links` | `bool` | `False` | BEHAVIOR | Raise `DeadLinksException` for dead links, malformed links or DOIs, and unreadable files. |
| `user_agent` | `str` | `'salted/<version>'` | BEHAVIOR | User-Agent header. `salted.get_user_agent('chrome')` returns a browser preset; `salted.list_presets()` lists them. |
| `domain_delay` | `float` | `0.25` | BEHAVIOR | Minimum seconds between requests to the same domain (`0` disables it). |
| `ignore_urls` | `set` of `str` | empty | BEHAVIOR | URLs that are not checked. |
| `ignore_domains` | `set` of `str` | empty | BEHAVIOR | Host names whose URLs are not checked, such as `'example.com'`. Matching is exact: `example.com` does not match `sub.example.com`. |
| `check_internal_links` | `bool` | `True` | BEHAVIOR | Check relative links and `#fragments` in HTML files against the filesystem. |
| `max_file_size_mb` | `int` | `20` | BEHAVIOR | Larger files are skipped and reported as unreadable (at least 1). |
| `cache_file` | path or `None` | `'salted-cache.sqlite3'` | CACHE | SQLite file that remembers valid URLs between runs. `None` disables the cache. |
| `dont_check_again_within_hours` | `int` | `24` | CACHE | How long a valid URL is not checked again (at least 0). |
| `template_searchpath` | `str` | built-in templates | TEMPLATE | Folder that holds a custom report template. |
| `template_name` | `str` | `'default.cli.jinja'` | TEMPLATE | Template file, ending in `.jinja`. Built in: `default.cli.jinja` and `default.md.jinja`. |
| `write_to` | path | `'cli'` | TEMPLATE | `'cli'` prints the report; anything else is the path of the report file. |
| `base_url` | `str` or `None` | `None` | TEMPLATE | Shows file paths in the report as URLs below this address. Unset, paths are shown relative to the checked folder. |
| `quiet` | `bool` | `False` | — | Suppresses progress messages. The report is still written. |

The folder or file to check is the argument of `check()`. (The `searchpath` attribute and config key are only used by the command line tool.)

**Use the types given above.** Values from a config file or the command line are validated and converted, but attributes are used as you set them. Some mistakes stop the run before any link is checked: an unusable `cache_file`, `template_name` or `write_to`, or `num_workers` below 1. Others are not reported. For example, `file_types = 'htlm'` checks all supported files, the string `raise_for_dead_links = 'no'` counts as true, and an `ignore_domains` entry written as a URL never matches.

## Exceptions

salted's own exceptions are defined in `salted.err`; the plain `ValueError` in the last row is Python's. Except for `DeadLinksException`, all of them are raised before any link is checked.

| Exception | Raised by | When |
|---|---|---|
| `ConfigFileError` | `Salted()` | The config file cannot be read, is not valid INI, has an unknown section or an invalid value, or a file passed as `config_path` does not exist. |
| `ConfigFileError` | `check()` | A config file found in the working directory points outside its own folder. |
| `SearchpathNotFoundError` | `check()` | The file or folder to check does not exist. It is also an `InvalidSettingError` and a `FileNotFoundError`. |
| `InvalidSettingError` | `check()` | A setting cannot work: a single file in an unsupported format, an unusable `cache_file`, a report template that is missing or not valid Jinja2, a `write_to` path in a folder that does not exist, or a custom template named like a built-in one. It is also a `ValueError`. |
| `UnsafeTemplateError` | `check()` | `template_name` does not end in `.jinja`. |
| `MissingOptionalDependencyError` | `check()` | A single `.bib` file was named, but `pybtex` is missing (`pip install "salted[bibtex]"`). A `.bib` file found in a folder is reported as unreadable instead. |
| `DeadLinksException` | `check()` | `raise_for_dead_links` is set and the run found dead or malformed links, malformed DOIs, or unreadable files. The report and the cache are written before it is raised; the message names every reason. |
| `ValueError` | `check()` | `num_workers` is below 1. |

All salted exceptions derive from `salted.err.SaltedException`. A typical CI script:

```python
import sys
import salted
from salted import err

linkcheck = salted.Salted()
linkcheck.raise_for_dead_links = True
linkcheck.write_to = 'linkcheck-report.md'
linkcheck.template_name = 'default.md.jinja'
try:
    linkcheck.check('public/')
except err.DeadLinksException as exc:
    print(f'Link check failed: {exc}')
    sys.exit(1)
except (err.ConfigFileError, err.InvalidSettingError,
        err.UnsafeTemplateError, err.MissingOptionalDependencyError) as exc:
    print(f'Cannot run the link check: {exc}')
    sys.exit(2)
```

## Logging

salted never configures logging itself: that is left to your program. Its messages go to loggers below `salted` (for example `salted.url_check`), so you can adjust them without touching other libraries, e.g. `logging.getLogger('salted').setLevel(logging.DEBUG)`. Until your program configures logging, salted prints no log messages. The report is not affected, as it is not written through logging.
