# Using a Configuration File for SALTED

For repeated runs you should create a configuration file.

## Parameters / Initializing

All versions of salted use the same parameters. Their categories are only important for config files:

* **Category "FILES":**
  * `searchpath`: Path to file or folder to check (default: current working directory)
  * `file_types`: Choose which types of files to check. Values can be 'supported' (all formats known to salted), 'html', 'tex', or 'markdown'.
* **Category "BEHAVIOR":**
  * `num_workers` defaults to automatic, which lets salted choose how many workers to start. You can set a specific number of workers. *This is not depended on the number of cores your system has, but more so dependent on the number of URLs to check!* Once a worker has sent a request it awaits the answer and meanwhile other workers can check other URLs. For example: A machine with 4 cores on a standard home connection should work fine with 32 or more workers.
  * `timeout`: The number of seconds to wait for a server to answer the request. This is necessary as some servers do not answer and a single one of those would block the check. This defaults to 5 seconds.
  * `raise_for_dead_links`: if set to `True` salted will raise an exception in case it finds obviously dead links that yield a HTTP status code like 404 ('Not found) or 410 ('Gone'). That behavior is useful for a publication workflow. It will *not* raise an exception for links it could not check as some servers block requests.
  * `user_agent`: sets the 'User-Agent' field of the HTTP header. This defaults to 'salted/version' if not set. You can use predefined browser presets (`chrome`, `firefox`, `edge`, `safari`, `chrome-mac`, `chrome-linux`) or provide a custom user agent string. Providing a browser user agent might help to avoid being wrongfully blocked.
  * `domain_delay`: minimum delay in seconds between requests to the same domain (default: 0.25). This prevents hammering servers with too many requests. Set to 0 to disable rate limiting. The rate limiter operates at the domain level (e.g., `example.com`), so `www.example.com` and `api.example.com` share the same rate limit.
  * `ignore_urls`: accepts a string with comma separated URLs (like `https://www.example.com/1.html, https://www.example.com/2.html`). Those will not be checked.
* **Category "CACHE":**
  * `cache_file`: Path to the cache file. Default is `salted-cache.sqlite3` in the current working directory.
  * `dont_check_again_within_hours`: The cache lifetime in full hours. If a link was valid this number of hours ago, salted assumes it is still valid and will not check it again. This defaults to 24 hours.
* **Category "TEMPLATE":**
  * `template_searchpath`: In case you want to use a custom template, this has to be the path to the *folder* in which the template file can be found.
  * `template_name`: The name of the template file. Built-In templates are `default.md.jinja` (for markdown output) and `default.cli.jinja` (for text output on the command line).
  * `write_to`: Default is 'cli' to write to standard out. Alternatively this accepts a file path.
  * `base_url`: The file system path to the checked folder is replaced with this URL in template outputs. So for example if you check the folder `/home/username/homepage/` and in the file `index.html` has a broken link, then the path could be changed to `https://www.example.com/index.html`.