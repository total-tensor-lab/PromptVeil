# PromptVeil — Quickstart Guide

This guide walks you through setting up a local development environment,
running the test suite, and using PromptVeil in your own code. For full details
on each class and function, see the [API reference](api-reference.md).

---

## Prerequisites

| Requirement | Minimum version | Notes |
|---|---|---|
| Python | 3.10 | 3.12 recommended |
| [uv](https://docs.astral.sh/uv/) | any recent | fast package manager used in this project |

To check what you have:

```bash
python3 --version
uv --version
```

If `uv` is not installed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 1. Local Environment Setup

### Clone and enter the project

```bash
git clone https://github.com/total-tensor-lab/PromptVeil.git
cd PromptVeil
```

### Create a virtual environment

```bash
uv venv --python 3.12
```

This creates a `.venv/` directory in the project root.

### Install the package

```bash
# Core + dev dependencies (pytest, pytest-cov)
uv pip install -e ".[dev]"
```

To also install optional extras:

```bash
# FastAPI middleware
uv pip install -e ".[dev,fastapi]"

# OpenAI adapter
uv pip install -e ".[dev,openai]"

# LangChain adapter
uv pip install -e ".[dev,langchain]"

# Everything at once
uv pip install -e ".[dev,fastapi,openai,langchain]"
```

> **Tip:** The `-e` flag installs in *editable* mode — any change you make to
> `promptveil/` is immediately reflected without reinstalling.

### Verify the install

```bash
uv run python -c "from promptveil import Shield; print('OK')"
# → OK
```

---

## 2. Running the Test Suite

All tests live in `tests/` and are discovered automatically by pytest.

### Run all tests

```bash
uv run pytest
```

### Run with verbose output (recommended)

```bash
uv run pytest -v
```

Expected output:

```
collected 206 items

tests/test_config.py::TestLoadConfig::test_valid_config PASSED          [ 0%]
tests/test_detector.py::TestEmailDetection::test_simple_email PASSED    [ 1%]
...
============================== 206 passed in 0.62s ==============================
```

### Run a specific test file

```bash
uv run pytest tests/test_shield.py -v
```

### Run a specific test class or function

```bash
# All tests in a class
uv run pytest tests/test_detector.py::TestEmailDetection -v

# A single test function
uv run pytest tests/test_shield.py::TestShieldBlock::test_blocks_api_key -v
```

### Run with coverage report

```bash
uv run pytest --cov=promptveil --cov-report=term-missing
```

### Test files and what they cover

| File | What it tests |
|---|---|
| `tests/test_config.py` | YAML loader — valid configs, missing files, bad actions |
| `tests/test_detector.py` | Regex patterns — email, phone, credit card, API key, overlap resolution |
| `tests/test_india_detector.py` | India PII — Aadhaar Verhoeff checksum, PAN, GSTIN, IFSC, Passport, Voter ID |
| `tests/test_masker.py` | Per-type masking functions and multi-entity substitution |
| `tests/test_policy.py` | Policy engine rule matching, default action, evaluation |
| `tests/test_shield.py` | End-to-end `Shield.scan()` — allow, mask, block, YAML config, `scan_response` |
| `tests/test_middleware.py` | FastAPI middleware — mask path, block path, non-JSON passthrough |
| `tests/test_confidence.py` | `DetectedEntity.confidence`, `Rule.min_confidence`, threshold enforcement |
| `tests/test_results.py` | `ScanResult`, `EntityResult`, risk scoring, `scan_detailed()` |
| `tests/test_profiles.py` | Profile registry, YAML `profile:` key, end-to-end scans per jurisdiction |
| `tests/test_vault.py` | `PseudonymVault` token lifecycle, restore, `scan_with_vault()` round-trip |
| `tests/test_adapters.py` | OpenAI and LangChain adapter integration and error paths |

---

## 3. Running the Example Script

`example_usage.py` at the project root demonstrates all major features with
six self-contained scenarios.

```bash
uv run python example_usage.py
```

### What each example shows

| Example | Scenario |
|---|---|
| **1** | Load `policy.yaml`; scan prompts containing email and phone — values are masked |
| **2** | Prompt containing an OpenAI API key — `SensitiveDataError` is raised and caught |
| **3** | Prompt containing a credit card number — blocked, error caught |
| **4** | Programmatic config (no YAML file) — mask email, block credit card |
| **5** | Custom plug-in detector for US Social Security Numbers (SSN) |
| **6** | `scan_response()` — sanitise LLM output before returning it to the user |

Audit log lines (JSON) are printed to stdout alongside the sanitised prompts.

---

## 4. Running Benchmarks

The repository includes a dedicated benchmark suite under `benchmarks/` built
on `pytest-benchmark` plus `tracemalloc`-based memory sampling.

### Run the full suite

```bash
uv run python benchmarks/run_benchmarks.py
```

This writes a timestamped JSON report to `benchmarks/results/` and prints a
terminal summary table with mean latency, percentile latency, throughput, and
peak memory where available.
The JSON keeps aggregate statistics, P50/P95/P99, workload parameter IDs, and
workload/memory metadata, plus minimal machine info (OS, architecture, Python
version, CPU model and core count) so results can be compared across machines.
Raw timing samples, full test inputs, hostname, and Git commit information are
omitted to keep reports small and easy to share.

### Pass through extra pytest arguments

```bash
# Only run scan hot-path benchmarks
uv run python benchmarks/run_benchmarks.py -k scan_latency

# Collect benchmarks without executing them
uv run python benchmarks/run_benchmarks.py -- --collect-only
```

The default `pytest` configuration still targets `tests/`, so benchmarks only
run when you explicitly invoke the `benchmarks/` path or the runner script.

---

## 5. Using PromptVeil in Your Own Code

### Minimal setup — three lines

```python
from promptveil import Shield

shield = Shield(config_path="policy.yaml")
safe_prompt = shield.scan(prompt)
```

### Handle blocked prompts

```python
from promptveil import Shield
from promptveil.exceptions import SensitiveDataError

shield = Shield(config_path="policy.yaml")

try:
    safe = shield.scan(user_input)
    # forward `safe` to your LLM API
except SensitiveDataError as e:
    print(f"Blocked ({e.entity_type}): {e}")
```

### Use a programmatic config instead of a YAML file

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

`min_confidence` is optional (default `0.0`). When a detector’s confidence for an entity is below the rule threshold, the rule is skipped and `default_action` applies.

### Rich scan results with risk scoring

```python
result = shield.scan_detailed("Contact alice@example.com or call 555-867-5309")
print(result.risk_score)    # e.g. 0.52
print(result.risk_level)    # "MEDIUM"
print(result.safe_text)     # sanitised prompt
print(result.was_mutated)   # True

for entity in result.entities:
    print(entity.entity_type, entity.action, entity.masked_value)
```

`risk_level` thresholds: `NONE` = 0.0, `LOW` < 0.30, `MEDIUM` < 0.60, `HIGH` < 0.85, `CRITICAL` ≥ 0.85.

### Activate a compliance profile

```yaml
# policy.yaml — activate with a single key
profile: india_dpdpa   # or eu_gdpr / us_hipaa
```

```python
shield = Shield(config_path="policy.yaml")  # profile detectors loaded automatically
```

Or programmatically:

```python
from promptveil.profiles import load_profile

profile = load_profile("us_hipaa")
shield = Shield(config=profile.policy, detectors=profile.detectors)
```

Available profiles:

| Profile | Detectors bundled | Notable rules |
|---|---|---|
| `india_dpdpa` | `RegexDetector` + `IndiaDetector` | Aadhaar/PAN/Passport → BLOCK |
| `eu_gdpr` | `RegexDetector` | email/phone → MASK; card/key → BLOCK |
| `us_hipaa` | `RegexDetector` + `USDetector` | SSN → BLOCK; passport/EIN → MASK |

### Pseudonymization vault (reversible)

```python
from promptveil import PseudonymVault

vault = PseudonymVault()
pseudo, vault = shield.scan_with_vault(
    "Email alice@example.com or call 555-867-5309",
    vault=vault,
)
# pseudo → "Email <EMAIL_1> or call <PHONE_1>"

llm_response = call_llm(pseudo)        # LLM sees tokens, not real PII
final = vault.restore(llm_response)    # swap tokens back in the reply
```

Pass the same `vault` instance across multiple turns to keep tokens stable throughout a conversation.

### Add a custom detector

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

shield = Shield(config=config, detectors=[SSNDetector()])
```

### FastAPI middleware

```python
from fastapi import FastAPI
from promptveil import Shield
from promptveil.middleware import PromptVeilMiddleware

app = FastAPI()
shield = Shield(config_path="policy.yaml")
app.add_middleware(PromptVeilMiddleware, shield=shield, prompt_field="prompt")
```

Every `POST /your-endpoint` with a JSON body that contains `"prompt"` will be
intercepted automatically. Blocked requests receive a `400` response; masked
requests continue to your route handler with the sanitised value.

To run a FastAPI app locally (requires `uvicorn`):

```bash
uv pip install ".[fastapi]" uvicorn
uv run uvicorn my_app:app --reload
```

### OpenAI adapter

Install the extra, then wrap your client once:

```bash
uv pip install ".[openai]"
```

```python
import openai
from promptveil.adapters import wrap_openai

client = openai.OpenAI()
wrap_openai(client, shield=shield)   # patches client in-place

# All subsequent calls are scanned automatically:
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": user_prompt}],
)
```

Optionally pass a `PseudonymVault` to `wrap_openai` for reversible pseudonymization instead of permanent masking.

### LangChain adapter

```bash
uv pip install ".[langchain]"
```

```python
from promptveil.adapters import get_langchain_callback

