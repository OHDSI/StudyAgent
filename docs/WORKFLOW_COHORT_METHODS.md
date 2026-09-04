**Cohort Methods Workflow**

Implementation lives in the external [`SlashOhdsiStrategusAssistant`](https://github.com/OHDSI/SlashOhdsiStrategusAssistant) R package; this document describes its integration with Study Agent.

This document captures the current cohort-methods workflow implemented by `slashOhdsiStrategusAssistant::runStrategusCohortMethodsShell()` and how it fits into a broader Strategus execution pipeline.

## Shell Workflow (Target/Comparator/Outcome + Analytic Settings)

```mermaid
flowchart TD
  A["Start: runStrategusCohortMethodsShell"] --> B["Enter Study Intent"]
  B --> B1{"Blank?"}
  B1 -- "No" --> C["cohort_methods_intent_split"]
  B1 -- "Yes" --> C0["Enter Target/Comparator/Outcome Statements Directly"]
  C0 --> C1["Confirm or Edit Derived Study Intent"]
  C --> D["Target Statement"]
  C --> E["Comparator Statement"]
  C --> F["Outcome Statement(s)"]
  C1 --> D
  C1 --> E
  C1 --> F

  D --> G["Target Recommendations or Cache Reuse"]
  G --> H["Select Target Cohort"]
  H --> I{"Do Target Improvements?"}
  I -- "Yes" --> J["phenotype_improvements-target"]
  J --> K{"Apply Improvements?"}
  K -- "Yes" --> L["Patched Target Cohort"]
  K -- "No" --> M["Keep Selected Target Cohort"]
  I -- "No" --> M

  E --> N["Comparator Recommendations or Cache Reuse"]
  N --> O["Select Comparator Cohort"]
  O --> P{"Do Comparator Improvements?"}
  P -- "Yes" --> Q["phenotype_improvements-comparator"]
  Q --> R{"Apply Improvements?"}
  R -- "Yes" --> S["Patched Comparator Cohort"]
  R -- "No" --> T["Keep Selected Comparator Cohort"]
  P -- "No" --> T

  F --> U["Outcome Recommendations or Cache Reuse"]
  U --> V["Select Outcome Cohort(s)"]
  V --> W{"Do Outcome Improvements?"}
  W -- "Yes" --> X["phenotype_improvements-outcome"]
  X --> Y{"Apply Improvements?"}
  Y -- "Yes" --> Z["Patched Outcome Cohort(s)"]
  Y -- "No" --> AA["Keep Selected Outcome Cohort(s)"]
  W -- "No" --> AA

  L --> AB["Write Cohort Role + Comparison Artifacts"]
  M --> AB
  S --> AB
  T --> AB
  Z --> AB
  AA --> AB

  AB --> AC["Capture Negative Control + Covariate Concept-Set Placeholders"]
  AC --> AD{"Analytic Settings Mode"}

  AD -- "step_by_step" --> AE["Study Population Settings"]
  AE --> AF["Time-at-Risk Settings"]
  AF --> AG["Propensity Score Adjustment Settings"]
  AG --> AH["Outcome Model Settings"]
  AH --> AI["Enter Profile Name"]
  AI --> AJ["Review Resolved Settings"]

  AD -- "free_text" --> AO["cohort_methods_specifications_recommendation"]
  AO --> AP{"ACP Available?"}
  AP -- "Yes" --> AQ["ACP Recommendation"]
  AP -- "No or Error" --> AR["Local Stub/Fallback Recommendation"]
  AQ --> AS["Review Recommendation"]
  AR --> AS

  AJ --> AT["Confirm Analytic Settings"]
  AS --> AT
  AT --> AU["Optional inline ACP Keeper review with bounded stage gates"]
  AU --> AV["Write Outputs + Generate Scripts 02-07"]
  AV --> AW["End"]
```

Build-mode note: interactive users can type `h` at the major design prompts to see step-specific help, `/back` at supported boundaries to revisit the prior step, and `/ohdsi <question>` for contextual guidance.

## Strategus Execution Context

```mermaid
flowchart TD
  A["Study Intent"] --> B["runStrategusCohortMethodsShell"]
  B --> C["Outputs: cohorts + comparisons + analytic settings + scripts"]

  C --> D["03_generate_cohorts.R"]
  D --> E["CohortGenerator"]
  E --> F["Cohort Table in CDM"]

  C --> G["04_keeper_concept_sets.R"]
  G --> H["ACP Keeper concept-set workflow"]
  H --> I["Concept-set generation"]

  C --> J["05_keeper_case_review.R"]
  J --> K["ACP Keeper case-review workflow"]
  K --> L["Keeper profile extraction"]
  K --> M["Phenotype validation review"]
  M --> N["Optional phenotype refinement"]
  N --> B

  C --> O["06_diagnostics.R"]
  O --> P["CohortDiagnostics"]

  C --> Q["outputs/cm_analysis_defaults.json"]
  C --> R["analysis-settings/cmAnalysis.json"]
  C --> S["outputs/cm_comparisons.json"]
  C --> T["selected or patched cohort definitions"]

  Q --> U["07_cm_spec.R"]
  R --> U
  S --> U
  T --> U
  F --> U

  U --> V["analysis-settings/analysisSpecification.json"]
  V --> W["Shared Cohort Resource"]
  V --> X["CharacterizationModule Spec"]
  V --> Y["CohortIncidenceModule Spec"]
  V --> Z["CohortMethodModule Spec"]
  V --> AA["Strategus::execute"]
  AA --> AB["CohortMethod Results + Strategus Execute Result"]
```

Keeper sequencing note: inline Keeper concept-set preparation may occur during build, but row-level Keeper case review is deferred until cohort generation has completed and rows are available. The shell records `deferred_pending_cohort_generation`; run `03_generate_cohorts.R` before `05_keeper_case_review.R`.

Execution note: `07_cm_spec.R` depends on the cohort-selection and analytic-settings outputs, not on Keeper or diagnostics completion. Keeper and diagnostics remain optional review/enrichment steps that can be run before or after the main CohortMethod specification, or explicitly skipped in the execution menu when that is the intentional workflow choice.

## Current Explicit Limitations

- Negative-control and covariate concept-set workflows are still placeholder-based.
- Cohort-method generation currently materializes only the first comparison from `cm_comparisons.json`.
- ACP analytic-settings recommendations are converted into shell settings, but a dedicated recommendation validation layer is still pending.
