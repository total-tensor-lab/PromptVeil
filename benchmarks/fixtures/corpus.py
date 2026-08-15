"""Deterministic benchmark corpora and synthetic entity bundles."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from statistics import mean
from typing import Iterable, Sequence

from promptshield.detector.base import DetectedEntity

TEXT_SIZES = (100, 500, 1_000, 5_000, 20_000)
ENTITY_DENSITIES = (0.00, 0.05, 0.20, 0.50)
COMPONENT_ENTITY_COUNTS = (1, 5, 10, 50)
POLICY_ENTITY_COUNTS = (1, 10, 50)
CONCURRENCY_LEVELS = (1, 2, 4, 8, 16)
VAULT_MEMORY_COUNTS = (1, 10, 50, 100)

CORE_ENTITY_SNIPPETS: tuple[tuple[str, str], ...] = (
    ("email", "alice.benchmark@example.com"),
    ("phone", "555-867-5309"),
    ("credit_card", "4111-1111-1111-1111"),
    ("api_key", "sk-proj-benchmarkabcdefghijklmnopqrstuv012345"),
    ("ssn", "123-45-6789"),
    ("in_aadhaar", "2345 6789 0124"),
    ("in_pan", "ABCPE1234F"),
)

FULL_STACK_ENTITY_SNIPPETS: tuple[tuple[str, str], ...] = CORE_ENTITY_SNIPPETS + (
    ("in_phone", "+91 98765 43210"),
    ("in_passport", "A1234567"),
    ("in_voter_id", "ABC1234567"),
    ("in_ifsc", "SBIN0001234"),
    ("in_gstin", "27ABCPE1234F1Z5"),
    ("us_passport", "A12345678"),
    ("us_ein", "12-3456789"),
)

ALL_POLICY_TYPES = tuple(dict.fromkeys(entity_type for entity_type, _ in FULL_STACK_ENTITY_SNIPPETS))

_FILLER = (
    "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor "
    "incididunt ut labore et dolore magna aliqua "
)


@dataclass(frozen=True)
class CorpusCase:
    size_chars: int
    density: float
    text: str
    entities: tuple[DetectedEntity, ...]

    @property
    def entity_count(self) -> int:
        return len(self.entities)

    @property
    def entity_types(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(entity.entity_type for entity in self.entities))

    @property
    def id(self) -> str:
        density_pct = int(self.density * 100)
        return f"{_size_label(self.size_chars)}_{density_pct}pct"


def _size_label(size_chars: int) -> str:
    if size_chars >= 1_000 and size_chars % 1_000 == 0:
        return f"{size_chars // 1_000}k"
    return str(size_chars)


def _rotated_filler(length: int, salt: int = 0) -> str:
    if length <= 0:
        return ""
    offset = salt % len(_FILLER)
    rotated = _FILLER[offset:] + _FILLER[:offset]
    repeat_count = (length // len(rotated)) + 2
    return (rotated * repeat_count)[:length]


def _distribute_budget(total: int, slots: int) -> list[int]:
    base = total // slots
    remainder = total % slots
    return [base + (1 if index < remainder else 0) for index in range(slots)]


def _coerce_sequence(entity_specs: Sequence[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    return tuple(entity_specs)


@lru_cache(maxsize=None)
def _build_entity_text_cached(
    specs: tuple[tuple[str, str], ...],
    target_size: int | None = None,
) -> tuple[str, tuple[DetectedEntity, ...]]:
    if not specs:
        filler_length = max(target_size or 0, 0)
        return _rotated_filler(filler_length), ()

    base_size = sum(len(value) for _, value in specs) + max(0, len(specs) - 1)
    final_size = max(base_size, target_size or base_size)
    gap_lengths = _distribute_budget(final_size - base_size, len(specs) + 1)

    pieces: list[str] = []
    entities: list[DetectedEntity] = []
    cursor = 0

    leading = _rotated_filler(gap_lengths[0], salt=0)
    pieces.append(leading)
    cursor += len(leading)

    for index, (entity_type, value) in enumerate(specs):
        entities.append(
            DetectedEntity(
                entity_type=entity_type,
                value=value,
                start=cursor,
                end=cursor + len(value),
            )
        )
        pieces.append(value)
        cursor += len(value)

        if index < len(specs) - 1:
            middle = " " + _rotated_filler(gap_lengths[index + 1], salt=index + 1)
            pieces.append(middle)
            cursor += len(middle)

    trailing = _rotated_filler(gap_lengths[-1], salt=len(specs) + 1)
    pieces.append(trailing)

    return "".join(pieces), tuple(entities)


def build_entity_text(
    entity_specs: Sequence[tuple[str, str]],
    target_size: int | None = None,
) -> tuple[str, tuple[DetectedEntity, ...]]:
    return _build_entity_text_cached(_coerce_sequence(entity_specs), target_size)


def _entity_count_for_density(
    size_chars: int,
    density: float,
    entity_pool: Sequence[tuple[str, str]],
) -> int:
    if density <= 0:
        return 0

    average_entity_length = mean(len(value) for _, value in entity_pool)
    desired = max(1, round((size_chars * density) / average_entity_length))

    while desired > 0:
        specs = [entity_pool[index % len(entity_pool)] for index in range(desired)]
        minimum_size = sum(len(value) for _, value in specs) + max(0, desired - 1)
        if minimum_size <= size_chars:
            return desired
        desired -= 1

    return 0


@lru_cache(maxsize=None)
def get_corpus_case(
    size_chars: int,
    density: float,
    entity_pool: Sequence[tuple[str, str]] = FULL_STACK_ENTITY_SNIPPETS,
) -> CorpusCase:
    pool = _coerce_sequence(entity_pool)
    entity_count = _entity_count_for_density(size_chars, density, pool)
    if entity_count == 0:
        text, entities = build_entity_text((), target_size=size_chars)
        return CorpusCase(size_chars=size_chars, density=density, text=text, entities=entities)

    size_offset = TEXT_SIZES.index(size_chars) * len(ENTITY_DENSITIES)
    density_offset = ENTITY_DENSITIES.index(density)
    start_index = (size_offset + density_offset) % len(pool)
    specs = tuple(pool[(start_index + index) % len(pool)] for index in range(entity_count))
    text, entities = build_entity_text(specs, target_size=size_chars)
    return CorpusCase(size_chars=size_chars, density=density, text=text, entities=entities)


@lru_cache(maxsize=None)
def corpus_cases(
    entity_pool: Sequence[tuple[str, str]] = FULL_STACK_ENTITY_SNIPPETS,
) -> tuple[CorpusCase, ...]:
    pool = _coerce_sequence(entity_pool)
    return tuple(
        get_corpus_case(size_chars, density, pool)
        for size_chars in TEXT_SIZES
        for density in ENTITY_DENSITIES
    )


def build_entity_bundle(
    entity_count: int,
    entity_pool: Sequence[tuple[str, str]] = FULL_STACK_ENTITY_SNIPPETS,
    target_size: int | None = None,
    start_index: int = 0,
) -> tuple[str, tuple[DetectedEntity, ...]]:
    pool = _coerce_sequence(entity_pool)
    specs = tuple(pool[(start_index + index) % len(pool)] for index in range(entity_count))
    return build_entity_text(specs, target_size=target_size)


def build_unique_entity_bundle(entity_count: int, seed: int) -> tuple[str, tuple[DetectedEntity, ...]]:
    unique_specs = (
        ("email", f"user{seed}@benchmark.dev"),
        ("phone", f"555-120-{seed:04d}"),
        ("credit_card", "4111-1111-1111-1111"),
        ("api_key", f"sk-proj-benchmark{seed:04d}abcdefghijklmnopqrst"),
        ("ssn", f"321-54-{seed % 9000 + 1000:04d}"),
    )
    specs = tuple(unique_specs[index % len(unique_specs)] for index in range(entity_count))
    return build_entity_text(specs)


def build_entity_results(entity_count: int) -> tuple[DetectedEntity, ...]:
    _, entities = build_entity_bundle(entity_count, entity_pool=CORE_ENTITY_SNIPPETS)
    return entities


def build_dense_memory_case() -> CorpusCase:
    return get_corpus_case(20_000, 0.50, FULL_STACK_ENTITY_SNIPPETS)


def iter_case_ids(cases: Iterable[CorpusCase]) -> list[str]:
    return [case.id for case in cases]
