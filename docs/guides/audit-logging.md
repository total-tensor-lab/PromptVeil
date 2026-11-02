---
id: audit-logging
title: Audit logging
---

# Audit logging

Every scan that masks or blocks something emits one JSON line. **Raw values are
never logged**, only masked previews (or vault tokens).

```json
{"event": "prompt_scan", "timestamp": "2026-05-03T07:34:19+00:00", "prompt_length": 44, "detections": 1, "entities": [{"entity_type": "email", "action": "mask", "value_preview": "a***@example.com", "confidence": 1.0, "position": {"start": 26, "end": 43}}], "scan_id": "886a7d3f…", "method": "scan", "risk_score": 0.4, "risk_level": "MEDIUM"}
```

| Event | Level | When |
|---|---|---|
| `prompt_scan` | `INFO` | Something was masked |
| `prompt_blocked` | `WARNING` | A `block` rule fired |

Each event carries a `scan_id`, the `method` used (`scan`, `scan_response`,
`scan_detailed`, `scan_with_vault`) and, for scans, a `risk_score` and
`risk_level`.

## Sending events elsewhere

Subclass `AuditLogger` and override `log_scan_result` and `log_blocked`. Accept
`**metadata` so new fields don't break your logger.

```python
from promptveil.logger import AuditLogger

class MyLogger(AuditLogger):
    def log_scan_result(self, entity_records, prompt_length, **metadata):
        ship_to_siem(entity_records, prompt_length, metadata)

    def log_blocked(self, entity, **metadata):
        ship_to_siem(entity, metadata)
```

See the [API reference](../api-reference.md#auditlogger) for the full field list.
