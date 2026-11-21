---
title: PromptVeil
emoji: 🛡️
colorFrom: indigo
colorTo: gray
sdk: static
app_file: index.html
pinned: false
license: mit
short_description: Mask, block, or pseudonymize PII before it reaches an LLM
tags:
  - pii
  - privacy
  - llm
  - redaction
  - security
---

# PromptVeil — interactive demo

[PromptVeil](https://github.com/total-tensor-lab/PromptVeil) is privacy and
safety middleware for LLM applications. It scans prompts **before** they reach
an LLM API, detects PII and secrets, and applies a YAML policy
(`mask` · `block` · `allow`).

This Space lets you try it in the browser:

- **Scan** — see every detected entity, the action the policy takes, the risk
  score, the sanitised prompt, and the JSON audit log (raw values are never
  logged).
- **Pseudonymize & restore** — swap PII for reversible `<EMAIL_1>`-style
  tokens, "send" them to an LLM, and restore the originals in the reply.
- **Policy** — pick a compliance profile (`india_dpdpa`, `eu_gdpr`,
  `us_hipaa`), toggle detectors, or edit the policy YAML yourself.
- **Examples & code** — one-click example prompts, and a snippet showing the
  same setup in your own code.

The Space runs PromptVeil 0.3.0 from PyPI. Detection is regex and checksum
based; see the [accuracy benchmarks](https://www.totaltensorlab.com/PromptVeil/benchmarks)
for precision and recall per entity type.

**Your text never leaves your browser.** The page runs PromptVeil in Python
via [Pyodide](https://pyodide.org) — there is no server. The first visit
downloads about 10 MB; after that it is cached.

Prefer the full Gradio app?
[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/total-tensor-lab/PromptVeil/blob/master/demo/colab/promptveil_demo.ipynb)

Full documentation: <https://www.totaltensorlab.com/PromptVeil/>

```bash
pip install promptveil
```
