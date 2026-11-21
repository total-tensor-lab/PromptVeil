"""
UI-independent logic for the PromptVeil demo.

Shared by two front ends so the behaviour stays identical:

- ``index.html`` — the Hugging Face Space. Runs this file in the visitor's
  browser with Pyodide and calls the ``*_json`` functions.
- ``app.py`` — the Gradio app used locally and in Google Colab.

Depends only on ``promptveil`` (and PyYAML), so it must not import gradio.
"""

from __future__ import annotations

import io
import json
import logging
import os
import tempfile
import uuid
from typing import Dict, List, Optional, Sequence, Tuple

import yaml

import promptveil
from promptveil import PseudonymVault, Shield
from promptveil.detector.base import BaseDetector, DetectedEntity
from promptveil.detector.india_detector import IndiaDetector
from promptveil.detector.regex_detector import RegexDetector
from promptveil.detector.us_detector import USDetector
from promptveil.exceptions import PromptVeilError, SensitiveDataError
from promptveil.logger.audit_logger import AuditLogger

VERSION = promptveil.__version__

# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------

DETECTORS: Dict[str, type] = {
    "Generic (email, phone, card, API key)": RegexDetector,
    "India (Aadhaar, PAN, GSTIN, IFSC, …)": IndiaDetector,
    "US (SSN, passport, EIN)": USDetector,
}
GENERIC, INDIA, US = list(DETECTORS)

DEFAULT_POLICY = """\
version: "1.0"
default_action: allow   # fallback: mask | block | allow

rules:
  - type: email
    action: mask        # a***@example.com
  - type: phone
    action: mask        # ***-***-5309
  - type: credit_card
    action: block       # never forward card numbers
  - type: api_key
    action: block       # leaking a key is a security incident
"""

PRESETS: Dict[str, Tuple[str, List[str]]] = {
    "Default policy": (DEFAULT_POLICY, [GENERIC]),
    "India DPDPA profile": (
        'version: "1.0"\nprofile: india_dpdpa\n\n# Optional per-type overrides:\n'
        "# rules:\n#   - type: in_pan\n#     action: mask\n",
        [GENERIC, INDIA],
    ),
    "EU GDPR profile": (
        'version: "1.0"\nprofile: eu_gdpr\n\n# Optional per-type overrides:\n'
        "# rules:\n#   - type: email\n#     action: allow\n",
        [GENERIC],
    ),
    "US HIPAA profile": (
        'version: "1.0"\nprofile: us_hipaa\n\n# Optional per-type overrides:\n'
        "# rules:\n#   - type: ssn\n#     action: mask\n",
        [GENERIC, US],
    ),
    "Mask everything (no blocking)": (
        'version: "1.0"\ndefault_action: mask\nrules: []\n',
        [GENERIC, INDIA, US],
    ),
}

EXAMPLES: List[Tuple[str, str]] = [
    ("Contact alice@example.com or call 555-867-5309 about the invoice.", "Default policy"),
    ("Charge card 4111-1111-1111-1111 for $99 and email bob@acme.io.", "Default policy"),
    ("Debug this: client = OpenAI(api_key='sk-abcdefABCDEF12345678901234')", "Default policy"),
    ("Customer GSTIN 27AAPFU0939F1ZV, IFSC SBIN0001234, phone +91 98765 43210.", "India DPDPA profile"),
    ("My Aadhaar is 2345 6789 0124 and PAN ABCPE1234F — please verify.", "India DPDPA profile"),
    ("Patient SSN 123-45-6789, reachable at jdoe@clinic.org.", "US HIPAA profile"),
    ("Vendor EIN 43-5478236; send the W-9 to ap@vendor.com.", "Mask everything (no blocking)"),
]

ACTION_COLORS = {"mask": "#f59e0b", "block": "#ef4444", "allow": "#22c55e"}

RISK_STYLE = {
    "NONE": ("#16a34a", "No sensitive data found"),
    "LOW": ("#65a30d", "Low risk"),
    "MEDIUM": ("#d97706", "Medium risk"),
    "HIGH": ("#ea580c", "High risk"),
    "CRITICAL": ("#dc2626", "Critical risk"),
}

USAGE_SNIPPET = '''from promptveil import Shield, SensitiveDataError

shield = Shield(config_path="policy.yaml")   # or: profile: india_dpdpa

try:
    result = shield.scan_detailed(user_prompt)
    send_to_llm(result.safe_text)            # masked prompt
    print(result.risk_level, result.risk_score)
except SensitiveDataError as exc:
    print("blocked:", exc.entity_type)

# Drop-in for OpenAI clients
from promptveil.adapters import wrap_openai
wrap_openai(client, shield=shield)
'''


