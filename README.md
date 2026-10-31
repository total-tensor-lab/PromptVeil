# PromptVeil

[![PyPI](https://img.shields.io/pypi/v/promptveil)](https://pypi.org/project/promptveil/)

> Privacy and safety middleware for LLM applications.

PromptVeil intercepts prompts **before** they reach an LLM API, detects
sensitive information (PII, secrets), applies configurable policies
(mask · block · allow), and produces structured JSON audit logs for compliance.

---

## Features

| Capability | Detail |
|---|---|
| **PII detection** | Email, phone, credit card, API keys (regex, extensible) |
| **India PII** | Aadhaar (Verhoeff checksum), PAN, GSTIN, IFSC, Passport, Voter ID |
| **US PII** | SSN (segment-validated), US Passport, EIN |
| **Policy engine** | YAML-driven rules: `mask`, `block`, `allow`; per-rule confidence thresholds |
| **Masking** | Type-aware redaction (domain preserved for email, last-4 for cards) |
| **Blocking** | Raises `SensitiveDataError` before the prompt is forwarded |
| **Audit logging** | Structured JSON lines — raw values never logged |
| **Confidence scoring** | Each detected entity carries a `confidence` float; rules can require a minimum |
| **Rich scan results** | `scan_detailed()` returns `ScanResult` with `risk_score`, `risk_level`, and per-entity `EntityResult` |
| **Compliance profiles** | One-line activation of `india_dpdpa`, `eu_gdpr`, or `us_hipaa` rule packs |
| **Pseudonymization vault** | `scan_with_vault()` replaces PII with reversible `<TYPE_N>` tokens; restore after LLM response |
| **OpenAI adapter** | `wrap_openai(client, shield)` patches `chat.completions.create` in-place |
| **LangChain adapter** | `get_langchain_callback()` returns a `BaseCallbackHandler` that scans prompts automatically |
| **Plug-in detectors** | Subclass `BaseDetector` to add spaCy, ML models, custom patterns |
| **FastAPI middleware** | Drop-in Starlette/FastAPI middleware (optional extra) |

---

## Installation

```bash
# Core (only requires PyYAML)
pip install promptveil

# With FastAPI middleware support
pip install "promptveil[fastapi]"

# With OpenAI adapter
pip install "promptveil[openai]"

# With LangChain adapter
pip install "promptveil[langchain]"

# Everything
pip install "promptveil[fastapi,openai,langchain,dev]"

# Development (includes pytest)
pip install "promptveil[dev]"
```

Requires **Python ≥ 3.10**.

## Documentation

- [Quickstart](docs/quickstart.md)
- [Changelog](CHANGELOG.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)

---

## Quick Start

```python
from promptveil import Shield

shield = Shield(config_path="policy.yaml")

safe = shield.scan("Bill me at alice@example.com, card 4111-1111-1111-1111")
# ↑ raises SensitiveDataError — credit card is blocked by default policy

safe = shield.scan("Contact alice@example.com for the invoice.")
# → "Contact a***@example.com for the invoice."
```

### Activate a compliance profile in one line

```yaml
# policy.yaml
profile: india_dpdpa   # or eu_gdpr / us_hipaa
# optional rule overrides go here under `rules:`
```

```python
shield = Shield(config_path="policy.yaml")  # profile detectors loaded automatically
```

### Rich scan result with risk scoring

```python
result = shield.scan_detailed("Call me on +91 98765 43210")
print(result.risk_score)   # e.g. 0.42
print(result.risk_level)   # "MEDIUM"
print(result.safe_text)    # sanitised prompt
```

### Reversible pseudonymization

```python
from promptveil import PseudonymVault

vault = PseudonymVault()
pseudo_text, vault = shield.scan_with_vault("Email alice@example.com", vault=vault)
# pseudo_text → "Email <EMAIL_1>"
llm_response = call_llm(pseudo_text)          # LLM sees tokens, not PII
final = vault.restore(llm_response)           # restore originals in the reply
```

### Drop-in OpenAI integration

```python
import openai
from promptveil.adapters import wrap_openai

client = openai.OpenAI()
wrap_openai(client, shield=shield)            # patches client in-place

# All subsequent calls are automatically scanned:
client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": prompt}],
)
```

---

## Policy Configuration (`policy.yaml`)

```yaml
version: "1.0"
default_action: allow   # fallback: mask | block | allow

# Optional: activate a built-in compliance profile (india_dpdpa | eu_gdpr | us_hipaa)
# profile: eu_gdpr

rules:
  - type: email
    action: mask         # a***@example.com
    min_confidence: 0.8  # optional: only apply rule when confidence ≥ this value
  - type: phone
    action: mask         # ***-***-5309
  - type: credit_card
    action: block        # raises SensitiveDataError
  - type: api_key
    action: block        # raises SensitiveDataError
```

Built-in entity types: `email`, `phone`, `credit_card`, `api_key`,
`in_aadhaar`, `in_pan`, `in_phone`, `in_passport`, `in_voter_id`, `in_ifsc`, `in_gstin`,
`ssn`, `us_passport`, `us_ein`.
Custom detectors can introduce any additional type labels.

### Compliance Profiles

Profiles bundle a pre-configured `PolicyConfig` and the appropriate detectors
for a jurisdiction. Activate via the YAML `profile:` key or programmatically:

```python
from promptveil.profiles import load_profile

profile = load_profile("us_hipaa")   # or india_dpdpa / eu_gdpr
shield = Shield(config=profile.policy, detectors=profile.detectors)
```

| Profile | Detectors | Key rules |
|---|---|---|
| `india_dpdpa` | `RegexDetector` + `IndiaDetector` | Aadhaar/PAN/Passport → BLOCK; phone/GSTIN/IFSC → MASK |
| `eu_gdpr` | `RegexDetector` | email/phone → MASK; credit card/API key → BLOCK |
| `us_hipaa` | `RegexDetector` + `USDetector` | SSN → BLOCK; email/phone/passport/EIN → MASK |

> **Disclaimer:** Profiles are starting-point policy presets, not legal advice
> and not a certification of compliance with DPDPA, GDPR, HIPAA, or any other
> regulation. Detection is heuristic and may miss sensitive data. You remain
> responsible for your own compliance obligations.

---

## API Reference

### `Shield(config_path=…, config=…, detectors=…, logger=…)`

| Param | Type | Description |
|---|---|---|
| `config_path` | `str \| Path` | Path to a YAML policy file |
| `config` | `PolicyConfig` | Pre-built config (alternative to `config_path`) |
| `detectors` | `list[BaseDetector]` | Custom detector list; overrides profile detectors when provided |
| `logger` | `AuditLogger` | Custom audit logger (default: JSON → stdout) |

### `shield.scan(prompt: str) -> str`

Scans the prompt, applies policy rules, and returns a sanitised string.
Raises `SensitiveDataError` if a `block` rule fires.

### `shield.scan_response(response: str) -> str`

Same as `scan` but semantically applied to LLM output.

### `shield.scan_detailed(prompt: str) -> ScanResult`

Like `scan`, but returns a `ScanResult` dataclass instead of a plain string:

```python
@dataclass(frozen=True)
class ScanResult:
    safe_text: str                # sanitised prompt
    entities: tuple[EntityResult] # per-entity detail
    risk_score: float             # 0.0 – 1.0 probabilistic risk
    risk_level: str               # NONE | LOW | MEDIUM | HIGH | CRITICAL
    was_mutated: bool             # True if any masking was applied
```

`risk_level` thresholds: NONE = 0.0, LOW < 0.30, MEDIUM < 0.60, HIGH < 0.85, CRITICAL ≥ 0.85.

### `shield.scan_with_vault(prompt: str, vault=None) -> tuple[str, PseudonymVault]`

Replaces each masked/blocked entity with a reversible token (`<EMAIL_1>`, `<PHONE_1>`, …).
Pass the returned `PseudonymVault` to `vault.restore(text)` to swap tokens back after the LLM response.

### `shield.add_detector(detector: BaseDetector)`

Register an additional detector at runtime.

### `PseudonymVault`

| Method | Description |
|---|---|
| `pseudonymize(text, entities)` | Replace entity spans with tokens (called internally by `scan_with_vault`) |
| `restore(text)` | Swap all tokens back to their original values |
| `get_token(value)` | Look up the token assigned to an original value |
| `token_map` | Read-only copy of the current `{token: original_value}` mapping |
| `clear()` | Reset the vault |
| `len(vault)` | Number of unique originals stored |

---

## Programmatic Config (no YAML file)

```python
from promptveil import Shield
from promptveil.policy.models import Action, PolicyConfig, Rule

config = PolicyConfig(
    rules=[
        Rule(type="email", action=Action.MASK, min_confidence=0.8),
        Rule(type="api_key", action=Action.BLOCK),
    ],
    default_action=Action.ALLOW,
)
shield = Shield(config=config)
```

`min_confidence` is optional (defaults to `0.0`). When a detector reports
`confidence < min_confidence` for an entity, the rule is skipped and
`default_action` applies instead.

---

## Custom Detectors

Subclass `BaseDetector` to add any detection logic:

```python
import re
from promptveil.detector.base import BaseDetector, DetectedEntity

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
from promptveil import Shield
from promptveil.middleware import PromptVeilMiddleware

app = FastAPI()
shield = Shield(config_path="policy.yaml")
app.add_middleware(PromptVeilMiddleware, shield=shield, prompt_field="prompt")
```

POST requests with `Content-Type: application/json` that contain the
`prompt_field` key are intercepted automatically. Blocked prompts receive a
`400` response with a structured error body.

---

## LangChain Adapter

```python
from promptveil.adapters import get_langchain_callback

CallbackClass = get_langchain_callback()   # lazy-imported; requires langchain-core
callback = CallbackClass(shield)

llm.invoke(prompt, config={"callbacks": [callback]})
```

The callback implements `on_llm_start` (string prompts) and
`on_chat_model_start` (chat messages), scanning and mutating content
in-place before it reaches the model.

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
promptveil/
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

234 tests, < 1 s.
