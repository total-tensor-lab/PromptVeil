# Privacy Accuracy Benchmarks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure PromptVeil's detection accuracy (precision/recall/F1 per type) on two public datasets and an in-repo set, and publish the results in the docs.

**Architecture:** A self-contained `benchmarks/accuracy/` package. Loaders turn each dataset into `Sample`s with gold `Span`s. The runner runs the full detector stack and resolves overlaps the same way `Shield` does. A pure scoring module computes the metrics. Each run writes JSON and a Markdown table, and the table is pasted into `docs/benchmarks.md`.

**Tech Stack:** Python ≥3.10, pytest, Hugging Face `datasets` (new `bench` extra), Docusaurus docs site in `website/`.

**Spec:** `docs/superpowers/specs/2026-11-03-privacy-accuracy-benchmarks-design.md`

## Global Constraints

- The core install stays `PyYAML` only. Add `bench = ["datasets>=2.18"]` under `[project.optional-dependencies]`.
- Never vendor public data. Download it at run time at pinned revisions:
  - `nvidia/Nemotron-PII` @ `b70ffaf5ff39e079776134c5bf4381f00a9fd1ed`, file `data/test-00000-of-00001.parquet`, columns `text`, `spans` (a **Python-literal** string; parse with `ast.literal_eval`), `uid`, `locale` (`us` / `intl`).
  - `gretelai/synthetic_pii_finance_multilingual` @ `7b844d16738527a04264f50214cb426a4cea0897`, file `data/English_test-00000-of-00001.parquet` (2,891 rows), text column `generated_text`, span column `pii_spans` (a **JSON** string of `{start, end, label}`), with `__index_level_0__` as the id.
- Nemotron: seeded random sample of 5,000 docs (default seed `20261103`). Do not filter by label content.
- Detector stack: `[RegexDetector(), IndiaDetector(), USDetector()]`. Predictions go through `promptveil.shield._resolve_overlaps` and do not depend on policy.
- `phone` ≡ `in_phone` for matching. Label constant `UNSUPPORTED = "_unsupported"`. `MIN_SUPPORT = 20`.
- No test touches the network.
- Existing `benchmarks/` performance suite is unchanged.
- Docs page must credit NVIDIA (CC-BY-4.0) and Gretel (Apache-2.0).
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never commit `CLAUDE.md`.

## Review Focus

1. **Gold offsets that don't match the text.** About 2% of Nemotron spans have `text` ≠ `text[start:end]`. Expect the span to be skipped, counted in `skipped_spans`, and the run to continue. Test: `test_parse_nemotron_skips_misaligned_span` (Task 2).
2. **Several predictions on one gold span** (e.g. two detectors, or two regex alternatives). Expect only one TP and the rest FP. Overlap resolution should already collapse exact duplicates. Test: `test_second_prediction_on_same_gold_is_fp` (Task 1).
3. **A type with zero gold spans but some FPs** (e.g. `in_aadhaar` firing on Nemotron). Expect the row to be shown with FP visible and metrics as `n < 20`, with no division-by-zero crash. Test: `test_type_with_only_false_positives` (Task 1) + `test_render_markdown_small_support` (Task 4).
4. **`tax_id` on `intl` Nemotron rows.** It isn't an EIN. Expect it to map to `us_ein` only when `locale == "us"`, and otherwise `_unsupported`. Test: `test_nemotron_tax_id_depends_on_locale` (Task 2).
5. **`datasets` not installed.** Expect exit code 2 with a message naming `pip install "promptveil[bench]"`, and no traceback. Test: `test_missing_datasets_package_message` (Task 4).

---

### Task 1: Scoring module

**Files:**
- Create: `benchmarks/accuracy/__init__.py` (docstring only)
- Create: `benchmarks/accuracy/scoring.py`
- Test: `tests/test_accuracy_scoring.py`

