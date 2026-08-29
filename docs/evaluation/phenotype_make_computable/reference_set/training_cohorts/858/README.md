# Cohort 858: Earliest event of Rheumatoid Arthritis

> **Evidence boundary:** This case belongs to an AI-screened development reference corpus. Its source status is **Pending peer review**. It is not independently adjudicated clinical gold.

## At a glance

| Field | Value |
|---|---|
| Original complexity tier | T2 |
| Collapsed analysis group | Simple (T1-T2) |
| Concept sets | 1 |
| Resolver retrieval targets | 1 |
| Reference root occurrences | 14 |
| Inclusion rules | 0 |
| Reference status | Pending peer review |

## Source requirement

> Earliest occurrence of Rheumatoid Arthritis indexed on diagnosis (condition or observation) date, for the first time in history cohort exit is the end of continuous observation

## Concept-set families

- Rheumatoid arthritis

## Files in this case

- `source.txt`: the natural-language requirement supplied to the cohort builder.
- `reference_circe.json`: the corresponding CIRCE reference expression.
- `concept_roots.csv`: concept-set roots and descendant/mapping policies.
- `retrieval_targets.json`: eligible retrieval targets and their CIRCE JSON-pointer bindings.
- `structural_summary.json`: compact construct and constraint summary.
- `provenance.json`: source status, hashes, and evidence-boundary metadata.

## Suggested reuse

Use `source.txt` as model input, keep `reference_circe.json` hidden during generation, and compare terminology and structure using the files above. Report results as development or benchmark evidence unless an independent clinical review is added.
