# Changelog

All notable changes to PromptVeil are documented here.

## [0.1.2] - 2026-10-31

### Fixed

- Publish workflow's TestPyPI smoke test now resolves dependencies with
  `--index-strategy unsafe-best-match`. Previously, once `promptveil` existed
  on PyPI, the installer's dependency-confusion protection pinned all version
  lookups to PyPI and refused to see the just-published version on TestPyPI,
  blocking every release after 0.1.0 from reaching PyPI.

## [0.1.0] - 2026-08-24

### Added

- Regex detection for emails, phone numbers, credit cards, and API keys.
- Configurable `allow`, `mask`, and `block` policies loaded from YAML.
- India, EU, and US compliance-oriented detector profiles.
- Confidence-aware policies and detailed scan risk results.
- Reversible pseudonymization with `PseudonymVault`.
- OpenAI, LangChain, and FastAPI integrations as optional features.
- Structured audit logging that excludes raw detected values.

### Known limitations

- Detectors are heuristic and cannot guarantee that all sensitive data is found.
- Compliance profiles are configuration presets, not legal compliance certifications.
- `PseudonymVault` is an in-process store and is not a durable or distributed vault.
- Optional integrations must be tested against the SDK versions used by the host application.