**Interfaces:**
- Produces:
  - `UNSUPPORTED: str = "_unsupported"`, `MIN_SUPPORT: int = 20`
  - `@dataclass(frozen=True) Span(start: int, end: int, label: str)`
  - `@dataclass(frozen=True) Sample(dataset: str, sample_id: str, text: str, spans: tuple[Span, ...])`
  - `@dataclass TypeCounts(tp: int = 0, fp: int = 0, fn: int = 0)`, with properties `support` (= tp+fn), `precision`, `recall`, `f1` (each 0.0 when its denominator is 0), and `__add__`.
  - `canonical(label: str) -> str`: `"in_phone"` → `"phone"`, otherwise unchanged.
  - `match_sample(gold: Sequence[Span], pred: Sequence[Span], *, strict: bool = False) -> dict[str, TypeCounts]`
  - `aggregate(per_sample: Iterable[dict[str, TypeCounts]]) -> dict[str, TypeCounts]`
  - `micro(counts: Mapping[str, TypeCounts]) -> TypeCounts`
  - `format_metric(value: float, support: int) -> str`: returns `"n < 20"` when support < `MIN_SUPPORT`, else `f"{value:.1%}"`.

Matching algorithm (`match_sample`): process predictions sorted by `(start, end)`. Each prediction takes the first still-unmatched gold span with the same `canonical` label that overlaps it (`p.start < g.end and g.start < p.end`), or in strict mode has identical `start`/`end`. A match is a TP under the canonical type. A prediction with no match is an FP under its own canonical type, including when it overlaps an `UNSUPPORTED` gold span. Unmatched gold spans of supported labels are FN. `UNSUPPORTED` gold spans never appear in the output.

