"""Memory-focused benchmarks backed by tracemalloc."""

from __future__ import annotations

import pytest

from promptveil import PseudonymVault

from benchmarks.fixtures.corpus import FULL_STACK_ENTITY_SNIPPETS, VAULT_MEMORY_COUNTS, build_dense_memory_case, build_entity_bundle
from benchmarks.utils.recording import attach_metadata, measure_memory

pytestmark = pytest.mark.benchmark_suite

DENSE_MEMORY_CASE = build_dense_memory_case()


def _populate_vault(text: str, entities):
    vault = PseudonymVault()
    vault.pseudonymize(text, list(entities))
    return vault


def test_scan_detailed_peak_memory(benchmark, full_stack_shield) -> None:
    attach_metadata(
        benchmark,
        operation="scan_detailed_memory",
        size_chars=DENSE_MEMORY_CASE.size_chars,
        density=DENSE_MEMORY_CASE.density,
        entity_count=DENSE_MEMORY_CASE.entity_count,
    )
    result, memory = benchmark.pedantic(
        measure_memory,
        args=(full_stack_shield.scan_detailed, DENSE_MEMORY_CASE.text),
        rounds=3,
        iterations=1,
    )
    attach_metadata(
        benchmark,
        peak_memory_bytes=memory.peak_bytes,
        retained_memory_bytes=memory.retained_bytes,
    )
    assert result.was_mutated


@pytest.mark.parametrize("entity_count", VAULT_MEMORY_COUNTS)
def test_vault_growth_memory(benchmark, entity_count: int) -> None:
    text, entities = build_entity_bundle(entity_count, entity_pool=FULL_STACK_ENTITY_SNIPPETS)
    attach_metadata(
        benchmark,
        operation="vault_growth_memory",
        entity_count=entity_count,
    )
    vault, memory = benchmark.pedantic(
        measure_memory,
        args=(_populate_vault, text, entities),
        rounds=3,
        iterations=1,
    )
    attach_metadata(
        benchmark,
        peak_memory_bytes=memory.peak_bytes,
        retained_memory_bytes=memory.retained_bytes,
        bytes_per_entity=(memory.retained_bytes / len(vault)) if len(vault) else 0.0,
    )
    # The vault stores one token per distinct (type, value), and the entity pool repeats.
    assert len(vault) == len({(entity.entity_type, entity.value) for entity in entities})
