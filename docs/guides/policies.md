---
id: policies
title: Policies
---

# Policies

A policy tells PromptVeil what to do when a detector finds an entity. It is a
YAML file (or a `PolicyConfig` built in code).

```yaml title="policy.yaml"
version: "1.0"
default_action: allow   # fallback when no rule matches: mask | block | allow

rules:
  - type: email
    action: mask
    min_confidence: 0.8   # optional: skip this rule below 0.8 confidence
  - type: credit_card
    action: block
  - type: api_key
    action: block
```

## Actions

| Action | Behaviour |
|---|---|
| `mask` | Replaces the value with a partially hidden placeholder (`a***@example.com`, last-4 for cards) |
| `block` | Raises `SensitiveDataError`; the prompt is never forwarded |
| `allow` | Passes the value through unchanged |

## Loading a policy

```python
from promptveil import Shield

shield = Shield(config_path="policy.yaml")
```

Or build one in code, no YAML needed:

```python
from promptveil.policy import Action, PolicyConfig, Rule

config = PolicyConfig(
    default_action=Action.ALLOW,
    rules=[Rule(type="email", action=Action.MASK)],
)
shield = Shield(config=config)
```

## Choosing detectors

Rules only fire for entity types some detector produces. `RegexDetector` is the
default; add regional detectors explicitly:

```python
from promptveil import Shield
from promptveil.detector import RegexDetector, IndiaDetector

shield = Shield(
    config_path="policy.yaml",
    detectors=[RegexDetector(), IndiaDetector()],
)
```

## Entity types

| Type | Detector | Example |
|---|---|---|
| `email`, `phone`, `credit_card`, `api_key` | `RegexDetector` | `alice@example.com` |
| `in_aadhaar`, `in_pan`, `in_gstin`, `in_ifsc`, `in_passport`, `in_voter_id`, `in_phone` | `IndiaDetector` | `ABCDE1234F` |
| `ssn`, `us_passport`, `us_ein` | `USDetector` | `123-45-6789` |

See the [API reference](../api-reference.md#policy) for the full schema.
