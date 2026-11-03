"""Tests for accuracy benchmark span matching and metrics."""

from benchmarks.accuracy.scoring import (
    UNSUPPORTED,
    Span,
    TypeCounts,
    aggregate,
    format_metric,
    match_sample,
    micro,
)


def test_overlap_match_is_tp():
    result = match_sample([Span(10, 20, "email")], [Span(12, 20, "email")])
    assert result == {"email": TypeCounts(1, 0, 0)}


def test_strict_requires_exact_bounds():
    result = match_sample([Span(10, 20, "email")], [Span(12, 20, "email")], strict=True)
    assert result == {"email": TypeCounts(0, 1, 1)}


def test_type_mismatch_is_fp_and_fn():
    result = match_sample([Span(0, 11, "ssn")], [Span(0, 11, "us_ein")])
    assert result == {"ssn": TypeCounts(0, 0, 1), "us_ein": TypeCounts(0, 1, 0)}


def test_phone_and_in_phone_are_equivalent():
    result = match_sample([Span(0, 14, "phone")], [Span(0, 14, "in_phone")])
    assert result == {"phone": TypeCounts(1, 0, 0)}


def test_second_prediction_on_same_gold_is_fp():
    result = match_sample([Span(0, 10, "email")], [Span(0, 5, "email"), Span(5, 10, "email")])
    assert result == {"email": TypeCounts(1, 1, 0)}


def test_prediction_on_unsupported_gold_is_fp():
    result = match_sample([Span(0, 9, UNSUPPORTED)], [Span(0, 9, "credit_card")])
    assert result == {"credit_card": TypeCounts(0, 1, 0)}
    assert UNSUPPORTED not in result


def test_unsupported_gold_never_fn():
    assert match_sample([Span(0, 9, UNSUPPORTED)], []) == {}


def test_type_with_only_false_positives():
    counts = TypeCounts(0, 3, 0)
    assert counts.precision == 0.0
    assert counts.recall == 0.0
    assert counts.f1 == 0.0
    assert counts.support == 0


def test_metrics_math():
    counts = TypeCounts(8, 2, 2)
    assert counts.precision == 0.8
    assert counts.recall == 0.8
    assert abs(counts.f1 - 0.8) < 1e-9


def test_aggregate_and_micro():
    total = aggregate([
        {"email": TypeCounts(1, 0, 1)},
        {"email": TypeCounts(2, 1, 0), "ssn": TypeCounts(0, 0, 3)},
    ])
    assert total == {"email": TypeCounts(3, 1, 1), "ssn": TypeCounts(0, 0, 3)}
    assert micro(total) == TypeCounts(3, 1, 4)


def test_format_metric():
    assert format_metric(0.9, 19) == "n < 20"
    assert format_metric(0.9234, 20) == "92.3%"