- [ ] **Step 1: Write failing tests** in `tests/test_accuracy_scoring.py`:
  - `test_overlap_match_is_tp`: gold `Span(10,20,"email")`, pred `Span(12,20,"email")` → `{"email": TypeCounts(1,0,0)}`
  - `test_strict_requires_exact_bounds`: same input with `strict=True` → `email` tp 0, fp 1, fn 1
  - `test_type_mismatch_is_fp_and_fn`: gold `ssn`, pred `us_ein` on the same range → `ssn` fn 1, `us_ein` fp 1
  - `test_phone_and_in_phone_are_equivalent`: gold `phone`, pred `in_phone` → `{"phone": TypeCounts(1,0,0)}`
  - `test_second_prediction_on_same_gold_is_fp`: one gold `email` 0–10, preds `email` 0–5 and 5–10 → tp 1, fp 1
  - `test_prediction_on_unsupported_gold_is_fp`: gold `Span(0,9,UNSUPPORTED)`, pred `credit_card` 0–9 → `{"credit_card": TypeCounts(0,1,0)}`, and the `UNSUPPORTED` key is absent
  - `test_unsupported_gold_never_fn`: gold `UNSUPPORTED` only, no preds → `{}`
  - `test_type_with_only_false_positives`: `TypeCounts(0,3,0)` → precision 0.0, recall 0.0, f1 0.0, support 0 (no exception)
  - `test_metrics_math`: `TypeCounts(8,2,2)` → precision 0.8, recall 0.8, f1 0.8
  - `test_aggregate_and_micro`: two dicts summed per key; `micro` sums across keys
  - `test_format_metric`: `format_metric(0.9, 19) == "n < 20"`, `format_metric(0.9234, 20) == "92.3%"`
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_accuracy_scoring.py -v`. Expected: FAIL (ModuleNotFoundError).
- [ ] **Step 3: Implement** `benchmarks/accuracy/scoring.py` per the interfaces and algorithm above. Use plain dataclasses and no third-party imports.
- [ ] **Step 4: Run** `.venv/bin/pytest tests/test_accuracy_scoring.py -v`. Expected: all PASS.
- [ ] **Step 5: Commit** with `git add benchmarks/accuracy/__init__.py benchmarks/accuracy/scoring.py tests/test_accuracy_scoring.py` and message `feat: add accuracy benchmark scoring`.

---

### Task 2: Label mapping and dataset loaders

**Files:**
- Create: `benchmarks/accuracy/labels.py`
- Create: `benchmarks/accuracy/datasets.py`
- Modify: `pyproject.toml` (add the `bench` extra after `langchain`)
- Test: `tests/test_accuracy_datasets.py`

**Interfaces:**
- Consumes: `Span`, `Sample`, `UNSUPPORTED` from Task 1.
- Produces:
  - `labels.GRETEL: dict[str, str]`: `email→email`, `phone_number→phone`, `credit_card_number→credit_card`, `ssn→ssn`, `api_key→api_key`, `passport_number→us_passport`
  - `labels.NEMOTRON: dict[str, str]`: `email→email`, `phone_number→phone`, `fax_number→phone`, `credit_debit_card→credit_card`, `ssn→ssn`, `api_key→api_key`
  - `labels.map_label(table: Mapping[str, str], label: str) -> str`: returns the mapped type, or `UNSUPPORTED`
  - `datasets.LoadResult(samples: list[Sample], skipped_spans: int, revision: str)`, a dataclass
  - `datasets.parse_gretel_row(row: Mapping) -> tuple[Sample, int]` and `datasets.parse_nemotron_row(row: Mapping) -> tuple[Sample, int]`. Each returns the sample and its skipped-span count. Both are pure functions with no I/O.
  - `datasets.load_gretel() -> LoadResult`, `datasets.load_nemotron(limit: int = 5000, seed: int = 20261103) -> LoadResult`, `datasets.load_promptveil_bench(path: Path = BENCH_PATH) -> LoadResult`
  - `datasets.BENCH_PATH = Path(__file__).parent / "data" / "promptveil_bench_v1.jsonl"`, `datasets.LOADERS: dict[str, Callable[..., LoadResult]]` with keys `"gretel"`, `"nemotron"`, `"promptveil_bench"`
  - `datasets.MissingDependency(Exception)`, raised by the HF loaders when `import datasets` fails

Row rules:
- A span is skipped (and counted) when `start < 0`, `end > len(text)`, `start >= end`, or, if the row carries `text`, when `text[start:end] != span["text"]`.
- Nemotron `tax_id` maps to `us_ein` when `row["locale"] == "us"`, else `UNSUPPORTED`.
- Sample IDs are `str(row["uid"])` for Nemotron and `str(row["__index_level_0__"])` for Gretel.
- The HF loaders `import datasets as hf` inside the function. Load with `hf.load_dataset(repo, data_files=..., revision=SHA, split="train")` (a single data file loads as split `train`). Nemotron then runs `.shuffle(seed=seed).select(range(min(limit, len(ds))))`.
- The PromptVeil-Bench JSONL row format is `{"id": str, "text": str, "spans": [{"start", "end", "label"}]}` with labels that are already PromptVeil types. `revision` is the file's sha256 (first 12 hex chars).

- [ ] **Step 1: Write failing tests** in `tests/test_accuracy_datasets.py` using inline dict rows shaped like the real data:
  - `test_map_label_unknown_is_unsupported`: `map_label(GRETEL, "name") == UNSUPPORTED`
  - `test_parse_gretel_row`: `pii_spans` is a JSON string with one `email` and one `name` span → spans labelled `email` and `UNSUPPORTED`, with 0 skipped
  - `test_parse_nemotron_row_literal_spans`: `spans` is `str([{...,'label':'credit_debit_card'}])` → label `credit_card`
  - `test_parse_nemotron_skips_misaligned_span`: span `text` differs from the slice → dropped, with 1 skipped
  - `test_nemotron_tax_id_depends_on_locale`: the same row with `locale="us"` → `us_ein`, and with `"intl"` → `UNSUPPORTED`
  - `test_out_of_range_span_skipped`: `end > len(text)` → skipped
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_accuracy_datasets.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `labels.py`, `datasets.py`, and the `bench` extra. Then run `uv pip install -e ".[bench,dev]"` (or the repo's usual install).
- [ ] **Step 4: Run** `.venv/bin/pytest tests/test_accuracy_datasets.py -v`. Expected: PASS.
- [ ] **Step 5: Smoke-check the real loaders (network, manual).** Run `.venv/bin/python -c "from benchmarks.accuracy.datasets import load_gretel, load_nemotron; g=load_gretel(); n=load_nemotron(); print(len(g.samples), g.skipped_spans, len(n.samples), n.skipped_spans)"`. Expected: `2891 0 5000 <~2% of spans>`.
- [ ] **Step 6: Commit** with message `feat: add accuracy benchmark dataset loaders`, including `pyproject.toml` (and `uv.lock` if it changed).

---

### Task 3: PromptVeil-Bench v1 generator and data

**Files:**
- Create: `benchmarks/accuracy/generate_bench.py`
- Create: `benchmarks/accuracy/data/promptveil_bench_v1.jsonl` (generated, committed)
- Test: add to `tests/test_accuracy_datasets.py`

**Interfaces:**
- Consumes: `load_promptveil_bench`, `BENCH_PATH` from Task 2.
- Produces: `generate(seed: int = 20261103) -> list[dict]` and `main()`, which writes `BENCH_PATH`. Running it is `python -m benchmarks.accuracy.generate_bench`.

Content rules (from the spec):
- 50 positives per supported type: email, phone, in_phone, credit_card, api_key, ssn, us_passport, us_ein, in_aadhaar, in_pan, in_passport, in_voter_id, in_ifsc, in_gstin. That is 700 positive spans, with one entity per positive row.
- 300 hard-negative rows with `spans: []`. Draw evenly from:
  - order/invoice IDs, ISO timestamps, semver strings
  - 12-digit numbers that **fail** Verhoeff (use `_valid_aadhaar` only to reject accidental passes)
  - 9-digit numbers in non-SSN contexts ("tracking 123456789")
  - PAN/GSTIN look-alikes with a wrong structure
  - short numbers
- Valid values are built from each format's published structure: Aadhaar with a Verhoeff check digit (implement Verhoeff locally; don't import detector regexes), Luhn-valid card numbers, PAN `AAAPA9999A` structure, GSTIN state code + PAN + entity + `Z` + check char, and so on.
- About 30 templates, mixing English and Indian-English: chat prompts, support tickets, form dumps, log lines.
- Vary the formatting: separators (space, dash, none) and case for alphanumeric IDs, with punctuation next to values and values at the start or end of a line.
- Spans are recorded when inserting the value into the template, so they are correct by construction.
- Use `random.Random(seed)` only. Output is sorted by id, one JSON object per line, `ensure_ascii=False`.

- [ ] **Step 1: Write failing tests:**
  - `test_bench_spans_slice_text`: for every row in `load_promptveil_bench()`, every span has `0 <= start < end <= len(text)`, and the label is one of the 14 types
  - `test_bench_counts`: 50 spans per type, 300 rows with no spans
  - `test_bench_is_reproducible`: `generate()` serialised identically equals the committed file bytes
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_accuracy_datasets.py -k bench -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `generate_bench.py`, then run `.venv/bin/python -m benchmarks.accuracy.generate_bench`.
- [ ] **Step 4: Run** the same pytest command. Expected: PASS. Eyeball 20 random rows with `shuf -n 20 benchmarks/accuracy/data/promptveil_bench_v1.jsonl` for realism.
- [ ] **Step 5: Commit** with message `feat: add PromptVeil-Bench v1 labelled dataset`.

---

### Task 4: Runner CLI and report output

**Files:**
- Create: `benchmarks/accuracy/run.py`
- Create: `benchmarks/accuracy/results/.gitkeep`
- Test: `tests/test_accuracy_run.py`

**Interfaces:**
- Consumes: everything from Tasks 1–2; `promptveil.shield._resolve_overlaps`; `promptveil.__version__`.
- Produces:
  - `predict(text: str, detectors: Sequence[BaseDetector]) -> list[Span]`: runs every detector, resolves overlaps, and maps the results to `Span(e.start, e.end, e.entity_type)`
  - `evaluate(result: LoadResult, detectors) -> dict`, shaped as `{"samples": int, "skipped_spans": int, "revision": str, "overlap": {type: {tp,fp,fn,precision,recall,f1}}, "strict": {...}, "micro": {"overlap": {...}, "strict": {...}}}`
  - `render_markdown(report: dict) -> str`: one `### <dataset>` section per dataset. Each has a table `| Type | Gold | TP | FP | FN | Precision | Recall | F1 |` sorted by type, with a final **Micro avg** row, and metrics run through `format_metric`. A header line gives the PromptVeil version, date, and dataset revisions.
  - `main(argv: list[str] | None = None) -> int` with options `--datasets` (comma list, default all three), `--limit` (default 5000, Nemotron only), `--seed` (default 20261103), and `--out-dir` (default `benchmarks/accuracy/results`). It writes `<YYYY-MM-DD_HH-MM>.json` (top-level `config`, `promptveil_version`, `datasets: {name: evaluate(...)}`, `errors: {name: str}`) and `latest.md`, then prints the Markdown.
  - Exit codes: 0 on success; 1 if any dataset failed to load (the others still run and are written); 2 on `MissingDependency`, with the message `Install the benchmark extra: pip install "promptveil[bench]"` printed to stderr.
