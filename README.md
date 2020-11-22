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
* *It is fast.* Many linkchecker work in a linear way - one link after another. This programme spawns many asynchronous worker threats that work in parallel and free up resources while waiting on a server's response. This means it is much faster and can check dozens of links *per second* (depending on your connection).
* *Salted can be used stand-alone or in a CI pipeline.*
     * The result can be written to standard out / the command line or to a file.
     * The result can be styled using Jinja2 templates. Two default templates (for the command line and for Markdown) are available. You can use your own templates. 
     * It can raise an exception if it found broken links.

## How to check links

1. All HTML files you want to check have to be in one directory. Subdirectories will be crawled.
2. Open a Python shell:
```python
import salted

# if there is no cache file, a new one will be created:
linkcheck = salted.Salted(cache_file='./salted-cache.sqlite3')

# Assuming there is a folder 'homepage' within your current working directory:
linkcheck.check_links('./homepage/')
```
That should look like this:


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

```
sudo pip3 install salted
```
