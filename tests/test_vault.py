"""Tests for PseudonymVault and shield.scan_with_vault()."""

import pytest

from promptshield import PseudonymVault, Shield
from promptshield.exceptions import SensitiveDataError
from promptshield.policy.models import Action, PolicyConfig, Rule


def make_shield(rules=None, default_action=Action.ALLOW) -> Shield:
    config = PolicyConfig(rules=rules or [], default_action=default_action)
    return Shield(config=config)


# ── PseudonymVault unit tests ─────────────────────────────────────────────

class TestPseudonymVaultTokenCreation:
    def test_creates_token_on_first_call(self):
        vault = PseudonymVault()
        from promptshield.detector.base import DetectedEntity
        entities = [DetectedEntity("email", "alice@example.com", 0, 17)]
        result = vault.pseudonymize("alice@example.com", entities)
        assert result == "<EMAIL_1>"

    def test_same_value_gets_same_token(self):
        vault = PseudonymVault()
        from promptshield.detector.base import DetectedEntity
        entities1 = [DetectedEntity("email", "alice@example.com", 0, 17)]
        entities2 = [DetectedEntity("email", "alice@example.com", 0, 17)]
        vault.pseudonymize("alice@example.com", entities1)
        vault.pseudonymize("alice@example.com", entities2)
        assert vault.get_token("alice@example.com") == "<EMAIL_1>"

    def test_different_values_get_different_tokens(self):
        vault = PseudonymVault()
        from promptshield.detector.base import DetectedEntity
        entities = [
            DetectedEntity("email", "a@x.com", 0, 7),
            DetectedEntity("email", "b@y.com", 8, 15),
        ]
        vault.pseudonymize("a@x.com b@y.com", entities)
        assert vault.get_token("a@x.com") != vault.get_token("b@y.com")

    def test_counter_increments_per_type(self):
        vault = PseudonymVault()
        from promptshield.detector.base import DetectedEntity
        entities = [
            DetectedEntity("email", "a@x.com", 0, 7),
            DetectedEntity("email", "b@y.com", 8, 15),
        ]
        vault.pseudonymize("a@x.com b@y.com", entities)
        # Entities processed right-to-left (highest position first),
        # so b@y.com (pos 8) receives EMAIL_1 and a@x.com (pos 0) gets EMAIL_2.
        assert vault.get_token("b@y.com") == "<EMAIL_1>"
        assert vault.get_token("a@x.com") == "<EMAIL_2>"

    def test_different_types_have_independent_counters(self):
        vault = PseudonymVault()
        from promptshield.detector.base import DetectedEntity
        entities = [
            DetectedEntity("email", "a@x.com", 0, 7),
            DetectedEntity("phone", "555-1234", 8, 16),
        ]
        vault.pseudonymize("a@x.com 555-1234", entities)
        assert vault.get_token("a@x.com") == "<EMAIL_1>"
        assert vault.get_token("555-1234") == "<PHONE_1>"

    def test_get_token_returns_none_for_unknown(self):
        vault = PseudonymVault()
        assert vault.get_token("unknown@example.com") is None


class TestPseudonymVaultRestore:
    def test_restore_replaces_tokens(self):
        vault = PseudonymVault()
        from promptshield.detector.base import DetectedEntity
        entities = [DetectedEntity("email", "alice@example.com", 0, 17)]
        vault.pseudonymize("alice@example.com", entities)
        restored = vault.restore("Contact <EMAIL_1> for details.")
        assert restored == "Contact alice@example.com for details."

    def test_restore_multiple_tokens(self):
        vault = PseudonymVault()
        from promptshield.detector.base import DetectedEntity
        text = "a@x.com and b@y.com"
        entities = [
            DetectedEntity("email", "a@x.com", 0, 7),
            DetectedEntity("email", "b@y.com", 12, 19),
        ]
        vault.pseudonymize(text, entities)
        restored = vault.restore("Reply to <EMAIL_1> and cc <EMAIL_2>.")
        assert "a@x.com" in restored
        assert "b@y.com" in restored

    def test_restore_unknown_tokens_unchanged(self):
        vault = PseudonymVault()
        text = "nothing to restore <UNKNOWN_99>"
        assert vault.restore(text) == text

    def test_restore_idempotent_when_no_tokens(self):
        vault = PseudonymVault()
        text = "plain text with no tokens"
        assert vault.restore(text) == text


