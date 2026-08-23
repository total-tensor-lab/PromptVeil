"""CLI entrypoint for PromptVeil benchmark runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.utils.recording import format_bytes, format_ops, format_seconds, percentile

RESULTS_DIR = ROOT / "benchmarks" / "results"


def _default_output_path() -> Path:
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    return RESULTS_DIR / f"{timestamp}.json"


def _percentiles(stats: dict[str, Any]) -> tuple[float | None, float | None, float | None]:
    data = stats.get("data") or []
    if data:
        return (
            percentile(data, 50),
            percentile(data, 95),
            percentile(data, 99),
        )
    return (
        stats.get("median"),
        None,
        None,
    )


def _summary_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for entry in payload.get("benchmarks", []):
        stats = entry.get("stats", {})
        extra = entry.get("extra_info", {})
        p50, p95, p99 = _percentiles(stats)
        rows.append(
            {
                "name": entry.get("fullname") or entry.get("name") or "<unknown>",
                "mean": stats.get("mean"),
                "p50": p50,
                "p95": p95,
                "p99": p99,
                "ops": stats.get("ops"),
                "peak": extra.get("peak_memory_bytes"),
            }
        )
    return rows


def _print_summary(payload: dict[str, Any], output_path: Path) -> None:
    rows = _summary_rows(payload)
    if not rows:
        print(f"No benchmark rows recorded in {output_path}")
        return

    header = f"{'Benchmark':60} {'Mean':>12} {'P50':>12} {'P95':>12} {'P99':>12} {'Ops/s':>12} {'Peak':>12}"
    print("\nBenchmark Summary")
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['name'][:60]:60} "
            f"{format_seconds(row['mean']):>12} "
            f"{format_seconds(row['p50']):>12} "
            f"{format_seconds(row['p95']):>12} "
            f"{format_seconds(row['p99']):>12} "
            f"{format_ops(row['ops']):>12} "
            f"{format_bytes(row['peak']):>12}"
        )
    print(f"\nSaved JSON results to {output_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run PromptVeil benchmark suite.",
        epilog="Unknown arguments are forwarded to pytest, for example: -k scan_latency --collect-only",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write benchmark JSON to this path. Defaults to benchmarks/results/<timestamp>.json",
    )
    parser.add_argument(
        "--benchmark-min-rounds",
        default="5",
        help="Forwarded to pytest-benchmark as --benchmark-min-rounds.",
    )
    args, pytest_args = parser.parse_known_args(argv)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = (args.output or _default_output_path()).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "pytest",
        str(ROOT / "benchmarks"),
        "-m",
        "benchmark_suite",
        "--benchmark-json",
        str(output_path),
        "--benchmark-save-data",
        "--benchmark-sort",
        "name",
        "--benchmark-min-rounds",
        str(args.benchmark_min_rounds),
        *pytest_args,
    ]

    completed = subprocess.run(command, cwd=ROOT)
    if completed.returncode != 0:
        return completed.returncode

    with output_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    _print_summary(payload, output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
