"""Tests for framework-native adapters (OpenAI and LangChain)."""

import pytest

from promptveil import Shield
from promptveil.adapters import get_langchain_callback, wrap_openai
from promptveil.exceptions import SensitiveDataError
from promptveil.policy.models import Action, PolicyConfig, Rule


def make_shield(rules=None, default_action=Action.ALLOW) -> Shield:
    config = PolicyConfig(rules=rules or [], default_action=default_action)
    return Shield(config=config)


# ── OpenAI adapter ────────────────────────────────────────────────────────

class TestWrapOpenAI:
    def test_raises_import_error_without_openai(self, monkeypatch):
        """When openai is not installed, wrap_openai raises ImportError."""
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "openai":
                raise ImportError("No module named 'openai'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        with pytest.raises(ImportError, match="openai"):
            wrap_openai(object(), shield=make_shield())

    def test_patches_create_method(self):
        """wrap_openai replaces chat.completions.create on the client object."""
        shield = make_shield(rules=[Rule(type="email", action=Action.MASK)])

        # Minimal mock client
        class FakeCompletions:
            def create(self, *args, **kwargs):
                return kwargs

        class FakeChat:
            completions = FakeCompletions()

        class FakeClient:
            chat = FakeChat()

        client = FakeClient()
        original_create = client.chat.completions.create

        # Temporarily provide a fake openai module so the import check passes
        import sys
        import types
        fake_openai = types.ModuleType("openai")
        sys.modules.setdefault("openai", fake_openai)

        wrapped = wrap_openai(client, shield=shield)
        assert wrapped is client
        assert client.chat.completions.create is not original_create

    def test_message_content_is_scanned(self):
        """The patched create() scans message content."""
        shield = make_shield(rules=[Rule(type="email", action=Action.MASK)])
        scanned_messages = []

        class FakeCompletions:
            def create(self, **kwargs):
                scanned_messages.extend(kwargs.get("messages", []))
                return {}

        class FakeChat:
            completions = FakeCompletions()

        class FakeClient:
            chat = FakeChat()

        import sys, types
        sys.modules.setdefault("openai", types.ModuleType("openai"))

        client = FakeClient()
        wrap_openai(client, shield=shield)
        client.chat.completions.create(
            messages=[{"role": "user", "content": "email alice@example.com"}]
        )
        assert scanned_messages
        assert "alice@example.com" not in scanned_messages[0]["content"]

    def test_block_raises_sensitive_data_error(self):
        """Blocked entities inside message content still raise SensitiveDataError."""
        shield = make_shield(rules=[Rule(type="credit_card", action=Action.BLOCK)])

        class FakeCompletions:
            def create(self, **kwargs):
                return {}

        class FakeChat:
            completions = FakeCompletions()

        class FakeClient:
            chat = FakeChat()

        import sys, types
        sys.modules.setdefault("openai", types.ModuleType("openai"))

        client = FakeClient()
        wrap_openai(client, shield=shield)
        with pytest.raises(SensitiveDataError):
            client.chat.completions.create(
                messages=[{"role": "user", "content": "card 4111-1111-1111-1111"}]
            )

    def test_non_string_content_passed_through(self):
        """Messages without string content are forwarded unchanged."""
        shield = make_shield(rules=[Rule(type="email", action=Action.MASK)])
        received = []

        class FakeCompletions:
            def create(self, **kwargs):
                received.extend(kwargs.get("messages", []))
                return {}

        class FakeChat:
            completions = FakeCompletions()

        class FakeClient:
            chat = FakeChat()

        import sys, types
        sys.modules.setdefault("openai", types.ModuleType("openai"))

        client = FakeClient()
        wrap_openai(client, shield=shield)
        # None content — should not crash
        client.chat.completions.create(
            messages=[{"role": "user", "content": None}]
        )
        assert received[0]["content"] is None


# ── LangChain adapter ─────────────────────────────────────────────────────

class TestGetLangchainCallback:
    def test_raises_import_error_without_langchain(self, monkeypatch):
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name in ("langchain_core", "langchain_core.callbacks"):
                raise ImportError("No module named 'langchain_core'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        with pytest.raises(ImportError, match="langchain-core"):
            get_langchain_callback()

    def test_returns_class_when_langchain_available(self, monkeypatch):
        """If langchain_core is importable, returns a class."""
        import sys
        import types

        # Build minimal fake langchain_core.callbacks
        fake_lc = types.ModuleType("langchain_core")
        fake_cb = types.ModuleType("langchain_core.callbacks")

        class BaseCallbackHandler:
            def __init__(self):
                pass

        fake_cb.BaseCallbackHandler = BaseCallbackHandler
        fake_lc.callbacks = fake_cb
        sys.modules["langchain_core"] = fake_lc
        sys.modules["langchain_core.callbacks"] = fake_cb

        try:
            cls = get_langchain_callback()
            assert callable(cls)
            shield = make_shield(rules=[Rule(type="email", action=Action.MASK)])
            instance = cls(shield)
            assert hasattr(instance, "on_llm_start")
            assert hasattr(instance, "on_chat_model_start")
        finally:
            del sys.modules["langchain_core"]
            del sys.modules["langchain_core.callbacks"]

    def test_on_llm_start_scans_prompts(self, monkeypatch):
        import sys, types

        fake_lc = types.ModuleType("langchain_core")
        fake_cb = types.ModuleType("langchain_core.callbacks")

        class BaseCallbackHandler:
            def __init__(self):
                pass

        fake_cb.BaseCallbackHandler = BaseCallbackHandler
        fake_lc.callbacks = fake_cb
        sys.modules["langchain_core"] = fake_lc
        sys.modules["langchain_core.callbacks"] = fake_cb

        try:
            cls = get_langchain_callback()
            shield = make_shield(rules=[Rule(type="email", action=Action.MASK)])
            handler = cls(shield)
            prompts = ["Contact alice@example.com now."]
            handler.on_llm_start({}, prompts)
            assert "alice@example.com" not in prompts[0]
        finally:
            del sys.modules["langchain_core"]
            del sys.modules["langchain_core.callbacks"]

    def test_on_chat_model_start_scans_messages(self, monkeypatch):
        import sys, types

        fake_lc = types.ModuleType("langchain_core")
        fake_cb = types.ModuleType("langchain_core.callbacks")

        class BaseCallbackHandler:
            def __init__(self):
                pass

        fake_cb.BaseCallbackHandler = BaseCallbackHandler
        fake_lc.callbacks = fake_cb
        sys.modules["langchain_core"] = fake_lc
        sys.modules["langchain_core.callbacks"] = fake_cb

        try:
            cls = get_langchain_callback()
            shield = make_shield(rules=[Rule(type="email", action=Action.MASK)])
            handler = cls(shield)

            class FakeMsg:
                def __init__(self, content):
                    self.content = content

            messages = [[FakeMsg("Contact alice@example.com")]]
            handler.on_chat_model_start({}, messages)
            assert "alice@example.com" not in messages[0][0].content
        finally:
            del sys.modules["langchain_core"]
            del sys.modules["langchain_core.callbacks"]
