# PromptVeil

**Catch PII and secrets in prompts before they reach the LLM. Mask, block or allow them, with an audit log for compliance.**

[![PyPI](https://img.shields.io/pypi/v/promptveil)](https://pypi.org/project/promptveil/)
[![Tests](https://github.com/total-tensor-lab/PromptVeil/actions/workflows/ci.yml/badge.svg)](https://github.com/total-tensor-lab/PromptVeil/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/promptveil)](https://pypi.org/project/promptveil/)

**[▶ Try it live on Hugging Face](https://huggingface.co/spaces/total-tensor-lab/PromptVeil)** (runs in your browser, nothing to install) ·
[Docs](https://www.totaltensorlab.com/PromptVeil/quickstart) ·
[Roadmap](ROADMAP.md) ·
[Discussions](https://github.com/total-tensor-lab/PromptVeil/discussions)

<!-- TODO(launch): record the Hugging Face Space and save it as docs/assets/demo.gif, then replace this comment with:
<p align="center"><img src="docs/assets/demo.gif" alt="PromptVeil masking an email and blocking a credit card in the live demo" width="720"></p>
-->

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
| **Response scanning** | `scan_response()` sanitises LLM output; the OpenAI adapter and FastAPI middleware can scan replies too |
| **Audit logging** | Structured JSON lines with `scan_id`, confidence and risk score — raw values never logged |
| **Confidence scoring** | Each detected entity carries a `confidence` float; rules can require a minimum |
| **Rich scan results** | `scan_detailed()` returns `ScanResult` with `risk_score`, `risk_level`, and per-entity `EntityResult` |
| **Compliance profiles** | One-line activation of `india_dpdpa`, `eu_gdpr`, or `us_hipaa` rule packs |
| **Pseudonymization vault** | `scan_with_vault()` replaces PII with reversible `<TYPE_N>` tokens; restore after LLM response |
| **OpenAI adapter** | `wrap_openai(client, shield)` patches `chat.completions.create` in-place |
| **LangChain adapter** | `get_langchain_callback()` returns a `BaseCallbackHandler` that scans prompts automatically |
| **Plug-in detectors** | Subclass `BaseDetector` to add spaCy, ML models, custom patterns |
| **FastAPI middleware** | Drop-in Starlette/FastAPI middleware (optional extra) |
| **Published accuracy** | Precision, recall and F1 per entity type on public datasets ([benchmarks](https://www.totaltensorlab.com/PromptVeil/benchmarks)) |

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

# Accuracy benchmarks (Hugging Face datasets)
pip install "promptveil[bench]"

# Everything
pip install "promptveil[fastapi,openai,langchain,bench,dev]"

# Development (includes pytest and ruff)
pip install "promptveil[dev]"
```

Requires **Python ≥ 3.10**.

## Interactive demo

Try scanning, masking, blocking, compliance profiles, and vault pseudonymization
without installing anything:

- **In your browser:** the [Hugging Face Space](https://huggingface.co/spaces/total-tensor-lab/PromptVeil)
  runs PromptVeil client-side with [Pyodide](https://pyodide.org), so prompts
  never leave the page. Source: [`demo/huggingface/index.html`](demo/huggingface/index.html).
- **In Google Colab:** the full Gradio app, with a temporary public link.
  [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/total-tensor-lab/PromptVeil/blob/master/demo/colab/promptveil_demo.ipynb)

Or run the Gradio app locally:

```bash
pip install promptveil gradio
python demo/huggingface/app.py   # http://localhost:7860
```

To host the Space: create a **Static** Space on Hugging Face, then set the
`HF_TOKEN` secret and `HF_SPACE_ID` variable on this repo — the
`Hugging Face Space` workflow syncs `demo/huggingface/` on every push to `master`.

## Documentation

- [Quickstart](https://www.totaltensorlab.com/PromptVeil/quickstart)
- [API reference](https://www.totaltensorlab.com/PromptVeil/api-reference)
- [Benchmarks](https://www.totaltensorlab.com/PromptVeil/benchmarks)
- [Changelog](https://github.com/total-tensor-lab/PromptVeil/blob/master/CHANGELOG.md)
- [Security policy](https://github.com/total-tensor-lab/PromptVeil/blob/master/SECURITY.md)
- [Contributing](https://github.com/total-tensor-lab/PromptVeil/blob/master/CONTRIBUTING.md)

## Community

- **Tell us what to detect next** in the [detector request thread](https://github.com/total-tensor-lab/PromptVeil/discussions/53).
- **See what's planned** in the [roadmap](ROADMAP.md), and vote with 👍 on the items you need.
- **Contribute a detector:** [good first issues](https://github.com/total-tensor-lab/PromptVeil/labels/good%20first%20issue)
  cover HIPAA identifiers, EU national IDs and more, and each one explains what to build.
- **Ask questions** in [Q&A](https://github.com/total-tensor-lab/PromptVeil/discussions/categories/q-a).

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

Pass `scan_responses=True` to also scan every returned choice with
`shield.scan_response()` (works with `OpenAI` and `AsyncOpenAI`; streaming is
not supported in this mode).

---

## Accuracy

PromptVeil publishes precision, recall and F1 per entity type. Highlights:

- **Email: 99.5% F1** and **credit cards: 96.0% F1** on NVIDIA Nemotron-PII.
- **India IDs: 95.0% recall at 99.3% precision** on PromptVeil-Bench.
- **Overall on Nemotron-PII: 89.6% recall, 69.9% precision.** SSN and phone
  patterns cause most false positives.

Detection is regex and checksum based, so names, addresses and other
free-text PII are out of scope. Full results, limitations and how to reproduce
them are in the [benchmarks page](https://www.totaltensorlab.com/PromptVeil/benchmarks):

```bash
pip install -e ".[bench]"
python -m benchmarks.accuracy.run
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

See the [API reference](https://www.totaltensorlab.com/PromptVeil/api-reference)
for the full public API.

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

Pass `response_field="response"` to also scan that field of 2xx JSON
responses. Blocked replies return `502` with code
`SENSITIVE_DATA_BLOCKED_RESPONSE`.

---

## LangChain Adapter

```python
from promptveil.adapters import get_langchain_callback

CallbackClass = get_langchain_callback()   # lazy-imported; requires langchain-core
callback = CallbackClass(shield)

chat_model.invoke(prompt, config={"callbacks": [callback]})
```

Chat messages are masked in place, and `block` rules raise `SensitiveDataError`.
String LLM prompts can't be masked by a callback, so they raise
`SensitiveDataError` too. Call `shield.scan(prompt)` first to send a masked
prompt. See the [API reference](https://www.totaltensorlab.com/PromptVeil/api-reference#get_langchain_callback).

---

## Audit Log Format

Each log line is a self-contained JSON object:

```json
{
  "event": "prompt_scan",
  "timestamp": "2026-11-21T20:37:03.689005+00:00",
  "prompt_length": 42,
  "detections": 1,
  "entities": [
    {
      "entity_type": "email",
      "action": "mask",
      "value_preview": "a***@example.com",
      "confidence": 1.0,
      "position": {"start": 8, "end": 25}
    }
  ],
  "scan_id": "11b5750eed904b6bafd146d8a4866d9b",
  "method": "scan",
  "risk_score": 0.4,
  "risk_level": "MEDIUM"
}
```

`scan_id` ties together every event from one call, and `method` records which
`Shield` method produced it. Blocked prompts emit a `prompt_blocked` event with
the entity type, confidence, position and prompt length.

Raw sensitive values are **never** stored in logs.

---

## Project Structure

```
promptveil/
├── __init__.py             # Public API: Shield, PseudonymVault, exceptions
├── shield.py               # Main Shield class — orchestration
├── results.py              # ScanResult / EntityResult (scan_detailed)
├── vault.py                # PseudonymVault — reversible <TYPE_N> tokens
├── exceptions.py           # SensitiveDataError, ConfigurationError
├── config/
│   └── loader.py           # YAML loader & validator (incl. `profile:` key)
├── detector/
│   ├── base.py             # BaseDetector ABC + DetectedEntity dataclass
│   ├── regex_detector.py   # Built-in regex patterns (email/phone/card/key)
│   ├── india_detector.py   # Aadhaar, PAN, GSTIN, IFSC, passport, voter ID
│   └── us_detector.py      # SSN, US passport, EIN
├── policy/
│   ├── models.py           # Action enum, Rule, PolicyConfig dataclasses
│   └── engine.py           # PolicyEngine — entity → action lookup
├── profiles/               # india_dpdpa, eu_gdpr, us_hipaa rule packs
├── actions/
│   ├── masker.py           # Per-type masking + apply_masks()
│   └── blocker.py          # block() — raises SensitiveDataError
├── adapters/
│   ├── openai_adapter.py   # wrap_openai()
│   └── langchain_adapter.py  # get_langchain_callback()
├── logger/
│   └── audit_logger.py     # Structured JSON audit logger
└── middleware/
    └── fastapi_middleware.py  # Optional Starlette/FastAPI middleware
benchmarks/accuracy/        # Precision/recall/F1 benchmark runner
demo/                       # Hugging Face Space, Gradio app, Colab notebook
policy.yaml                 # Example policy (mask email/phone, block card/key)
example_usage.py            # Runnable demo
```

---

## Running Tests

```bash
uv run pytest -v
# or: python -m pytest -v
uv run ruff check .   # lint, as run in CI
```

300+ tests, < 1 s.
