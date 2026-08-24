"""Tests for PromptVeilMiddleware (FastAPI/Starlette integration)."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from promptveil import Shield
from promptveil.middleware import PromptVeilMiddleware
from promptveil.policy.models import Action, PolicyConfig, Rule


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_app(rules=None, default_action=Action.ALLOW, prompt_field="prompt") -> TestClient:
    """Build a minimal FastAPI app with PromptVeilMiddleware and return a TestClient."""
    app = FastAPI()
    shield = Shield(
        config=PolicyConfig(
            rules=rules or [],
            default_action=default_action,
        )
    )
    app.add_middleware(PromptVeilMiddleware, shield=shield, prompt_field=prompt_field)

    @app.post("/chat")
    async def chat(body: dict):
        # Echo back the (possibly sanitised) body so tests can inspect it.
        return body

    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Pass-through (allow)
# ---------------------------------------------------------------------------

class TestMiddlewareAllow:
    def test_no_pii_passes_unchanged(self):
        client = make_app()
        resp = client.post("/chat", json={"prompt": "Hello world"})
        assert resp.status_code == 200
        assert resp.json()["prompt"] == "Hello world"

    def test_non_post_method_passes_unchanged(self):
        app = FastAPI()
        shield = Shield(config=PolicyConfig(rules=[]))

        app.add_middleware(PromptVeilMiddleware, shield=shield)

        @app.get("/chat")
        async def get_chat():
            return {"ok": True}

        client = TestClient(app)
        resp = client.get("/chat")
        assert resp.status_code == 200

    def test_non_json_content_type_passes_unchanged(self):
        client = make_app()
        resp = client.post(
            "/chat",
            content="plain text body",
            headers={"Content-Type": "text/plain"},
        )
        # Route won't match but middleware should not crash — just pass through.
        assert resp.status_code != 500

    def test_missing_prompt_field_passes_unchanged(self):
        client = make_app(rules=[Rule(type="email", action=Action.MASK)])
        resp = client.post("/chat", json={"message": "alice@example.com"})
        assert resp.status_code == 200
        # 'prompt' key not present — body untouched.
        assert resp.json()["message"] == "alice@example.com"

    def test_invalid_json_body_passes_through(self):
        client = make_app()
        resp = client.post(
            "/chat",
            content=b"{not valid json}",
            headers={"Content-Type": "application/json"},
        )
        # Middleware swallows the JSON error and forwards; FastAPI will 422.
        assert resp.status_code in (200, 422)


# ---------------------------------------------------------------------------
# Masking
# ---------------------------------------------------------------------------

class TestMiddlewareMask:
    def test_email_is_masked_in_request(self):
        client = make_app(rules=[Rule(type="email", action=Action.MASK)])
        resp = client.post("/chat", json={"prompt": "Contact alice@example.com"})
        assert resp.status_code == 200
        body = resp.json()
        assert "alice@example.com" not in body["prompt"]
        assert "@example.com" in body["prompt"]

    def test_phone_is_masked_in_request(self):
        client = make_app(rules=[Rule(type="phone", action=Action.MASK)])
        resp = client.post("/chat", json={"prompt": "Call 555-867-5309 now."})
        assert resp.status_code == 200
        assert "555-867-5309" not in resp.json()["prompt"]
        assert "5309" in resp.json()["prompt"]

    def test_other_fields_preserved_after_mask(self):
        client = make_app(rules=[Rule(type="email", action=Action.MASK)])
        resp = client.post(
            "/chat",
            json={"prompt": "email me at a@b.com", "model": "gpt-4", "temperature": 0.7},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["model"] == "gpt-4"
        assert data["temperature"] == 0.7

    def test_custom_prompt_field_name(self):
        client = make_app(
            rules=[Rule(type="email", action=Action.MASK)],
            prompt_field="user_message",
        )
        resp = client.post("/chat", json={"user_message": "hi bob@corp.io"})
        assert resp.status_code == 200
        assert "bob@corp.io" not in resp.json()["user_message"]


# ---------------------------------------------------------------------------
# Blocking
# ---------------------------------------------------------------------------

class TestMiddlewareBlock:
    def test_blocked_returns_400(self):
        client = make_app(rules=[Rule(type="api_key", action=Action.BLOCK)])
        resp = client.post(
            "/chat", json={"prompt": "My key is sk-abcdefABCDEF12345678901234"}
        )
        assert resp.status_code == 400

    def test_blocked_response_has_expected_fields(self):
        client = make_app(rules=[Rule(type="api_key", action=Action.BLOCK)])
        resp = client.post(
            "/chat", json={"prompt": "sk-abcdefABCDEF12345678901234"}
        )
        body = resp.json()
        assert body["code"] == "SENSITIVE_DATA_BLOCKED"
        assert "error" in body
        assert "detail" in body

    def test_blocked_request_never_reaches_handler(self):
        """Route handler must not be called when policy blocks the request."""
        reached = []

        app = FastAPI()
        shield = Shield(
            config=PolicyConfig(rules=[Rule(type="api_key", action=Action.BLOCK)])
        )
        app.add_middleware(PromptVeilMiddleware, shield=shield)

        @app.post("/chat")
        async def handler(body: dict):
            reached.append(True)
            return body

        client = TestClient(app, raise_server_exceptions=False)
        client.post("/chat", json={"prompt": "sk-abcdefABCDEF12345678901234"})
        assert not reached

    def test_credit_card_blocked(self):
        client = make_app(rules=[Rule(type="credit_card", action=Action.BLOCK)])
        resp = client.post("/chat", json={"prompt": "Charge 4111-1111-1111-1111"})
        assert resp.status_code == 400
