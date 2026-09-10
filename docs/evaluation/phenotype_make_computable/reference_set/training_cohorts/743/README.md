# Cohort 743: Diabetic ketoacidosis IP-ER (SNOMED concept)

> **Evidence boundary:** This case belongs to an AI-screened development reference corpus. Its source status is **Pending peer review**. It is not independently adjudicated clinical gold.

## At a glance

| Field | Value |
|---|---|
| Original complexity tier | T3 |
| Collapsed analysis group | Complex (T3-T5) |
| Concept sets | 2 |
| Resolver retrieval targets | 2 |
| Reference root occurrences | 4 |
| Inclusion rules | 0 |
| Reference status | Pending peer review |

## Source requirement

> All condition occurrences of DKA during an ER or IP visit, with 30-day event persistence (SNOMED code only)

## Concept-set families

- Diabetic ketoacidosis
- Inpatient or ER visit

## Files in this case

- `source.txt`: the natural-language requirement supplied to the cohort builder.
- `reference_circe.json`: the corresponding CIRCE reference expression.
- `concept_roots.csv`: concept-set roots and descendant/mapping policies.
- `retrieval_targets.json`: eligible retrieval targets and their CIRCE JSON-pointer bindings.
- `structural_summary.json`: compact construct and constraint summary.
- `provenance.json`: source status, hashes, and evidence-boundary metadata.

## Suggested reuse

Use `source.txt` as model input, keep `reference_circe.json` hidden during generation, and compare terminology and structure using the files above. Report results as development or benchmark evidence unless an independent clinical review is added.
