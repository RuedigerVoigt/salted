# Changelog for salted

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