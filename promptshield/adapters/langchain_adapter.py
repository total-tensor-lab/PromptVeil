"""LangChain callback handler for PromptShield.

Provides a :func:`get_langchain_callback` factory that returns a
``langchain_core.callbacks.BaseCallbackHandler`` subclass configured to scan
prompts via a :class:`~promptshield.shield.Shield`.

``langchain-core`` is a soft dependency — importing this module does **not**
require it to be installed.  The class is only materialised when
:func:`get_langchain_callback` is called.

Usage::

    from langchain_openai import ChatOpenAI
    from promptshield import Shield
    from promptshield.adapters import get_langchain_callback

    shield = Shield(config_path="policy.yaml")
    PromptShieldCallback = get_langchain_callback()

    llm = ChatOpenAI(callbacks=[PromptShieldCallback(shield)])
    # Every LLM / chat-model invocation is now scanned automatically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Type

if TYPE_CHECKING:
    from ..shield import Shield


def get_langchain_callback() -> Type:
    """
    Build and return the ``PromptShieldCallback`` class (requires
    ``langchain-core``).

    Returns:
        A :class:`langchain_core.callbacks.BaseCallbackHandler` subclass that
        scans LLM inputs via :class:`~promptshield.shield.Shield`.

    Raises:
        ImportError: If ``langchain-core`` is not installed.
    """
    try:
        from langchain_core.callbacks import BaseCallbackHandler
    except ImportError:
        raise ImportError(
            "langchain-core is required for the LangChain adapter. "
            "Install it with: pip install langchain-core"
        ) from None

    class PromptShieldCallback(BaseCallbackHandler):
        """
        LangChain callback handler that intercepts LLM and chat-model inputs
        and scans them via PromptShield.

        Args:
            shield: A configured :class:`~promptshield.shield.Shield` instance.
        """

        def __init__(self, shield: "Shield") -> None:
            super().__init__()
            self._shield = shield

        # ── Plain LLM (string prompts) ─────────────────────────────────

        def on_llm_start(
            self,
            serialized: Dict[str, Any],
            prompts: List[str],
            **kwargs: Any,
        ) -> None:
            """Scan each prompt string in-place before the LLM sees it."""
            for i, prompt in enumerate(prompts):
                prompts[i] = self._shield.scan(prompt)

        # ── Chat models (message objects) ──────────────────────────────

        def on_chat_model_start(
            self,
            serialized: Dict[str, Any],
            messages: List[List[Any]],
            **kwargs: Any,
        ) -> None:
            """Scan ``content`` of every chat message in-place."""
            for message_list in messages:
                for msg in message_list:
                    if (
                        hasattr(msg, "content")
                        and isinstance(msg.content, str)
                    ):
                        msg.content = self._shield.scan(msg.content)

    return PromptShieldCallback
