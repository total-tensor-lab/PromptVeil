---
title: PromptVeil
emoji: 🛡️
colorFrom: indigo
colorTo: gray
sdk: gradio
sdk_version: 6.31.0
app_file: app.py
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
  `us_hipaa`) or edit the policy YAML yourself.

Nothing you type is stored; each scan runs in memory.

Full documentation: <https://www.totaltensorlab.com/PromptVeil/>

```bash
pip install promptveil
```
