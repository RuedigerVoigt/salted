#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Provide a command line interface for the salted library
~~~~~~~~~~~~~~~~~~~~~
Smart, Asynchronous Link Tester with Database backend (SALTED)
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2021: Released under the Apache License 2.0
"""

import argparse
import logging
import pathlib

import salted
from userprovided.parameters import separated_string_to_set
from salted.user_agents import get_user_agent, list_presets


def main() -> None:
    """Provide an entrypoint for the command line interface of salted.

    Parses command line arguments, overrides defaults and config file settings,
    and runs the link checker.
    """
    # pylint: disable=too-many-branches

    logging.debug('salted called via the CLI')

    # Create an instance of the main application.
    # This already sets default values and reads an existent config file
    checker = salted.Salted()

    parser = argparse.ArgumentParser(
        prog='salted',
        description=f"""Salted is an extremely fast link checker.
        It works with HTML, Markdown and TeX files.
        Currently it only checks external links.
        You are using version {checker.VERSION}.""",
        epilog="For more information see: https://github.com/RuedigerVoigt/salted"
    )

    # Set no defaults in the arguments as they are already set:
    parser.add_argument(
        "-i", "--searchpath",
        type=pathlib.Path,
        help="File or Folder to check (default: current working directory)",
        metavar='<path>')
    parser.add_argument(
        "--file_types",
        choices=['supported', 'html', 'tex', 'markdown'],
        help="Choose which kind of files will be checked.")

    parser.add_argument(
        "-w", "--num_workers",
        type=int,
        help="The number of workers to use in parallel (default: automatic)",
        metavar='<num>')
    parser.add_argument(
        "--timeout",
        type=int,
        help="Number of seconds to wait for an answer of a server (default: 5).",
        metavar='<seconds>')
    parser.add_argument(
        "--raise_for_dead_links",
        type=str,
        help="True if dead links shall raise an exception (default: False).",
        metavar='<True/False>')
    presets = ', '.join(list_presets())
    parser.add_argument(
        "--user_agent",
        type=str,
        help=f"User agent to identify itself. Use a preset ({presets}) or provide a custom string. (If nothing is set it defaults to: salted / version)",
        metavar="<preset or custom string>"
    )
    parser.add_argument(
        "--ignore_urls",
        type=str,
        help="String with URLs that will not be checked. Separate them with commas.",
        metavar="<str,str,str>"
    )
    parser.add_argument(
        "--domain_delay",
        type=float,
        help="Minimum delay in seconds between requests to the same domain (default: 0.25). Set to 0 to disable rate limiting.",
        metavar="<seconds>"
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
        default='default.cli.jinja',
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

    args = parser.parse_args()

    # Settings on the command line interface shall override any setting in a
    # configfile and defaults. So if anything was set here, use it to override:
    if args.searchpath:
        # Strip quotes that may be preserved due to trailing backslash escaping
        # e.g., "C:\path\" becomes "C:\path\"" on Windows
        searchpath_str = str(args.searchpath).strip('"').strip("'")
        checker.searchpath = pathlib.Path(searchpath_str)
    if args.file_types:
        checker.file_types = args.file_types

    if args.num_workers:
        checker.num_workers = args.num_workers
    if args.timeout:
        checker.timeout = args.timeout
    if args.raise_for_dead_links:
        if args.raise_for_dead_links in ("True", "true", "yes"):
            checker.raise_for_dead_links = True
        elif args.raise_for_dead_links in ("False", "false", "no"):
            checker.raise_for_dead_links = False
        else:
            raise ValueError("Unknown value for raise_for_dead_links")
    if args.user_agent:
        # Check if it's a preset or a custom string
        try:
            checker.user_agent = get_user_agent(args.user_agent)
        except ValueError:
            # Not a preset, treat as custom user agent string
            checker.user_agent = args.user_agent
    if args.ignore_urls:
        # Parse comma-separated values into a clean set using userprovided helper
        parsed_ignores = separated_string_to_set(args.ignore_urls)
        if parsed_ignores is not None:
            checker.ignore_urls = parsed_ignores
    if args.domain_delay is not None:
        checker.domain_delay = args.domain_delay

    if args.cache_file:
        checker.cache_file = args.cache_file
    if args.dont_check_again_within_hours:
        checker.dont_check_again_within_hours = args.dont_check_again_within_hours

    if args.template_searchpath:
        checker.template_searchpath = args.template_searchpath
    if args.template_name:
        checker.template_name = args.template_name
    if args.write_to:
        checker.write_to = args.write_to
    if args.base_url:
        checker.base_url = args.base_url

    checker.check(checker.searchpath)
