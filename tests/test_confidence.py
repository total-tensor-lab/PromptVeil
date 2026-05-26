"""Tests for confidence scores and min_confidence policy thresholds."""

import pytest

from promptshield import Shield
from promptshield.detector.base import DetectedEntity
from promptshield.policy.engine import PolicyEngine
from promptshield.policy.models import Action, PolicyConfig, Rule


def make_entity(entity_type: str, value: str = "x", confidence: float = 1.0) -> DetectedEntity:
    return DetectedEntity(entity_type, value, 0, len(value), confidence)


# ── DetectedEntity confidence field ──────────────────────────────────────

class TestDetectedEntityConfidence:
    def test_default_confidence_is_one(self):
        entity = DetectedEntity("email", "a@b.com", 0, 7)
        assert entity.confidence == 1.0

    def test_explicit_confidence(self):
        entity = DetectedEntity("email", "a@b.com", 0, 7, confidence=0.75)
        assert entity.confidence == 0.75

    def test_frozen_prevents_mutation(self):
        entity = DetectedEntity("email", "a@b.com", 0, 7, confidence=0.9)
        with pytest.raises((AttributeError, TypeError)):
            entity.confidence = 0.5  # type: ignore[misc]


# ── Rule min_confidence field ─────────────────────────────────────────────

class TestRuleMinConfidence:
    def test_default_min_confidence_is_zero(self):
        rule = Rule(type="email", action=Action.MASK)
        assert rule.min_confidence == 0.0

    def test_explicit_min_confidence(self):
        rule = Rule(type="email", action=Action.MASK, min_confidence=0.8)
        assert rule.min_confidence == 0.8


# ── PolicyEngine respects min_confidence ─────────────────────────────────

class TestPolicyEngineConfidenceThreshold:
    def _engine(self, min_confidence: float) -> PolicyEngine:
        config = PolicyConfig(
            rules=[Rule(type="email", action=Action.MASK, min_confidence=min_confidence)],
            default_action=Action.ALLOW,
        )
        return PolicyEngine(config)

    def test_entity_above_threshold_uses_rule(self):
        engine = self._engine(0.7)
        entity = make_entity("email", confidence=0.9)
        assert engine.get_action(entity) == Action.MASK

    def test_entity_at_threshold_uses_rule(self):
        engine = self._engine(0.7)
        entity = make_entity("email", confidence=0.7)
        assert engine.get_action(entity) == Action.MASK

    def test_entity_below_threshold_falls_back_to_default(self):
        engine = self._engine(0.7)
        entity = make_entity("email", confidence=0.5)
        assert engine.get_action(entity) == Action.ALLOW

    def test_zero_threshold_always_matches(self):
        engine = self._engine(0.0)
        entity = make_entity("email", confidence=0.01)
        assert engine.get_action(entity) == Action.MASK

    def test_threshold_one_requires_full_confidence(self):
        engine = self._engine(1.0)
        assert engine.get_action(make_entity("email", confidence=0.99)) == Action.ALLOW
        assert engine.get_action(make_entity("email", confidence=1.0)) == Action.MASK


# ── YAML loader parses min_confidence ────────────────────────────────────

class TestLoaderMinConfidence:
    def test_min_confidence_parsed(self, tmp_path):
        yaml_text = """\
version: "1.0"
default_action: allow
rules:
  - type: email
    action: mask
    min_confidence: 0.85
"""
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(yaml_text)

        shield = Shield(config_path=str(policy_file))
        # Access internal policy engine to verify rule was parsed
        rule = shield._policy._rule_map.get("email")
        assert rule is not None
        assert rule.min_confidence == 0.85

    def test_invalid_min_confidence_raises(self, tmp_path):
        from promptshield.exceptions import ConfigurationError

        yaml_text = """\
version: "1.0"
default_action: allow
rules:
  - type: email
    action: mask
    min_confidence: 1.5
"""
        policy_file = tmp_path / "bad_policy.yaml"
        policy_file.write_text(yaml_text)

        with pytest.raises(ConfigurationError, match="min_confidence"):
            Shield(config_path=str(policy_file))

    def test_missing_min_confidence_defaults_to_zero(self, tmp_path):
        yaml_text = """\
version: "1.0"
default_action: allow
rules:
  - type: email
    action: mask
"""
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(yaml_text)

        shield = Shield(config_path=str(policy_file))
        rule = shield._policy._rule_map.get("email")
        assert rule is not None
        assert rule.min_confidence == 0.0


# ── End-to-end: low-confidence entity passes through ─────────────────────

class TestConfidenceEndToEnd:
    def test_low_confidence_entity_allowed_through(self):
        """A custom detector that emits low-confidence entities should be
        skipped when min_confidence threshold is not met."""
        from promptshield.detector.base import BaseDetector

        class LowConfidenceDetector(BaseDetector):
            def detect(self, text: str):
                if "secret" in text:
                    return [DetectedEntity("custom", "secret", text.index("secret"), text.index("secret") + 6, confidence=0.4)]
                return []

            @property
            def supported_types(self):
                return ["custom"]

        config = PolicyConfig(
            rules=[Rule(type="custom", action=Action.MASK, min_confidence=0.7)],
            default_action=Action.ALLOW,
        )
        shield = Shield(config=config, detectors=[LowConfidenceDetector()])
        result = shield.scan("keep secret here")
        # confidence 0.4 < min_confidence 0.7 → falls back to ALLOW → unchanged
        assert result == "keep secret here"

    def test_high_confidence_entity_is_masked(self):
        from promptshield.detector.base import BaseDetector

        class HighConfidenceDetector(BaseDetector):
            def detect(self, text: str):
                if "secret" in text:
                    return [DetectedEntity("custom", "secret", text.index("secret"), text.index("secret") + 6, confidence=0.9)]
                return []

            @property
            def supported_types(self):
                return ["custom"]

        config = PolicyConfig(
            rules=[Rule(type="custom", action=Action.MASK, min_confidence=0.7)],
            default_action=Action.ALLOW,
        )
        shield = Shield(config=config, detectors=[HighConfidenceDetector()])
        result = shield.scan("keep secret here")
        assert "secret" not in result
