# Changelog for salted

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