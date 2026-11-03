"""Span matching and precision/recall/F1 for the accuracy benchmarks."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

UNSUPPORTED = "_unsupported"
MIN_SUPPORT = 20

# Types that count as the same entity when matching.
_EQUIVALENT = {"in_phone": "phone"}


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    label: str


@dataclass(frozen=True)
class Sample:
    dataset: str
    sample_id: str
    text: str
    spans: tuple[Span, ...]


@dataclass
class TypeCounts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def support(self) -> int:
        return self.tp + self.fn

    @property
    def precision(self) -> float:
        predicted = self.tp + self.fp
        return self.tp / predicted if predicted else 0.0

    @property
    def recall(self) -> float:
        return self.tp / self.support if self.support else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    def __add__(self, other: TypeCounts) -> TypeCounts:
        return TypeCounts(self.tp + other.tp, self.fp + other.fp, self.fn + other.fn)


def canonical(label: str) -> str:
    """Collapse equivalent types (``in_phone`` → ``phone``)."""
    return _EQUIVALENT.get(label, label)


def _matches(pred: Span, gold: Span, strict: bool) -> bool:
    if strict:
        return pred.start == gold.start and pred.end == gold.end
    return pred.start < gold.end and gold.start < pred.end


def match_sample(
    gold: Sequence[Span], pred: Sequence[Span], *, strict: bool = False
) -> dict[str, TypeCounts]:
    """
    Score one sample's predictions against its gold spans.

    Each gold span matches at most one prediction of the same canonical type.
    Unmatched predictions are false positives, including those landing on an
    ``UNSUPPORTED`` gold span; ``UNSUPPORTED`` gold spans are never counted.
    """
    counts: dict[str, TypeCounts] = defaultdict(TypeCounts)
    unmatched = [g for g in gold if g.label != UNSUPPORTED]

    for p in sorted(pred, key=lambda s: (s.start, s.end)):
        label = canonical(p.label)
        hit = next(
            (g for g in unmatched if canonical(g.label) == label and _matches(p, g, strict)),
            None,
        )
        if hit is None:
            counts[label].fp += 1
        else:
            unmatched.remove(hit)
            counts[label].tp += 1

    for g in unmatched:
        counts[canonical(g.label)].fn += 1
    return dict(counts)


def aggregate(per_sample: Iterable[Mapping[str, TypeCounts]]) -> dict[str, TypeCounts]:
    """Sum per-type counts across samples."""
    total: dict[str, TypeCounts] = defaultdict(TypeCounts)
    for counts in per_sample:
        for label, c in counts.items():
            total[label] = total[label] + c
    return dict(total)


def micro(counts: Mapping[str, TypeCounts]) -> TypeCounts:
    """Micro-average: sum counts over every type."""
    return sum(counts.values(), TypeCounts())


def format_metric(value: float, support: int) -> str:
    """Format a metric as a percentage, or ``n < 20`` when there is too little gold data."""
    if support < MIN_SUPPORT:
        return f"n < {MIN_SUPPORT}"
    return f"{value:.1%}"
