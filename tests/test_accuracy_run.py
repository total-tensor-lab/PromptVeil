"""Tests for the accuracy benchmark runner."""

import json

import pytest

from benchmarks.accuracy import run
from benchmarks.accuracy.loaders import LOADERS, LoadResult, MissingDependency
from benchmarks.accuracy.scoring import Sample, Span


def test_predict_resolves_overlaps():
    spans = run.predict("call +91 98765 43210", run.default_detectors())
    assert len(spans) == 1
    assert spans[0].label in {"phone", "in_phone"}


def test_evaluate_on_tiny_sample():
    text = "mail alice@example.com"
    result = LoadResult([Sample("t", "1", text, (Span(5, 22, "email"),))], 0, "rev")
    report = run.evaluate(result, run.default_detectors())
    assert report["samples"] == 1
    assert report["overlap"]["email"]["tp"] == 1
    assert report["micro"]["overlap"]["tp"] == 1


def test_render_markdown_small_support():
    counts = {"tp": 0, "fp": 2, "fn": 0, "precision": 0.0, "recall": 0.0, "f1": 0.0}
    report = {
        "promptveil_version": "0.2.0",
        "date": "2026-11-03",
        "datasets": {
            "nemotron": {
                "samples": 10, "skipped_spans": 0, "revision": "abc",
                "overlap": {"in_aadhaar": counts}, "strict": {"in_aadhaar": counts},
                "micro": {"overlap": counts, "strict": counts},
            },
        },
    }
    md = run.render_markdown(report)
    assert "### nemotron" in md
    row = next(line for line in md.splitlines() if line.startswith("| in_aadhaar"))
    assert row == "| in_aadhaar | 0 | 0 | 2 | 0 | n < 20 | n < 20 | n < 20 |"


def test_main_promptveil_bench_only(tmp_path):
    assert run.main(["--datasets", "promptveil_bench", "--out-dir", str(tmp_path)]) == 0
    assert (tmp_path / "latest.md").exists()
    [json_file] = tmp_path.glob("*.json")
    data = json.loads(json_file.read_text())
    assert "promptveil_bench" in data["datasets"]


def _raise(exc):
    def loader(**_kwargs):
        raise exc
    return loader


def test_missing_datasets_package_message(monkeypatch, capsys, tmp_path):
    monkeypatch.setitem(LOADERS, "gretel", _raise(MissingDependency("datasets")))
    assert run.main(["--datasets", "gretel", "--out-dir", str(tmp_path)]) == 2
    assert "promptveil[bench]" in capsys.readouterr().err


def test_failed_dataset_exits_1(monkeypatch, tmp_path):
    monkeypatch.setitem(LOADERS, "gretel", _raise(OSError("network down")))
    code = run.main(["--datasets", "gretel,promptveil_bench", "--out-dir", str(tmp_path)])
    assert code == 1
    [json_file] = tmp_path.glob("*.json")
    data = json.loads(json_file.read_text())
    assert "promptveil_bench" in data["datasets"]
    assert "network down" in data["errors"]["gretel"]


def test_unknown_dataset_rejected():
    with pytest.raises(SystemExit):
        run.main(["--datasets", "nope"])
