---
id: benchmarks
title: Benchmarks
---

# Benchmarks

How accurately does PromptVeil find the PII and secrets it claims to support?
We measure precision, recall and F1 per entity type on two public third-party
datasets and on PromptVeil-Bench, a labelled set we wrote ourselves. Every
number on this page comes from one command, and you can rerun it (see
[Reproduce](#reproduce)).

Results are for PromptVeil 0.2.0, run on 2026-11-03.

## Summary

- **Email: 99.5% F1** on NVIDIA Nemotron-PII (2,641 addresses).
- **Credit cards: 96.0% F1** on Nemotron-PII (632 card numbers).
- **India IDs: 95.0% recall at 99.3% precision** on PromptVeil-Bench (Aadhaar,
  PAN, GSTIN, IFSC, voter ID and Indian passport; 300 values). No public
  benchmark labels these types, so this number comes from our own set.
- **Overall on Nemotron-PII: 89.6% recall, 69.9% precision.** Most false
  positives come from the SSN and phone patterns matching other numeric IDs,
  such as bank routing and account numbers.

PromptVeil uses regular expressions and checksums. It does not detect names,
addresses or other free-text PII, and those types are not scored here. See
[Limitations](#limitations).

## Results

A detection counts as correct when it has the right type and overlaps the
labelled span. "Gold" is the number of labelled values of that type. Where a
type has fewer than 20 gold values, metrics are shown as `n < 20`. The FP
count is still shown, because those false positives are real.

### NVIDIA Nemotron-PII

A seeded random sample of 5,000 documents from the test split. Both the US and
international locales are included, and documents were not filtered by
content. 614 of the 42,024 gold spans of all types were skipped because their
offsets didn't match the text. Only 3 of those were of a scored type.

| Type | Gold | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| api_key | 235 | 24 | 38 | 211 | 38.7% | 10.2% | 16.2% |
| credit_card | 632 | 587 | 4 | 45 | 99.3% | 92.9% | 96.0% |
| email | 2641 | 2625 | 12 | 16 | 99.5% | 99.4% | 99.5% |
| in_aadhaar | 0 | 0 | 15 | 0 | n < 20 | n < 20 | n < 20 |
| in_pan | 0 | 0 | 2 | 0 | n < 20 | n < 20 | n < 20 |
| in_passport | 0 | 0 | 56 | 0 | n < 20 | n < 20 | n < 20 |
| in_voter_id | 0 | 0 | 16 | 0 | n < 20 | n < 20 | n < 20 |
| phone | 1466 | 1194 | 1085 | 272 | 52.4% | 81.4% | 63.8% |
| ssn | 291 | 289 | 641 | 2 | 31.1% | 99.3% | 47.3% |
| us_ein | 7 | 7 | 41 | 0 | n < 20 | n < 20 | n < 20 |
| us_passport | 0 | 0 | 121 | 0 | n < 20 | n < 20 | n < 20 |
| **Micro avg** | 5272 | 4726 | 2031 | 546 | 69.9% | 89.6% | 78.6% |

### Gretel synthetic PII (finance), English

All 2,891 English documents in the test split.

Gretel labels only the PII types each document was generated to contain, so
other real PII in the text has no label. For example, 500 of the 813 email
addresses in this split are unlabelled. Detecting those would count as a false
positive, which makes precision meaningless here. We therefore report
**recall only**.

| Type | Gold | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| api_key | 54 | 14 | n/a | 40 | n/a | 25.9% | n/a |
| credit_card | 83 | 29 | n/a | 54 | n/a | 34.9% | n/a |
| email | 330 | 303 | n/a | 27 | n/a | 91.8% | n/a |
| phone | 480 | 407 | n/a | 73 | n/a | 84.8% | n/a |
| ssn | 85 | 70 | n/a | 15 | n/a | 82.4% | n/a |
| us_passport | 76 | 33 | n/a | 43 | n/a | 43.4% | n/a |
| **Micro avg** | 1108 | 856 | n/a | 252 | n/a | 77.3% | n/a |

### PromptVeil-Bench v1 (our own set)

**We wrote this dataset, so read its numbers as a self-check, not an
independent result.** It exists because no public benchmark labels Indian ID
types, US EINs or US passport numbers.

It has 1,000 short texts: 50 values for each supported type, and 300 hard
negatives that must not be flagged. The hard negatives are order IDs,
timestamps, version strings, 12-digit numbers that fail the Aadhaar checksum,
9-digit tracking numbers, and PAN/GSTIN look-alikes. Values follow each
identifier's real-world format, including checksums, legacy formats and
occasional lowercase. They are not copied from PromptVeil's own patterns. The
`phone` row combines US and Indian numbers.

| Type | Gold | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| api_key | 50 | 37 | 0 | 13 | 100.0% | 74.0% | 85.1% |
| credit_card | 50 | 37 | 0 | 13 | 100.0% | 74.0% | 85.1% |
| email | 50 | 50 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| in_aadhaar | 50 | 50 | 2 | 0 | 96.2% | 100.0% | 98.0% |
| in_gstin | 50 | 43 | 0 | 7 | 100.0% | 86.0% | 92.5% |
| in_ifsc | 50 | 48 | 0 | 2 | 100.0% | 96.0% | 98.0% |
| in_pan | 50 | 46 | 0 | 4 | 100.0% | 92.0% | 95.8% |
| in_passport | 50 | 50 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| in_voter_id | 50 | 48 | 0 | 2 | 100.0% | 96.0% | 98.0% |
| phone | 100 | 95 | 0 | 5 | 100.0% | 95.0% | 97.4% |
| ssn | 50 | 50 | 67 | 0 | 42.7% | 100.0% | 59.9% |
| us_ein | 50 | 44 | 12 | 6 | 78.6% | 88.0% | 83.0% |
| us_passport | 50 | 27 | 0 | 23 | 100.0% | 54.0% | 70.1% |
| **Micro avg** | 700 | 625 | 81 | 75 | 88.5% | 89.3% | 88.9% |

## Method

- **Scope.** Only the 14 entity types PromptVeil supports are scored: email,
  phone, credit_card, api_key, ssn, us_passport, us_ein, in_aadhaar, in_pan,
  in_phone, in_passport, in_voter_id, in_ifsc and in_gstin. Gold labels of
  other types (names, addresses, dates and so on) never count as misses.
- **What runs.** The full detector stack (`RegexDetector`, `IndiaDetector`,
  `USDetector`), with overlapping matches resolved the same way `Shield`
  resolves them before masking. Policy rules are not applied, so the numbers
  measure detection alone.
- **Matching.** A detection is a true positive when it has the same type as a
  gold span and overlaps it. Each gold span can match only one detection.
  `phone` and `in_phone` count as the same type. Under a strict rule that
  requires exact boundaries, micro recall is 89.2% on Nemotron-PII, 71.6% on
  Gretel and 89.3% on PromptVeil-Bench.
- **False positives.** Any detection that doesn't match counts as a false
  positive. That includes detections that land on a labelled value of a type
  we don't support, such as a bank routing number flagged as an SSN. Users see
  this as over-masking, so it counts against precision.
- **Label mapping.** The dataset labels map to PromptVeil types as follows:
  - Nemotron-PII: `email` → email; `phone_number` and `fax_number` → phone;
    `credit_debit_card` → credit_card; `ssn` → ssn; `api_key` → api_key;
    `tax_id` → us_ein only on US-locale documents and only in the EIN format
    `NN-NNNNNNN`. 18 of the 25 US `tax_id` values in the sample are
    SSN/ITIN-formatted, so they are not scored as EINs.
  - Gretel: `email` → email; `phone_number` → phone; `credit_card_number` →
    credit_card; `ssn` → ssn; `api_key` → api_key; `passport_number` →
    us_passport.
- **No combined score.** Public and in-house results are reported separately
  and never averaged together.

## Datasets and attribution

| Dataset | Licence | Revision | Used |
|---|---|---|---|
| [nvidia/Nemotron-PII](https://huggingface.co/datasets/nvidia/Nemotron-PII) | CC BY 4.0 | `b70ffaf5ff39e079776134c5bf4381f00a9fd1ed` | test split, 5,000 documents, seed 20261103 |
| [gretelai/synthetic_pii_finance_multilingual](https://huggingface.co/datasets/gretelai/synthetic_pii_finance_multilingual) | Apache 2.0 | `7b844d16738527a04264f50214cb426a4cea0897` | English test split, 2,891 documents |
| PromptVeil-Bench v1 | MIT (this repo) | sha256 `b805cf48df92…` | all 1,000 rows |

Nemotron-PII is © NVIDIA Corporation, used under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The public datasets
are downloaded at run time and are not redistributed in this repository.

We did not use `ai4privacy/pii-masking-400k`, because its licence covers only
academic and non-commercial use.

## Limitations

- **Generic API keys are missed.** PromptVeil recognises keys by their
  provider prefix (OpenAI, Anthropic, GitHub classic, AWS, Slack, Google,
  Stripe, JWTs). It misses random hex strings, keys like `api_dev_…`, GitHub
  fine-grained tokens (`github_pat_…`), and OpenAI project keys that contain
  `_`.
- **SSN and phone patterns over-match.** Unseparated 9- and 10-digit numbers,
  such as routing, account and tracking numbers, are flagged as SSNs or phone
  numbers. That gives high recall but low precision for those types.
- **Card coverage is partial.** Visa, Mastercard 51–55, Amex and Discover are
  detected. Mastercard's 2221–2720 range, Diners Club and UnionPay are not.
- **US passports.** Only the letter + 8 digits format is detected. Legacy
  9-digit passport numbers are missed.
- **Phones.** International numbers outside the North American and Indian
  formats, such as UK `020 8725 0123` or `+61 2 9983 1567`, are often missed.
- **Lowercase Indian IDs.** PAN, GSTIN, IFSC and voter ID numbers typed in
  lowercase are missed.
- **English only.** Non-English text is not evaluated.
- **Dataset noise.** Some gold labels are imperfect. Gretel labels
  placeholders like `[Phone Number]` as phones, and its `ssn` labels include
  non-US national IDs, which lowers ssn recall there.

These are tracked as detector improvements. The numbers above will change as
they land.

## Reproduce

The benchmark code lives in the repository, not in the PyPI package, so run it
from a clone:

```bash
git clone https://github.com/total-tensor-lab/PromptVeil.git && cd PromptVeil
pip install -e ".[bench]"
python -m benchmarks.accuracy.run
```

The runner writes a JSON report and `latest.md` to `benchmarks/accuracy/results/`.
Options are `--datasets gretel,nemotron,promptveil_bench`, `--limit` (Nemotron
sample size) and `--seed`. To regenerate PromptVeil-Bench, run
`python -m benchmarks.accuracy.generate_bench`.

## Performance

Speed, concurrency and memory are measured by a separate suite. See
[`benchmarks/`](https://github.com/total-tensor-lab/PromptVeil/tree/master/benchmarks)
in the repository.
