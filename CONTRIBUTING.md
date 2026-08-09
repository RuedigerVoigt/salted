# How to contribute

Welcome,

Open Source thrives on code contributions so pull requests (PRs) are always welcome.

## The use of Software Coding Agents

Software engineering agents like OpenAI Codex or Claude Code are becoming an important part of modern software development.
So it is ok if you use artificial intelligence to find bugs or to support you in the development of a new feature.
As those tools sometimes hallucinate or choose overcomplicated ways to solve an issue, check your pull requests before submitting them.



## Pull Requests / Code Guidelines

* This project uses the **[Apache License 2.0](LICENSE)**. In order to submit you must agree with its terms.
* **Keep the dependency footprint small.** salted does use external dependencies, but each one is a maintenance and security liability. A PR adding one needs to say in its description why the Python Standard Library or an existing dependency cannot do the job. Optional dependencies (like `lxml`) must degrade gracefully when absent.
* Please respond to comments and requests for change of your PR.
* Use develop as your base branch for PRs.
* If you add a new feature, please add corresponding unit tests.
* Please do not put too many changes in one PR. Instead group them logically.
* Please check that there are no untracked, modified, or staged files left unintentionally before you make a commit (e.g. run `git status` to confirm a clean working tree).

## Running the checks locally

```bash
poetry install --with dev         # test and lint dependencies
poetry run pytest                 # the full test suite
poetry run ruff check salted/     # style and lint
poetry run mypy salted/           # type checking
poetry run bandit -r salted/ -ll  # security scan
```

The GitHub Actions workflows run the tests on Linux, macOS and Windows, so please make sure the suite passes locally before opening a PR.

## Coding Style

* Respect [PEP 8](https://peps.python.org/pep-0008/) style guidelines.
* The use of type hints ([PEP 484](https://peps.python.org/pep-0484/)) is encouraged. Use modern [PEP 604](https://peps.python.org/pep-0604/) / [PEP 585](https://peps.python.org/pep-0585/) syntax (`X | None`, built-in generics like `list[str]`) rather than `typing.Optional`/`Union`/`List`.
* Please provide useful log and error messages. Use `logging.debug` for handled validation failures so the library does not spam the host application's logs.
* Docstrings are required for all functions and classes using [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).

This project supports Python 3.11 to 3.14 and uses [Poetry](https://python-poetry.org/) for packaging and dependency management.
