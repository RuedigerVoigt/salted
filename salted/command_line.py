#!/usr/bin/python3

"""
Provide a command line interface for the salted library
~~~~~~~~~~~~~~~~~~~~~
Smart, Asynchronous Link Tester with Database backend (SALTED)
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026 Rüdiger Voigt and contributors
Released under the Apache License 2.0
"""

import argparse
import logging
import pathlib
import sys

from userprovided.parameters import separated_string_to_set

import salted
from salted import parameter_rules
from salted.err import ConfigFileError
from salted.user_agents import get_user_agent, list_presets

# ##################### CLI argument -> Salted attribute maps #####################
#
# The application defaults live in Salted.__init__ and may be changed by a
# config file. A CLI value only wins when it was actually supplied, so each
# table below maps an argparse destination to the attribute it overrides and
# the override helpers skip anything the user did not set. Adding a new plain
# option is a one-line entry here — no extra branch in the override logic.

# Assigned only when the argument is truthy. An empty/omitted value falls
# through to the config value or the built-in default.
_TRUTHY_OVERRIDES = (
    ('mailto', 'mailto'),
    ('cache_file', 'cache_file'),
    ('template_searchpath', 'template_searchpath'),
    ('template_name', 'template_name'),
    ('write_to', 'write_to'),
    ('base_url', 'base_url'),
)

