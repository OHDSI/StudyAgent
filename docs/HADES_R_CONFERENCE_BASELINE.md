# HADES/R conference baseline

## Purpose

This record defines the accepted HADES package baseline for the symposium release candidate. It is a reproducibility and compatibility target, not evidence of clinical validation. The R Strategus clients and the MCP phenotype validator were tested against the same explicit R library.

## Accepted shared library

- Library: `/ai-agent/HadesProject/renv/library/linux-ubuntu-noble/R-4.5/x86_64-pc-linux-gnu`
- R: 4.5.3 (2026-03-11), `x86_64-pc-linux-gnu`
- `JAVA_HOME`: `/usr/lib/jvm/java-8-openjdk-amd64/`
- rJava selected runtime: Java 8 (`1.8.0_482`). The host `java` executable reports Java 21; do not use that command alone to infer rJava selected runtime.

| Package | Version |
| --- | --- |
| Strategus | 1.6.0 |
| CohortGenerator | 1.1.1 |
| CohortIncidence | 4.2.0 |
| CohortMethod | 6.0.3 |
| Capr | 3.0.0 |
| CirceR | 1.3.3 |
| SqlRender | 1.19.7 |
| DatabaseConnector | 8.0.0 |
| PhenotypeLibrary | 3.37.0 |
| CohortDiagnostics | 3.4.2 |
| Characterization | 4.1.0 |
| FeatureExtraction | 3.14.0 |
| Cyclops | 3.7.1 |
| ParallelLogger | 3.5.1 |

## Acceptance evidence

- `slashOhdsiStrategusAssistant` testthat suite: 195 passing tests.
- MCP `phenotype_make_computable` suite: 51 passing tests, including direct Condition, reviewed Visit restriction, Drug with supporting Condition, and Drug with Visit qualifier patterns.
- The MCP-launched R validator successfully sources emitted Capr code, writes cohort JSON, parses it with CirceR, and builds SQL.

## Reproduction requirements

Use this library explicitly for R clients and MCP validation. In particular, set `mcp.r.library` in `config.yaml` and use `R_LIBS_USER=<library>` for ad-hoc R commands and package checks. On hosts with multiple JDKs, set `mcp.r.java_home` to the intended JDK root and verify rJava with:

```r
rJava::.jinit()
rJava::.jcall("java/lang/System", "S", "getProperty", "java.version")
```

The validator returns bounded R-runtime diagnostics on technical failure: configured Rscript and library, selected `JAVA_HOME`, PATH/JDK preference summary, process return code, and bounded stdout/stderr. These diagnostics establish technical compatibility only; they do not validate clinical cohort design or database results.
