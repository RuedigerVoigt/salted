# Developer scripts

Maintenance tooling for salted. These are **not** part of the published package —
they are run by maintainers from a checkout.

## `generate_dependency_graph.py`

Regenerates
[`documentation/dependency-graph-diagram.md`](../documentation/dependency-graph-diagram.md)
— and only that file, which contains nothing but the generated Mermaid block. The
prose explaining the graph lives next to it in
[`documentation/dependency-graph.md`](../documentation/dependency-graph.md), which is
linked from `documentation/dependencies-and-security.md`. Keeping the two apart is
deliberate: an earlier version of this script wrote both into one file and deleted
most of the hand-written notes every time it ran.

It reads the installed packages' metadata, walks the requirement tree from `salted`
(including the extras' own dependencies, so `latexcodec` and `PyYAML` appear under
`pybtex`), and labels each node with the **lowest** version its constraints admit —
not the version installed. Where two parents constrain the same package, the higher
floor wins. Run it after changing dependencies so the documented graph stays in sync.

Environment markers are evaluated against the interpreter running the script, so
regenerate on the platform the committed graph was made on (Windows / CPython 3.14)
or a few nodes will move — see the notes in `dependency-graph.md`.

`tests/test_dependency_graph.py` checks the generated graph against `pyproject.toml`,
so drift fails the test suite either way.

Beyond the standard library it needs `packaging`, which the dev group already brings
in through `pytest`. It is not declared separately, so `poetry install --with dev` is
enough — but if this script ever moves somewhere without pytest, declare it.

Must be run inside the project virtualenv so it reads the right metadata:

```bash
poetry run python scripts/generate_dependency_graph.py
```

The script aborts if it is not running inside a virtualenv, and writes its output
relative to the repository root regardless of the current working directory.