class TestPseudonymVaultLifecycle:
    def test_len_returns_stored_count(self):
        vault = PseudonymVault()
        from promptshield.detector.base import DetectedEntity
        entities = [
            DetectedEntity("email", "a@x.com", 0, 7),
            DetectedEntity("email", "b@y.com", 8, 15),
        ]
        vault.pseudonymize("a@x.com b@y.com", entities)
        assert len(vault) == 2

    def test_clear_resets_vault(self):
        vault = PseudonymVault()
        from promptshield.detector.base import DetectedEntity
        entities = [DetectedEntity("email", "a@x.com", 0, 7)]
        vault.pseudonymize("a@x.com", entities)
        vault.clear()
        assert len(vault) == 0
        assert vault.get_token("a@x.com") is None

    def test_token_map_is_copy(self):
        vault = PseudonymVault()
        from promptshield.detector.base import DetectedEntity
        entities = [DetectedEntity("email", "a@x.com", 0, 7)]
        vault.pseudonymize("a@x.com", entities)
        snapshot = vault.token_map
        vault.clear()
        # Snapshot is not affected by clear
        assert len(snapshot) == 1


# ── scan_with_vault() integration ─────────────────────────────────────────

class TestScanWithVault:
    def test_returns_pseudonymized_text_and_vault(self):
        shield = make_shield(rules=[Rule(type="email", action=Action.MASK)])
        text, vault = shield.scan_with_vault("email alice@example.com please")
        assert "alice@example.com" not in text
        assert "<EMAIL_1>" in text
        assert isinstance(vault, PseudonymVault)

    def test_vault_can_restore_to_original(self):
        shield = make_shield(rules=[Rule(type="email", action=Action.MASK)])
        original = "Contact alice@example.com for info."
        pseudonymized, vault = shield.scan_with_vault(original)
        restored = vault.restore(pseudonymized)
        assert restored == original

    def test_clean_text_returns_unchanged(self):
        shield = make_shield(rules=[Rule(type="email", action=Action.MASK)])
        text = "No PII here."
        result, vault = shield.scan_with_vault(text)
        assert result == text
        assert len(vault) == 0

    def test_block_still_raises(self):
        shield = make_shield(rules=[Rule(type="credit_card", action=Action.BLOCK)])
        with pytest.raises(SensitiveDataError):
            shield.scan_with_vault("Card 4111-1111-1111-1111")

    def test_reusing_vault_preserves_consistency(self):
        shield = make_shield(rules=[Rule(type="email", action=Action.MASK)])
        vault = PseudonymVault()
        _, vault = shield.scan_with_vault("first alice@example.com", vault=vault)
        _, vault = shield.scan_with_vault("second alice@example.com", vault=vault)
        # Same email should get same token across both calls
        assert vault.get_token("alice@example.com") == "<EMAIL_1>"

    def test_type_error_on_non_string(self):
        shield = make_shield()
        with pytest.raises(TypeError):
            shield.scan_with_vault(123)  # type: ignore[arg-type]

    def test_allowed_entities_not_pseudonymized(self):
        shield = make_shield(rules=[], default_action=Action.ALLOW)
        text = "email alice@example.com"
        result, vault = shield.scan_with_vault(text)
        # ALLOW → not pseudonymized
        assert result == text
        assert len(vault) == 0

    def test_full_round_trip_multiple_entity_types(self):
        shield = make_shield(rules=[
            Rule(type="email", action=Action.MASK),
            Rule(type="phone", action=Action.MASK),
        ])
        original = "email alice@example.com call 555-867-5309"
        pseudonymized, vault = shield.scan_with_vault(original)
        assert "alice@example.com" not in pseudonymized
        assert "555-867-5309" not in pseudonymized
        restored = vault.restore(pseudonymized)
        assert "alice@example.com" in restored
        assert "555-867-5309" in restored
