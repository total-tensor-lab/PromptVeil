# PromptShield

> Privacy and safety middleware for LLM applications.

PromptShield intercepts prompts **before** they reach an LLM API, detects
sensitive information (PII, secrets), applies configurable policies
(mask · block · allow), and produces structured JSON audit logs for compliance.

---

## Features

| Capability | Detail |
|---|---|
| **PII detection** | Email, phone, credit card, API keys (regex, extensible) |
| **Policy engine** | YAML-driven rules: `mask`, `block`, `allow` |
| **Masking** | Type-aware redaction (domain preserved for email, last-4 for cards) |
| **Blocking** | Raises `SensitiveDataError` before the prompt is forwarded |
| **Audit logging** | Structured JSON lines — raw values never logged |
| **Plug-in detectors** | Subclass `BaseDetector` to add spaCy, ML models, custom patterns |
| **FastAPI middleware** | Drop-in Starlette/FastAPI middleware (optional extra) |

---

## Installation

```bash
# Core (only requires PyYAML)
pip install .

# With FastAPI middleware support
pip install ".[fastapi]"

# Development (includes pytest)
pip install ".[dev]"
```

Requires **Python ≥ 3.10**.

---

## Quick Start

```python
from promptshield import Shield

shield = Shield(config_path="policy.yaml")

safe = shield.scan("Bill me at alice@example.com, card 4111-1111-1111-1111")
# ↑ raises SensitiveDataError — credit card is blocked by default policy

safe = shield.scan("Contact alice@example.com for the invoice.")
# → "Contact a***@example.com for the invoice."
```

---

## Policy Configuration (`policy.yaml`)

```yaml
version: "1.0"
default_action: allow   # fallback: mask | block | allow

rules:
  - type: email
    action: mask         # a***@example.com
  - type: phone
    action: mask         # ***-***-5309
  - type: credit_card
    action: block        # raises SensitiveDataError
  - type: api_key
    action: block        # raises SensitiveDataError
```

Built-in entity types: `email`, `phone`, `credit_card`, `api_key`.
Custom detectors can introduce any additional type labels.

---

## API Reference

### `Shield(config_path=…, config=…, detectors=…, logger=…)`

| Param | Type | Description |
|---|---|---|
| `config_path` | `str \| Path` | Path to a YAML policy file |
| `config` | `PolicyConfig` | Pre-built config (alternative to `config_path`) |
| `detectors` | `list[BaseDetector]` | Custom detector list (default: `[RegexDetector()]`) |
| `logger` | `AuditLogger` | Custom audit logger (default: JSON → stdout) |

### `shield.scan(prompt: str) -> str`

Scans the prompt, applies policy rules, and returns a sanitised string.
Raises `SensitiveDataError` if a `block` rule fires.

### `shield.scan_response(response: str) -> str`

Same as `scan` but semantically applied to LLM output.

### `shield.add_detector(detector: BaseDetector)`

Register an additional detector at runtime.

---

## Programmatic Config (no YAML file)

```python
from promptshield import Shield
from promptshield.policy.models import Action, PolicyConfig, Rule

config = PolicyConfig(
    rules=[
        Rule(type="email", action=Action.MASK),
        Rule(type="api_key", action=Action.BLOCK),
    ],
    default_action=Action.ALLOW,
)
shield = Shield(config=config)
```

---

## Custom Detectors

Subclass `BaseDetector` to add any detection logic:

```python
import re
from promptshield.detector.base import BaseDetector, DetectedEntity

class SSNDetector(BaseDetector):
    _PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

    def detect(self, text: str) -> list[DetectedEntity]:
        return [
            DetectedEntity("ssn", m.group(), m.start(), m.end())
            for m in self._PATTERN.finditer(text)
        ]

    @property
    def supported_types(self) -> list[str]:
        return ["ssn"]

shield = Shield(
    config=PolicyConfig(rules=[Rule(type="ssn", action=Action.MASK)]),
    detectors=[SSNDetector()],
)
```

---

## FastAPI Middleware

```python
from fastapi import FastAPI
from promptshield import Shield
from promptshield.middleware import PromptShieldMiddleware

app = FastAPI()
shield = Shield(config_path="policy.yaml")
app.add_middleware(PromptShieldMiddleware, shield=shield, prompt_field="prompt")
```

POST requests with `Content-Type: application/json` that contain the
`prompt_field` key are intercepted automatically. Blocked prompts receive a
`400` response with a structured error body.

---

## Audit Log Format

Each log line is a self-contained JSON object:

```json
{
  "event": "prompt_scan",
  "timestamp": "2026-05-03T07:34:19.800456+00:00",
  "prompt_length": 44,
  "detections": 1,
  "entities": [
    {
      "entity_type": "email",
      "action": "mask",
      "value_preview": "a***@example.com",
      "position": {"start": 26, "end": 43}
    }
  ]
}
```

Raw sensitive values are **never** stored in logs.

---

## Project Structure

```
promptshield/
├── __init__.py             # Public API: Shield, exceptions
├── shield.py               # Main Shield class — orchestration
├── exceptions.py           # SensitiveDataError, ConfigurationError
├── config/
│   └── loader.py           # YAML loader & validator
├── detector/
│   ├── base.py             # BaseDetector ABC + DetectedEntity dataclass
│   └── regex_detector.py   # Built-in regex patterns (email/phone/card/key)
├── policy/
│   ├── models.py           # Action enum, Rule, PolicyConfig dataclasses
│   └── engine.py           # PolicyEngine — entity → action lookup
├── actions/
│   ├── masker.py           # Per-type masking + apply_masks()
│   └── blocker.py          # block() — raises SensitiveDataError
├── logger/
│   └── audit_logger.py     # Structured JSON audit logger
└── middleware/
    └── fastapi_middleware.py  # Optional Starlette/FastAPI middleware
policy.yaml                 # Example policy (mask email/phone, block card/key)
example_usage.py            # Runnable demo
```

---

## Running Tests

```bash
uv run pytest -v
# or: python -m pytest -v
```

62 tests, 0.06 s.

