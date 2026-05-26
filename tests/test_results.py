"""Tests for ScanResult, risk scoring, and scan_detailed()."""

import pytest

from promptshield import Shield, ScanResult
from promptshield.exceptions import SensitiveDataError
from promptshield.policy.models import Action, PolicyConfig, Rule
from promptshield.results import EntityResult, _compute_risk_score, _risk_level


def make_shield(rules=None, default_action=Action.ALLOW) -> Shield:
    config = PolicyConfig(rules=rules or [], default_action=default_action)
    return Shield(config=config)


# ── _risk_level helper ────────────────────────────────────────────────────

class TestRiskLevel:
    def test_zero_is_none(self):
        assert _risk_level(0.0) == "NONE"

    def test_low(self):
        assert _risk_level(0.1) == "LOW"
        assert _risk_level(0.29) == "LOW"

    def test_medium(self):
        assert _risk_level(0.30) == "MEDIUM"
        assert _risk_level(0.59) == "MEDIUM"

    def test_high(self):
        assert _risk_level(0.60) == "HIGH"
        assert _risk_level(0.84) == "HIGH"

    def test_critical(self):
        assert _risk_level(0.85) == "CRITICAL"
        assert _risk_level(1.0) == "CRITICAL"


# ── _compute_risk_score ───────────────────────────────────────────────────

class TestComputeRiskScore:
    def _er(self, entity_type: str, action: str = "mask", confidence: float = 1.0) -> EntityResult:
        return EntityResult(entity_type=entity_type, action=action, start=0, end=1,
                            masked_value="***", confidence=confidence)

    def test_empty_returns_zero(self):
        assert _compute_risk_score([]) == 0.0

    def test_single_high_risk_entity(self):
        score = _compute_risk_score([self._er("credit_card")])
        assert score == pytest.approx(0.90, abs=0.001)

    def test_allow_actioned_entity_lower_weight(self):
        allow_score = _compute_risk_score([self._er("credit_card", action="allow")])
        mask_score = _compute_risk_score([self._er("credit_card", action="mask")])
        assert allow_score < mask_score

    def test_multiple_entities_increases_score(self):
        single = _compute_risk_score([self._er("email")])
        double = _compute_risk_score([self._er("email"), self._er("phone")])
        assert double > single

    def test_score_bounded_to_one(self):
        many = [self._er("credit_card")] * 20
        score = _compute_risk_score(many)
        assert 0.0 <= score <= 1.0

    def test_confidence_scales_weight(self):
        full = _compute_risk_score([self._er("email", confidence=1.0)])
        half = _compute_risk_score([self._er("email", confidence=0.5)])
        assert full > half


# ── scan_detailed() ───────────────────────────────────────────────────────

class TestScanDetailed:
    def test_returns_scan_result_instance(self):
        shield = make_shield()
        result = shield.scan_detailed("Hello world")
        assert isinstance(result, ScanResult)

    def test_clean_text_returns_none_risk(self):
        shield = make_shield()
        result = shield.scan_detailed("Hello world, no PII here.")
        assert result.risk_score == 0.0
        assert result.risk_level == "NONE"
        assert result.was_mutated is False
        assert result.entities == []
        assert result.safe_text == "Hello world, no PII here."

    def test_masked_email_in_result(self):
        shield = make_shield(rules=[Rule(type="email", action=Action.MASK)])
        result = shield.scan_detailed("Contact alice@example.com now.")
        assert result.was_mutated is True
        assert "alice@example.com" not in result.safe_text
        assert len(result.entities) == 1
        assert result.entities[0].entity_type == "email"
        assert result.entities[0].action == "mask"

    def test_allowed_entity_included_in_result(self):
        shield = make_shield(rules=[], default_action=Action.ALLOW)
        result = shield.scan_detailed("email alice@example.com")
        # email is allowed through — still appears in entities
        email_entities = [e for e in result.entities if e.entity_type == "email"]
        assert len(email_entities) == 1
        assert email_entities[0].action == "allow"
        assert result.was_mutated is False

    def test_block_still_raises(self):
        shield = make_shield(rules=[Rule(type="credit_card", action=Action.BLOCK)])
        with pytest.raises(SensitiveDataError):
            shield.scan_detailed("Card: 4111-1111-1111-1111")

    def test_risk_score_populated(self):
        shield = make_shield(rules=[Rule(type="email", action=Action.MASK)])
        result = shield.scan_detailed("Contact alice@example.com now.")
        assert result.risk_score > 0.0

    def test_type_error_on_non_string(self):
        shield = make_shield()
        with pytest.raises(TypeError):
            shield.scan_detailed(42)  # type: ignore[arg-type]

    def test_entity_result_has_confidence(self):
        shield = make_shield(rules=[Rule(type="email", action=Action.MASK)])
        result = shield.scan_detailed("Contact alice@example.com now.")
        assert result.entities[0].confidence == pytest.approx(1.0)

    def test_entity_positions_are_correct(self):
        shield = make_shield(rules=[Rule(type="email", action=Action.MASK)])
        prompt = "email alice@example.com done"
        result = shield.scan_detailed(prompt)
        er = result.entities[0]
        assert prompt[er.start:er.end] == "alice@example.com"
