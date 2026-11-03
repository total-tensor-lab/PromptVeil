PromptVeil 0.2.0 · run 2026-11-03 · overlap match

### gretel

2891 samples · revision `7b844d16738527a04264f50214cb426a4cea0897` · 0 misaligned gold spans skipped

_Labels are incomplete for this dataset, so results are recall only._

| Type | Gold | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| api_key | 54 | 14 | n/a | 40 | n/a | 25.9% | n/a |
| credit_card | 83 | 29 | n/a | 54 | n/a | 34.9% | n/a |
| email | 330 | 303 | n/a | 27 | n/a | 91.8% | n/a |
| phone | 480 | 407 | n/a | 73 | n/a | 84.8% | n/a |
| ssn | 85 | 70 | n/a | 15 | n/a | 82.4% | n/a |
| us_passport | 76 | 33 | n/a | 43 | n/a | 43.4% | n/a |
| **Micro avg** | 1108 | 856 | n/a | 252 | n/a | 77.3% | n/a |

### nemotron

5000 samples · revision `b70ffaf5ff39e079776134c5bf4381f00a9fd1ed` · 614 misaligned gold spans skipped

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
| us_ein | 25 | 7 | 41 | 18 | 14.6% | 28.0% | 19.2% |
| us_passport | 0 | 0 | 121 | 0 | n < 20 | n < 20 | n < 20 |
| **Micro avg** | 5290 | 4726 | 2031 | 564 | 69.9% | 89.3% | 78.5% |

### promptveil_bench

1000 samples · revision `b805cf48df92` · 0 misaligned gold spans skipped

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