- Use the same `sys.path` bootstrap as `benchmarks/run_benchmarks.py` so `python benchmarks/accuracy/run.py` works as well as `python -m benchmarks.accuracy.run`.

- [ ] **Step 1: Write failing tests** in `tests/test_accuracy_run.py`:
  - `test_predict_resolves_overlaps`: on `"call +91 98765 43210"`, the full stack gives exactly one span (phone or in_phone)
  - `test_evaluate_on_tiny_sample`: one `Sample` with an email gold span → `overlap["email"]["tp"] == 1`
  - `test_render_markdown_small_support`: a report with `in_aadhaar` tp 0, fp 2, fn 0 renders the row with `n < 20` and FP `2`
  - `test_main_promptveil_bench_only(tmp_path)`: `main(["--datasets","promptveil_bench","--out-dir",str(tmp_path)]) == 0`, `latest.md` exists, and the JSON has a `promptveil_bench` key
  - `test_missing_datasets_package_message(monkeypatch, capsys)`: patch `LOADERS["gretel"]` to raise `MissingDependency`, then `main(["--datasets","gretel",...]) == 2` and stderr contains `promptveil[bench]`
  - `test_failed_dataset_exits_1(monkeypatch, tmp_path)`: patch `LOADERS["gretel"]` to raise `OSError`; with `--datasets gretel,promptveil_bench` it returns 1 and `promptveil_bench` is still in the JSON
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_accuracy_run.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `run.py`.
- [ ] **Step 4: Run** `.venv/bin/pytest tests/ -q`. Expected: the whole suite passes, including the existing tests.
- [ ] **Step 5: Commit** with message `feat: add accuracy benchmark runner`.

