# Dependency graph

Versions shown are the **minimum** each constraint allows, not the versions that
happen to be installed anywhere. For salted's own dependencies they are the floors
declared in `pyproject.toml`; for everything below them they are derived from the
constraint on the edge that pulls them in. Installing today resolves to newer
versions than these — this graph answers "what is the oldest set salted claims to
work with", which is what a lower-bound bump has to be checked against.

**[→ The graph itself is in `dependency-graph-diagram.md`](dependency-graph-diagram.md)**

That file is written by `scripts/generate_dependency_graph.py` and holds nothing but
the generated Mermaid block, so regenerating it cannot destroy the notes below. Do
not edit it by hand; edit this file instead.

## How to read it

Solid arrows are installed by `pip install salted`. Dotted arrows and greyed nodes
are optional extras: `salted[lxml]`, `salted[bibtex]`, or `salted[all]` for both.
Note that `latexcodec` and `PyYAML` reach a default install through nothing else —
they arrive only with `pybtex`.

Where two parents constrain the same package, the higher floor wins: `propcache` is
`>=0.2.1` (yarl) rather than `>=0.2.0` (aiohttp), and `frozenlist` is `>=1.1.1`
(aiohttp) rather than `>=1.1.0` (aiosignal). `colorama` and `pycparser` are pulled in
without a lower bound at all.

## What the graph depends on

Environment markers are evaluated against the interpreter that generated the graph,
so a few nodes are specific to it (Windows, CPython 3.14):

* `colorama` arrives through `tqdm` on Windows only.
* `pycares` asks for `cffi>=2.0.0b1` on Python 3.14 and `cffi>=1.5.0` below it.
* `aiohttp`'s `async-timeout` and its own `typing_extensions` floor apply below
  Python 3.11 and 3.13 respectively, so neither shows up here.

Regenerate on the same platform, or expect those to move.
