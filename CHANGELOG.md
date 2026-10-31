# Changelog

All notable changes to PromptVeil are documented here.

## [Unreleased]

### Security

- The LangChain callback now enforces `block` rules. Previously LangChain
  swallowed `SensitiveDataError` and sent blocked prompts to the model.

### Changed

- The LangChain callback now raises `SensitiveDataError` when a string LLM prompt
  contains an entity that would be masked. Previously these prompts were sent
  unmasked, because a callback can't change them. Call `Shield.scan()` before
  invoking the LLM to send a masked prompt.

### Documentation

- Added a full API reference in `docs/api-reference.md`, replacing the README's
  API section.

## [0.1.3] - 2026-10-31

### Fixed

- `Shield.scan`, `scan_detailed`, and `scan_with_vault` no longer corrupt the
  output when two detectors report the same span (for example `phone` from the
  regex detector and `in_phone` from the India detector). Overlaps are now
  resolved among the spans being masked or pseudonymized, so
  `PseudonymVault.restore` returns the original text. `block` rules are still
  checked against every detected match.

## [0.1.2] - 2026-10-31

### Fixed

- Publish workflow's TestPyPI smoke test now resolves dependencies with
  `--index-strategy unsafe-best-match`. Previously, once `promptveil` existed
  on PyPI, the installer's dependency-confusion protection pinned all version
  lookups to PyPI and refused to see the just-published version on TestPyPI,
  blocking every release after 0.1.0 from reaching PyPI.

## [0.1.1] - 2026-09-19

### Changed

- Bumped the package and runtime version from `0.1.0` to `0.1.1`. This version
  was tagged and published to TestPyPI only; it was never published to PyPI.

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
