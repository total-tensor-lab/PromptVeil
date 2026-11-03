# Automatic Response Scanning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Opt-in automatic scanning of LLM output in `wrap_openai` and `PromptVeilMiddleware` via the existing `Shield.scan_response()`.

**Architecture:** `wrap_openai` gains `scan_responses`; when set, the wrapper scans each choice's string content after the call, awaiting first when the result is awaitable (`inspect.isawaitable` — the real `AsyncOpenAI.create` is a sync decorator returning a coroutine). `PromptVeilMiddleware` gains `response_field`; when set it buffers 2xx JSON responses, scans that field, and rebuilds the response (502 on block).

**Tech Stack:** Python 3.10+, Starlette `BaseHTTPMiddleware`, pytest, FastAPI `TestClient`.

**Spec:** `docs/superpowers/specs/2026-11-03-auto-response-scanning-design.md`

## Global Constraints

- Opt-in only: `scan_responses=False` and `response_field=None` must leave behaviour byte-for-byte unchanged.
- `stream=True` with `scan_responses=True` raises `ConfigurationError` before the API is called.
- Blocked response in middleware: status `502`, body `{"error": "Blocked: sensitive data detected in response.", "detail": str(exc), "code": "SENSITIVE_DATA_BLOCKED_RESPONSE"}`.
- Same `PolicyConfig` for prompts and responses; no new config keys.

## Review Focus

- Response object whose `choices` is missing or empty (e.g. a plain dict from a fake client) — must not crash; return as-is.
- Middleware response with a JSON array body (not an object) — pass through unchanged.
- Middleware response where the field is masked — `Content-Length` must match the new body.
- Non-2xx JSON response containing PII (e.g. a 422 echoing input) — untouched.
- Async client with `scan_responses=True` and `stream=True` — raises `ConfigurationError` without awaiting the API.

---

### Task 1: OpenAI adapter response scanning

**Files:**
- Modify: `promptveil/adapters/openai_adapter.py`
- Test: `tests/test_adapters.py` (new class `TestWrapOpenAIResponses`)

**Interfaces:**
- Produces: `wrap_openai(client, shield, vault=None, scan_responses: bool = False)`

- [ ] **Step 1: Write failing tests** using fake clients whose `create` returns `SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=...))])`:
  - `test_response_masked_when_enabled` — `"alice@example.com"` not in returned content.
  - `test_response_unchanged_when_disabled` — content still contains the email.
  - `test_response_block_raises` — `credit_card` BLOCK rule → `SensitiveDataError`.
  - `test_all_choices_scanned` — two choices, both masked.
  - `test_none_content_skipped` — content `None` stays `None`.
  - `test_response_without_choices_returned_as_is` — `create` returns `{}`; result `== {}`.
  - `test_stream_raises_configuration_error` — API never called.
  - `test_async_response_masked` — `async def create`; `asyncio.run(...)` result masked.
  - `test_async_stream_raises_configuration_error` — raises, API never called.
  - `test_async_disabled_returns_coroutine_unchanged` — existing behaviour: result of `create` awaited by caller yields unmasked content.
- [ ] **Step 2:** `pytest tests/test_adapters.py -k Responses -v` → FAIL (unexpected kwarg `scan_responses`).
- [ ] **Step 3: Implement.** Keep existing `patched_create` for `scan_responses=False`. Otherwise: helper `_scan_response(response)` iterating `getattr(response, "choices", None) or []`, rewriting `choice.message.content` when it is a `str`; helper `_check_stream(kwargs)` raising `ConfigurationError("scan_responses does not support stream=True ...")`; one wrapper that, if the result is awaitable, returns a coroutine awaiting then scanning it. Test `test_async_response_masked_through_sync_decorator` pins the real-SDK shape. Update module and function docstrings.
- [ ] **Step 4:** `pytest tests/test_adapters.py -v` → all PASS.
- [ ] **Step 5:** Commit `feat: scan OpenAI responses with scan_responses option`.

### Task 2: FastAPI middleware response scanning

**Files:**
- Modify: `promptveil/middleware/fastapi_middleware.py`
- Test: `tests/test_middleware.py` (new class `TestMiddlewareResponse`)

**Interfaces:**
- Produces: `PromptVeilMiddleware(app, shield, prompt_field="prompt", response_field: Optional[str] = None)`

- [ ] **Step 1: Write failing tests** with an app whose handler returns `{"response": <text>}` (and variants):
  - `test_response_field_masked` — 200, email not in `resp.json()["response"]`, `int(resp.headers["content-length"]) == len(resp.content)`.
  - `test_blocked_response_returns_502` — status 502, `code == "SENSITIVE_DATA_BLOCKED_RESPONSE"`, `error` and `detail` present.
  - `test_non_json_response_passes_through` — `PlainTextResponse` containing an email unchanged.
  - `test_non_2xx_response_untouched` — `JSONResponse(status_code=422, content={"response": email})` unchanged.
  - `test_missing_or_non_string_field_passes_through` — `{"other": email}` and `{"response": 5}` unchanged.
  - `test_json_array_response_passes_through` — `[email]` unchanged.
  - `test_default_does_not_scan_responses` — no `response_field`, email unchanged.
- [ ] **Step 2:** `pytest tests/test_middleware.py -k Response -v` → FAIL.
- [ ] **Step 3: Implement.** Extract current request logic so `dispatch` always flows into `_scan_response(response)` when `response_field` is set. Gate on `200 <= status < 300` and `"application/json"` in content-type before reading `body_iterator`. Rebuild with `Response(content=..., status_code=..., headers=..., media_type=...)`, dropping the old `content-length` header so it is recomputed. Update docstrings.
- [ ] **Step 4:** `pytest tests/test_middleware.py -v` → all PASS.
- [ ] **Step 5:** Commit `feat: scan FastAPI responses with response_field option`.

### Task 3: Docs and changelog

**Files:** `docs/guides/integrations.md`, `docs/api-reference.md`, `CHANGELOG.md`

- [ ] **Step 1:** Document `scan_responses` (incl. stream limitation, async support) and `response_field` (502, pass-through rules, buffered `application/json` streaming caveat). Add `[Unreleased]` → Added entries.
- [ ] **Step 2:** `pytest -q` → all pass.
- [ ] **Step 3:** Commit `docs: document automatic response scanning`.
