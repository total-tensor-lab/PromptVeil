"""Detector-level throughput and scaling benchmarks."""

from __future__ import annotations

import pytest

from promptshield.detector.india_detector import _COMPILED as INDIA_COMPILED
from promptshield.detector.india_detector import _valid_aadhaar

from benchmarks.fixtures.corpus import FULL_STACK_ENTITY_SNIPPETS, build_entity_bundle, build_entity_text, get_corpus_case
from benchmarks.fixtures.corpus import TEXT_SIZES
from benchmarks.utils.recording import attach_metadata

pytestmark = pytest.mark.benchmark_suite

BASE_CASE = get_corpus_case(1_000, 0.20, FULL_STACK_ENTITY_SNIPPETS)
SCALING_CASES = tuple(get_corpus_case(size_chars, 0.20, FULL_STACK_ENTITY_SNIPPETS) for size_chars in TEXT_SIZES)
AADHAAR_TEXT, _ = build_entity_text((("in_aadhaar", "2345 6789 0124"),) * 40, target_size=5_000)
AADHAAR_PATTERN = INDIA_COMPILED["in_aadhaar"][0]


def _run_detector_stack(detectors, text: str):
    entities = []
    for detector in detectors:
        entities.extend(detector.detect(text))
    return entities


def _aadhaar_candidates(text: str) -> list[str]:
    return [match.group() for match in AADHAAR_PATTERN.finditer(text)]


def _validate_candidates(candidates: list[str]) -> list[bool]:
    return [_valid_aadhaar(candidate) for candidate in candidates]


@pytest.mark.parametrize(
    ("detector_name", "fixture_name"),
    (("regex", "regex_detector"), ("india", "india_detector"), ("us", "us_detector")),
)
def test_detector_latency(benchmark, request, detector_name: str, fixture_name: str) -> None:
    detector = request.getfixturevalue(fixture_name)
    attach_metadata(
        benchmark,
        operation="detect",
        detector=detector_name,
        size_chars=BASE_CASE.size_chars,
        density=BASE_CASE.density,
        entity_count=BASE_CASE.entity_count,
    )
    result = benchmark(detector.detect, BASE_CASE.text)
    assert isinstance(result, list)


@pytest.mark.parametrize(
    ("stack_name", "fixture_names"),
    (
        ("regex", ("regex_detector",)),
        ("regex+india", ("regex_detector", "india_detector")),
        ("regex+india+us", ("regex_detector", "india_detector", "us_detector")),
    ),
)
def test_stacked_detector_cost(benchmark, request, stack_name: str, fixture_names: tuple[str, ...]) -> None:
    detectors = [request.getfixturevalue(name) for name in fixture_names]
    attach_metadata(
        benchmark,
        operation="stack_detect",
        detector_stack=stack_name,
        detector_count=len(detectors),
        size_chars=BASE_CASE.size_chars,
        density=BASE_CASE.density,
        entity_count=BASE_CASE.entity_count,
    )
    result = benchmark(_run_detector_stack, detectors, BASE_CASE.text)
    assert isinstance(result, list)


@pytest.mark.parametrize(
    ("detector_name", "fixture_name"),
    (("regex", "regex_detector"), ("india", "india_detector"), ("us", "us_detector")),
)
@pytest.mark.parametrize("case", SCALING_CASES, ids=[case.id for case in SCALING_CASES])
def test_detector_scaling_curve(benchmark, request, detector_name: str, fixture_name: str, case) -> None:
    detector = request.getfixturevalue(fixture_name)
    attach_metadata(
        benchmark,
        operation="detect_scaling",
        detector=detector_name,
        size_chars=case.size_chars,
        density=case.density,
        entity_count=case.entity_count,
    )
    result = benchmark(detector.detect, case.text)
    assert isinstance(result, list)


def test_aadhaar_pattern_match_cost(benchmark) -> None:
    attach_metadata(
        benchmark,
        operation="aadhaar_pattern_match",
        size_chars=len(AADHAAR_TEXT),
        detector="india",
    )
    result = benchmark(_aadhaar_candidates, AADHAAR_TEXT)
    assert result


def test_aadhaar_checksum_cost(benchmark) -> None:
    candidates = _aadhaar_candidates(AADHAAR_TEXT)
    attach_metadata(
        benchmark,
        operation="aadhaar_checksum",
        size_chars=len(AADHAAR_TEXT),
        detector="india",
        entity_count=len(candidates),
    )
    result = benchmark(_validate_candidates, candidates)
    assert all(result)
