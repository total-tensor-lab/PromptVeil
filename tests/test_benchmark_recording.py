"""Regression coverage for compact benchmark reports."""

import pytest

from benchmarks.run_benchmarks import _percentiles, _summary_rows
from benchmarks.utils.recording import compact_results


def test_compact_results_preserves_metrics_and_summary():
    payload = {
        "machine_info": {
            "node": "private-host",
            "system": "Linux",
            "python_version": "3.13.9",
            "release": "6.8.0",
            "cpu": {"brand_raw": "Test CPU", "count": 8, "flags": ["avx"]},
        },
        "commit_info": {"id": "revision"},
        "datetime": "2026-10-31T00:00:00+00:00",
        "benchmarks": [
            {
                "name": "test_scan[large]",
                "param": "large",
                "params": {"case": "full corpus" * 1000},
                "extra_info": {"size_chars": 1000, "peak_memory_bytes": 4096},
                "stats": {
                    "data": [1.0, 2.0, 3.0, 4.0, 5.0],
                    "mean": 3.0,
                    "median": 3.0,
                    "ops": 1 / 3,
                    "rounds": 5,
                },
            }
        ],
    }
    original_summary = _summary_rows(payload)

    compact_results(payload)

    assert payload["machine_info"] == {
        "system": "Linux",
        "python_version": "3.13.9",
        "cpu": {"brand_raw": "Test CPU", "count": 8},
    }
    assert "commit_info" not in payload
    entry = payload["benchmarks"][0]
    assert "params" not in entry
    assert "data" not in entry["stats"]
    assert entry["param"] == "large"
    assert entry["extra_info"]["size_chars"] == 1000
    assert entry["stats"]["rounds"] == 5
    assert _percentiles(entry["stats"]) == pytest.approx((3.0, 4.8, 4.96))
    assert _summary_rows(payload) == original_summary
    compact_results(payload)
    assert _summary_rows(payload) == original_summary


def test_compact_results_handles_reports_without_samples():
    payload = {"benchmarks": [{"stats": {"median": 2.0, "data": []}}]}
    compact_results(payload)
    assert _percentiles(payload["benchmarks"][0]["stats"]) == (2.0, None, None)
