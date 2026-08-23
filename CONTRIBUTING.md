# Contributing

## Development setup

Use Python 3.10 or newer and install the development dependencies:

```bash
python -m pip install -e ".[dev]"
```

## Checks before opening a change

Run the test suite and coverage locally:

```bash
python -m pytest tests/ -q
python -m pytest tests/ --cov=promptveil --cov-branch --cov-report=term-missing
```

Keep changes focused, add regression tests for behavior changes, and do not
include real sensitive data in tests, fixtures, logs, or documentation.

## Release checklist

1. Align the version in `pyproject.toml`, `promptveil.__version__`, and docs.
2. Update `CHANGELOG.md`.
3. Run the full test and coverage checks.
4. Build and inspect the sdist and wheel.
5. Verify a clean installation before publishing.
