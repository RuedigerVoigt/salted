# Changelog for salted

## Version 0.5.4 (December 18, 2020)

* Salted sets the HTTP header 'User-Agent' to `salted/<version>`. Users can overwrite this by setting a custom user agent.
* Require lxml version >= 4.6.2 (released 2020-11-26) as it fixes a vulnerability *and* works with Python 3.9.