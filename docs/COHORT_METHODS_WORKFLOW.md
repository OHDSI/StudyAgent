**Cohort Methods Workflow**

This document captures the current cohort-methods workflow implemented by `OHDSIAssistant::runStrategusCohortMethodsShell()` and how it fits into a broader Strategus execution pipeline.

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
  AT --> AU["Write Outputs + Generate Scripts 02-06"]
  AU --> AV["End"]
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
  G --> H["Keeper Case Review"]
  H --> I["Optional: refine phenotypes"]
  I --> B

  C --> J["05_diagnostics.R"]
  J --> K["CohortDiagnostics"]

  C --> L["outputs/cm_analysis_defaults.json"]
  C --> M["analysis-settings/cmAnalysis.json"]
  C --> N["outputs/cm_comparisons.json"]
  C --> O["selected or patched cohort definitions"]

  L --> P["06_cm_spec.R"]
  M --> P
  N --> P
  O --> P
  F --> P
  K --> P

  P --> Q["analysis-settings/analysisSpecification.json"]
  Q --> R["Shared Cohort Resource"]
  Q --> S["CharacterizationModule Spec"]
  Q --> T["CohortIncidenceModule Spec"]
  Q --> U["CohortMethodModule Spec"]
  Q --> V["Strategus::execute"]
  V --> W["CohortMethod Results + Strategus Execute Result"]
```