# Options checked by the central rules in parameter_rules — the same rules
# a config file value passes through. Applied whenever the argument is not
# None, so an explicit 0/False is honored; an invalid value aborts via
# parser.error() with a message naming the CLI option.
_VALIDATED_OVERRIDES = (
    'num_workers',
    'timeout',
    'dont_check_again_within_hours',
    'max_file_size_mb',
    'domain_delay',
    'raise_for_dead_links',
    'check_dois',
    'check_internal_links',
    'file_types',
)


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the salted CLI.

    Defaults are intentionally left unset on the arguments: they are already
    applied by Salted.__init__ / the config file, and the override helpers only
    touch an attribute when the matching argument was actually supplied.

    Returns:
        The configured argument parser.
    """
    parser = argparse.ArgumentParser(
        prog='salted',
        description=f"""Salted is an extremely fast link checker.
        It works with HTML, Markdown and TeX files.
        It checks external links and - for HTML files - internal links.
        You are using version {salted.__version__}.""",
        epilog="For more information see: https://github.com/RuedigerVoigt/salted"
    )

    parser.add_argument(
        "--config",
        type=pathlib.Path,
        default=None,
        help="Path to an alternative config file (default: salted-linkcheck.ini in the current directory)",
        metavar='<path>'
    )

    # Set no defaults in the arguments as they are already set:
    parser.add_argument(
        "-i", "--searchpath",
        type=pathlib.Path,
        help="File or Folder to check (default: current working directory)",
        metavar='<path>')
    parser.add_argument(
        "--file_types",
        choices=sorted(parameter_rules.FILE_TYPES),
        help="Choose which kind of files will be checked.")

    parser.add_argument(
        "-w", "--num_workers",
        type=int,
        help="The number of workers to use in parallel (default: automatic)",
        metavar='<num>')
    parser.add_argument(
        "--timeout",
        type=int,
        help="Number of seconds to wait for an answer of a server (default: 5, minimum: 1).",
        metavar='<seconds>')
    parser.add_argument(
        "--raise_for_dead_links",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Raise an exception if dead links are found (default: False).")
    presets = ', '.join(list_presets())
    parser.add_argument(
        "--user_agent",
        type=str,
        help=f"User agent to identify itself. Use a preset ({presets}) or provide a custom string. (If nothing is set it defaults to: salted / version)",
        metavar="<preset or custom string>"
    )
    parser.add_argument(
        "--check_dois",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Check DOIs via the CrossRef API (default: True). Use --no-check_dois to skip DOI validation.")
    parser.add_argument(
        "--check_internal_links",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=("Verify that internal links in HTML files (relative paths, "
              "/root-relative paths, #fragments) point to existing files "
              "within the checked folder (default: True). "
              "Use --no-check_internal_links to skip."))
    parser.add_argument(
        "--mailto",
        type=str,
        help="Contact e-mail address included in the CrossRef API User-Agent to opt into the polite pool (faster, less rate-limited).",
        metavar="<email>")
    parser.add_argument(
        "--ignore_urls",
        type=str,
        help="String with URLs that will not be checked. Separate them with commas.",
        metavar="<str,str,str>"
    )
    parser.add_argument(
        "--ignore_domains",
        type=str,
        help="Comma-separated list of domain names whose URLs will not be checked (e.g. example.com,skip.org).",
        metavar="<domain,domain>"
    )
    parser.add_argument(
        "--domain_delay",
        type=float,
        help="Minimum delay in seconds between requests to the same domain (default: 0.25). Set to 0 to disable rate limiting.",
        metavar="<seconds>"
    )
    parser.add_argument(
        "--max_file_size_mb",
        type=int,
        help="Maximum file size in MB to read. Files larger than this are skipped (default: 20).",
        metavar="<MB>"
    )

    parser.add_argument(
        "--cache_file",
        type=pathlib.Path,
        help="Path to the cache file (default: salted-cache.sqlite3 in the current working directory)",
        metavar='<path>')
    parser.add_argument(
        "--dont_check_again_within_hours",
        type=int,
        help="Number of hours an already verified URL is considered valid (default: 24).",
        metavar="<hours>")

    parser.add_argument(
        "--template_searchpath",
        type=pathlib.Path,
        help="Path to *folder* in which the template file can be found.",
        metavar='<path to folder>')
    parser.add_argument(
        "--template_name",
        type=str,
        help="Name of the template file.",
        default=None,
        metavar='<filename>')

    parser.add_argument(
        "--write_to",
        type=str,
        help="Either 'cli' to write to standard out or a path (default: cli)",
        metavar="<path>")
    parser.add_argument(
        "--base_url",
        type=str,
        help="The file system path to the checked folder is replaced with this URL in template outputs.",
        metavar='https://www.example.com')

    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        default=False,
        help="Suppress all progress messages. Only the final report is written to output. Useful for CI pipelines.")

    return parser


def _apply_mapped_overrides(checker: 'salted.Salted',
                            args: argparse.Namespace,
                            parser: argparse.ArgumentParser) -> None:
    """Apply the table-driven CLI overrides to the checker.

    Handles the plain options described by the override maps: truthy-only
    assignments and validated assignments. The latter go through the central
    rules in parameter_rules (shared with config file values), honor an
    explicit 0/False, and abort via parser.error() on an invalid value.

    Args:
        checker: The Salted instance whose attributes are overridden.
        args: The parsed command line arguments.
        parser: The parser, used to report invalid values via parser.error().
    """
    for dest, attr in _TRUTHY_OVERRIDES:
        value = getattr(args, dest)
        if value:
            setattr(checker, attr, value)

    for dest in _VALIDATED_OVERRIDES:
        value = getattr(args, dest)
        if value is not None:
            try:
                validated = parameter_rules.validate(
                    dest, value, f"given on the command line (--{dest})")
            except ValueError as exc:
                parser.error(str(exc))
            setattr(checker, dest, validated)


def _apply_special_overrides(checker: 'salted.Salted',
                             args: argparse.Namespace) -> None:
    """Apply the CLI overrides that need more than a plain assignment.

    These options require quote stripping, preset resolution, or parsing into
    a set, so they cannot be expressed in the override maps.

    Args:
        checker: The Salted instance whose attributes are overridden.
        args: The parsed command line arguments.
    """
    if args.searchpath:
        # Strip quotes that may be preserved due to trailing backslash escaping
        # e.g., "C:\path\" becomes "C:\path\"" on Windows
        searchpath_str = str(args.searchpath).strip('"').strip("'")
        checker.searchpath = pathlib.Path(searchpath_str)

    if args.user_agent:
        # A preset name (e.g. "chrome") resolves to a full UA string; anything
        # else is treated as a custom user agent string verbatim.
        try:
            checker.user_agent = get_user_agent(args.user_agent)
        except ValueError:
            checker.user_agent = args.user_agent

    if args.ignore_urls:
        # Parse comma-separated values into a clean set using userprovided helper
        parsed_ignores = separated_string_to_set(args.ignore_urls)
        if parsed_ignores is not None:
            checker.ignore_urls = parsed_ignores

    if args.ignore_domains:
        parsed_domains = separated_string_to_set(args.ignore_domains)
        if parsed_domains is not None:
            checker.ignore_domains = checker._validate_domains(parsed_domains)

    if args.quiet:
        checker.quiet = True


def main() -> None:
    """Provide an entrypoint for the command line interface of salted.

    Parses command line arguments, overrides defaults and config file settings,
    and runs the link checker.
    """
    logging.debug('salted called via the CLI')

    parser = _build_arg_parser()
    args = parser.parse_args()

    # Create the application instance after parsing so --config is known.
    # A bad config file (missing, unreadable, corrupted) is a clear, expected
    # user error: the message is already logged, so stop with a non-zero exit
    # code instead of dumping a traceback.
    try:
        checker = salted.Salted(config_path=args.config)
    except ConfigFileError:
        sys.exit(1)

    # Settings on the command line interface shall override any setting in a
    # configfile and the defaults.
    _apply_mapped_overrides(checker, args, parser)
    _apply_special_overrides(checker, args)

    checker.check(checker.searchpath)
