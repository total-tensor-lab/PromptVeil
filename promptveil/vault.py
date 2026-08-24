"""Reversible pseudonymization vault for PromptVeil.

Replaces detected PII with consistent, numbered tokens (e.g. ``<EMAIL_1>``,
``<PHONE_2>``) so that the pseudonymized text can be safely sent to an LLM.
After the LLM responds, call :meth:`PseudonymVault.restore` to substitute
tokens back to their original values.

Example
-------
::

    shield = Shield(config_path="policy.yaml")

    pseudonymized, vault = shield.scan_with_vault(
        "Email john@acme.com or call +1-555-867-5309."
    )
    # pseudonymized → "Email <EMAIL_1> or call <PHONE_1>."

    llm_response = llm.complete(pseudonymized)
    # llm_response → "I will contact <EMAIL_1> tomorrow."

    restored = vault.restore(llm_response)
    # restored → "I will contact john@acme.com tomorrow."
"""

import threading
from typing import Dict, List, Optional

from .detector.base import DetectedEntity


class PseudonymVault:
    """
    Session-scoped reversible pseudonymization vault.

    Tokens follow the pattern ``<ENTITY_TYPE_N>`` where *N* is a per-type
    counter starting from 1.  The same original value always receives the
    same token within a vault instance, ensuring consistency when the same
    piece of PII appears multiple times.

    Thread-safe: token creation is guarded by an internal lock.
    """

    def __init__(self) -> None:
        self._store: Dict[str, str] = {}   # token  → real_value
        self._reverse: Dict[str, str] = {} # real_value → token
        self._counters: Dict[str, int] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    def _get_or_create_token(self, entity_type: str, value: str) -> str:
        """Return the existing token for *value* or mint a new one."""
        with self._lock:
            if value in self._reverse:
                return self._reverse[value]
            count = self._counters.get(entity_type, 0) + 1
            self._counters[entity_type] = count
            token = f"<{entity_type.upper()}_{count}>"
            self._store[token] = value
            self._reverse[value] = token
            return token

    def get_token(self, value: str) -> Optional[str]:
        """
        Return the pseudonym token assigned to *value*, or ``None`` if
        *value* has not been vaulted yet.
        """
        return self._reverse.get(value)

    # ------------------------------------------------------------------
    # Pseudonymization / restoration
    # ------------------------------------------------------------------

    def pseudonymize(self, text: str, entities: List[DetectedEntity]) -> str:
        """
        Replace each entity's span in *text* with a pseudonym token.

        Entities are processed right-to-left so that earlier character
        positions remain valid after each substitution.

        Args:
            text:     The original input text.
            entities: Entities whose values should be pseudonymized.

        Returns:
            A new string with entity values replaced by tokens.
        """
        sorted_entities = sorted(entities, key=lambda e: e.start, reverse=True)
        result = text
        for entity in sorted_entities:
            token = self._get_or_create_token(entity.entity_type, entity.value)
            result = result[: entity.start] + token + result[entity.end :]
        return result

    def restore(self, text: str) -> str:
        """
        Replace all pseudonym tokens in *text* with their original values.

        Tokens are replaced longest-first to avoid partial substitution of
        tokens that share a common prefix.

        Args:
            text: Text that may contain pseudonym tokens.

        Returns:
            Text with all known tokens replaced by their original values.
        """
        result = text
        # Longest tokens first to prevent prefix collisions.
        for token, real_value in sorted(
            self._store.items(), key=lambda kv: -len(kv[0])
        ):
            result = result.replace(token, real_value)
        return result

    # ------------------------------------------------------------------
    # Inspection / lifecycle
    # ------------------------------------------------------------------

    @property
    def token_map(self) -> Dict[str, str]:
        """Read-only snapshot of the ``token → original_value`` mapping."""
        return dict(self._store)

    def clear(self) -> None:
        """Reset all stored mappings.  Call this to start a new session."""
        with self._lock:
            self._store.clear()
            self._reverse.clear()
            self._counters.clear()

    def __len__(self) -> int:
        """Number of unique values currently stored in the vault."""
        return len(self._store)
