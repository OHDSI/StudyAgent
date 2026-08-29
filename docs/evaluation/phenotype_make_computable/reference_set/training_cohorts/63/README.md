# Cohort 63: Transverse myelitis or symptoms indexed on symptoms or diagnosis (1Ps, 0Era, 365W)

> **Evidence boundary:** This case belongs to an AI-screened development reference corpus. Its source status is **Accepted**. It is not independently adjudicated clinical gold.

## At a glance

| Field | Value |
|---|---|
| Original complexity tier | T3 |
| Collapsed analysis group | Complex (T3-T5) |
| Concept sets | 2 |
| Resolver retrieval targets | 2 |
| Reference root occurrences | 6 |
| Inclusion rules | 1 |
| Reference status | Accepted |

## Source requirement

> events with a diagnosis of transverse myelitis indexed on diagnosis of transverse myelitis, related spinal disease or symptoms of transverse myelitis, followed by a diagnosis of transverse myelitis within 30 days. Events have a 365 days washout period. The events persist for 1 day. Symptoms of Transverse Myelitis included asthenia, muscle weakness, myelitis, paresthesia

## Concept-set families

- Symptoms for Transverse Myelitis
- Transverse Myelitis

## Files in this case

- `source.txt`: the natural-language requirement supplied to the cohort builder.
- `reference_circe.json`: the corresponding CIRCE reference expression.
- `concept_roots.csv`: concept-set roots and descendant/mapping policies.
- `retrieval_targets.json`: eligible retrieval targets and their CIRCE JSON-pointer bindings.
- `structural_summary.json`: compact construct and constraint summary.
- `provenance.json`: source status, hashes, and evidence-boundary metadata.

## Suggested reuse

Use `source.txt` as model input, keep `reference_circe.json` hidden during generation, and compare terminology and structure using the files above. Report results as development or benchmark evidence unless an independent clinical review is added.
