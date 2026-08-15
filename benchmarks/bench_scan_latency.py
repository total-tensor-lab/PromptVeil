"""Hot-path benchmarks for Shield scan variants."""

from __future__ import annotations

import pytest

from benchmarks.fixtures.corpus import corpus_cases, iter_case_ids
from benchmarks.utils.recording import attach_metadata

pytestmark = pytest.mark.benchmark_suite

SCAN_CASES = corpus_cases()


@pytest.mark.parametrize("case", SCAN_CASES, ids=iter_case_ids(SCAN_CASES))
def test_scan_latency(benchmark, full_stack_shield, case) -> None:
    attach_metadata(
        benchmark,
        operation="scan",
        size_chars=case.size_chars,
        density=case.density,
        entity_count=case.entity_count,
        detector_stack="regex+india+us",
    )
    result = benchmark(full_stack_shield.scan, case.text)
    assert result


@pytest.mark.parametrize("case", SCAN_CASES, ids=iter_case_ids(SCAN_CASES))
def test_scan_detailed_latency(benchmark, full_stack_shield, case) -> None:
    expected = full_stack_shield.scan(case.text)
    attach_metadata(
        benchmark,
        operation="scan_detailed",
        baseline="scan",
        size_chars=case.size_chars,
        density=case.density,
        entity_count=case.entity_count,
    )
    result = benchmark(full_stack_shield.scan_detailed, case.text)
    assert result.safe_text == expected


@pytest.mark.parametrize("case", SCAN_CASES, ids=iter_case_ids(SCAN_CASES))
def test_scan_with_vault_latency(benchmark, full_stack_shield, case) -> None:
    attach_metadata(
        benchmark,
        operation="scan_with_vault",
        baseline="scan",
        size_chars=case.size_chars,
        density=case.density,
        entity_count=case.entity_count,
    )
    pseudonymized, vault = benchmark(full_stack_shield.scan_with_vault, case.text)
    assert vault.restore(pseudonymized) == case.text


@pytest.mark.parametrize("case", SCAN_CASES, ids=iter_case_ids(SCAN_CASES))
def test_scan_response_latency(benchmark, full_stack_shield, case) -> None:
    expected = full_stack_shield.scan(case.text)
    attach_metadata(
        benchmark,
        operation="scan_response",
        baseline="scan",
        size_chars=case.size_chars,
        density=case.density,
        entity_count=case.entity_count,
    )
    result = benchmark(full_stack_shield.scan_response, case.text)
    assert result == expected
