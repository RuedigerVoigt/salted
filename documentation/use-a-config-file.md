# Using a Configuration File for SALTED

For repeated runs you should create a configuration file.

## Config File Location

By default, salted looks for a file named `salted-linkcheck.ini` in the **current working directory**. If no file is found, salted starts with built-in defaults.

To use a config file in a different location, pass its path with `--config`:

```bash
salted --config /path/to/my-config.ini -i ./docs
```

This is useful when you want to share a single config file across multiple projects, or when running salted from a CI pipeline where the working directory does not contain the config file.

When you pass a config file with `--config`, salted treats any problem with it as a hard error: if the file is missing, cannot be read (for example a permission error), or is corrupted (not valid INI), salted prints a clear message and stops with a non-zero exit code instead of silently falling back to defaults. The same applies to a `salted-linkcheck.ini` found in the working directory if it is corrupted or contains an unknown section — only a *missing* default file is treated as "use defaults". (When used as a library, these conditions raise `salted.err.ConfigFileError`.)

### Auto-discovered config files may only point inside their own folder

A config file that salted simply *finds* in the working directory is not necessarily something you wrote: it can ship with the very content you are checking, for example in a repository you cloned. Such a file is therefore restricted — the path settings `template_searchpath`, `write_to`, and `cache_file` must resolve **inside the folder holding the config file**. A value pointing outside it stops the run with a clear message.

This matters because those settings are powerful. `template_searchpath` combined with `template_name` decides which file is loaded as a template, and Jinja2 renders a file that contains no template syntax as its own content — so an unrestricted value could copy an SSH key or a `.env` file straight into the report. `write_to` and `cache_file` decide where salted writes.

The restriction applies **only** to a config file that was auto-discovered, and only to keys that file actually sets. It does not apply when you:

* name the file yourself with `--config` (you opted into it),
* set the value on the command line (e.g. `--write_to /tmp/report.md`), or
* assign the attribute when using salted as a library.

So a project can still ship a config that points at its own template folder, while a config file you did not write cannot reach the rest of your filesystem.

## Parameters / Initializing

All versions of salted use the same parameters. Their categories are only important for config files.

Values are validated at startup with the same rules regardless of whether they are set on the command line or in a config file. An invalid value in a config file raises a `ConfigFileError` naming the file; on the command line salted exits with a message naming the option.

* **Category "FILES":**
  * `searchpath`: Path to file or folder to check (default: current working directory)
  * `file_types`: Choose which types of files to check. Values can be 'supported' (all formats known to salted), 'html', 'tex', or 'markdown'.
  * `exclude_paths`: accepts a comma-separated list of files and folders that will not be scanned (like `vendor, drafts/wip.html`). An excluded file is never read; an excluded folder is skipped together with everything below it. Entries are literal paths — not glob patterns — and each may be absolute or relative to the directory salted was called from (**not** relative to the `searchpath`). Backslashes are part of the path, so Windows paths can be written as usual (`C:\site\vendor`); wrap a path containing a comma in double quotes. Unlike `template_searchpath`, `write_to` and `cache_file`, this key is *not* restricted to the config file's own folder in an auto-discovered file: an exclusion can only ever reduce what salted reads, never point it at something new.
