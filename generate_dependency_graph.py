#!/usr/bin/env python3
"""Generate a Mermaid dependency graph for salted and write it to documentation/.

Must be run inside the project virtualenv so that pipdeptree sees the correct
packages. Use:

    poetry run python generate_dependency_graph.py
"""

import subprocess
import sys
import pathlib

ROOT = pathlib.Path(__file__).parent
OUTPUT_FILE = ROOT / 'documentation' / 'dependency-graph.md'
VENV_DIR = ROOT / '.venv'


def _check_venv() -> None:
    """Abort if not running inside the project virtualenv."""
    running_inside_venv = (
        hasattr(sys, 'real_prefix') or
        (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    )
    if not running_inside_venv:
        print(
            "ERROR: This script must be run inside the project virtualenv.\n"
            "Use:  poetry run python generate_dependency_graph.py",
            file=sys.stderr,
        )
        sys.exit(1)


def main() -> None:
    _check_venv()
    result = subprocess.run(
        [sys.executable, '-m', 'pipdeptree',
         '--warn', 'silence', '--packages', 'salted', '-o', 'mermaid'],
        capture_output=True,
        text=True,
        check=True
    )
    OUTPUT_FILE.write_text(f"```mermaid\n{result.stdout}```\n", encoding='utf-8')
    print(f"Written to {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
