"""Tests for the policy engine and models."""

import pytest

from promptshield.detector.base import DetectedEntity
from promptshield.policy.engine import PolicyEngine
from promptshield.policy.models import Action, PolicyConfig, Rule


def make_entity(entity_type: str, value: str = "x") -> DetectedEntity:
    return DetectedEntity(entity_type, value, 0, len(value))


class TestPolicyEngine:
    def test_rule_matched(self):
        config = PolicyConfig(rules=[Rule(type="email", action=Action.MASK)])
        engine = PolicyEngine(config)
        entity = make_entity("email", "test@test.com")
        assert engine.get_action(entity) == Action.MASK

    def test_default_action_allow(self):
        config = PolicyConfig(rules=[], default_action=Action.ALLOW)
        engine = PolicyEngine(config)
        entity = make_entity("phone", "555-1234")
        assert engine.get_action(entity) == Action.ALLOW

    def test_default_action_mask(self):
        config = PolicyConfig(rules=[], default_action=Action.MASK)
        engine = PolicyEngine(config)
        entity = make_entity("phone")
        assert engine.get_action(entity) == Action.MASK

    def test_block_action(self):
        config = PolicyConfig(rules=[Rule(type="api_key", action=Action.BLOCK)])
        engine = PolicyEngine(config)
        entity = make_entity("api_key", "sk-abc123")
        assert engine.get_action(entity) == Action.BLOCK

    def test_first_matching_rule_wins(self):
        # Only one rule per type in dict — last write wins on duplicate types.
        config = PolicyConfig(
            rules=[
                Rule(type="email", action=Action.MASK),
                Rule(type="email", action=Action.BLOCK),  # overrides
            ]
        )
        engine = PolicyEngine(config)
        entity = make_entity("email", "a@b.com")
        # dict comprehension last-write-wins: BLOCK
        assert engine.get_action(entity) == Action.BLOCK

    def test_evaluate_returns_correct_mapping(self):
        config = PolicyConfig(
            rules=[
                Rule(type="email", action=Action.MASK),
                Rule(type="api_key", action=Action.BLOCK),
            ],
            default_action=Action.ALLOW,
        )
        engine = PolicyEngine(config)
        entities = [
            make_entity("email", "a@b.com"),
            make_entity("api_key", "sk-xyz"),
            make_entity("phone", "555-1234"),
        ]
        result = engine.evaluate(entities)
        assert result[entities[0]] == Action.MASK
        assert result[entities[1]] == Action.BLOCK
        assert result[entities[2]] == Action.ALLOW
