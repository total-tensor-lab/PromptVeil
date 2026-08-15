"""Helpers for benchmark metadata, memory sampling, and result summaries."""

from __future__ import annotations

from dataclasses import dataclass
import gc
import math
import tracemalloc
from typing import Any, Iterable


@dataclass(frozen=True)
class MemorySample:
    retained_bytes: int
    peak_bytes: int


def attach_metadata(benchmark, **metadata: Any) -> None:
    """Attach JSON-serializable metadata to a pytest-benchmark entry."""
    benchmark.extra_info.update(metadata)


def measure_memory(func, *args, **kwargs):
    """Run *func* under tracemalloc and return ``(result, MemorySample)``."""
    gc.collect()
    tracemalloc.start()
    baseline_current, _ = tracemalloc.get_traced_memory()
    result = func(*args, **kwargs)
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    retained = max(0, current - baseline_current)
    return result, MemorySample(retained_bytes=retained, peak_bytes=peak)


def percentile(values: Iterable[float], percent: float) -> float | None:
    samples = sorted(values)
    if not samples:
        return None
    if len(samples) == 1:
        return samples[0]
    rank = (len(samples) - 1) * (percent / 100.0)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return samples[lower]
    weight = rank - lower
    return samples[lower] + (samples[upper] - samples[lower]) * weight


def format_seconds(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value * 1000:.3f} ms"


def format_ops(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:,.1f}"


def format_bytes(value: int | None) -> str:
    if value is None:
        return "-"
    units = ("B", "KB", "MB", "GB")
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(amount)} {unit}"
            return f"{amount:.2f} {unit}"
        amount /= 1024
    return f"{value} B"
