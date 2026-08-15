"""Vault-centric pseudonymization and round-trip benchmarks."""

from __future__ import annotations

import pytest

from promptshield import PseudonymVault

from benchmarks.fixtures.corpus import COMPONENT_ENTITY_COUNTS, FULL_STACK_ENTITY_SNIPPETS, build_entity_bundle
from benchmarks.utils.recording import attach_metadata

pytestmark = pytest.mark.benchmark_suite


def _round_trip(text: str, entities) -> str:
    vault = PseudonymVault()
    pseudonymized = vault.pseudonymize(text, list(entities))
    return vault.restore(pseudonymized)


@pytest.mark.parametrize("entity_count", COMPONENT_ENTITY_COUNTS)
def test_vault_pseudonymize_latency(benchmark, entity_count: int) -> None:
    text, entities = build_entity_bundle(entity_count, entity_pool=FULL_STACK_ENTITY_SNIPPETS)

    def run_once() -> str:
        vault = PseudonymVault()
        return vault.pseudonymize(text, list(entities))

    attach_metadata(
        benchmark,
        operation="vault_pseudonymize",
        entity_count=entity_count,
    )
    result = benchmark(run_once)
    assert "<" in result


@pytest.mark.parametrize("entity_count", COMPONENT_ENTITY_COUNTS)
def test_vault_restore_latency(benchmark, entity_count: int) -> None:
    text, entities = build_entity_bundle(entity_count, entity_pool=FULL_STACK_ENTITY_SNIPPETS)
    vault = PseudonymVault()
    pseudonymized = vault.pseudonymize(text, list(entities))

    attach_metadata(
        benchmark,
        operation="vault_restore",
        entity_count=entity_count,
        token_count=len(vault),
    )
    result = benchmark(vault.restore, pseudonymized)
    assert result == text


@pytest.mark.parametrize("entity_count", COMPONENT_ENTITY_COUNTS)
def test_vault_round_trip_latency(benchmark, entity_count: int) -> None:
    text, entities = build_entity_bundle(entity_count, entity_pool=FULL_STACK_ENTITY_SNIPPETS)
    attach_metadata(
        benchmark,
        operation="vault_round_trip",
        entity_count=entity_count,
    )
    result = benchmark(_round_trip, text, entities)
    assert result == text
