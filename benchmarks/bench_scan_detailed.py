"""Component benchmarks for scan_detailed supporting steps."""

from __future__ import annotations

import pytest

from promptshield.actions.masker import apply_masks
from promptshield.policy.engine import PolicyEngine
from promptshield.policy.models import Action, PolicyConfig, Rule
from promptshield.results import EntityResult, _compute_risk_score

from benchmarks.fixtures.corpus import POLICY_ENTITY_COUNTS, build_entity_bundle
from benchmarks.utils.recording import attach_metadata

pytestmark = pytest.mark.benchmark_suite

POLICY = PolicyEngine(
    PolicyConfig(
        rules=[
            Rule(type="email", action=Action.MASK),
            Rule(type="phone", action=Action.MASK),
            Rule(type="credit_card", action=Action.MASK),
            Rule(type="api_key", action=Action.MASK),
            Rule(type="ssn", action=Action.MASK),
            Rule(type="in_aadhaar", action=Action.MASK),
            Rule(type="in_pan", action=Action.MASK),
        ],
        default_action=Action.ALLOW,
    )
)


def _entity_results_for_count(entity_count: int) -> list[EntityResult]:
    _, entities = build_entity_bundle(entity_count)
    return [
        EntityResult(
            entity_type=entity.entity_type,
            action="mask",
            start=entity.start,
            end=entity.end,
            masked_value="***",
            confidence=entity.confidence,
        )
        for entity in entities
    ]


@pytest.mark.parametrize("entity_count", POLICY_ENTITY_COUNTS)
def test_policy_engine_evaluate_latency(benchmark, entity_count: int) -> None:
    _, entities = build_entity_bundle(entity_count)
    attach_metadata(
        benchmark,
        operation="policy_evaluate",
        entity_count=entity_count,
    )
    result = benchmark(POLICY.evaluate, list(entities))
    assert len(result) == entity_count


@pytest.mark.parametrize("entity_count", POLICY_ENTITY_COUNTS)
def test_masker_apply_masks_latency(benchmark, entity_count: int) -> None:
    text, entities = build_entity_bundle(entity_count)
    attach_metadata(
        benchmark,
        operation="apply_masks",
        entity_count=entity_count,
        text_size=len(text),
    )
    result = benchmark(apply_masks, text, list(entities))
    assert result != text


@pytest.mark.parametrize("entity_count", POLICY_ENTITY_COUNTS)
def test_risk_score_compute_latency(benchmark, entity_count: int) -> None:
    entity_results = _entity_results_for_count(entity_count)
    attach_metadata(
        benchmark,
        operation="risk_score_compute",
        entity_count=entity_count,
    )
    result = benchmark(_compute_risk_score, entity_results)
    assert 0.0 <= result <= 1.0
