# Current Sprint Plan — Symposium Stage 1

## Objective

Establish a stable, reviewable conference-demo baseline for Study Agent, Atlas3, WebAPI, and the two slashOhdsi R packages. This stage combines release-baseline work with the first integration step so the R-to-Atlas handoff can begin immediately afterward.

The outcome is not a production release or a broad feature expansion. It is a reproducible conference-focused branch set with a known-compatible HADES/R runtime, confirmed supported workflow boundary, and a short code-review gate before subsequent implementation.

## Scope and priorities

The primary symposium journeys are:

1. **Atlas concept-set authoring:** use `/ohdsi` assistance, Atlas vocabulary exploration, and explicit policy review to build or refine a concept set.
2. **Atlas cohort authoring:** use the supported AI-assisted cohort-definition paths to review a computable phenotype draft and save a cohort definition.
3. **Atlas phenotype recommendation and selection:** use AI-supported search or direct phenotype-library browsing, inspect computability and provenance information, and either open an executable draft or use a non-computable phenotype as evidence for new authoring.
4. **R Strategus workflow:** use the `slashOhdsiStrategusAssistant` incidence-rate or cohort-method shell to select, import, or create target/comparator/outcome cohorts.
5. **R-to-Atlas concept-policy handoff:** start phenotype creation in R, review and revise the concept-set policy in Atlas, then resume the R workflow from the approved immutable policy snapshot.

Stage 1 concentrates on the prerequisites for all five journeys:

- integrate the proven sandbox implementation into conference-focused branches;
- establish a compatible R/HADES package baseline;
- make the current `phenotype_make_computable` Capr/Circe validation failure diagnosable and resolve it against that baseline;
- document exactly which phenotype-emitter patterns are demonstrated;
- preserve the existing review-gated and snapshot/provenance guardrails.

Explicitly out of scope: grounded vocabulary retrieval or vocabulary embeddings, arbitrary multi-component Circe cohorts, broad UX redesign, AWS deployment/QR codes/authentication, and treating a retrieval sample as evidence that a concept set is complete.

## Workstream A — Conference branch and integration baseline

### A1. Inventory all release candidates

Identify the exact current branch, commit, tag, remote, and dirty-worktree state for:

- this Study Agent repository and `sandbox/StudyAgent`, if distinct;
- `sandbox/Atlas3`;
- `sandbox/WebAPI`;
- `slashOhdsiAcpClient`;
- `slashOhdsiStrategusAssistant`.

Record the source and target conference branch before copying or cherry-picking. Preserve unrelated worktree changes; do not reset or clean another worktree to simplify integration.

### A2. Create or verify conference-focused branches

Use dedicated, named symposium release-candidate branches. Prefer coherent commits/cherry-picks over copying uncommitted files. Capture immutable commit IDs in a release inventory.

### A3. Integrate proven sandbox capabilities

Bring across the already manually tested Atlas3/WebAPI functionality:

- `/ohdsi` concept-set assistance and provenance;
- supported AI-assisted cohort authoring;
- phenotype recommendation, library browse, and selection UI;
- Study Agent role/permission handling and database migrations;
- cohort-plan persistence, linked concept-set review, provenance cards, and plan discard/deletion behavior.

Do not bring over experimental or incomplete code merely because it exists in a sandbox branch. Every integration commit must be traceable and buildable.

### A4. Build and smoke-test the integration baseline

At minimum:

- build WebAPI and confirm Flyway migrations against a designated demo database;
- run Atlas3 production build and preview smoke test;
- verify Atlas/WebAPI connectivity, enabled Study Agent controls, and normal non-AI Atlas loading;
- verify ACP/MCP health and the presence of `phenotype_make_computable`, `phenotype_make_computable_emit`, and `phenotype_make_computable_validate`.

## Review gate — User code review

After Workstream A and before substantive new workflow work, the user will perform a brief code review of the conference branches.

Prepare:

- branch names and commit IDs for every component;
- grouped diff/stat summary;
- migrations and role/permission changes;
- build/test commands and results;
- known limitations and deliberate behavior changes;
- a concise map of R, ACP/MCP, WebAPI, and Atlas responsibilities.

