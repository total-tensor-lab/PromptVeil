"""LangChain callback handler for PromptVeil.

Provides a :func:`get_langchain_callback` factory that returns a
``langchain_core.callbacks.BaseCallbackHandler`` subclass configured to scan
prompts via a :class:`~promptveil.shield.Shield`.

``langchain-core`` is a soft dependency — importing this module does **not**
require it to be installed.  The class is only materialised when
:func:`get_langchain_callback` is called.

Usage::

    from langchain_openai import ChatOpenAI
    from promptveil import Shield
    from promptveil.adapters import get_langchain_callback

    shield = Shield(config_path="policy.yaml")
    PromptVeilCallback = get_langchain_callback()

    llm = ChatOpenAI(callbacks=[PromptVeilCallback(shield)])
    # Every LLM / chat-model invocation is now scanned automatically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Type

from ..exceptions import SensitiveDataError

if TYPE_CHECKING:
    from ..shield import Shield


def get_langchain_callback() -> Type:
    """
    Build and return the ``PromptVeilCallback`` class (requires
    ``langchain-core``).

    Returns:
        A :class:`langchain_core.callbacks.BaseCallbackHandler` subclass that
        scans LLM inputs via :class:`~promptveil.shield.Shield`.

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

    class PromptVeilCallback(BaseCallbackHandler):
        """
        LangChain callback handler that intercepts LLM and chat-model inputs
        and scans them via PromptVeil.

        Args:
            shield: A configured :class:`~promptveil.shield.Shield` instance.
        """

        # LangChain logs and swallows handler errors unless this is set, which
        # would send blocked prompts to the model.
        raise_error = True

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
            """
            Scan each prompt, rejecting any that would need masking.

            LangChain passes this handler a copy of each prompt, so a masked
            version can't reach the model. Sending the original would leak the
            value, so the call is stopped instead.

            Raises:
                SensitiveDataError: If a prompt matches a ``block`` rule or
                    contains an entity that would be masked.
            """
            for prompt in prompts:
                result = self._shield.scan_detailed(prompt)
                if result.was_mutated:
                    entity_type = next(
                        e.entity_type for e in result.entities if e.action == "mask"
                    )
                    raise SensitiveDataError(
                        f"Sensitive data of type '{entity_type}' was detected, "
                        "but callbacks can't mask string LLM prompts. Call "
                        "Shield.scan() on the prompt before invoking the LLM.",
                        entity_type=entity_type,
                    )

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

    return PromptVeilCallback
