**Cohort Methods Workflow**

This document captures the current cohort-methods workflow implemented by `slashOhdsiStrategusAssistant::runStrategusCohortMethodsShell()` and how it fits into a broader Strategus execution pipeline.

## Shell Workflow (Target/Comparator/Outcome + Analytic Settings)

```mermaid
flowchart TD
  A["Start: runStrategusCohortMethodsShell"] --> B["Enter Study Intent"]
  B --> C["cohort_methods_intent_split"]
  C --> D["Target Statement"]
  C --> E["Comparator Statement"]
  C --> F["Outcome Statement(s)"]

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
  AU --> AV["Write Outputs + Generate Scripts 02-06"]
  AV --> AW["End"]
```

## Strategus Execution Context

```mermaid
flowchart TD
  A["Study Intent"] --> B["runStrategusCohortMethodsShell"]
  B --> C["Outputs: cohorts + comparisons + analytic settings + scripts"]

  C --> D["03_generate_cohorts.R"]
  D --> E["CohortGenerator"]
  E --> F["Cohort Table in CDM"]

  C --> G["04_keeper_review.R"]
  G --> H["ACP Keeper flow"]
  H --> I["Concept-set generation"]
  H --> J["Keeper profile extraction"]
  H --> K["Phenotype validation review"]
  K --> L["Optional phenotype refinement"]
  L --> B

  C --> M["05_diagnostics.R"]
  M --> N["CohortDiagnostics"]

  C --> O["outputs/cm_analysis_defaults.json"]
  C --> P["analysis-settings/cmAnalysis.json"]
  C --> Q["outputs/cm_comparisons.json"]
  C --> R["selected or patched cohort definitions"]

  O --> S["06_cm_spec.R"]
  P --> S
  Q --> S
  R --> S
  F --> S
  N --> S

  S --> T["analysis-settings/analysisSpecification.json"]
  T --> U["Shared Cohort Resource"]
  T --> V["CharacterizationModule Spec"]
  T --> W["CohortIncidenceModule Spec"]
  T --> X["CohortMethodModule Spec"]
  T --> Y["Strategus::execute"]
  Y --> Z["CohortMethod Results + Strategus Execute Result"]
```

## Current Explicit Limitations

- Negative-control and covariate concept-set workflows are still placeholder-based.
- Cohort-method generation currently materializes only the first comparison from `cm_comparisons.json`.
- ACP analytic-settings recommendations are converted into shell settings, but a dedicated recommendation validation layer is still pending.
