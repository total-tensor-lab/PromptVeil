"""Load benchmark datasets as :class:`Sample` lists with PromptVeil-typed gold spans."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from benchmarks.accuracy.labels import GRETEL, NEMOTRON, map_label
from benchmarks.accuracy.scoring import UNSUPPORTED, Sample, Span

BENCH_PATH = Path(__file__).parent / "data" / "promptveil_bench_v1.jsonl"

GRETEL_REPO = "gretelai/synthetic_pii_finance_multilingual"
GRETEL_REVISION = "7b844d16738527a04264f50214cb426a4cea0897"
GRETEL_FILE = "data/English_test-00000-of-00001.parquet"

NEMOTRON_REPO = "nvidia/Nemotron-PII"
NEMOTRON_REVISION = "b70ffaf5ff39e079776134c5bf4381f00a9fd1ed"
NEMOTRON_FILE = "data/test-00000-of-00001.parquet"

DEFAULT_LIMIT = 5000
DEFAULT_SEED = 20261103


class MissingDependency(Exception):
    """The optional ``datasets`` package is not installed."""


@dataclass
class LoadResult:
    samples: list[Sample]
    skipped_spans: int
    revision: str
    # False when the dataset leaves some real PII unlabelled, so FP counts are
    # not trustworthy and only recall is reported.
    labels_complete: bool = True


def _build_spans(
    text: str, raw_spans: Iterable[Mapping[str, Any]], to_label: Callable[[str], str]
) -> tuple[tuple[Span, ...], int]:
    """Validate raw spans against *text*; return the good ones and a skip count."""
    spans: list[Span] = []
    skipped = 0
    for s in raw_spans:
        start, end = s["start"], s["end"]
        if start < 0 or end > len(text) or start >= end:
            skipped += 1
            continue
        if "text" in s and text[start:end] != s["text"]:
            skipped += 1
            continue
        spans.append(Span(start, end, to_label(s["label"])))
    return tuple(spans), skipped


def parse_gretel_row(row: Mapping[str, Any]) -> tuple[Sample, int]:
    text = row["generated_text"]
    spans, skipped = _build_spans(
        text, json.loads(row["pii_spans"]), lambda label: map_label(GRETEL, label)
    )
    return Sample("gretel", str(row["__index_level_0__"]), text, spans), skipped


def parse_nemotron_row(row: Mapping[str, Any]) -> tuple[Sample, int]:
    text = row["text"]
    is_us = row["locale"] == "us"

    def to_label(label: str) -> str:
        if label == "tax_id":
            return "us_ein" if is_us else UNSUPPORTED
        return map_label(NEMOTRON, label)

    # Nemotron stores spans as a Python literal, not JSON.
    spans, skipped = _build_spans(text, ast.literal_eval(row["spans"]), to_label)
    return Sample("nemotron", str(row["uid"]), text, spans), skipped


def _load_hf(repo: str, data_file: str, revision: str):
    try:
        import datasets as hf
    except ImportError as exc:
        raise MissingDependency("datasets") from exc
    return hf.load_dataset(repo, data_files=data_file, revision=revision, split="train")


def _collect(rows: Iterable[Mapping[str, Any]], parse, revision: str) -> LoadResult:
    samples: list[Sample] = []
    skipped = 0
    for row in rows:
        sample, n = parse(row)
        samples.append(sample)
        skipped += n
    return LoadResult(samples, skipped, revision)


def load_gretel() -> LoadResult:
    ds = _load_hf(GRETEL_REPO, GRETEL_FILE, GRETEL_REVISION)
    result = _collect(ds, parse_gretel_row, GRETEL_REVISION)
    # Gretel labels only the PII types each document was generated for; e.g.
    # 500 of 813 email addresses in the English test split carry no label.
    result.labels_complete = False
    return result


def load_nemotron(limit: int = DEFAULT_LIMIT, seed: int = DEFAULT_SEED) -> LoadResult:
    ds = _load_hf(NEMOTRON_REPO, NEMOTRON_FILE, NEMOTRON_REVISION)
    ds = ds.shuffle(seed=seed).select(range(min(limit, len(ds))))
    return _collect(ds, parse_nemotron_row, NEMOTRON_REVISION)


def load_promptveil_bench(path: Path = BENCH_PATH) -> LoadResult:
    raw = path.read_bytes()
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]

    def parse(row: Mapping[str, Any]) -> tuple[Sample, int]:
        spans, skipped = _build_spans(row["text"], row["spans"], lambda label: label)
        return Sample("promptveil_bench", row["id"], row["text"], spans), skipped

    return _collect(rows, parse, hashlib.sha256(raw).hexdigest()[:12])


LOADERS: dict[str, Callable[..., LoadResult]] = {
    "gretel": load_gretel,
    "nemotron": load_nemotron,
    "promptveil_bench": load_promptveil_bench,
}
