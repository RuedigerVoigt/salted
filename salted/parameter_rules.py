#!/usr/bin/python3

"""
Central validation rules for salted parameters
~~~~~~~~~~~~~~~~~~~~~
Smart, Asynchronous Link Tester with Database backend (SALTED)
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026 Rüdiger Voigt and contributors
Released under the Apache License 2.0
"""

from typing import Final

from userprovided.parameters import clean_trim, parse_boolean

# Allowed values for the file_types parameter. The CLI builds its
# argparse choices from this set, so both input paths share one definition.
FILE_TYPES: Final[frozenset] = frozenset(
    {'supported', 'html', 'tex', 'markdown'})

# Minimum allowed value per integer parameter.
# timeout must not be 0: that would disable the timeout entirely and a
# never-responding server could occupy a worker forever.
_INT_MINIMUMS: Final[dict] = {
    'num_workers': 1,
    'timeout': 1,
    'dont_check_again_within_hours': 0,
    'max_file_size_mb': 1,
}

_BOOL_PARAMETERS: Final[frozenset] = frozenset(
    {'raise_for_dead_links', 'check_dois'})


def validate(name: str,
             value: str | int | float | bool,
             source: str) -> str | int | float | bool:
    """Validate and convert a parameter value, whatever its origin.

    The same rules apply to values from the CLI, a config file, or the
    library API. The source string is included in error messages so the
    user knows where to fix the value.

    Args:
        name: Parameter name (e.g. 'timeout').
        value: The value as provided: a string from a config file, or an
            already typed value from argparse or the library API.
        source: Human-readable origin to include in error messages, e.g.
            "in config file salted-linkcheck.ini" or
            "given on the command line (--timeout)".

    Returns:
        The validated, correctly typed value.

    Raises:
        ValueError: If the value violates the rules for this parameter.
        KeyError: If no rule exists for name (a programming error,
            not a user error).
    """
    if name == 'num_workers':
        return _validate_num_workers(value, source)
    if name in _INT_MINIMUMS:
        return _validate_int(name, value, source, _INT_MINIMUMS[name])
    if name == 'domain_delay':
        return _validate_float(name, value, source, minimum=0.0)
    if name in _BOOL_PARAMETERS:
        return _validate_bool(name, value, source)
    if name == 'file_types':
        return _validate_choice(name, value, source, FILE_TYPES)
    raise KeyError(f"No validation rule for parameter '{name}'.")


def _msg(name: str,
         value: str | int | float | bool,
         source: str,
         requirement: str) -> str:
    """Build a uniform error message naming value, parameter, and origin."""
    return f"Invalid value '{value}' for {name} {source} - {requirement}."


def _to_int(value: str | int | float | bool) -> int:
    """Convert to int. Strict: rejects booleans, floats, and bad strings.

    Raises:
        ValueError: If the value is not an integer or integer string.
    """
    if isinstance(value, bool):
        raise ValueError('boolean is not an integer')
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value.strip())
    raise ValueError('not an integer')


def _validate_num_workers(value: str | int | float | bool,
                          source: str) -> int | str:
    """Accept the string 'automatic' or an integer >= 1."""
    if isinstance(value, str):
        value = clean_trim(value, empty_as='') or ''
        if value.lower() == 'automatic':
            return 'automatic'
    requirement = "must be 'automatic' or a positive integer (>= 1)"
    try:
        workers = _to_int(value)
    except ValueError as exc:
        raise ValueError(
            _msg('num_workers', value, source, requirement)) from exc
    if workers < 1:
        raise ValueError(_msg('num_workers', value, source, requirement))
    return workers


def _validate_int(name: str,
                  value: str | int | float | bool,
                  source: str,
                  minimum: int) -> int:
    """Accept an integer (or integer string) >= minimum."""
    requirement = f"must be an integer >= {minimum}"
    try:
        converted = _to_int(value)
    except ValueError as exc:
        raise ValueError(_msg(name, value, source, requirement)) from exc
    if converted < minimum:
        raise ValueError(_msg(name, value, source, requirement))
    return converted


def _validate_float(name: str,
                    value: str | int | float | bool,
                    source: str,
                    minimum: float) -> float:
    """Accept a number (or numeric string) >= minimum."""
    requirement = f"must be a number >= {minimum}"
    if isinstance(value, bool):
        raise ValueError(_msg(name, value, source, requirement))
    try:
        converted = float(value.strip() if isinstance(value, str) else value)
    except (TypeError, ValueError) as exc:
        raise ValueError(_msg(name, value, source, requirement)) from exc
    if converted < minimum:
        raise ValueError(_msg(name, value, source, requirement))
    return converted


def _validate_bool(name: str,
                   value: str | int | float | bool,
                   source: str) -> bool:
    """Accept a real boolean or one of the config file spellings."""
    if not isinstance(value, (bool, str)):
        raise ValueError(_msg(
            name, value, source,
            "must be a boolean (true/false, yes/no, on/off, 1/0)"))
    return parse_boolean(value, name=name, source=source)


def _validate_choice(name: str,
                     value: str | int | float | bool,
                     source: str,
                     allowed: frozenset) -> str:
    """Accept one of a fixed set of strings (case-insensitive)."""
    if isinstance(value, str):
        cleaned = (clean_trim(value, empty_as='') or '').lower()
        if cleaned in allowed:
            return cleaned
    raise ValueError(_msg(
        name, value, source,
        f"must be one of: {', '.join(sorted(allowed))}"))
