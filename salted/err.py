#!/usr/bin/env python3

"""
Salted: Custom Exceptions

Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026 Rüdiger Voigt and contributors
Released under the Apache License 2.0
"""


class SaltedException(Exception):
    """Base exception for salted-specific errors."""
    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        """Pass all arguments to the base Exception class."""
        Exception.__init__(self, *args, **kwargs)


class DeadLinksException(SaltedException):
    """Raised when dead links are found and raise_for_dead_links is enabled.

    This exception is raised if dead links are found and the configuration
    requires raising an exception for them (typically in CI/CD pipelines).
    """


class ConfigFileError(SaltedException):
    """Raised when a configuration file cannot be read or is invalid.

    Covers config files that exist but cannot be read (e.g. a permission
    error) and files that are corrupted / not valid INI (e.g. a missing
    section header or duplicate keys).
    """


class UnsafeTemplateError(SaltedException):
    """Raised when a template must not be loaded or rendered.

    Report templates are loaded from a path that may originate in the
    checked folder, so they are treated as untrusted input: only files
    with the expected template extension are accepted, and rendering
    happens in a sandbox. This exception reports a template rejected
    before it was read.
    """


class MissingOptionalDependencyError(SaltedException):
    """Raised when a file format needs an optional dependency that is absent.

    Some formats are only supported if an extra was installed. BibTeX
    needs `pybtex` (`pip install "salted[bibtex]"`), which is not part of
    the default install because most users never check `.bib` files.
    This is raised when such a file was asked for explicitly; a `.bib`
    file merely found while scanning a folder is reported in the run's
    file access errors instead.
    """


class RedirectBlockedException(SaltedException):
    """Raised when a redirect target must not be requested.

    The GET fallback follows redirects manually and runs each target
    through the SSRF preflight. Targets that fail that check or use a
    non-HTTP scheme raise this exception; the message states the reason.
    """


class TooManyRedirectsException(SaltedException):
    """Raised when a redirect chain exceeds the allowed maximum."""