No new R-to-Atlas handoff behavior begins before this gate is accepted, except small build/test fixes required to make the integrated baseline reviewable.

## Workstream B — HADES/R compatibility baseline

### B1. Select and record the target HADES package set

Choose current intended versions for at least `Strategus`, `CohortGenerator`, `CohortIncidence`, `CohortMethod`, `Capr`, `CirceR`, `SqlRender`, `DatabaseConnector`, and `PhenotypeLibrary` where used. These will all be updated to the latest releases as of 10/12/2026. Retain a file-based record of the update process so the lead developer can replicate it on other machine including the AWS EC2 that will be used for the conference.

Record R version/platform, selected R library, rJava-selected Java runtime, and package versions. The MCP Python-launched R validator and RStudio/Strategus should use the same library where practical.

### B2. Update slashOhdsi packages against that baseline

Update `slashOhdsiAcpClient` and `slashOhdsiStrategusAssistant` only as needed for HADES and ACP compatibility. Preserve the shells as ACP clients; do not duplicate ACP orchestration in R.

For package changes:

- add focused `testthat` coverage;
- parse edited R files;
- build tarballs and run `R CMD check --no-manual` with an explicit R library;
- reinstall from the tarballs and restart R before manual testing.

### B3. Resolve or accurately diagnose phenotype-make-computable validation

Use a simple direct Drug/Condition fixture first. The MCP validator must report actionable, safe diagnostics on failure: Rscript path, R library, selected `JAVA_HOME`/safe PATH summary, process return code, and bounded stdout/stderr.

Confirm that the MCP-launched R process—not merely an interactive R session—can source emitted Capr code, write cohort JSON, parse it through CirceR, and build SQL. If package APIs differ, adjust the emitter only after identifying the specific incompatibility and adding a regression test.

## Workstream C — Supported-demo contract and examples

### C1. Freeze supported phenotype patterns

Document the exact demonstrated patterns:

- one direct index event in a supported OMOP domain;
- Condition index with supported reviewed Visit overlap/restriction;
- Drug index with a reviewed supporting Condition;
- Drug index with a reviewed Visit qualifier.

State what is review-only, executable, or unsupported. Continue to distinguish reusable concept-set assets, criterion bindings, and cohort logic.

### C2. Define repeatable demo narratives

Prepare concise examples and expected outcomes, including:

- acute cystitis with ER/inpatient visit restriction;
- new esketamine exposure with major depressive disorder supporting evidence;
- adults with type 2 diabetes for recommendation/library selection;
- anemia or bronchitis for direct authoring.

These are demonstration material, not clinical gold standards.

### C3. Define user-visible recovery guidance

For no-candidate retrieval, unsupported temporal logic, expired sessions, and validation failure, provide clear next steps: refine terms, move to Atlas vocabulary search, resume later, or use a supported pattern. Preserve review state whenever safe.

## Completion criteria

Stage 1 is complete when:

1. Conference branches and immutable commits are recorded for every component.
2. The user has reviewed and accepted the integration baseline.
3. Atlas3/WebAPI build successfully and AI controls appear under expected settings.
4. ACP/MCP exposes the required phenotype-make-computable flow/emitter/validator paths.
5. The chosen HADES/R package versions are recorded and shared by R workflows and MCP validation.
6. Capr/Circe validation passes or fails with specific actionable diagnostics.
7. Supported patterns, demo narratives, and fallback behavior are documented.

## Handoff to Stage 2

After acceptance, build the minimum viable R-to-Atlas handoff:

1. R creates a durable named review request.
2. R presents a direct Atlas URL.
3. Atlas opens the existing concept-set editor in workflow-linked mode.
4. The user searches, reviews, edits, and saves a policy.
5. R resumes from the accepted expression snapshot/checksum and emits only a supported definition.

The Tuesday student session is the first usability gate. Before testing, reinstall changed R packages and restart R; restart MCP after MCP/prompt/config changes; and restart ACP after ACP server/contract changes.
