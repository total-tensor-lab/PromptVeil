# Releasing PromptVeil

## One-time setup

1. Confirm that the `promptveil` project name and the intended version are
   available on PyPI. PyPI releases cannot be replaced.
2. Rename the GitHub repository to `PromptVeil`, then update the three project
   URLs in `pyproject.toml` and the clone command in `docs/quickstart.md`.
3. Configure TestPyPI and PyPI Trusted Publishing (or pending publishers) for
   this repository, the `publish.yml` workflow, and the `testpypi` / `pypi`
   environments.
4. Protect the `pypi` environment with a required reviewer. The workflow uses
   OpenID Connect and intentionally does not require a stored API token.

## Release checklist

1. Update the package version in `pyproject.toml` and `promptveil/__init__.py`.
2. Move the matching `CHANGELOG.md` section from `Unreleased` to a dated
   release entry.
3. Run the local release gate:

   ```bash
   uv lock
   uv run --extra dev pytest --cov=promptveil --cov-branch --cov-fail-under=90
   uv build
   uv run --with twine twine check dist/*
   ```

4. Regenerate the PNG files in `docs/diagrams/` from their corresponding
   `.drawio` sources.
5. Commit the release changes, then create and push a matching version tag:

   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

The publish workflow verifies that the tag and package version match, publishes
the tested artifacts to TestPyPI, installs that release in a fresh environment,
and then waits for approval before publishing the same artifacts to PyPI.
