"""CLI entrypoint for PromptVeil detection-accuracy benchmarks."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from promptveil import __version__
from promptveil.detector.base import BaseDetector
from promptveil.detector.india_detector import IndiaDetector
from promptveil.detector.regex_detector import RegexDetector, _resolve_overlaps
from promptveil.detector.us_detector import USDetector

from benchmarks.accuracy.loaders import (
    DEFAULT_LIMIT,
    DEFAULT_SEED,
    LOADERS,
    LoadResult,
    MissingDependency,
)
from benchmarks.accuracy.scoring import Span, TypeCounts, aggregate, format_metric, match_sample, micro

RESULTS_DIR = ROOT / "benchmarks" / "accuracy" / "results"
INSTALL_HINT = 'Install the benchmark extra from the repo root: pip install -e ".[bench]" (promptveil[bench])'


def default_detectors() -> list[BaseDetector]:
    """The full detector stack, as used by the performance suite."""
    return [RegexDetector(), IndiaDetector(), USDetector()]


def predict(text: str, detectors: Sequence[BaseDetector]) -> list[Span]:
    """Run every detector and keep the spans ``Shield`` would mask."""
    entities = [e for d in detectors for e in d.detect(text)]
    return [Span(e.start, e.end, e.entity_type) for e in _resolve_overlaps(entities)]


def _as_dict(c: TypeCounts) -> dict[str, Any]:
    return {"tp": c.tp, "fp": c.fp, "fn": c.fn, "precision": c.precision, "recall": c.recall, "f1": c.f1}


def evaluate(result: LoadResult, detectors: Sequence[BaseDetector]) -> dict[str, Any]:
    overlap, strict = [], []
    for sample in result.samples:
        pred = predict(sample.text, detectors)
        overlap.append(match_sample(sample.spans, pred))
        strict.append(match_sample(sample.spans, pred, strict=True))
    overlap_totals, strict_totals = aggregate(overlap), aggregate(strict)
    return {
        "samples": len(result.samples),
        "skipped_spans": result.skipped_spans,
        "revision": result.revision,
        "labels_complete": result.labels_complete,
        "overlap": {k: _as_dict(v) for k, v in sorted(overlap_totals.items())},
        "strict": {k: _as_dict(v) for k, v in sorted(strict_totals.items())},
        "micro": {"overlap": _as_dict(micro(overlap_totals)), "strict": _as_dict(micro(strict_totals))},
    }


def _row(name: str, c: Mapping[str, Any], recall_only: bool = False) -> str:
    support = c["tp"] + c["fn"]
    if recall_only:
        return f"| {name} | {support} | {c['tp']} | n/a | {c['fn']} | n/a | {format_metric(c['recall'], support)} | n/a |"
    metrics = " | ".join(format_metric(c[m], support) for m in ("precision", "recall", "f1"))
    return f"| {name} | {support} | {c['tp']} | {c['fp']} | {c['fn']} | {metrics} |"


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [f"PromptVeil {report['promptveil_version']} · run {report['date']} · overlap match"]
    for name, ds in report["datasets"].items():
        recall_only = not ds.get("labels_complete", True)
        lines += [
            "",
            f"### {name}",
            "",
            f"{ds['samples']} samples · revision `{ds['revision']}` · {ds['skipped_spans']} misaligned gold spans skipped",
        ]
        if recall_only:
            lines += ["", "_Labels are incomplete for this dataset, so results are recall only._"]
        lines += [
            "",
            "| Type | Gold | TP | FP | FN | Precision | Recall | F1 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        lines += [
            _row(t, c, recall_only)
            for t, c in ds["overlap"].items()
            if not (recall_only and c["tp"] + c["fn"] == 0)
        ]
        lines.append(_row("**Micro avg**", ds["micro"]["overlap"], recall_only))
    for name, err in report.get("errors", {}).items():
        lines += ["", f"### {name}", "", f"Failed to load: {err}"]
    return "\n".join(lines) + "\n"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PromptVeil detection-accuracy benchmarks.")
    parser.add_argument("--datasets", default=",".join(LOADERS), help="Comma-separated: " + ", ".join(LOADERS))
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Nemotron sample size.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Nemotron sample seed.")
    parser.add_argument("--out-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)
    args.datasets = [d.strip() for d in args.datasets.split(",") if d.strip()]
    unknown = [d for d in args.datasets if d not in LOADERS]
    if unknown:
        parser.error(f"unknown dataset(s): {', '.join(unknown)}")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    detectors = default_detectors()
    now = datetime.now()
    report: dict[str, Any] = {
        "config": {"datasets": args.datasets, "limit": args.limit, "seed": args.seed},
        "promptveil_version": __version__,
        "date": now.strftime("%Y-%m-%d"),
        "datasets": {},
        "errors": {},
    }

    for name in args.datasets:
        kwargs = {"limit": args.limit, "seed": args.seed} if name == "nemotron" else {}
        try:
            result = LOADERS[name](**kwargs)
        except MissingDependency:
            print(INSTALL_HINT, file=sys.stderr)
            return 2
        except Exception as exc:  # report and carry on with the other datasets
            print(f"{name}: failed to load: {exc}", file=sys.stderr)
            report["errors"][name] = f"{type(exc).__name__}: {exc}"
            continue
        report["datasets"][name] = evaluate(result, detectors)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / f"{now.strftime('%Y-%m-%d_%H-%M')}.json"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown = render_markdown(report)
    (args.out_dir / "latest.md").write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"Wrote {json_path}")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
