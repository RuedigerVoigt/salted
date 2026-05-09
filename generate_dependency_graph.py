#!/usr/bin/env python3
"""Generate a Mermaid dependency graph for salted and write it to documentation/.

Must be run inside the project virtualenv so that pipdeptree sees the correct
packages. Use:

    poetry run python generate_dependency_graph.py
"""

import re
import subprocess
import sys
import pathlib
from importlib.metadata import requires as pkg_requires, version as pkg_version, PackageNotFoundError

ROOT = pathlib.Path(__file__).parent
OUTPUT_FILE = ROOT / 'documentation' / 'dependency-graph.md'


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


def _get_optional_deps() -> dict:
    """Return optional extras for salted: {node_id: {display_name, constraint, installed}}."""
    reqs = pkg_requires('salted') or []
    optional = {}
    # Format: 'lxml (>=6.1.0) ; extra == "lxml"'
    pattern = re.compile(
        r'^([A-Za-z0-9_\-\.]+)\s*\(([^)]*)\)\s*;\s*extra\s*==\s*["\'](.+)["\']'
    )
    for req in reqs:
        m = pattern.match(req.strip())
        if not m:
            continue
        pkg_name = m.group(1)
        constraint = m.group(2).strip()
        node_id = pkg_name.lower()
        try:
            installed = pkg_version(pkg_name)
        except PackageNotFoundError:
            installed = None
        optional[node_id] = {
            'display_name': pkg_name,
            'constraint': constraint,
            'installed': installed,
        }
    return optional


def _inject_optional(mermaid: str, optional: dict) -> str:
    """Inject optional dependency nodes and edges into a pipdeptree mermaid graph."""
    if not optional:
        return mermaid

    lines = mermaid.splitlines()

    # Locate the existing classDef line to insert our classDef after it
    classdef_idx = next(
        (i for i, ln in enumerate(lines) if ln.strip().startswith('classDef')),
        None
    )

    # Locate where node definitions end — first line containing ' -- ' is the
    # start of edge definitions
    first_edge_idx = next(
        (i for i, ln in enumerate(lines) if ' -- ' in ln),
        len(lines)
    )

    optional_classdef = (
        '    classDef optional '
        'fill:#e8e8e8,stroke:#aaaaaa,color:#777777,stroke-dasharray:4'
    )
    optional_nodes = []
    optional_edges = []

    for node_id, info in optional.items():
        version_str = info['installed'] or 'not installed'
        label = f"{info['display_name']}<br/>{version_str}"
        optional_nodes.append(f'    {node_id}["{label}"]:::optional')
        optional_edges.append(
            f'    salted -. "{info["constraint"]}" .-> {node_id}'
        )

    if classdef_idx is not None:
        lines.insert(classdef_idx + 1, optional_classdef)
        if first_edge_idx > classdef_idx:
            first_edge_idx += 1

    for node in reversed(optional_nodes):
        lines.insert(first_edge_idx, node)

    lines.extend(optional_edges)

    return '\n'.join(lines)


def main() -> None:
    _check_venv()
    result = subprocess.run(
        [sys.executable, '-m', 'pipdeptree',
         '--warn', 'silence', '--packages', 'salted', '-o', 'mermaid'],
        capture_output=True,
        text=True,
        check=True
    )
    optional = _get_optional_deps()
    mermaid = _inject_optional(result.stdout.rstrip(), optional)
    OUTPUT_FILE.write_text(f"```mermaid\n{mermaid}\n```\n", encoding='utf-8')
    print(f"Written to {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
