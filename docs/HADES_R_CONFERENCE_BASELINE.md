# HADES/R conference baseline

## Purpose

This record defines the proposed HADES package baseline for the symposium release
candidate. It is a reproducibility and compatibility target, not evidence of
clinical validation. The R Strategus clients and the MCP phenotype validator must
be tested against the same explicit R library before this baseline is accepted.

## Current shared library

The current Study Agent validation library is:

- R 4.5.3 on Linux;
- Strategus 1.5.0;
- CohortGenerator 1.1.1;
- CohortIncidence 4.1.1;
- CohortMethod 6.0.3;
- Capr 2.1.1;
- CirceR 1.3.3;
- SqlRender 1.19.4;
- DatabaseConnector 7.2.0;
- PhenotypeLibrary 3.37.0.

The installed versions match the parent `renv.lock` for these packages.

## Proposed upgrade candidates

Official OHDSI GitHub releases inspected on 2026-10-12:

| Package | Proposed version | Current shared library | Notes |
| --- | --- | --- | --- |
| Strategus | 1.6.0 | 1.5.0 | Minor upgrade |
| CohortGenerator | 1.1.1 | 1.1.1 | Already current |
| CohortIncidence | 4.2.0 | 4.1.1 | Minor upgrade |
| CohortMethod | 6.0.3 | 6.0.3 | Already current |
| Capr | 3.0.0 | 2.1.1 | Major upgrade; validate emitter API |
| CirceR | 1.3.3 | 1.3.3 | Already current release |
| SqlRender | 1.19.7 | 1.19.4 | Patch upgrade |
| DatabaseConnector | 8.0.0 | 7.2.0 | Major upgrade; validate connection behavior |
| PhenotypeLibrary | 3.37.0 | 3.37.0 | Already current release |
| CohortDiagnostics | 3.4.2 | 3.4.2 | Already current release |
| FeatureExtraction | 3.14.0 | 3.13.0 | Minor upgrade |

The Strategus assistant also imports Characterization 4.0.0, Cyclops 3.7.1,
and ParallelLogger 3.5.1. Resolve these transitively from the selected package
set rather than pinning an incompatible mix by hand.

## Safe acceptance sequence

1. Create a separate, explicit conference R library; do not mutate the working
   validation library or either R client source tree.
2. Install the proposed package set and record package sources, versions, R
   version, platform, and selected Java runtime.
3. Install current slashOhdsiAcpClient and slashOhdsiStrategusAssistant tarballs
   into that same library.
4. Run the R client compatibility MCP tool and package test/check commands.
5. Run the MCP-launched phenotype_make_computable fixture. It must source emitted
   Capr code, serialize cohort JSON, parse through CirceR, and build SQL.
6. Promote this library only after the direct Drug/Condition fixture and the
   supported Condition/Visit and Drug/Condition/Visit patterns pass.

If a package API differs, capture the exact R subprocess stdout/stderr and amend
the emitter with a regression test. Do not silently retain an older dependency
combination or report technical validation as clinical validation.
