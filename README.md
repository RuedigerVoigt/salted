# Smart, Asynchronous Link Tester with Database backend (SALTED)

![Supported Python Versions](https://img.shields.io/pypi/pyversions/salted)
![Last commit](https://img.shields.io/github/last-commit/RuedigerVoigt/salted)
![pypi version](https://img.shields.io/pypi/v/salted)

Broken hyperlinks are bad for user experience and may hurt SEO.
Salted checks if hyperlinks in HTML files are valid.
Key advantages of this application compared to other linkcheckers are:
* *It is smart.*
    * Salted uses a configurable cache. So if your check found some broken links and you fixed them, then the next run will only check the changed links.
    * It normalizes URLs. Because `https://www.example.com/index.html#one` and `https://www.example.com/index.html#two` point to the same page, only one check is performed.
* *It is fast.*
    * Many linkcheckers work in a linear way - one link after another. This program spawns many asynchronous worker threats that work in parallel and free up resources while waiting on a server's response.
    * Salted is much faster and can check dozens of links *per second* (depending on your connection).
* *Salted can be used stand-alone or in a CI pipeline.*
     * The result can be written to standard out / the command line or to a file.
     * The result can be styled using Jinja2 templates. Two default templates (for the command line and for Markdown) are available. You can use your own templates. 
     * It can raise an exception if it found broken links.

## Example

1. All HTML files you want to check have to be in one directory. Subdirectories will be crawled.
2. Open a Python shell:
```python
import logging
import salted
logging.basicConfig(level=logging.INFO)

# if there is no cache file, a new one will be created:
linkcheck = salted.Salted(cache_file='./salted-cache.sqlite3')

# Assuming there is a folder 'homepage' within your current working directory:
linkcheck.check_links('./homepage/')
```
Two runs in a row (i.e. one full check and one using the cache):
![Using salted - animated example](https://github.com/RuedigerVoigt/salted/raw/main/documentation/salted-0.5.2.gif)

## Installation

This application uses `aiohttp` to realize its high network speed. Python 3.7 - which is as of November 2020 still used by Debian 10 'Buster' - seems to cause an [issue](https://github.com/aio-libs/aiohttp/issues/3535). As Ubuntu and others have moved on to newer versions of Python, that will be not looked into. **So you need Python 3.8. or newer.**

You can check your Python version this way:
```bash
python3 -v
# or depending on your system:
python -v
```

`Salted` is built with `aoihttp`.
If installing `aiohttp` fails because `multidict` does not install you need a C-Compiler present or need to install the binary. Please look at [multidict's documentation](https://github.com/aio-libs/multidict).

Aside from those issues installation is easy:

```bash
sudo pip3 install salted
```

## Using salted


You need a very small Python script to run salted:

```python
import logging
import salted

# This displays all messages of level info or above on your screen. You could write the log output to a file.
logging.basicConfig(level=logging.INFO)

# If there is no cache file, a new one will be created. You need to provide a path / name:
linkcheck = salted.Salted(cache_file='./choose-a-name.sqlite3')

# Salted assumes all your HTML files are in one folder or subfolders of that:
linkcheck.check_links('./path_to_your_html_files/')
```

Salted uses the `logging` module instead of the `print()` command, because:
* You may want to sent the output to a file or another destination.
* By adapting the log level you can decide which information to see.

### Initializing

The first thing to do after importing the libraries is initializing salted by creating an object. As above:
```python
linkcheck = salted.Salted(cache_file='./choose-a-name.sqlite3')
```
The only necessary parameter is to provide a path at which to store your cache file.

There are some optional parameters:
* `workers` defaults to automatic, which lets salted choose how many workers to start. You can set a specific number of workers. *This is not depended on the number of cores your system has, but more so dependent on the number of URLs to check!* Once a worker has sent a request it awaits the answer and meanwhile other workers can check other URLs. For example: A machine with 4 cores on a standard home connection should work fine with 32 or more workers.
* `timeout_sec`: The number of seconds to wait for a server to answer the request. This is necessary as some servers do not answer and a single one of those would block the check. This defaults to 5 seconds. 
* `dont_check_again_within_hours`: the cache lifetime in full hours. If a link was valid this number of hours ago, salted assumes it is still valid and will not check it again. This defaults to 24 hours.
* `raise_for_dead_links`: if set to `True` salted will raise an exception in case it finds obviously dead links that yield a HTTP status code like 404 ('Not found) or 410 ('Gone'). That behavior is useful for a publication workflow. It will *not* raise an exception for links it could not check as some servers block requests.
* `user_agent`: sets the 'User-Agent' field of the HTTP header. This defaults to 'salted' if not set.

### Running the check

Once you initialized salted you can use the object to call the `check_links' function.

As above:
```python
# linkcheck is the object we just initialized
linkcheck.check_links('./path_to_your_html_files/')
```

The only necessary parameter is the path to the folder which contains your HTML files. This is enough for salted to find all files within that and its subfolders whose filename ends on `.htm` or `.html`.

This starts the check. By default the results will be displayed on the command line interface you are using.

### Style the Output and Write to File

However you can style the output using templates and can choose to write it to a file.

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
