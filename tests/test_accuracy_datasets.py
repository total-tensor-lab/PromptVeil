"""Tests for accuracy benchmark label mapping and dataset row parsing."""

import json

from benchmarks.accuracy.labels import GRETEL, map_label
from benchmarks.accuracy.loaders import parse_gretel_row, parse_nemotron_row
from benchmarks.accuracy.scoring import UNSUPPORTED, Span


def _nemotron_row(text, spans, locale="us"):
    return {"uid": "abc", "locale": locale, "text": text, "spans": str(spans)}


def test_map_label_unknown_is_unsupported():
    assert map_label(GRETEL, "name") == UNSUPPORTED


def test_parse_gretel_row():
    text = "Betty Norris, betty@example.com"
    row = {
        "__index_level_0__": 7,
        "generated_text": text,
        "pii_spans": json.dumps([
            {"start": 0, "end": 12, "label": "name"},
            {"start": 14, "end": 31, "label": "email"},
        ]),
    }
    sample, skipped = parse_gretel_row(row)
    assert sample.sample_id == "7"
    assert sample.text == text
    assert sample.spans == (Span(0, 12, UNSUPPORTED), Span(14, 31, "email"))
    assert skipped == 0


def test_parse_nemotron_row_literal_spans():
    text = "Card 5490 3479 1287 6543 on file"
    spans = [{"start": 5, "end": 24, "text": "5490 3479 1287 6543", "label": "credit_debit_card"}]
    sample, skipped = parse_nemotron_row(_nemotron_row(text, spans))
    assert sample.spans == (Span(5, 24, "credit_card"),)
    assert skipped == 0


def test_parse_nemotron_skips_misaligned_span():
    text = "Card 5490 3479 1287 6543 on file"
    spans = [{"start": 4, "end": 24, "text": "5490 3479 1287 6543", "label": "credit_debit_card"}]
    sample, skipped = parse_nemotron_row(_nemotron_row(text, spans))
    assert sample.spans == ()
    assert skipped == 1


def test_nemotron_tax_id_depends_on_locale():
    text = "EIN 43-5478236"
    spans = [{"start": 4, "end": 14, "text": "43-5478236", "label": "tax_id"}]
    us, _ = parse_nemotron_row(_nemotron_row(text, spans, locale="us"))
    intl, _ = parse_nemotron_row(_nemotron_row(text, spans, locale="intl"))
    assert us.spans == (Span(4, 14, "us_ein"),)
    assert intl.spans == (Span(4, 14, UNSUPPORTED),)


def test_out_of_range_span_skipped():
    row = {
        "__index_level_0__": 1,
        "generated_text": "short",
        "pii_spans": json.dumps([{"start": 0, "end": 50, "label": "email"}]),
    }
    sample, skipped = parse_gretel_row(row)
    assert sample.spans == ()
    assert skipped == 1


# ── PromptVeil-Bench v1 ───────────────────────────────────────────────────

BENCH_TYPES = {
    "email", "phone", "in_phone", "credit_card", "api_key", "ssn", "us_passport",
    "us_ein", "in_aadhaar", "in_pan", "in_passport", "in_voter_id", "in_ifsc", "in_gstin",
}


def test_bench_spans_slice_text():
    from benchmarks.accuracy.loaders import load_promptveil_bench

    result = load_promptveil_bench()
    assert result.skipped_spans == 0
    for sample in result.samples:
        for span in sample.spans:
            assert 0 <= span.start < span.end <= len(sample.text)
            assert span.label in BENCH_TYPES


def test_bench_counts():
    from collections import Counter

    from benchmarks.accuracy.loaders import load_promptveil_bench

    samples = load_promptveil_bench().samples
    per_type = Counter(span.label for s in samples for span in s.spans)
    assert per_type == {label: 50 for label in BENCH_TYPES}
    assert sum(1 for s in samples if not s.spans) == 300


def test_bench_is_reproducible():
    from benchmarks.accuracy.generate_bench import generate, serialize
    from benchmarks.accuracy.loaders import BENCH_PATH

    assert serialize(generate()) == BENCH_PATH.read_text(encoding="utf-8")


def test_gretel_labels_marked_incomplete(monkeypatch):
    from benchmarks.accuracy import loaders

    monkeypatch.setattr(loaders, "_load_hf", lambda *a: [])
    assert loaders.load_gretel().labels_complete is False
    assert loaders.load_promptveil_bench().labels_complete is True
