# Roadmap

Some ideas for future work. Feel free to do a pull request to add your ideas! 

## Near Term

### `data_quality_interpretation`

Interpret Data Quality Dashboard, Achilles Heel, and Achilles characterization outputs in the context of a user's study intent so the findings are more actionable for study design.

### `create_new_phenotype_definition`

Guide users through building a new phenotype definition for a target or outcome cohort, including concept selection, concept-set organization, and cohort-definition logic assembly.

## Broader Future-Service Catalog

These items are directional and should not be read as fully implemented.

### High-Level Conceptual Services

- `protocol_generator`: generate a templated protocol from a study intent
- `background_writer`: draft a study background with supporting rationale
- `protocol_critique`: review a protocol for completeness and consistency
- `dag_create`: propose a causal graph from protocol or study-intent text
- `explain_cohort_diagnostics`: summarize cohort diagnostics outputs in study context
- `explain_incidence_estimation_characterization_results`: summarize completed analysis outputs in study context

### High-Level Operational Services

- `strategus_*`: compose, compare, edit, critique, and debug Strategus JSON

### Improving and validating search and suggest services

- `propose_negative_control_outcomes`
- `propose_comparator`
- `propose_adjustment_set`

### Study component testing, improvement, and linting

- `propose_concept_set_diff`
- `phenotype_characterize`
- `phenotype_data_quality_review`
- `phenotype_dataset_profiler`
- `phenotype_validation_review`
- `cohort_definition_build`
- `cohort_definition_lint`
- `review_negative_control`
