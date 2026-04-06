# Running salted from the command line

Once salted is installed with pip, it registers itself as a command line script and is available in your path. So open a command line, switch into the directory you want to check and try:

```bash
# Check all supported files within this directory and its subdirectories.
# Output result to the command line.
salted -i ./
```

On the command line salted supports all parameters. To get an overview, simply type `salted -h` and it will display this help message with all available options.

```
usage: salted [-h] [-i <path>] [--file_types {supported,html,tex,markdown}] [-w <num>] [--timeout <seconds>]
              [--raise_for_dead_links | --no-raise_for_dead_links] [--user_agent <preset or custom string>]
              [--ignore_urls <str,str,str>] [--domain_delay <seconds>] [--cache_file <path>]
              [--dont_check_again_within_hours <hours>] [--template_searchpath <path to folder>]
              [--template_name <filename>] [--write_to <path>] [--base_url https://www.example.com] [-q]

Salted is an extremely fast link checker. It works with HTML, Markdown, TeX and BibTeX files.
Currently it only checks external links.

options:
  -h, --help            show this help message and exit
  -i, --searchpath <path>
                        File or Folder to check (default: current working directory)
  --file_types {supported,html,tex,markdown}
                        Choose which kind of files will be checked. 'tex' includes BibTeX (.bib) files.
  -w, --num_workers <num>
                        The number of workers to use in parallel (default: automatic)
  --timeout <seconds>   Number of seconds to wait for an answer of a server (default: 5).
  --raise_for_dead_links, --no-raise_for_dead_links
                        Raise an exception if dead links are found (default: False).
  --user_agent <preset or custom string>
                        User agent to identify itself. Use a preset (chrome, firefox, edge, safari,
                        chrome-mac, chrome-linux) or provide a custom string. (Default: salted / version)
  --ignore_urls <str,str,str>
                        String with URLs that will not be checked. Separate them with commas.
  --domain_delay <seconds>
                        Minimum delay in seconds between requests to the same domain (default: 0.25).
                        Set to 0 to disable rate limiting.
  --cache_file <path>   Path to the cache file (default: salted-cache.sqlite3 in the current working directory)
  --dont_check_again_within_hours <hours>
                        Number of hours an already verified URL is considered valid (default: 24).
  --template_searchpath <path to folder>
                        Path to *folder* in which the template file can be found.
  --template_name <filename>
                        Name of the template file.
  --write_to <path>     Either 'cli' to write to standard out or a path (default: cli)
  --base_url https://www.example.com
                        The file system path to the checked folder is replaced with this URL in template outputs.
  -q, --quiet           Suppress all progress messages. Only the final report is written to output.
                        Useful for CI pipelines.

For more information see: https://github.com/RuedigerVoigt/salted

```

## Quiet mode for CI pipelines

By default, salted prints progress messages (number of URLs to check, cache hits, etc.) to standard output alongside the final report. In a CI pipeline you may want only the report:

```bash
salted -i ./homepage/ --quiet
# or short form:
salted -i ./homepage/ -q
```

With `--quiet`, all progress messages and progress bars are suppressed. Only the final report is written to output.
