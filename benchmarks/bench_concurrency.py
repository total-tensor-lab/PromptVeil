"""Concurrency and contention benchmarks."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading

import pytest

from promptveil import PseudonymVault

from benchmarks.fixtures.corpus import CONCURRENCY_LEVELS, build_unique_entity_bundle, get_corpus_case
from benchmarks.utils.recording import attach_metadata

pytestmark = pytest.mark.benchmark_suite

CONCURRENCY_CASE = get_corpus_case(1_000, 0.20)


@pytest.mark.parametrize("worker_count", CONCURRENCY_LEVELS)
def test_concurrent_scan_shared_instance(benchmark, full_stack_shield, worker_count: int) -> None:
    texts = [CONCURRENCY_CASE.text] * worker_count
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        attach_metadata(
            benchmark,
            operation="concurrent_scan_shared",
            worker_count=worker_count,
            calls_per_round=worker_count,
            size_chars=CONCURRENCY_CASE.size_chars,
            density=CONCURRENCY_CASE.density,
        )
        result = benchmark(lambda: list(executor.map(full_stack_shield.scan, texts)))
    assert len(result) == worker_count


@pytest.mark.parametrize("worker_count", CONCURRENCY_LEVELS)
def test_concurrent_scan_per_thread_instance(benchmark, shield_factory, worker_count: int) -> None:
    texts = [CONCURRENCY_CASE.text] * worker_count
    thread_local = threading.local()

    def scan_with_thread_local(text: str) -> str:
        shield = getattr(thread_local, "shield", None)
        if shield is None:
            shield = shield_factory()
            thread_local.shield = shield
        return shield.scan(text)

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        attach_metadata(
            benchmark,
            operation="concurrent_scan_per_thread",
            worker_count=worker_count,
            calls_per_round=worker_count,
            size_chars=CONCURRENCY_CASE.size_chars,
            density=CONCURRENCY_CASE.density,
        )
        result = benchmark(lambda: list(executor.map(scan_with_thread_local, texts)))
    assert len(result) == worker_count


@pytest.mark.parametrize("worker_count", CONCURRENCY_LEVELS)
def test_vault_contention_round_trip(benchmark, worker_count: int) -> None:
    bundles = [build_unique_entity_bundle(5, seed=index + 1) for index in range(worker_count)]
    expected = [text for text, _ in bundles]

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        attach_metadata(
            benchmark,
            operation="vault_contention_round_trip",
            worker_count=worker_count,
            calls_per_round=worker_count,
            entity_count_per_call=5,
        )

        def run_once():
            vault = PseudonymVault()

            def round_trip(bundle):
                text, entities = bundle
                pseudonymized = vault.pseudonymize(text, list(entities))
                return vault.restore(pseudonymized)

            return list(executor.map(round_trip, bundles))

        result = benchmark(run_once)

    assert result == expected
