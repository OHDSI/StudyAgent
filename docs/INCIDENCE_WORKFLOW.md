**Incidence Workflow**

This document captures the current incidence-rate workflow implemented by
`OHDSIAssistant::runStrategusIncidenceShell()` and how it fits into a broader
Strategus execution pipeline.

## Shell Workflow (Target/Outcome Orchestration)

```mermaid
flowchart TD
  A[Start: runStrategusIncidenceShell] --> B[Enter Study Intent]
  B --> C[phenotype_intent_split]
  C --> D[Target Statement]
  C --> E[Outcome Statement]

  D --> F[Target Recommendations]
  F --> G{Acceptable?}
  G -- No --> H[Optional: widen candidates]
  H --> F
  G -- No --> I[phenotype_recommendation_advice]
  I --> J[Checkpoint: target_advice]
  J --> K[Stop + Resume Later]
  G -- Yes --> L[Select Target Cohort]
  L --> M{Do Improvements?}
  M -- Yes --> N[phenotype_improvements-target]
  N --> O[Apply Improvements?]
  O --> P[Patched Target Cohort]
  M -- No --> Q[Skip Target Improvements]
  P --> R[Proceed to Outcome]
  Q --> R

  E --> S[Outcome Recommendations]
  S --> T{Acceptable?}
  T -- No --> U[Optional: widen candidates]
  U --> S
  T -- No --> V[phenotype_recommendation_advice]
  V --> W[Checkpoint: outcome_advice]
  W --> X[Stop + Resume Later]
  T -- Yes --> Y[Select Outcome Cohorts]
  Y --> Z{Do Improvements?}
  Z -- Yes --> AA[phenotype_improvements-outcome]
  AA --> AB[Apply Improvements?]
  AB --> AC[Patched Outcome Cohorts]
  Z -- No --> AD[Skip Outcome Improvements]

  AC --> AE[Write Outputs + Roles + Cohorts.csv]
  AD --> AE
  AE --> AF[Generate Scripts 01–06]
  AF --> AG[End]
```

## Strategus Execution Context

```mermaid
flowchart TD
  A[Study Intent] --> B[runStrategusIncidenceShell]
  B --> C[Outputs: cohorts + roles + scripts]
  C --> D[03_generate_cohorts.R]
  D --> E[CohortGenerator]
  E --> F[Cohort Table in CDM]

  C --> G[04_keeper_review.R]
  G --> H[Keeper Case Review]
  H --> I[Optional: refine phenotypes]
  I --> B

  C --> J[05_diagnostics.R]
  J --> K[CohortDiagnostics]

  C --> L[06_incidence_spec.R]
  L --> M[CohortIncidence Spec JSON]

  E --> L
  K --> L
  M --> N[Strategus Execution]
  N --> O[Incidence Rate Results]
```
