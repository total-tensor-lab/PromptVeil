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