CallbackClass = get_langchain_callback()
callback = CallbackClass(shield)

# Pass as a callback to a chat model:
chat_model.invoke(prompt, config={"callbacks": [callback]})
```

Chat messages are masked in place, and `block` rules raise `SensitiveDataError`.
String LLM prompts can't be masked by a callback, so they raise
`SensitiveDataError` too. Call `shield.scan(prompt)` first to send a masked
prompt. See the [API reference](api-reference.md#get_langchain_callback).

---

## 5. Policy Configuration Reference

Edit `policy.yaml` to control per-type behaviour.

```yaml
version: "1.0"
default_action: allow   # fallback: mask | block | allow

# Optional: activate a jurisdiction compliance profile
# profile: india_dpdpa  # or eu_gdpr | us_hipaa

rules:
  - type: email
    action: mask
    min_confidence: 0.8   # optional; skip rule when confidence < 0.8
  - type: phone
    action: mask
  - type: credit_card
    action: block
  - type: api_key
    action: block
```

| Action | Behaviour |
|---|---|
| `mask` | Replaces sensitive value with a partially-hidden placeholder |
| `block` | Raises `SensitiveDataError` — prompt is never forwarded |
| `allow` | Passes through unchanged |

Built-in entity types:

| Type | Source detector | Example match |
|---|---|---|
| `email` | `RegexDetector` | `alice@example.com` |
| `phone` | `RegexDetector` | `555-867-5309`, `+442071234567` |
| `credit_card` | `RegexDetector` | `4111-1111-1111-1111` |
| `api_key` | `RegexDetector` | `sk-…`, `ghp_…`, `AKIA…`, JWT tokens |
| `in_aadhaar` | `IndiaDetector` | `1234 5678 9012` (Verhoeff-validated) |
| `in_pan` | `IndiaDetector` | `ABCDE1234F` |
| `in_gstin` | `IndiaDetector` | `22AAAAA0000A1Z5` |
| `in_ifsc` | `IndiaDetector` | `SBIN0001234` |
| `in_passport` | `IndiaDetector` | `A1234567` |
| `in_voter_id` | `IndiaDetector` | `ABC1234567` |
| `in_phone` | `IndiaDetector` | `+91 98765 43210` |
| `ssn` | `USDetector` | `123-45-6789` (segment-validated) |
| `us_passport` | `USDetector` | `A12345678` |
| `us_ein` | `USDetector` | `12-3456789` |

---

## 6. Project Layout (quick reference)

```
PromptVeil/
├── docs/
│   └── quickstart.md        ← you are here
├── promptveil/
│   ├── shield.py            main Shield class (scan / scan_detailed / scan_with_vault)
│   ├── exceptions.py        SensitiveDataError, ConfigurationError
│   ├── results.py           ScanResult, EntityResult, risk scoring
│   ├── vault.py             PseudonymVault — reversible pseudonymization
│   ├── config/loader.py     YAML loader (supports `profile:` key)
│   ├── detector/            BaseDetector + RegexDetector + IndiaDetector + USDetector
│   ├── profiles/            india_dpdpa, eu_gdpr, us_hipaa compliance packs
│   ├── adapters/            wrap_openai(), get_langchain_callback()
│   ├── policy/              Action, Rule (min_confidence), PolicyConfig, PolicyEngine
│   ├── actions/             masker.py, blocker.py
│   ├── logger/              structured JSON audit logger
│   └── middleware/          FastAPI/Starlette middleware (optional)
├── tests/                   234 pytest tests
├── example_usage.py         runnable demo
├── policy.yaml              default policy
└── pyproject.toml           package metadata + dependencies
```
