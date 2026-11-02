---
id: compliance-profiles
title: Compliance profiles
---

# Compliance profiles

A profile bundles a policy **and** the detectors it needs, so one line gets you
a sensible starting point for a jurisdiction.

| Profile | Masks | Blocks |
|---|---|---|
| `india_dpdpa` | `in_voter_id`, `in_phone`, `in_gstin`, `in_ifsc`, `email`, `phone` | `in_aadhaar`, `in_pan`, `in_passport`, `credit_card`, `api_key` |
| `eu_gdpr` | `email`, `phone` | `credit_card`, `api_key` |
| `us_hipaa` | `email`, `phone`, `us_passport`, `us_ein` | `ssn`, `credit_card`, `api_key` |

## Activate in YAML

```yaml title="policy.yaml"
version: "1.0"
profile: india_dpdpa
```

## Activate in code

```python
from promptveil import Shield
from promptveil.profiles import load_profile, available_profiles

print(available_profiles())  # ['eu_gdpr', 'india_dpdpa', 'us_hipaa']

profile = load_profile("us_hipaa")
shield = Shield(config=profile.policy, detectors=list(profile.detectors))
```

:::warning Not legal advice
Profiles are starting-point presets, not a certification of compliance with
DPDPA, GDPR, HIPAA or any other regulation. Detection is heuristic and may miss
sensitive data. You remain responsible for your own compliance obligations.
:::
