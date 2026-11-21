"""
PromptVeil — interactive Gradio demo (local and Google Colab).

Run locally::

    pip install promptveil gradio
    python demo/huggingface/app.py

In Colab, ``demo/colab/promptveil_demo.ipynb`` downloads this file and
``core.py`` and calls :func:`launch`. The Hugging Face Space uses
``index.html`` instead, which runs ``core.py`` in the browser.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

import gradio as gr

import core
from core import DEFAULT_POLICY, DETECTORS, EXAMPLES, GENERIC, PRESETS, DemoError
from promptveil import PseudonymVault

# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


def _verdict_html(level: str, score: float, blocked: Optional[str] = None) -> str:
    if blocked:
        color, title = "#dc2626", "Blocked"
        sub = f"Prompt was <b>not</b> forwarded — policy blocks <code>{blocked}</code>."
    else:
        color, title = core.RISK_STYLE.get(level, ("#64748b", level))
        sub = f"Risk score <b>{score:.2f}</b> · level <b>{level}</b>"
    return (
        f'<div class="pv-verdict" style="border-left:6px solid {color}">'
        f'<div class="pv-verdict-title" style="color:{color}">{title}</div>'
        f'<div class="pv-verdict-sub">{sub}</div></div>'
    )


def run_scan(text: str, policy_yaml: str, detector_names: List[str]):
    try:
        r = core.scan(text, policy_yaml, detector_names)
    except DemoError as exc:
        raise gr.Error(str(exc)) from None
    colors: Dict[str, str] = {label: core.ACTION_COLORS[a] for _, label, a in r["segments"] if label}
    highlighted = gr.HighlightedText(value=[(s, label) for s, label, _ in r["segments"]], color_map=colors)
    safe = r["safe_text"] if r["blocked"] is None else "⛔ Blocked — nothing would be sent to the LLM."
    audit = json.dumps(r["audit"], indent=2) if r["audit"] else "// no audit events (nothing masked or blocked)"
    return _verdict_html(r["level"], r["score"], r["blocked"]), highlighted, safe, r["entities"], audit


def run_pseudonymize(text: str, policy_yaml: str, detector_names: List[str]):
    try:
        pseudo, vault, mock = core.pseudonymize(text, policy_yaml, detector_names)
    except DemoError as exc:
        raise gr.Error(str(exc)) from None
    table = [[tok, orig] for tok, orig in vault.token_map.items()]
    return pseudo, table, mock, vault, ""


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
`pip install promptveil` · v{core.VERSION} ·
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
        gr.Code(language="python", value=core.USAGE_SNIPPET)

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


def launch(**kwargs):
    """Launch the demo; extra kwargs (e.g. ``share=True``) go to ``demo.launch``."""
    return demo.launch(theme=gr.themes.Soft(primary_hue="indigo"), css=CSS, **kwargs)


if __name__ == "__main__":
    launch()
