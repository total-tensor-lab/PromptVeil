"""
PromptVeil — interactive Hugging Face Spaces demo.

Run locally::

    pip install promptveil gradio
    python demo/huggingface/app.py
"""

from __future__ import annotations

import io
import json
import logging
import os
import tempfile
import uuid
from typing import Dict, List, Optional, Sequence, Tuple

import gradio as gr
import yaml

import promptveil
from promptveil import PseudonymVault, Shield
from promptveil.detector.base import BaseDetector, DetectedEntity
from promptveil.detector.india_detector import IndiaDetector
from promptveil.detector.regex_detector import RegexDetector
from promptveil.detector.us_detector import USDetector
from promptveil.exceptions import PromptVeilError, SensitiveDataError
from promptveil.logger.audit_logger import AuditLogger
from promptveil.policy.engine import PolicyEngine

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


def _build_shield(policy_yaml: str, detector_names: Sequence[str], logger: AuditLogger) -> Shield:
    try:
        yaml.safe_load(policy_yaml)
    except yaml.YAMLError as exc:
        raise gr.Error(f"Policy YAML is invalid: {exc}") from exc
    if not detector_names:
        raise gr.Error("Select at least one detector.")

    detectors: List[BaseDetector] = [DETECTORS[n]() for n in detector_names]
    fd, path = tempfile.mkstemp(suffix=".yaml")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(policy_yaml)
        return Shield(config_path=path, detectors=detectors, logger=logger)
    except PromptVeilError as exc:
        raise gr.Error(f"Policy error: {exc}") from exc
    finally:
        os.unlink(path)


def _evaluate(shield: Shield, text: str) -> Dict[DetectedEntity, str]:
    """Run detection + policy without enforcing, so blocked prompts can be shown."""
    entities: List[DetectedEntity] = []
    for det in shield._detectors:  # demo-only peek at the configured stack
        entities.extend(det.detect(text))
    evaluated = shield._policy.evaluate(entities) if entities else {}
    return {e: a.value for e, a in evaluated.items()}


def _highlight(text: str, evaluated: Dict[DetectedEntity, str]) -> List[Tuple[str, Optional[str]]]:
    """Split *text* into (segment, label) pairs for gr.HighlightedText."""
    # Prefer block > mask > allow, then longer span, when spans overlap.
    rank = {"block": 0, "mask": 1, "allow": 2}
    spans = sorted(evaluated.items(), key=lambda kv: (kv[0].start, rank[kv[1]], -(kv[0].end - kv[0].start)))
    out: List[Tuple[str, Optional[str]]] = []
    cursor = 0
    for ent, action in spans:
        if ent.start < cursor:
            continue
        if ent.start > cursor:
            out.append((text[cursor:ent.start], None))
        out.append((text[ent.start:ent.end], f"{ent.entity_type} → {action}"))
        cursor = ent.end
    if cursor < len(text):
        out.append((text[cursor:], None))
    return out


def _color_map(evaluated: Dict[DetectedEntity, str]) -> Dict[str, str]:
    return {f"{e.entity_type} → {a}": ACTION_COLORS[a] for e, a in evaluated.items()}


def _verdict_html(level: str, score: float, blocked: Optional[str] = None) -> str:
    if blocked:
        color, title = "#dc2626", "Blocked"
        sub = f"Prompt was <b>not</b> forwarded — policy blocks <code>{blocked}</code>."
    else:
        color, title = RISK_STYLE.get(level, ("#64748b", level))
        sub = f"Risk score <b>{score:.2f}</b> · level <b>{level}</b>"
    return (
        f'<div class="pv-verdict" style="border-left:6px solid {color}">'
        f'<div class="pv-verdict-title" style="color:{color}">{title}</div>'
        f'<div class="pv-verdict-sub">{sub}</div></div>'
    )


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


def run_scan(text: str, policy_yaml: str, detector_names: List[str]):
    text = text or ""
    cap = _CapturingLogger()
    try:
        shield = _build_shield(policy_yaml, detector_names, cap.logger)
        evaluated = _evaluate(shield, text)
        highlighted = gr.HighlightedText(value=_highlight(text, evaluated), color_map=_color_map(evaluated))

        rows = [
            [e.entity_type, a, e.start, e.end, round(e.confidence, 2)]
            for e, a in sorted(evaluated.items(), key=lambda kv: kv[0].start)
        ]

        try:
            result = shield.scan_detailed(text)
        except SensitiveDataError as exc:
            verdict = _verdict_html("CRITICAL", 1.0, blocked=exc.entity_type or "sensitive data")
            safe = "⛔ Blocked — nothing would be sent to the LLM."
        else:
            verdict = _verdict_html(result.risk_level, result.risk_score)
            safe = result.safe_text

        audit = json.dumps(cap.lines(), indent=2) if cap.lines() else "// no audit events (nothing masked or blocked)"
        return verdict, highlighted, safe, rows, audit
    finally:
        cap.close()