---

### Task 5: Full run and published docs

**Files:**
- Create: `benchmarks/accuracy/results/<timestamp>.json`, `benchmarks/accuracy/results/latest.md` (from the real run)
- Create: `docs/benchmarks.md`
- Modify: `website/sidebars.js` (add `'benchmarks'` after `'api-reference'`)
- Modify: `README.md` (add `- [Benchmarks](https://github.com/total-tensor-lab/PromptVeil/blob/master/docs/benchmarks.md)` to the Documentation list, after API reference)
- Modify: `CHANGELOG.md` (an `Unreleased` → `Added` entry)

- [ ] **Step 1: Full run.** `.venv/bin/python -m benchmarks.accuracy.run`. Expected: exit 0 and three tables printed. Note any type with recall or precision below 80%. Those go on the limitations list and become follow-up issues, not detector changes on this branch.
- [ ] **Step 2: Write `docs/benchmarks.md`** with Docusaurus front matter `title: Benchmarks`. Sections:
  - Summary: 3–4 headline numbers, each with its dataset named
  - Results: the tables from `latest.md`, public datasets first, then PromptVeil-Bench under its own heading that says it is ours
  - Method: scope, the overlap and strict rules, the FP policy, `phone`≡`in_phone`, `n < 20`, detection-only
  - Datasets & attribution: names, licences, pinned SHAs, sample size and seed, and the reason ai4privacy is not used
  - Limitations: English only; regex-only, so names and addresses are out of scope; PromptVeil-Bench is self-authored; plus the weak types from Step 1
  - Reproduce: `pip install "promptveil[bench]"` and `python -m benchmarks.accuracy.run`
  - Performance: a link to the `benchmarks/` speed suite
- [ ] **Step 3: Build the docs.** `cd website && npm run build`. Expected: build succeeds with no broken-link errors.
- [ ] **Step 4: Commit** the results, docs page, sidebar, README and changelog with message `docs: publish privacy accuracy benchmark results`.
- [ ] **Step 5: Product-page block.** Give the user a short, pasteable summary block in chat (headline numbers, a one-line method, a link to `/PromptVeil/benchmarks`). It is not committed, because the product site is not in this repo.
