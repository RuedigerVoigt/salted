# Smart, Asynchronous Link Tester with Database backend (SALTED)

![Supported Python Versions](https://img.shields.io/pypi/pyversions/salted)
![Last commit](https://img.shields.io/github/last-commit/RuedigerVoigt/salted)
![pypi version](https://img.shields.io/pypi/v/salted)
[![Downloads](https://pepy.tech/badge/salted)](https://pepy.tech/project/salted)
[![Coverage](https://img.shields.io/badge/coverage-65%25-yellow)](https://www.ruediger-voigt.eu/coverage/salted/index.html)

Broken hyperlinks are bad for user experience and may hurt SEO.
Salted checks if external links in HTML, Markdown, or TeX files are valid.
Key advantages of this application compared to other linkcheckers are:
* *It is smart.*
    * Salted uses a configurable cache. If your check found some broken links and you fixed them within the cache lifetime (default: 24h), then the next run will only check the changed links.
    * It normalizes URLs. Because `https://www.example.com/index.html#one` and `https://www.example.com/index.html#two` point to the same page, only one check is performed.
* *It is fast.*
    * Many linkcheckers work in a linear way - one link after another. This applications spawns many asynchronous worker threats that work in parallel and free up resources while waiting on a server's response.
    * Salted is much faster and can check dozens of links *per second* (depending on your connection).
* *Salted can be used stand-alone or in a CI pipeline.*
     * The result can be written to standard out / the command line or to a file.
     * It can raise an exception in case it found broken links.
     * You can use salted as a library or as a command line script.
* *The result can be styled using Jinja2 templates.*
     * Two default templates (for the command line and for Markdown) are available.
     * You can use your own templates. 

## Example

All files you want to check have to be in one directory. Subdirectories will be crawled.

Assuming the files you want to check are located in the "homepage" folder.

Open the command line:
```
cd /folder_above_homepage
salted -i ./homepage/
```
*Alternatively* open a Python shell:
```python
import logging
import salted
logging.basicConfig(level=logging.INFO)

linkcheck = salted.Salted()
linkcheck.check('./homepage/')
```
Two runs in a row (i.e. one full check and one using the cache):
![Using salted - animated example](https://github.com/RuedigerVoigt/salted/raw/main/documentation/salted-0.5.2.gif)

Salted automatically recognizes supported file formats by their extension (i.e. `htm`, `html`, `md`, and `tex`).

## Installation

Python 3.7 causes an [issue](https://github.com/aio-libs/aiohttp/issues/3535). **You need Python 3.8. or newer.**

You can check your Python version this way:
```bash
python3 -v
# or depending on your system:
python -v
```

`Salted` is built with `aoihttp`.
If installing `aiohttp` fails because `multidict` does not install you need a C-Compiler present or need to install the binary. Please look at [multidict's documentation](https://github.com/aio-libs/multidict).

Aside from this installation is easy:

```bash
sudo pip3 install salted
```

*The installation via pip / pip3 install the library salted AND registers it as a command line script in the path. So you can just call salted in the terminal.*

## Salted: Supported File Formats

*Salted does not yet check relative links in any file-format.*

* **HTML** : Standard hyperlinks / anchors are checked. Salted does not yet check relative links or `src` attributes of pictures. Mailto links are not yet checked.
* **Markdown** : The pandoc version as well as GitHub flavored markdown are supported.
* **TeX** : salted recognizes `\url{url}` as well as `\href{url}{text}`, but the hyperref option `baseurl` is ignored.

## Running salted from the command line

Once salted is installed with pip, it registers itself as a command line script and is available in your path. So open a command line, switch into the directory you want to check and try:
```bash
# Check all supported files within this directory and it subdirectories.
# Output result to the command line.
salted -i ./
```
On the command line salted supports all parameters. To get an overview, simply type `salted -h` and it will display this help message with all availbale options.

```
usage: salted [-h] [-i <path>] [--file_types {supported,html,tex,markdown}] [-w <num>] [--timeout <seconds>]
              [--raise_for_dead_links <True/False>] [--user_agent <str>] [--cache_file <path>]
              [--dont_check_again_within_hours <hours>] [--template_searchpath <path to folder>] [--template_name <filename>]
              [--write_to <path>] [--base_url https://www.example.com]

Salted is an extremly fast link checker. It works with HTML, Markdown and TeX files. Currently it only checks external links.
You are using version 0.7.0.

optional arguments:
  -h, --help            show this help message and exit
  -i <path>, --searchpath <path>
                        File or Folder to check (default: current working directory)
  --file_types {supported,html,tex,markdown}
                        Choose which kind of files will be checked.
  -w <num>, --num_workers <num>
                        The number of workers to use in parallel (default: automatic)
  --timeout <seconds>   Number of seconds to wait for an answer of a server (default: 5).
  --raise_for_dead_links <True/False>
                        True if dead links shall rise an exception (default: False).
  --user_agent <str>    User agent to identify itself. (Default: salted / version)
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

For more information see: https://github.com/RuedigerVoigt/salted

```

## Using salted as a Python library

If you want to use `salted` not as a CLI script but as a Python library, a small script is all you need:

```python
import logging
import salted

# This displays all messages of level info or above on your screen.
# You could write the log output to a file.
logging.basicConfig(level=logging.INFO)

# Initializing salted by creating an object
linkcheck = salted.Salted()

# Now you can set parameters to specifc values, for example:
linkcheck.timeout = 10

# Salted assumes all your files are in one folder or subfolders of that.
# Simply call the check function of the instance just created:
linkcheck.check('path_to_your_files/')
```

This starts the check. By default the results will be displayed on the command line interface you are using.

## Using a Configuration File

## Parameters / Initializing

All versions of salted use the same parameters. Their categories are only important for config files:

* Category "FILES":
  * `searchpath`: Path to file or folder to check (default: current working directory)
  * `file_types`: Choose which types of files to check. Values can be 'supported' (all formats known to salted), 'html', 'tex', or 'markdown'.
* Category "BEHAVIOR":
  * `num_workers` defaults to automatic, which lets salted choose how many workers to start. You can set a specific number of workers. *This is not depended on the number of cores your system has, but more so dependent on the number of URLs to check!* Once a worker has sent a request it awaits the answer and meanwhile other workers can check other URLs. For example: A machine with 4 cores on a standard home connection should work fine with 32 or more workers.
  * `timeout`: The number of seconds to wait for a server to answer the request. This is necessary as some servers do not answer and a single one of those would block the check. This defaults to 5 seconds.
  * `raise_for_dead_links`: if set to `True` salted will raise an exception in case it finds obviously dead links that yield a HTTP status code like 404 ('Not found) or 410 ('Gone'). That behavior is useful for a publication workflow. It will *not* raise an exception for links it could not check as some servers block requests.
  * `user_agent`: sets the 'User-Agent' field of the HTTP header. This defaults to 'salted' if not set.
* Category "CACHE":
  * `cache_file`: Path to the cache file. Default is `salted-cache.sqlite3` in the current working directory.
  * `dont_check_again_within_hours`: The cache lifetime in full hours. If a link was valid this number of hours ago, salted assumes it is still valid and will not check it again. This defaults to 24 hours.
* Category "TEMPLATE":
  * `template_searchpath`: In case you want to use a custom template, this has to be the path to the *folder* in which the template file can be found.
  * `template_name`: The name of the template file. Built-In templates are `default.md.jinja` (for markdown output) and `default.cli.jinja` (for text output on the command line).
  * `write_to`: Default is 'cli' to write to standard out. Alternatively this accepts a file path.
  * `base_url`: The file system path to the checked folder is replaced with this URL in template outputs. So for example if you check the folder `/home/username/homepage/` and in the file `index.html` has a broken link, then the path could be changed to `https://www.example.com/index.html`.


## Style the Output and Write to File

You can style the output using templates and can choose to write it to a file.

There are two builtin templates for salted:
* `default.cli.jinja`: formats the output for display on the command line interface.
* `default.md.jinja`: formats the output as markdown using the [pandoc syntax](https://pandoc.org/). This can easily be converted to other formats like .docx or PDF. (See the pandoc documentation for this.)

You can choose between those two templates by setting the parameter `template_name` to either of them.

The parameter `write_to` defaults to `cli` (command line interface). If you want to write the result to a file, set the value of `write_to` to the path of that file including the filename. Existing files will be overwritten.

The parameter `template_searchpath` defaults to `salted/templates`. This tells salted to use the builtin templates. If you want to use your own template, set this to the path **to the folder** on your file-system that has your template in it. Its name must be given with the `write_to` parameter!

Salted uses [Jinja2 templates](https://jinja.palletsprojects.com/en/2.11.x/).


The last optional parameter is `base_url`. Assume all your HTML files will be hosted on `www.example.com`. Salted does not know that. So if it finds a defect link it will tell you it is in `/home/youruser/path_to_your_folder/index.html`. If you set `base_url` to `https://www.example.com/` it will instead tell you the defect link is in `https://www.example.com/index.html`.

### Handling problematic servers

Servers might block you if you send too many requests in a certain amount of time, then you should reduce the number of workers to slow salted down.

However, some servers block bots in general fearing automated access might be with malicious intent. This often includes link checkers although having working links pointing to their pages helps their SEO. Salted also mainly uses HEAD requests which do not load the full webpage, but only the headers. (Full requests are used as backup, but even then only a part is read.) You might ask the page's owner to excempt a specific IP or user agent. If that is not feasible it might help to set the `user_agent` parameter to something a browser might send.