def run_pseudonymize(text: str, policy_yaml: str, detector_names: List[str]):
    text = text or ""
    cap = _CapturingLogger()
    try:
        shield = _build_shield(policy_yaml, detector_names, cap.logger)
        try:
            pseudo, vault = shield.scan_with_vault(text, vault=PseudonymVault())
        except SensitiveDataError as exc:
            raise gr.Error(
                f"Blocked by policy ({exc.entity_type}). Switch to “Mask everything” "
                "or change the rule to `mask` to pseudonymize it instead."
            ) from None
        tokens = vault.token_map
        table = [[tok, orig] for tok, orig in tokens.items()]
        if tokens:
            mentions = ", ".join(tokens)
            mock = (
                f"Thanks! I've noted the details ({mentions}). "
                f"I'll follow up using {next(iter(tokens))} shortly."
            )
        else:
            mock = "Nothing to pseudonymize — the prompt contains no masked entities."
        return pseudo, table, mock, vault, ""
    finally:
        cap.close()


def run_restore(reply: str, vault: Optional[PseudonymVault]):
    if vault is None:
        raise gr.Error("Pseudonymize a prompt first.")
    return vault.restore(reply or "")


def load_preset(name: str):
    policy, dets = PRESETS[name]
    return policy, dets


def load_example(text: str, preset: str):
    """Apply an example's preset, then scan it."""
    policy, dets = PRESETS[preset]
    return (policy, dets, *run_scan(text, policy, dets))


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

CSS = """
.pv-hero h1 { margin-bottom: 0.2rem; }
.pv-hero p { opacity: 0.8; margin-top: 0; }
.pv-verdict { padding: 0.75rem 1rem; border-radius: 8px; background: var(--block-background-fill); }
.pv-verdict-title { font-size: 1.25rem; font-weight: 700; }
.pv-verdict-sub { opacity: 0.85; }
footer { visibility: hidden; }
"""

with gr.Blocks(title="PromptVeil — PII shield for LLM prompts") as demo:
    gr.Markdown(
        f"""
<div class="pv-hero">

# 🛡️ PromptVeil

Privacy and safety middleware for LLM apps. Detect PII and secrets in a prompt
**before** it reaches the model, then mask, block, or pseudonymize it by policy.
`pip install promptveil` · v{promptveil.__version__} ·
[GitHub](https://github.com/total-tensor-lab/PromptVeil) ·
[Docs](https://www.totaltensorlab.com/PromptVeil/)

</div>
"""
    )

    with gr.Row():
        with gr.Column(scale=3):
            prompt = gr.Textbox(
                label="Prompt",
                lines=5,
                value=EXAMPLES[0][0],
                placeholder="Paste a prompt containing emails, phone numbers, cards, API keys, Aadhaar, SSN…",
            )
        with gr.Column(scale=2):
            preset = gr.Dropdown(list(PRESETS), value="Default policy", label="Policy preset")
            detectors = gr.CheckboxGroup(list(DETECTORS), value=[GENERIC], label="Detectors")

    with gr.Accordion("Policy YAML (editable)", open=False):
        policy = gr.Code(value=DEFAULT_POLICY, language="yaml", label="policy.yaml")

    with gr.Tabs():
        with gr.Tab("🔍 Scan"):
            scan_btn = gr.Button("Scan prompt", variant="primary")
            verdict = gr.HTML()
            highlighted = gr.HighlightedText(label="Detected entities", combine_adjacent=False, show_legend=True)
            safe_text = gr.Textbox(label="What the LLM receives", lines=3, buttons=["copy"])
            entities = gr.Dataframe(
                headers=["type", "action", "start", "end", "confidence"],
                label="Entities",
                interactive=False,
            )
            with gr.Accordion("Audit log (JSON lines — raw values never logged)", open=False):
                audit = gr.Code(language="json")

        with gr.Tab("🔁 Pseudonymize & restore"):
            gr.Markdown(
                "Replace PII with reversible tokens, let the LLM work on the tokens, "
                "then restore the original values in its reply — the model never sees the raw data."
            )
            vault_state = gr.State(None)
            pseudo_btn = gr.Button("1 · Pseudonymize prompt", variant="primary")
            pseudo_text = gr.Textbox(label="Sent to the LLM", lines=3, buttons=["copy"])
            token_table = gr.Dataframe(headers=["token", "original"], label="Vault (kept on your side)", interactive=False)
            llm_reply = gr.Textbox(label="2 · LLM reply (edit to simulate one)", lines=3)
            restore_btn = gr.Button("3 · Restore originals")
            restored = gr.Textbox(label="Reply shown to the user", lines=3)

    gr.Examples(
        examples=[list(e) for e in EXAMPLES],
        inputs=[prompt, preset],
        outputs=[policy, detectors, verdict, highlighted, safe_text, entities, audit],
        fn=load_example,
        run_on_click=True,
        cache_examples=False,
        label="Try an example",
    )

    with gr.Accordion("Use it in your code", open=False):
        gr.Code(
            language="python",
            value='''from promptveil import Shield, SensitiveDataError

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
''',
        )

    scan_inputs = [prompt, policy, detectors]
    scan_outputs = [verdict, highlighted, safe_text, entities, audit]

    preset.input(load_preset, preset, [policy, detectors]).then(run_scan, scan_inputs, scan_outputs)
    scan_btn.click(run_scan, scan_inputs, scan_outputs)
    prompt.submit(run_scan, scan_inputs, scan_outputs)

    pseudo_btn.click(
        run_pseudonymize,
        scan_inputs,
        [pseudo_text, token_table, llm_reply, vault_state, restored],
    )
    restore_btn.click(run_restore, [llm_reply, vault_state], restored)

    demo.load(run_scan, scan_inputs, scan_outputs)


if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft(primary_hue="indigo"), css=CSS)
