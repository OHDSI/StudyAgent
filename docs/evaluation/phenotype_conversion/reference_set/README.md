# CIPHER Conversion Reference Set

This reference set defines expected deterministic behavior for selected indexed
CIPHER phenotypes. It contains no copied source payloads. A deployment supplies the
underlying CIPHER JSON through its phenotype index, and tests compare the indexed
snapshot, presentation, and readiness result with these expectations.

Each case records the expected readiness class, whether Circe emission is prohibited,
and the human decisions that must remain unresolved. It is a development regression
set, not a clinical validation set.

## Required checks

- The source snapshot preserves the phenotype ID, source revision/hash, and available
  `algorithmDesc` text.
- Presentation distinguishes source statements from ACP implementation choices.
- Readiness is deployment-aware: source vocabulary availability is checked against
  the configured OMOP vocabulary database.
- No raw CIPHER codes, PheCodes, text snippets, mappings, or LLM output becomes an
  approved concept set without review.
- A `circe_prohibited` case never produces executable Circe JSON.

Use `reference_cases.json` as the machine-readable expectation surface. Add an
anonymized fixture only where the source license and repository data policy permit it.