* **Category "BEHAVIOR":**
  * `num_workers` defaults to automatic, which lets salted choose how many workers to start. You can set a specific number of workers (must be 1 or higher — other values raise a `ConfigFileError`). *This is not depended on the number of cores your system has, but more so dependent on the number of URLs to check!* Once a worker has sent a request it awaits the answer and meanwhile other workers can check other URLs. For example: A machine with 4 cores on a standard home connection should work fine with 32 or more workers.
  * `timeout`: The number of seconds to wait for a server to answer the request. This is necessary as some servers do not answer and a single one of those would block the check. This defaults to 5 seconds and must be at least 1.
  * `raise_for_dead_links`: if set to `True` salted will raise an exception in case it finds obviously dead links that yield a HTTP status code like 404 ('Not found) or 410 ('Gone'). That behavior is useful for a publication workflow. It will *not* raise an exception for links it could not check as some servers block requests. It *does* raise for files that could not be read at all (missing, no permission, over the size limit, or unparseable): their links were never checked, so passing such a run would hide dead links in exactly the pipeline meant to catch them. Those files are listed in the report's FILE ACCESS ERRORS section.
  * `user_agent`: sets the 'User-Agent' field of the HTTP header. This defaults to 'salted/version' if not set. You can use predefined browser presets (`chrome`, `firefox`, `edge`, `safari`, `chrome-mac`, `chrome-linux`) or provide a custom user agent string. Providing a browser user agent might help to avoid being wrongfully blocked.
  * `domain_delay`: minimum delay in seconds between requests to the same domain (default: 0.25). This prevents hammering servers with too many requests. Set to 0 to disable rate limiting. The rate limiter operates at the domain level (e.g., `example.com`), so `www.example.com` and `api.example.com` share the same rate limit.
  * `ignore_urls`: accepts a string with comma separated URLs (like `https://www.example.com/1.html, https://www.example.com/2.html`). Those will not be checked.
  * `ignore_domains`: accepts a comma-separated list of hostnames (like `example.com, skip.org`). All URLs on those domains will not be checked. Matching is exact: `example.com` does not match `sub.example.com`. Full URLs are also accepted and normalized to just the hostname.
  * `check_dois`: set to `False` to skip DOI validation entirely (default: `True`). Useful if you want faster runs without CrossRef API calls.
  * `check_internal_links`: set to `False` to skip checking internal links (default: `True`). When enabled, links in **HTML files** that point to local targets — relative paths (`../about/index.html`), root-relative paths (`/contact.html`), and fragments (`#section`, `page.html#intro`) — are resolved on disk and verified to exist. Fragments must match an `id` attribute (or `<a name>`) in the target HTML file. Root-relative paths are resolved against the checked folder, so run salted on your site root for those to resolve correctly. Security note: the checked folder is a strict boundary — a link that resolves outside it (e.g. via `../../`) is never probed on disk and is listed as "not checked" instead of broken.
  * `mailto`: a contact e-mail address, included in the User-Agent header sent to the CrossRef API. Providing this opts your requests into CrossRef's [polite pool](https://github.com/CrossRef/rest-api-doc), which has higher rate limits and better reliability. It is optional but strongly recommended if you check DOIs. Example: `mailto = you@example.com`. The value must be a single valid address — a mistyped one stops salted with an error rather than being sent to CrossRef, where it would go unrecognized and the run would be rate limited without any visible cause.
  * `max_file_size_mb`: maximum file size in megabytes that salted will read. Files larger than this limit are skipped and logged as errors (default: 20). This prevents accidental loading of very large binary or data files that happen to carry a supported extension.
* **Category "CACHE":**
  * `cache_file`: Path to the cache file. Default is `salted-cache.sqlite3` in the current working directory. The cache records which URLs were already valid, and those are skipped on the next run. Its contents are not verified, so whoever can write the file decides what salted does *not* check. Treat it like a build artefact: keep it out of version control and do not share it across trust boundaries.
  * `dont_check_again_within_hours`: The cache lifetime in full hours for **URLs**. If a URL was valid this number of hours ago, salted assumes it is still valid and will not check it again. This defaults to 24 hours. Note: validated DOIs are cached permanently and are never re-checked — DOIs are persistent identifiers by design.
* **Category "TEMPLATE":**
  * `template_searchpath`: In case you want to use a custom template, this has to be the path to the *folder* in which the template file can be found. In an auto-discovered config file this path must stay inside that file's own folder (see above).
  * `template_name`: The name of the template file, which must end in `.jinja`. Built-In templates are `default.md.jinja` (for markdown output) and `default.cli.jinja` (for text output on the command line). Custom templates are rendered in a Jinja2 sandbox, since a template can come from the folder being checked: expressions that reach into Python internals (`__class__`, `__mro__`, `__subclasses__` and similar) raise a `SecurityError` rather than being evaluated.
  * `write_to`: Default is 'cli' to write to standard out. Alternatively this accepts a file path.
  * `base_url`: The file system path to the checked folder is replaced with this URL in template outputs. So for example if you check the folder `/home/username/homepage/` and in the file `index.html` has a broken link, then the path could be changed to `https://www.example.com/index.html`.