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


def main() -> None:

    logging.debug('salted called via the CLI')

    # Create an instance of the main application.
    # This already sets default values!
    checker = salted.Salted()

    parser = argparse.ArgumentParser(
        prog='salted',
        description=f"""Salted is an extremly fast link checker.
        It works with HTML, Markdown and TeX files.
        Currently it only checks external links.
        You are using version {checker.VERSION}.""",
        epilog="For more information see: https://github.com/RuedigerVoigt/salted"
    )

    # Set no defaults in the arguments as they are already set:
    parser.add_argument(
        "-i", "--searchpath",
        type=str,
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
        help="True if dead links shall rise an exception (default: False).",
        metavar='<True/False>')
    parser.add_argument(
        "--user_agent",
        type=str,
        help="User agent to identify itself. (Default: salted / version)",
        metavar="<str>"
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
        checker.searchpath = pathlib.Path(args.searchpath)
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
        checker.user_agent = args.user_agent

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

    checker.check(args.searchpath)
