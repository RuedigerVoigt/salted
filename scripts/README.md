# Developer scripts

Maintenance tooling for salted. These are **not** part of the published package —
they are run by maintainers from a checkout.

## `generate_dependency_graph.py`

Regenerates the Mermaid dependency graph in
[`documentation/dependency-graph.md`](../documentation/dependency-graph.md), which is
linked from `documentation/dependencies-and-security.md`.

It runs `pipdeptree` against the installed `salted` package and augments the result
with the optional extras (e.g. `lxml`) declared in `pyproject.toml`, marking them as
optional/dashed nodes. Run it after changing dependencies so the documented graph stays
in sync.

Must be run inside the project virtualenv so `pipdeptree` sees the right packages:

```bash
poetry run python scripts/generate_dependency_graph.py
```

The script aborts if it is not running inside a virtualenv, and writes its output
relative to the repository root regardless of the current working directory.
