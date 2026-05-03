"""Tests for masking logic."""

import pytest

from promptshield.actions.masker import apply_masks, mask_value
from promptshield.detector.base import DetectedEntity


class TestMaskValue:
    def test_email_masks_local_part(self):
        result = mask_value("john.doe@example.com", "email")
        assert result == "j***@example.com"

    def test_email_short_local(self):
        result = mask_value("a@b.com", "email")
        assert "@b.com" in result

    def test_phone_keeps_last_four(self):
        result = mask_value("555-867-5309", "phone")
        assert result == "***-***-5309"

    def test_phone_international(self):
        result = mask_value("+44 7911 123456", "phone")
        assert "3456" in result

    def test_credit_card_keeps_last_four(self):
        result = mask_value("4111-1111-1111-1111", "credit_card")
        assert result == "****-****-****-1111"

    def test_api_key_shows_prefix_suffix(self):
        result = mask_value("sk-abcdefABCDEF12345678", "api_key")
        assert result.startswith("sk-a")
        assert result.endswith("5678")
        assert "..." in result

    def test_api_key_too_short(self):
        result = mask_value("ab12", "api_key")
        assert result == "***"

    def test_generic_fallback(self):
        result = mask_value("MySecretValue", "custom_type")
        assert result.startswith("My")
        assert result.endswith("ue")
        assert "***" in result


class TestApplyMasks:
    def _entity(self, text: str, entity_type: str, start: int) -> DetectedEntity:
        return DetectedEntity(entity_type, text, start, start + len(text))

    def test_single_mask(self):
        text = "Email me at alice@example.com please"
        entity = self._entity("alice@example.com", "email", 12)
        result = apply_masks(text, [entity])
        assert "alice@example.com" not in result
        assert "@example.com" in result

    def test_multiple_masks_non_overlapping(self):
        text = "a@b.com and 555-123-4567"
        e1 = self._entity("a@b.com", "email", 0)
        e2 = self._entity("555-123-4567", "phone", 12)
        result = apply_masks(text, [e1, e2])
        assert "a@b.com" not in result
        assert "555-123-4567" not in result

    def test_right_to_left_ordering_preserves_positions(self):
        text = "X" * 5 + "a@b.com" + "Y" * 5 + "c@d.com"
        e1 = self._entity("a@b.com", "email", 5)
        e2 = self._entity("c@d.com", "email", 17)
        result = apply_masks(text, [e1, e2])
        assert "a@b.com" not in result
        assert "c@d.com" not in result

    def test_no_entities_returns_original(self):
        text = "Hello world"
        assert apply_masks(text, []) == text
