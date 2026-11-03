# Privacy Accuracy Benchmarks — Design

**Date:** 2026-11-03
**Branch:** `feat/privacy-benchmarks`
**Status:** Approved design, pending spec review

## Goal

Measure how accurately PromptVeil detects the PII and secrets it claims to
support, using public third-party datasets plus our own labelled set, and publish
the results in the docs site and on the product page. Results must be
reproducible with one command and honest about scope.

## Scope

In scope:

- Detection accuracy (precision, recall, F1) per entity type and per dataset.
- Only entity types PromptVeil supports (14 types, see *Label mapping*).
  Dataset labels for unsupported types (names, addresses, dates, …) are not
  scored for recall.
- Two public datasets, downloaded at run time (never vendored):
  - `gretelai/synthetic_pii_finance_multilingual` (Apache-2.0), English rows
    of the `test` split.
  - `nvidia/Nemotron-PII` (CC-BY-4.0), seeded random sample of the `test` split.
- One in-repo dataset, **PromptVeil-Bench v1**, covering types the public
  datasets do not (India IDs, US EIN, US passport) plus hard negatives.
- A new docs page, `docs/benchmarks.md`, and a short product-page summary block.

Out of scope:

- Comparison against other tools (Presidio etc.).
- Policy behaviour (mask/block/allow) — we measure detection only.
- Non-English text.
- Changes to detectors. Weak spots the benchmark reveals become follow-up issues.
- The existing performance suite in `benchmarks/` — untouched.

Not used: `ai4privacy/pii-masking-400k`. Its licence allows academic and
non-commercial use only; publishing results on a commercial product page would
need a licence from ai4privacy.

## Design

### 1. Layout

```
benchmarks/accuracy/
    __init__.py
    run.py            # CLI entry point
    scoring.py        # span matching + metrics (pure, no I/O)
    labels.py         # dataset label -> PromptVeil type mapping
    datasets.py       # loaders: gretel, nemotron, promptveil_bench -> Sample
    generate_bench.py # seeded generator for PromptVeil-Bench
    data/promptveil_bench_v1.jsonl   # committed output of generate_bench.py
    results/          # JSON + Markdown output of each run
```

Common record type:

```python
@dataclass(frozen=True)
class Span:
    start: int; end: int; label: str     # label = PromptVeil type, or "_unsupported"

@dataclass(frozen=True)
class Sample:
    dataset: str; sample_id: str; text: str; spans: tuple[Span, ...]
```

### 2. Running detection

Each sample's text goes through the full detector stack
(`RegexDetector`, `IndiaDetector`, `USDetector`), the same set the performance
suite uses. We call each detector's `detect()` and combine the results, so
policy settings (block raising `SensitiveDataError`, allow rules, thresholds)
do not affect the numbers.

### 3. Label mapping

`labels.py` holds one table per dataset that maps the dataset's label to a
PromptVeil type. Any label not in the table becomes `_unsupported`. Planned
mapping (exact label strings to be checked against the data during
implementation):

| PromptVeil type | Gretel | Nemotron-PII | PromptVeil-Bench |
|---|---|---|---|
| email | `email` | `email` | yes |
| phone | `phone_number` | `phone_number` | yes |
| credit_card | `credit_card_number` | card-number label, if present | yes |
| api_key | `api_key` | api-key label, if present | yes |
| ssn | `ssn` | `ssn` | yes |
| us_passport, us_ein | — | — | yes |
| in_aadhaar, in_pan, in_phone, in_passport, in_voter_id, in_ifsc, in_gstin | — | — | yes |

`phone` and `in_phone` count as the same type when matching, since both
detectors can legitimately claim a phone number.

### 4. Scoring

- **Match rule (headline):** a prediction is a true positive (TP) when it has
  the same type as a gold span and their character ranges overlap. Each gold
  span can match at most one prediction.
- **Strict rule (secondary):** exact `start`/`end` match. Reported in the JSON
  output and in a docs-page footnote.
- **False positives (FP):** every prediction that is not a TP, including one
  that lands on a span labelled `_unsupported` (for example a customer ID
  flagged as `credit_card`). Users see that as over-masking, so it counts
  against precision.
- **False negatives (FN):** gold spans of supported types with no match.
  `_unsupported` gold spans never count as FN.
- Precision, recall and F1 are computed per type and per dataset, plus a
  micro-average per dataset. Types with fewer than 20 gold spans in a dataset
  are reported as `n < 20` instead of a percentage.
- No cross-dataset aggregate headline: public and in-house results stay in
  separate tables.

### 5. PromptVeil-Bench v1

- `generate_bench.py` builds it with a fixed seed. Spans are computed while
  inserting values, so labels are correct by construction.
- Content:
  - About 50 positives per supported type.
  - About 300 hard negatives: order and invoice numbers, timestamps, version
    strings, 12-digit numbers that fail the Aadhaar checksum, 9-digit numbers
    in non-SSN contexts, and look-alike strings that are not PAN or GSTIN.
- Formatting varies (spaces, dashes, no separators, line breaks, nearby
  punctuation, upper and lower case) across about 30 hand-written English and
  Indian-English templates (chat prompts, support tickets, forms, logs).
- Values are produced by format, not copied from the detector regexes, so the
  set is not just a mirror of the patterns. The docs page still states clearly
  that this set is ours and is reported separately.
- The generated JSONL is committed. The generator is committed alongside it so
  the set can be regenerated and reviewed.

### 6. Reproducibility

- Dataset revisions are pinned to Hugging Face commit SHAs in `datasets.py`.
- Nemotron sample: a seeded random draw of 5,000 documents. It is not filtered
  to documents that contain supported types, because filtering would inflate
  precision.
- The CLI is `python -m benchmarks.accuracy.run [--datasets gretel,nemotron,promptveil_bench] [--limit N] [--seed S]`.
- Each run writes `results/<YYYY-MM-DD_HH-MM>.json` (config, dataset SHAs,
  PromptVeil version, per-type counts and metrics, both match rules) and
  `results/latest.md` (tables ready to paste into the docs).
- New optional extra: `bench = ["datasets>=2.18"]`. The core install is unchanged.

### 7. Publication

- `docs/benchmarks.md`, added to `website/sidebars.js` after `api-reference`:
  - headline table per dataset
  - method (match rules, FP policy, scope)
  - dataset versions and attribution (CC-BY requires credit to NVIDIA)
  - known limitations
  - how to reproduce
  - a link to the performance suite
- A link from the README "Documentation" list.
- A product-page summary block (3–4 headline numbers, one-line method, link to
  the docs page), delivered to the user as text, since the product site lives
  outside this repo.
- Numbers on the page are whatever the run produces. Weak types are shown, not
  hidden.

## Error handling

- Missing `datasets` package: exit with a message that names
  `pip install "promptveil[bench]"`.
- Download failure for one dataset: report it, skip that dataset, continue with
  the others, and exit non-zero.
- A gold span whose offsets don't match the text (bad source data): skip the
  span, count it in a `skipped_spans` field, and warn.

## Testing

- `tests/test_accuracy_scoring.py`: unit tests for overlap matching, one-to-one
  gold matching, the `phone`/`in_phone` equivalence, `_unsupported` handling,
  strict versus overlap rules, metric maths and the `n < 20` rule. Network-free.
- `tests/test_accuracy_datasets.py`: label-mapping tests on small inline
  fixtures shaped like each dataset's rows, plus a PromptVeil-Bench integrity
  check (every span's offsets slice the text to a non-empty value).
- No test downloads data. The full run is manual.
