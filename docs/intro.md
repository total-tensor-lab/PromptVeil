---
id: intro
slug: /
title: Introduction
sidebar_label: Introduction
---

# PromptVeil

**PromptVeil is privacy and safety middleware for LLM applications.** It sits
between your code and the LLM API, detects sensitive data (PII, secrets) in
prompts, applies a policy you control, and writes a structured audit log.

```text
your app ──► PromptVeil ──► LLM API
              │  detect → policy → mask / block / allow
              └─► JSON audit log (raw values never logged)
```

## Why PromptVeil

- **Catch it before it leaves.** Prompts are scanned *before* they reach a
  third-party API.
- **Policy as config.** Rules live in a YAML file: per entity type, choose
  `mask`, `block` or `allow`, with optional confidence thresholds.
- **Regional coverage.** Built-in detectors for India (Aadhaar, PAN, GSTIN, …)
  and US (SSN, EIN, …) identifiers, plus email, phone, cards and API keys.
- **Compliance presets.** One-line `india_dpdpa`, `eu_gdpr` and `us_hipaa`
  starting points.
- **Reversible pseudonymization.** Swap PII for `<EMAIL_1>`-style tokens and
  restore them in the LLM's response.
- **Drop-in integrations.** OpenAI client wrapper, LangChain callback and
  FastAPI middleware.
- **Extensible.** Subclass `BaseDetector` to plug in spaCy, ML models or custom
  patterns.

## Install

```bash
pip install promptveil
```

Optional extras: `promptveil[openai]`, `promptveil[langchain]`,
`promptveil[fastapi]`. Requires Python 3.10+.

## 30-second example

```python
from promptveil import Shield, SensitiveDataError

shield = Shield(config_path="policy.yaml")

shield.scan("Contact alice@example.com for the invoice.")
# → "Contact a***@example.com for the invoice."

try:
    shield.scan("Bill card 4111-1111-1111-1111")
except SensitiveDataError:
    ...  # credit_card is blocked by the default policy
```

## Where to go next

| I want to… | Read |
|---|---|
| Set up and run my first scan | [Quickstart](quickstart.md) |
| Write rules and tune confidence | [Policies](guides/policies.md) |
| Start from GDPR / HIPAA / DPDPA | [Compliance profiles](guides/compliance-profiles.md) |
| Restore original values after the LLM call | [Pseudonymization vault](guides/vault.md) |
| Plug into OpenAI, LangChain or FastAPI | [Integrations](guides/integrations.md) |
| Ship events to my logging stack | [Audit logging](guides/audit-logging.md) |
| Look up a class or function | [API reference](api-reference.md) |
| Understand the internals | [Project summary](project-summary.md) |

:::caution Alpha software
PromptVeil is alpha, so APIs may change between releases. Detection is
heuristic and may miss sensitive data; it is not a compliance certification.
:::
