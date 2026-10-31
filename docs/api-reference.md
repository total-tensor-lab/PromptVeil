# PromptVeil — API Reference

Reference for the public API of PromptVeil 0.1.3. For setup and walkthroughs,
see the [Quickstart](quickstart.md).

PromptVeil is alpha software, so this API may change between releases. Anything
not listed here, including `PolicyEngine`, `promptveil.actions`, and names
starting with an underscore, is internal.

| Import from | Names |
|---|---|
| `promptveil` | [`Shield`](#shield), [`ScanResult`](#scanresult), [`EntityResult`](#entityresult), [`PseudonymVault`](#pseudonymvault), [`PromptVeilError`](#exceptions), [`SensitiveDataError`](#exceptions), [`ConfigurationError`](#exceptions) |
| `promptveil.policy` | [`Action`](#action), [`Rule`](#rule), [`PolicyConfig`](#policyconfig) |
| `promptveil.config` | [`load_config`](#load_config) |
| `promptveil.profiles` | [`load_profile`](#load_profile), [`available_profiles`](#available_profiles), [`Profile`](#profile) |
| `promptveil.detector` | [`BaseDetector`](#basedetector), [`DetectedEntity`](#detectedentity), [`RegexDetector`](#built-in-detectors), [`IndiaDetector`](#built-in-detectors) |
| `promptveil.detector.us_detector` | [`USDetector`](#built-in-detectors) |
| `promptveil.logger` | [`AuditLogger`](#auditlogger) |
| `promptveil.adapters` | [`wrap_openai`](#wrap_openai), [`get_langchain_callback`](#get_langchain_callback) |
| `promptveil.middleware` | [`PromptVeilMiddleware`](#promptveilmiddleware) |

---

## Shield

```python
Shield(config_path=None, config=None, detectors=None, logger=None)
```

Runs detection, policy evaluation, masking, and audit logging.

| Param | Type | Description |
|---|---|---|
| `config_path` | `str \| Path` | Path to a YAML policy file. See [YAML policy files](#yaml-policy-files) |
| `config` | `PolicyConfig` | Pre-built policy, used instead of a YAML file |
| `detectors` | `list[BaseDetector]` | Detectors to run, in order |
| `logger` | `AuditLogger` | Audit logger. Default: JSON lines to `stdout` |

Provide exactly one of `config_path` or `config`. Anything else raises
`ConfigurationError`, as does a missing or invalid YAML file.

Detectors are chosen in this order: the `detectors` argument, then the
detectors of the YAML file's `profile:`, then `[RegexDetector()]`.

### `scan`

```python
shield.scan(prompt: str) -> str
```

Returns `prompt` with `mask` entities redacted. The original string is returned
when nothing needs masking.

**Raises:** `SensitiveDataError` if any detected entity resolves to `block`.
`TypeError` if `prompt` is not a `str`.

Block rules are checked against every match before any masking happens. If mask
spans overlap, the longer span wins. On a tie, the span that starts first wins,
then the detector registered first.

### `scan_response`

```python
shield.scan_response(response: str) -> str
```

Same as `scan`, for LLM output. It can raise `SensitiveDataError` too.

### `scan_detailed`

```python
shield.scan_detailed(prompt: str) -> ScanResult
```

Same policy behavior as `scan`, including raising on `block`, but returns a
[`ScanResult`](#scanresult) with per-entity detail and a risk score.

### `scan_with_vault`

```python
shield.scan_with_vault(
    prompt: str,
    vault: PseudonymVault | None = None,
) -> tuple[str, PseudonymVault]
```

Replaces `mask` entities with reversible tokens such as `<EMAIL_1>` instead of
masked values. Entities that resolve to `block` still raise
`SensitiveDataError`, and `allow` entities are left as they are. Pass the same
vault on each turn of a conversation to keep tokens consistent. A new vault is
created when `vault` is `None`.

```python
safe, vault = shield.scan_with_vault("Email john@acme.com")
# safe → "Email <EMAIL_1>"

reply = call_llm(safe)
print(vault.restore(reply))
```

### `add_detector`

```python
shield.add_detector(detector: BaseDetector) -> None
```

Appends a detector to the end of the list this `Shield` is using.

> **Warning:** That list isn't copied. For a `Shield` built from a YAML
> `profile:` it's the list shared by every `Shield` using that profile, so the
> new detector applies to all of them. To add a detector to one profile-based
> `Shield`, pass your own list instead:
>
> ```python
> detectors = [*load_profile("us_hipaa").detectors, MyDetector()]
> shield = Shield(config_path="policy.yaml", detectors=detectors)
> ```

---

## Results

### `ScanResult`

Frozen dataclass returned by [`scan_detailed`](#scan_detailed).

| Field | Type | Description |
|---|---|---|
| `safe_text` | `str` | Text with masks applied |
| `entities` | `list[EntityResult]` | Entities and the action taken on each |
| `risk_score` | `float` | Composite risk from `0.0` to `1.0`, rounded to 4 places |
| `risk_level` | `str` | `NONE`, `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL` |
| `was_mutated` | `bool` | `True` if any masking was applied |

`entities` includes `allow` entities. It leaves out `mask` entities that lost an
overlap with a longer span.

| `risk_level` | `risk_score` |
|---|---|
| `NONE` | `0.0` |
| `LOW` | below `0.30` |
| `MEDIUM` | below `0.60` |
| `HIGH` | below `0.85` |
| `CRITICAL` | `0.85` or above |

The score combines every reported entity:

```text
score = 1 - product(1 - weight × confidence × allow_factor)
```

`allow_factor` is `0.3` for `allow` entities and `1.0` otherwise. Weights are
listed under [Entity types](#entity-types). Any other type uses `0.35`.

### `EntityResult`

Frozen dataclass describing one entity in a `ScanResult`.

| Field | Type | Description |
|---|---|---|
| `entity_type` | `str` | For example `"email"` |
| `action` | `str` | `"mask"` or `"allow"`. A `block` raises, so no result is produced |
| `start` | `int` | Start index in the original prompt |
| `end` | `int` | End index in the original prompt (exclusive) |
| `masked_value` | `str` | The masked form. For `allow`, this is the **original value** |
| `confidence` | `float` | Detector confidence from `0.0` to `1.0` |

---

## Exceptions

```text
Exception
└── PromptVeilError
    ├── SensitiveDataError
    └── ConfigurationError
```

| Exception | Raised when |
|---|---|
| `PromptVeilError` | Never directly. Catch it to handle both errors below |
| `SensitiveDataError` | An entity resolves to `block`. `entity_type` holds the type. Neither the message nor the attribute contains the sensitive value |
| `ConfigurationError` | A policy can't be loaded or is invalid, or a profile name is unknown |

```python
from promptveil import SensitiveDataError

try:
    safe = shield.scan(prompt)
except SensitiveDataError as exc:
    print(f"Blocked: {exc.entity_type}")
```

---

## Policy

Import these from `promptveil.policy`.

### `Action`

String enum with the values `Action.MASK` (`"mask"`), `Action.BLOCK` (`"block"`),
and `Action.ALLOW` (`"allow"`).

### `Rule`

```python
Rule(type: str, action: Action, min_confidence: float = 0.0)
```

| Field | Description |
|---|---|
| `type` | Entity type to match. See [Entity types](#entity-types) |
| `action` | Action to take |
| `min_confidence` | Minimum detector confidence for the rule to apply |

An entity below `min_confidence` gets the policy's `default_action`, not the
rule's action. If a policy has more than one rule for a type, the last one wins.

### `PolicyConfig`

```python
PolicyConfig(rules: list[Rule], default_action: Action = Action.ALLOW, version: str = "1.0")
```

`default_action` applies to detected entities with no matching rule.
`PolicyConfig` and `Rule` don't validate their values. Only YAML files are
validated, so a `min_confidence` outside `0.0`–`1.0` is accepted in code.

```python
from promptveil import Shield
from promptveil.policy import Action, PolicyConfig, Rule

shield = Shield(
    config=PolicyConfig(
        rules=[
            Rule(type="email", action=Action.MASK, min_confidence=0.8),
            Rule(type="api_key", action=Action.BLOCK),
        ],
    ),
)
```

### YAML policy files

| Key | Required | Description |
|---|---|---|
| `version` | No | Schema version string. Default: `"1.0"` |
| `default_action` | No | `mask`, `block`, or `allow`. Default: the profile's value, otherwise `allow` |
| `profile` | No | Built-in [profile](#compliance-profiles) to use as the base policy |
| `rules` | No | List of rules. With `profile`, each one replaces that profile's rule for the same type |

Each rule takes `type`, `action`, and optionally `min_confidence`.

```yaml
profile: eu_gdpr
default_action: allow
rules:
  - type: email
    action: allow
  - type: phone
    action: mask
    min_confidence: 0.8
```

### `load_config`

```python
load_config(config_path: str | Path) -> PolicyConfig
```

Loads and validates a YAML policy without building a `Shield`. Profile rules are
merged in, but the profile's detectors aren't returned, so use
`Shield(config_path=...)` when you need them.

**Raises:** `ConfigurationError` if the file is missing, isn't valid YAML, or has
invalid fields. A non-numeric `min_confidence` raises `ValueError` instead.

---

## Compliance profiles

Import these from `promptveil.profiles`.

| Profile | Detectors | Masks | Blocks |
|---|---|---|---|
| `india_dpdpa` | `RegexDetector`, `IndiaDetector` | `in_voter_id`, `in_phone`, `in_gstin`, `in_ifsc`, `email`, `phone` | `in_aadhaar`, `in_pan`, `in_passport`, `credit_card`, `api_key` |
| `eu_gdpr` | `RegexDetector` | `email`, `phone` | `credit_card`, `api_key` |
| `us_hipaa` | `RegexDetector`, `USDetector` | `email`, `phone`, `us_passport`, `us_ein` | `ssn`, `credit_card`, `api_key` |

All three have a `default_action` of `allow`.

> **Disclaimer:** Profiles are starting-point policy presets, not legal advice
> and not a certification of compliance with DPDPA, GDPR, HIPAA, or any other
> regulation. Detection is heuristic and may miss sensitive data. You remain
> responsible for your own compliance obligations.

### `load_profile`

```python
load_profile(name: str) -> Profile
```

Returns a built-in profile. **Raises** `ConfigurationError` if the name is
unknown.

The returned object is shared, so copy its lists before changing them:

```python
profile = load_profile("us_hipaa")
shield = Shield(config=profile.policy, detectors=list(profile.detectors))
```

### `available_profiles`

```python
available_profiles() -> list[str]
```

Returns the registered profile names, sorted.

### `Profile`

Dataclass with the fields `name: str`, `policy: PolicyConfig`, and
`detectors: list[BaseDetector]`.

---

## Detectors

Import these from `promptveil.detector`, except `USDetector`, which is in
`promptveil.detector.us_detector`.

### Built-in detectors

| Detector | Entity types |
|---|---|
| `RegexDetector` | `email`, `phone`, `credit_card`, `api_key` |
| `IndiaDetector` | `in_aadhaar`, `in_pan`, `in_phone`, `in_passport`, `in_voter_id`, `in_ifsc`, `in_gstin` |
| `USDetector` | `ssn`, `us_passport`, `us_ein` |

All three take no arguments and report matches with a confidence of `1.0`. Use
`IndiaDetector` or `USDetector` alongside `RegexDetector`, not in place of it,
unless you don't need the global types.

### Entity types

| Type | Example | Masked form | Risk weight |
|---|---|---|---|
| `email` | `alice@example.com` | `a***@example.com` | 0.40 |
| `phone` | `555-867-5309` | `***-***-5309` | 0.40 |
| `credit_card` | `4111-1111-1111-1111` | `****-****-****-1111` | 0.90 |
| `api_key` | `sk-abcdefghij1234567890` | `sk-a...7890` | 0.85 |
| `in_aadhaar` | `2345 6789 0124` | `XXXX-XXXX-0124` | 0.90 |
| `in_pan` | `ABCPE1234F` | `AB*******F` | 0.80 |
| `in_phone` | `+91 98765 43210` | `+91-***-***-3210` | 0.40 |
| `in_passport` | `A1234567` | `A*******` | 0.85 |
| `in_voter_id` | `ABC1234567` | `ABC*******` | 0.70 |
| `in_ifsc` | `SBIN0001234` | `SBIN0******` | 0.50 |
| `in_gstin` | `27ABCPE1234F1Z5` | `27*************` | 0.60 |
| `ssn` | `123-45-6789` | `***-**-6789` | 0.90 |
| `us_passport` | `A12345678` | `A********` | 0.80 |
| `us_ein` | `12-3456789` | `12-*******` | 0.65 |

Custom types are masked to their first and last two characters (`My***et`), or
`***` if the value has 4 characters or fewer.

### `DetectedEntity`

Frozen dataclass.

| Field | Type | Description |
|---|---|---|
| `entity_type` | `str` | Type label, matched against `Rule.type` |
| `value` | `str` | The matched substring |
| `start` | `int` | Start index in the text (inclusive) |
| `end` | `int` | End index in the text (exclusive) |
| `confidence` | `float` | Confidence from `0.0` to `1.0`. Default: `1.0` |

### `BaseDetector`

Abstract base class for custom detectors. Implement both members:

| Member | Description |
|---|---|
| `detect(text: str) -> list[DetectedEntity]` | Return every match, or an empty list |
| `supported_types -> list[str]` (property) | Return the type labels this detector can emit |

`start` and `end` must be exact offsets, so that `text[start:end] == value`.
Masking replaces that span rather than searching for the value.

```python
import re

from promptveil.detector import BaseDetector, DetectedEntity


class EmployeeIdDetector(BaseDetector):
    _PATTERN = re.compile(r"\bEMP-\d{6}\b")

    def detect(self, text: str) -> list[DetectedEntity]:
        return [
            DetectedEntity("employee_id", m.group(), m.start(), m.end())
            for m in self._PATTERN.finditer(text)
        ]

    @property
    def supported_types(self) -> list[str]:
        return ["employee_id"]
```

A new type needs a matching rule. Otherwise it gets `default_action`.

---

## `PseudonymVault`

```python
PseudonymVault()
```

Stores the mapping between tokens and original values for one session. Tokens
look like `<ENTITY_TYPE_N>`, using the uppercased type and a per-type counter,
for example `<IN_PHONE_1>`. A value keeps the same token for the life of the
vault.

| Member | Description |
|---|---|
| `restore(text) -> str` | Replace every known token in `text` with its original value |
| `pseudonymize(text, entities) -> str` | Replace non-overlapping entity spans with tokens. `scan_with_vault` calls this for you |
| `get_token(value) -> str \| None` | Return the token for an original value, or `None` |
| `token_map` (property) | Copy of the `{token: original_value}` mapping |
| `clear() -> None` | Remove all mappings and reset the counters |
| `len(vault)` | Number of unique values stored |

A vault holds raw sensitive values in memory, so treat `token_map` as sensitive.
Use a separate vault for each user or session. `restore` only matches exact
tokens, so a token the LLM reformats won't be restored.

Token creation and `clear` are guarded by a lock. `restore`, `get_token`, and
`token_map` aren't.

---

## `AuditLogger`

```python
AuditLogger(name: str = "promptveil.audit", stream: IO[str] | None = None)
```

Writes one JSON object per line to `stream`, or to `stdout` by default.

> **Warning:** `AuditLogger` only attaches a handler if the named Python logger
> has none. `stream` is ignored if that name is already set up, which includes
> the default name once any `Shield` has been created with the default logger.
> To write to a different stream, also pass a new `name`.

When it does attach a handler, it sets the level to `INFO` and turns off
propagation to the root logger.

`Shield` calls these two methods, so override them to send events elsewhere:

| Method | Event | Level |
|---|---|---|
| `log_scan_result(entity_records, prompt_length)` | `prompt_scan` | `INFO` |
| `log_blocked(entity)` | `prompt_blocked` | `WARNING` |

`entity_records` is a list of `(entity, action, masked_value)` tuples. A
`prompt_scan` event is written only when something was masked, so scans with no
findings or only `allow` entities produce no log line.

```json
{"event": "prompt_scan", "timestamp": "2026-05-03T07:34:19.800456+00:00", "prompt_length": 44, "detections": 1, "entities": [{"entity_type": "email", "action": "mask", "value_preview": "a***@example.com", "position": {"start": 26, "end": 43}}]}
{"event": "prompt_blocked", "timestamp": "2026-05-03T07:34:19.800456+00:00", "entity_type": "api_key", "action": "block"}
```

Logs contain masked previews, or vault tokens for `scan_with_vault`, and never
full raw values. Masked previews do keep part of the value, such as the last
four digits of a card.

---

## Integrations

### `wrap_openai`

```python
wrap_openai(client, shield: Shield, vault: PseudonymVault | None = None)
```

Requires `pip install "promptveil[openai]"`. Raises `ImportError` otherwise.

Patches `client.chat.completions.create` in place and returns the same client.
Each call scans the messages before sending them, with `shield.scan`, or with
`shield.scan_with_vault` if you pass a `vault`. `SensitiveDataError` is raised
to the caller, and the request isn't sent.

```python
from openai import OpenAI
from promptveil.adapters import wrap_openai

client = wrap_openai(OpenAI(), shield)
```

Some content isn't scanned:

- **List content:** only string `content` is scanned. Multimodal messages, where
  `content` is a list of parts, are sent as they are.
- **Responses:** replies aren't scanned or restored. With a `vault`, call
  `vault.restore()` on the reply yourself.
- **Other endpoints:** only `chat.completions.create` is patched, so calls such
  as `client.responses.create` aren't scanned.

### `get_langchain_callback`

```python
get_langchain_callback() -> type
```

Requires `pip install "promptveil[langchain]"`. Raises `ImportError` otherwise.

Returns a callback handler class. Create it with `CallbackClass(shield)`.

> **Warning:** With default settings this callback doesn't stop blocked prompts,
> and it doesn't mask string prompts. LangChain catches callback errors and logs
> them, so the `SensitiveDataError` never reaches your code and the prompt is
> still sent. It also passes callbacks a copy of string prompts, so the masked
> text is discarded.

Behavior tested against `langchain-core` 1.7.3:

| Model type | `mask` | `block` (default) | `block` with `raise_error = True` |
|---|---|---|---|
| Chat models | Applied | **Not enforced, prompt is sent** | Enforced |
| String LLMs | **Not applied, prompt is sent unmasked** | **Not enforced, prompt is sent** | Enforced |

Set `raise_error` so that blocks are enforced. For string LLMs, also scan the
prompt yourself:

```python
from promptveil.adapters import get_langchain_callback

CallbackClass = get_langchain_callback()
callback = CallbackClass(shield)
callback.raise_error = True

# Chat models
chat_model.invoke(prompt, config={"callbacks": [callback]})

# String LLMs
llm.invoke(shield.scan(prompt))
```

The callback only reads string `content`, so list content isn't scanned.
Responses aren't scanned either.

### `PromptVeilMiddleware`

```python
app.add_middleware(PromptVeilMiddleware, shield=shield, prompt_field="prompt")
```

Requires `pip install "promptveil[fastapi]"`. Importing `promptveil.middleware`
raises `ImportError` otherwise.

| Param | Type | Description |
|---|---|---|
| `shield` | `Shield` | The configured `Shield` |
| `prompt_field` | `str` | Top-level JSON key holding the prompt. Default: `"prompt"` |

For a POST request with a JSON body containing `prompt_field`, the middleware
masks that field and passes the request on. A blocked prompt returns `400`
without calling the route handler:

```json
{
  "error": "Blocked: sensitive data detected in prompt.",
  "detail": "Sensitive data of type 'api_key' was detected and blocked by the active policy. Remove or redact the value before sending this prompt.",
  "code": "SENSITIVE_DATA_BLOCKED"
}
```

All other requests pass through unscanned, including other HTTP methods,
non-JSON bodies, and bodies without the field. Nested fields aren't scanned, so
this won't cover an OpenAI-style `messages` array.

A request returns `500` if `prompt_field` holds a non-string value, or if the
JSON body is an array that contains the field name.
