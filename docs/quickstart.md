# PromptShield — Quickstart Guide

This guide walks you through setting up a local development environment,
running the test suite, and using PromptShield in your own code.

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
git clone https://github.com/total-tensor-lab/PromptShield.git
cd PromptShield
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

To also install the optional FastAPI middleware support:

```bash
uv pip install -e ".[dev,fastapi]"
```

> **Tip:** The `-e` flag installs in *editable* mode — any change you make to
> `promptshield/` is immediately reflected without reinstalling.

### Verify the install

```bash
uv run python -c "from promptshield import Shield; print('OK')"
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
collected 62 items

tests/test_config.py::TestLoadConfig::test_valid_config PASSED          [ 1%]
tests/test_detector.py::TestEmailDetection::test_simple_email PASSED    [ 14%]
...
============================== 62 passed in 0.06s ==============================
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
uv run pytest --cov=promptshield --cov-report=term-missing
```

### Test files and what they cover

| File | What it tests |
|---|---|
| `tests/test_config.py` | YAML loader — valid configs, missing files, bad actions |
| `tests/test_detector.py` | Regex patterns — email, phone, credit card, API key, overlap resolution |
| `tests/test_masker.py` | Per-type masking functions and multi-entity substitution |
| `tests/test_policy.py` | Policy engine rule matching, default action, evaluation |
| `tests/test_shield.py` | End-to-end `Shield.scan()` — allow, mask, block, YAML config, `scan_response` |

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

## 4. Using PromptShield in Your Own Code

### Minimal setup — three lines

```python
from promptshield import Shield

shield = Shield(config_path="policy.yaml")
safe_prompt = shield.scan(prompt)
```

### Handle blocked prompts

```python
from promptshield import Shield
from promptshield.exceptions import SensitiveDataError

shield = Shield(config_path="policy.yaml")

try:
    safe = shield.scan(user_input)
    # forward `safe` to your LLM API
except SensitiveDataError as e:
    print(f"Blocked ({e.entity_type}): {e}")
```

### Use a programmatic config instead of a YAML file

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

### Add a custom detector

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

shield = Shield(config=config, detectors=[SSNDetector()])
```

### FastAPI middleware

```python
from fastapi import FastAPI
from promptshield import Shield
from promptshield.middleware import PromptShieldMiddleware

app = FastAPI()
shield = Shield(config_path="policy.yaml")
app.add_middleware(PromptShieldMiddleware, shield=shield, prompt_field="prompt")
```

Every `POST /your-endpoint` with a JSON body that contains `"prompt"` will be
intercepted automatically. Blocked requests receive a `400` response; masked
requests continue to your route handler with the sanitised value.

To run a FastAPI app locally (requires `uvicorn`):

```bash
uv pip install ".[fastapi]" uvicorn
uv run uvicorn my_app:app --reload
```

---

## 5. Policy Configuration Reference

Edit `policy.yaml` to control per-type behaviour.

```yaml
version: "1.0"
default_action: allow   # fallback: mask | block | allow

rules:
  - type: email
    action: mask
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

Built-in entity types detected by `RegexDetector`:

| Type | Example match |
|---|---|
| `email` | `alice@example.com` |
| `phone` | `555-867-5309`, `+442071234567` |
| `credit_card` | `4111-1111-1111-1111` |
| `api_key` | `sk-…`, `ghp_…`, `AKIA…`, JWT tokens |

---

## 6. Project Layout (quick reference)

```
PromptShield/
├── docs/
│   └── quickstart.md        ← you are here
├── promptshield/
│   ├── shield.py            main Shield class
│   ├── exceptions.py        SensitiveDataError, ConfigurationError
│   ├── config/loader.py     YAML loader
│   ├── detector/            BaseDetector + RegexDetector
│   ├── policy/              Action, Rule, PolicyConfig, PolicyEngine
│   ├── actions/             masker.py, blocker.py
│   ├── logger/              structured JSON audit logger
│   └── middleware/          FastAPI/Starlette middleware (optional)
├── tests/                   62 pytest tests
├── example_usage.py         runnable demo
├── policy.yaml              default policy
└── pyproject.toml           package metadata + dependencies
```
