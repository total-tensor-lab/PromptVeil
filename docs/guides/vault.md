---
id: vault
title: Pseudonymization vault
---

# Pseudonymization vault

Masking is one-way. When you need the real values back after the LLM answers,
use `scan_with_vault`: PII is replaced with stable tokens like `<EMAIL_1>`, and
the vault restores them in the response.

```python
from promptveil import Shield, PseudonymVault

shield = Shield(config_path="policy.yaml")
vault = PseudonymVault()

safe = shield.scan_with_vault("Email alice@example.com or call 555-867-5309", vault)
# → "Email <EMAIL_1> or call <PHONE_1>"

reply = call_llm(safe)          # "I'll write to <EMAIL_1> today."
print(vault.restore(reply))     # "I'll write to alice@example.com today."
```

## Things to know

- The same value keeps the same token for the life of the vault.
- `restore` matches exact tokens only; a token the LLM reformats won't be
  restored.
- A vault holds **raw sensitive values in memory**. Use one vault per user or
  session and treat `vault.token_map` as sensitive.
- `PseudonymVault.clear()` drops all mappings.

With the OpenAI adapter, pass `vault=` to `wrap_openai` and call
`vault.restore()` on replies yourself. See [Integrations](integrations.md).
