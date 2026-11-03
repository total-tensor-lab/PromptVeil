# Automatic Response Scanning — Design

**Date:** 2026-11-03
**Branch:** `feat/auto-response-scanning`
**Status:** Approved design, pending spec review

## Goal

Let the OpenAI adapter and the FastAPI middleware scan LLM *output* automatically,
using the existing `Shield.scan_response()`, so users no longer have to call it by
hand. The feature is opt-in: existing users see no behaviour change.

## Scope

In scope:

- OpenAI adapter (`wrap_openai`), sync `OpenAI` and async `AsyncOpenAI` clients,
  non-streaming `chat.completions.create` responses.
- FastAPI / Starlette middleware (`PromptVeilMiddleware`), JSON responses.

Out of scope (later work):

- Streaming responses (`stream=True`, `StreamingResponse`).
- LangChain output scanning (callbacks cannot rewrite output; could only raise).
- Separate response-specific policy rules.
- Prompt injection detection.

## Design

### 1. OpenAI adapter

New signature:

```python
wrap_openai(client, shield, vault=None, scan_responses=False)
```

- `scan_responses` defaults to `False`. When `False`, the adapter behaves exactly
  as today, including passing the async coroutine through unawaited.
- When `True`:
  - If `stream=True` is in the call kwargs, raise `ConfigurationError` **before**
    calling the API. Silently skipping the scan would be a false sense of safety.
  - If the result of the original `create` is awaitable (`inspect.isawaitable`),
    return a coroutine that awaits it and then scans; otherwise scan directly.
    The result is checked rather than the function because the real
    `AsyncOpenAI` SDK wraps `create` in a sync decorator, so
    `inspect.iscoroutinefunction` returns `False` for it.
  - After the call, for each `choice` in `response.choices`, if
    `choice.message.content` is a `str`, replace it with
    `shield.scan_response(content)`. Choices whose content is `None` (tool calls)
    or not a string are left untouched. The response object is mutated in place
    and returned.
  - A response entity matching a `block` rule raises `SensitiveDataError`
    (propagated from `scan_response`), same as for prompts.
- Prompt scanning (mask or vault) is unchanged and still runs first.
- Vault tokens (`<EMAIL_1>` etc.) do not match any detector, so combining
  `vault=` with `scan_responses=True` is safe. Users still call
  `vault.restore()` on the (scanned) response themselves.
- Audit events are logged with `method="scan_response"` (existing behaviour).

### 2. FastAPI middleware

New signature:

```python
PromptVeilMiddleware(app, shield, prompt_field="prompt", response_field=None)
```

- `response_field=None` (default) keeps today's behaviour.
- When set, after `call_next` the middleware scans the response only if all hold:
  - status code is 2xx,
  - `content-type` contains `application/json`,
  - the body parses as a JSON object,
  - `response_field` is present and its value is a `str`.
- Otherwise the original response passes through unchanged (body bytes re-emitted
  with original status and headers).
- Mask: the field is rewritten, the body re-serialised, and a new `Response` is
  returned with the original status and headers, `Content-Length` recomputed.
- Block: return a **502** JSON response:

  ```json
  {
    "error": "Blocked: sensitive data detected in response.",
    "detail": "<exception message>",
    "code": "SENSITIVE_DATA_BLOCKED_RESPONSE"
  }
  ```

  502 because the client request was valid; the upstream model output violated
  policy.
- Streaming responses: `BaseHTTPMiddleware` exposes every response as a body
  iterator, so the middleware reads the body only when the response is JSON and
  2xx. Responses with a non-JSON content type (including `text/event-stream`) are
  never buffered. Documented limitation: a streamed response declared as
  `application/json` will be buffered in full.
- Response scanning applies to every route whose response matches the conditions
  above, independent of whether the request had a `prompt_field`.

### 3. Policy

Responses use the same `PolicyConfig` as prompts. No new config keys.

## Error handling summary

| Situation | OpenAI adapter | FastAPI middleware |
|---|---|---|
| Response entity → mask | content masked | field masked, 2xx kept |
| Response entity → block | `SensitiveDataError` raised | 502 JSON error |
| `stream=True` / streaming body | `ConfigurationError` | non-JSON passes through |
| Tool call / non-string content | skipped | skipped |
| Non-2xx response | n/a | passes through |

## Testing

OpenAI (`tests/test_adapters.py`, fake clients, no network):

- sync client: response content masked when `scan_responses=True`
- sync client: response unchanged when `scan_responses=False`
- block rule in response raises `SensitiveDataError`
- multiple choices each scanned
- `None` content (tool call) skipped
- `stream=True` raises `ConfigurationError` and the API is not called
- async client: response awaited and masked
- async client with `scan_responses=False` behaves as before

FastAPI (`tests/test_middleware.py`):

- response field masked
- blocked response returns 502 with expected fields
- non-JSON response passes through
- non-2xx response passes through untouched
- missing or non-string response field passes through
- default (`response_field=None`) does not scan responses

## Docs and release

- `docs/guides/integrations.md`: response scanning section for both integrations,
  including the streaming limitation.
- `docs/api-reference.md`: new parameters.
- `CHANGELOG.md`: entry under `[Unreleased]` → Added.
