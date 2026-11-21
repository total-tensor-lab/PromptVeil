# Contributing

## Finding something to work on

- [Good first issues](https://github.com/total-tensor-lab/PromptVeil/labels/good%20first%20issue)
  are scoped starter tasks, mostly new detectors. Each one lists the format,
  the validation rules and where the code goes. Comment on an issue to claim it.
- The [roadmap](ROADMAP.md) shows what's planned and links to the issues and
  Discussions behind each item.
- To propose a new detector, use the **Missing detector / false negative**
  issue template or the [detector request thread](https://github.com/total-tensor-lab/PromptVeil/discussions/53).

## Development setup

Use Python 3.10 or newer and install the development dependencies:

```bash
python -m pip install -e ".[dev]"
```

## Checks before opening a change

Run the test suite and coverage locally:

```bash
uv run --extra dev pytest tests/ -q
uv run --extra dev pytest tests/ --cov=promptveil --cov-branch --cov-report=term-missing
```

Keep changes focused, add regression tests for behavior changes, and do not
include real sensitive data in tests, fixtures, logs, or documentation.

## Release checklist

1. Align the version in `pyproject.toml`, `promptveil.__version__`, and docs.
2. Update `CHANGELOG.md`.
3. Run the full test and coverage checks.
4. Build and inspect the sdist and wheel.
5. Verify a clean installation before publishing.