class DemoError(ValueError):
    """A user-facing error (bad YAML, no detectors, blocked pseudonymization)."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _CapturingLogger:
    """An AuditLogger whose JSON lines go to an in-memory buffer."""

    def __init__(self) -> None:
        self.buffer = io.StringIO()
        self._name = f"promptveil.demo.{uuid.uuid4().hex}"
        self.logger = AuditLogger(name=self._name, stream=self.buffer)

    def lines(self) -> List[dict]:
        out = []
        for line in self.buffer.getvalue().splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    def close(self) -> None:
        log = logging.getLogger(self._name)
        for h in list(log.handlers):
            log.removeHandler(h)
        logging.Logger.manager.loggerDict.pop(self._name, None)


def build_shield(policy_yaml: str, detector_names: Sequence[str], logger: AuditLogger) -> Shield:
    try:
        yaml.safe_load(policy_yaml)
    except yaml.YAMLError as exc:
        raise DemoError(f"Policy YAML is invalid: {exc}") from exc
    if not detector_names:
        raise DemoError("Select at least one detector.")

    detectors: List[BaseDetector] = [DETECTORS[n]() for n in detector_names]
    fd, path = tempfile.mkstemp(suffix=".yaml")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(policy_yaml)
        return Shield(config_path=path, detectors=detectors, logger=logger)
    except PromptVeilError as exc:
        raise DemoError(f"Policy error: {exc}") from exc
    finally:
        os.unlink(path)


def evaluate(shield: Shield, text: str) -> Dict[DetectedEntity, str]:
    """Run detection + policy without enforcing, so blocked prompts can be shown."""
    entities: List[DetectedEntity] = []
    for det in shield._detectors:  # demo-only peek at the configured stack
        entities.extend(det.detect(text))
    evaluated = shield._policy.evaluate(entities) if entities else {}
    return {e: a.value for e, a in evaluated.items()}


def segments(text: str, evaluated: Dict[DetectedEntity, str]) -> List[Tuple[str, Optional[str], Optional[str]]]:
    """Split *text* into ``(segment, label, action)`` triples; label is None for plain text."""
    # Prefer block > mask > allow, then longer span, when spans overlap.
    rank = {"block": 0, "mask": 1, "allow": 2}
    spans = sorted(evaluated.items(), key=lambda kv: (kv[0].start, rank[kv[1]], -(kv[0].end - kv[0].start)))
    out: List[Tuple[str, Optional[str], Optional[str]]] = []
    cursor = 0
    for ent, action in spans:
        if ent.start < cursor:
            continue
        if ent.start > cursor:
            out.append((text[cursor:ent.start], None, None))
        out.append((text[ent.start:ent.end], f"{ent.entity_type} → {action}", action))
        cursor = ent.end
    if cursor < len(text):
        out.append((text[cursor:], None, None))
    return out


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


def scan(text: str, policy_yaml: str, detector_names: Sequence[str]) -> dict:
    """Detect, evaluate, and enforce. Returns plain data for any front end.

    Keys: ``level``, ``score``, ``blocked`` (entity type or None),
    ``segments``, ``safe_text`` (None when blocked), ``entities`` (rows of
    type/action/start/end/confidence), ``audit`` (list of audit events).
    """
    text = text or ""
    cap = _CapturingLogger()
    try:
        shield = build_shield(policy_yaml, detector_names, cap.logger)
        evaluated = evaluate(shield, text)
        rows = [
            [e.entity_type, a, e.start, e.end, round(e.confidence, 2)]
            for e, a in sorted(evaluated.items(), key=lambda kv: kv[0].start)
        ]
        try:
            result = shield.scan_detailed(text)
        except SensitiveDataError as exc:
            level, score, blocked, safe = "CRITICAL", 1.0, exc.entity_type or "sensitive data", None
        else:
            level, score, blocked, safe = result.risk_level, result.risk_score, None, result.safe_text
        return {
            "level": level,
            "score": score,
            "blocked": blocked,
            "segments": segments(text, evaluated),
            "safe_text": safe,
            "entities": rows,
            "audit": cap.lines(),
        }
    finally:
        cap.close()


def pseudonymize(text: str, policy_yaml: str, detector_names: Sequence[str]) -> Tuple[str, PseudonymVault, str]:
    """Return ``(pseudonymized_text, vault, mock_llm_reply)``."""
    text = text or ""
    cap = _CapturingLogger()
    try:
        shield = build_shield(policy_yaml, detector_names, cap.logger)
        try:
            pseudo, vault = shield.scan_with_vault(text, vault=PseudonymVault())
        except SensitiveDataError as exc:
            raise DemoError(
                f"Blocked by policy ({exc.entity_type}). Switch to “Mask everything” "
                "or change the rule to `mask` to pseudonymize it instead."
            ) from None
        tokens = vault.token_map
        if tokens:
            mock = (
                f"Thanks! I've noted the details ({', '.join(tokens)}). "
                f"I'll follow up using {next(iter(tokens))} shortly."
            )
        else:
            mock = "Nothing to pseudonymize — the prompt contains no masked entities."
        return pseudo, vault, mock
    finally:
        cap.close()


# ---------------------------------------------------------------------------
# JSON bridge for the in-browser page (index.html)
# ---------------------------------------------------------------------------

_browser_vault: Optional[PseudonymVault] = None


def _guard(fn):
    def wrapper(*args):
        try:
            return json.dumps({"ok": True, **fn(*args)})
        except DemoError as exc:
            return json.dumps({"ok": False, "error": str(exc)})

    return wrapper


def config_json() -> str:
    return json.dumps(
        {
            "version": VERSION,
            "detectors": list(DETECTORS),
            "presets": {k: {"policy": p, "detectors": d} for k, (p, d) in PRESETS.items()},
            "examples": EXAMPLES,
            "colors": ACTION_COLORS,
            "risk": RISK_STYLE,
            "snippet": USAGE_SNIPPET,
        }
    )


@_guard
def scan_json(text: str, policy_yaml: str, detectors_json: str) -> dict:
    return scan(text, policy_yaml, json.loads(detectors_json))


@_guard
def pseudonymize_json(text: str, policy_yaml: str, detectors_json: str) -> dict:
    global _browser_vault
    pseudo, _browser_vault, mock = pseudonymize(text, policy_yaml, json.loads(detectors_json))
    return {"text": pseudo, "tokens": list(_browser_vault.token_map.items()), "reply": mock}


@_guard
def restore_json(reply: str) -> dict:
    if _browser_vault is None:
        raise DemoError("Pseudonymize a prompt first.")
    return {"text": _browser_vault.restore(reply or "")}
