"""OpenAI SDK adapter for PromptVeil.

Wraps an ``openai.OpenAI`` (or ``openai.AsyncOpenAI``) client so that every
``chat.completions.create`` call has its message content scanned by a
:class:`~promptveil.shield.Shield` before being forwarded to the API.

Usage::

    import openai
    from promptveil import Shield
    from promptveil.adapters import wrap_openai

    shield = Shield(config_path="policy.yaml")
    client = wrap_openai(openai.OpenAI(), shield=shield)

    # All calls are now scanned automatically — zero code-change needed.
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "My card is 4111-1111-1111-1111"}],
    )
    # ↑ raises SensitiveDataError (credit_card is blocked by default policy).

Pass ``scan_responses=True`` to also scan the model's reply with
:meth:`~promptveil.shield.Shield.scan_response`.
"""

import inspect
from typing import TYPE_CHECKING, Any, List, Optional

from ..exceptions import ConfigurationError

if TYPE_CHECKING:
    from ..shield import Shield
    from ..vault import PseudonymVault


def wrap_openai(
    client,
    shield: "Shield",
    vault: Optional["PseudonymVault"] = None,
    scan_responses: bool = False,
):
    """
    Patch an OpenAI client's ``chat.completions.create`` method in-place to
    scan all message content via *shield* before each API call.

    If *vault* is provided, message content is pseudonymized instead of
    masked.  The vault accumulates tokens across calls — call
    :meth:`~promptveil.vault.PseudonymVault.restore` on the LLM response
    to reinstate original values.

    Args:
        client:  An ``openai.OpenAI`` or ``openai.AsyncOpenAI`` instance.
        shield:  A configured :class:`~promptveil.shield.Shield`.
        vault:   Optional :class:`~promptveil.vault.PseudonymVault` for
                 reversible pseudonymization.  When ``None``, standard
                 masking (irreversible) is used.
        scan_responses: When ``True``, the string ``message.content`` of
                 every returned choice is scanned with
                 :meth:`~promptveil.shield.Shield.scan_response`. Streaming
                 (``stream=True``) is not supported in this mode.

    Returns:
        The same *client* instance with its ``chat.completions.create``
        method patched.

    Raises:
        ImportError: If the ``openai`` package is not installed.

    The patched method raises
    :class:`~promptveil.exceptions.ConfigurationError` when called with
    ``stream=True`` while *scan_responses* is enabled, and
    :class:`~promptveil.exceptions.SensitiveDataError` when a response
    matches a ``block`` rule.
    """
    try:
        import openai as _openai  # noqa: F401
    except ImportError:
        raise ImportError(
            "The 'openai' package is required for wrap_openai. "
            "Install it with: pip install openai"
        ) from None

    original_create = client.chat.completions.create

    def _scan_messages(messages: List[dict]) -> List[dict]:
        scanned: List[dict] = []
        for msg in messages:
            if (
                isinstance(msg, dict)
                and "content" in msg
                and isinstance(msg["content"], str)
            ):
                if vault is not None:
                    safe_content, _ = shield.scan_with_vault(msg["content"], vault)
                else:
                    safe_content = shield.scan(msg["content"])
                scanned.append({**msg, "content": safe_content})
            else:
                scanned.append(msg)
        return scanned

    def _prepare(kwargs: dict) -> None:
        if scan_responses and kwargs.get("stream"):
            raise ConfigurationError(
                "scan_responses does not support stream=True; streamed "
                "responses can't be scanned before they reach the caller."
            )
        if "messages" in kwargs:
            kwargs["messages"] = _scan_messages(kwargs["messages"])

    def _scan_response(response: Any) -> Any:
        for choice in getattr(response, "choices", None) or []:
            message = getattr(choice, "message", None)
            content = getattr(message, "content", None)
            if isinstance(content, str):
                message.content = shield.scan_response(content)
        return response

    def patched_create(*args, **kwargs):
        _prepare(kwargs)
        result = original_create(*args, **kwargs)
        if not scan_responses:
            return result
        # AsyncOpenAI's create() is wrapped in a sync decorator that returns a
        # coroutine, so check the result rather than the function.
        if inspect.isawaitable(result):
            async def _scan_awaited():
                return _scan_response(await result)

            return _scan_awaited()
        return _scan_response(result)

    client.chat.completions.create = patched_create
    return client
