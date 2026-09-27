#!/usr/bin/python3

"""
Check the Format of DOIs
~~~~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026 Rüdiger Voigt and contributors
Released under the Apache License 2.0

Only the form of a DOI is checked here, without any network access. Whether
a DOI is registered is known only when a doi.org link to it was checked as
a URL and answered as fine (see DatabaseIO.confirm_dois_from_links).
"""
import re
import urllib.parse
from typing import Final, NamedTuple

# Per the DOI Handbook: '10.', a registrant code of at least four digits,
# optionally with dot-separated subdivisions (10.1000.10), then '/' and a
# non-empty suffix without whitespace.
DOI_PATTERN: Final = re.compile(r'^10\.\d{4,}(?:\.\d+)*/\S+$')

# Hosts of the DOI resolver. dx.doi.org is the old name of doi.org.
DOI_HOSTS: Final = frozenset({'doi.org', 'dx.doi.org'})

# The form recommended by the Crossref and DataCite display guidelines.
RECOMMENDED_PREFIX: Final[str] = 'https://doi.org/'


class DoiField(NamedTuple):
    """A DOI as read from a BibTeX doi field."""
    doi: str
    well_formed: bool
    outdated: bool


def is_well_formed(doi: str) -> bool:
    """Return True if the string has the form of a DOI.

    DOIs are case-insensitive, and the pattern accepts either case.

    Args:
        doi: The bare DOI, without a resolver URL or 'doi:' prefix.

    Returns:
        True if it matches the DOI syntax.
    """
    return bool(DOI_PATTERN.match(doi))


def _parse_doi_link(url: str) -> urllib.parse.SplitResult | None:
    """Parse the URL if it is a link to the DOI resolver.

    Args:
        url: Any URL.

    Returns:
        The parsed URL for http(s) links to doi.org or dx.doi.org, else None.
    """
    # urlsplit, not urlparse: urlparse cuts ';...' off the last path
    # segment as parameters, which would truncate DOIs such as
    # 10.1175/1520-0469(1963)020<0130:DNF>2.0.CO;2.
    try:
        parsed = urllib.parse.urlsplit(url)
        host = parsed.hostname
    except ValueError:
        return None
    if parsed.scheme.lower() not in ('http', 'https') or host not in DOI_HOSTS:
        return None
    return parsed


def doi_from_link(url: str) -> str | None:
    """Return the DOI a doi.org or dx.doi.org link points to.

    Args:
        url: Any URL.

    Returns:
        The DOI with percent-encoding undone, or None if the URL is not a
        link to the DOI resolver or names no DOI.
    """
    parsed = _parse_doi_link(url)
    if parsed is None:
        return None
    return urllib.parse.unquote(parsed.path.lstrip('/')) or None


def recommended_link(url: str) -> str | None:
    """Return the recommended form of an outdated DOI link.

    'http://' and the old host name dx.doi.org still work, but the display
    guidelines ask for https://doi.org/.

    Args:
        url: Any URL.

    Returns:
        The same link as https://doi.org/..., or None if the URL is not a
        DOI link or already has the recommended form.
    """
    parsed = _parse_doi_link(url)
    if parsed is None:
        return None
    if parsed.scheme.lower() == 'https' and parsed.hostname == 'doi.org':
        return None
    recommended = RECOMMENDED_PREFIX + parsed.path.lstrip('/')
    if parsed.query:
        recommended += '?' + parsed.query
    return recommended


def parse_doi_field(value: str) -> DoiField:
    """Read the DOI from a BibTeX doi field.

    A bare DOI is the usual content. A doi.org link is accepted as well.
    A 'doi:' prefix and the old link forms (http://, dx.doi.org) are marked
    as outdated, so the report can suggest https://doi.org/.

    Args:
        value: The content of the doi field.

    Returns:
        The DOI, whether it is well-formed, and whether it was written in an
        outdated form.
    """
    value = value.strip()
    if value.lower().startswith('doi:'):
        doi = value[4:].strip()
        return DoiField(doi, is_well_formed(doi), True)
    linked = doi_from_link(value)
    if linked is not None:
        return DoiField(linked, is_well_formed(linked),
                        recommended_link(value) is not None)
    return DoiField(value, is_well_formed(value), False)
