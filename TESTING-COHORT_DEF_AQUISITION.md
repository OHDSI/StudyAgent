Use a matrix-driven test pass. The goal is to verify the same source-mode behaviors in both shells, then verify the workflow-specific downstream stages still behave correctly.

Scope

Test both shells:

- runStrategusIncidenceShell()
- runStrategusCohortMethodsShell()

Test each cohort-definition source mode:

- recommendation / index search
- existing database cohort definition
- single local JSON file
- directory of local JSON files

Test both DB connection roles where applicable:

- execution DB: strategus-db-details.json
- cohort-definition source DB: strategus-cohort-source-db-details.json

Pre-test setup

Prepare one clean test area per shell, for example:

- airgap-test-incidence/
- airgap-test-cohort-method/

Prepare these inputs ahead of time:

- phenotype index available locally
- execution DB config for patient-level workflows
- cohort-source DB config for Atlas-style cohort-definition lookup
- at least 2 valid local cohort JSON files for incidence
- at least 4 valid local cohort JSON files for cohort method
- one directory containing multiple valid cohort JSON files
- one known-good cohort definition in the source DB for each role you plan to test

For Windows-integrated SQL Server execution DB, verify:

- strategus-db-details.json uses authType = "windows"
- DATABASECONNECTOR_JAR_FOLDER is set if required locally

For cohort-source DB, verify:

- strategus-cohort-source-db-details.json uses the correct postgres user/password if that is your setup

High-level test strategy

Do this in three phases.

1. Shell-start and template/guardrail checks
2. Source-mode acquisition checks
3. Downstream workflow and resume checks

For the current execution runner, include explicit checks for optional-step skipping and resumed state:

- `skip <step>` for `apply_improvements`, `keeper_concept_sets`, `keeper_case_review`, and `diagnostics`
- resumed sessions with `resume=TRUE` after one or more optional steps were skipped
- `/ohdsi` behavior after optional review/enrichment steps were skipped intentionally

---

Phase 1: shell-start and guardrail checks

Run each shell fresh in a new output directory.

For each shell, verify:

- workflow folder is created
- strategus-db-details.json is created
- strategus-cohort-source-db-details.json is created
- strategus-execution-settings.json is created
- startup banner can be suppressed with `showBanner = FALSE` without affecting the shell prompts
- typing `h` during study-intent and cohort-source prompts shows step-appropriate help and then returns to the same prompt
- the shell can proceed without pre-populating strategus-cohort-source-db-details.json if you do not choose db

Then explicitly test the direct-acquisition study-intent fallback:

1. start fresh shell
2. press Enter at `Study intent [Enter to acquire cohorts directly]:`
3. enter role statements directly
4. confirm the shell proposes a template study intent built from those statements
5. accept the default once
6. repeat once more and edit the proposed study intent
7. confirm the edited value is the one that persists into saved state and `/ohdsi` context

Then explicitly test the DB guardrail:

1. start fresh shell
2. choose db for the first cohort role
3. leave strategus-cohort-source-db-details.json as template/blank
4. confirm the shell refuses DB import and tells you to populate the file
5. populate the file
6. retry DB import and confirm it proceeds

Pass criteria:

- template files are seeded automatically
- banner suppression is cosmetic only and does not change workflow behavior
- build-time help is available from the major design prompts
- blank study intent is replaced by a confirmable derived study intent before downstream configuration continues
- DB import is blocked cleanly until the cohort-source file is populated
- non-DB modes are not blocked by the cohort-source template

---

Phase 2: source-mode acquisition matrix

Use this matrix.

For incidence shell:
- target: recommendation
- target: db
- target: file
- target: directory
- outcome: recommendation
- outcome: db
- outcome: file
- outcome: directory

For cohort method shell:
- target: recommendation
- target: db
- target: file
- target: directory
- comparator: recommendation
- comparator: db
- comparator: file
- comparator: directory
- outcome: recommendation
- outcome: db
- outcome: file
- outcome: directory

You do not necessarily need every possible cross-product combination. A disciplined reduced set is better.

Recommended scenario set:

Incidence shell scenarios

1. recommendation + recommendation
2. db + db
3. file + file
4. directory + directory
5. recommendation + db
6. file + directory

Cohort method scenarios

1. recommendation + recommendation + recommendation
2. db + db + db
3. file + file + file
4. directory + directory + directory
5. recommendation + db + file
6. file + recommendation + directory

For each scenario, verify:

- source prompt appears correctly
- typing `h` at least once during design prompts shows step-appropriate help and returns to the same prompt
- selected role can be acquired from the chosen source
- imported file/db/directory cohorts are cached under imported-cohort-definitions/
- copied selected cohorts land in the selected cohort folders
- role metadata is written correctly
- session summary shows source ... -> cohort ..., not Atlas-specific wording
- when study intent started blank, the derived study-intent prompt appears after role statements and the confirmed value persists
- cohort ID remap still works if enabled
- phenotype improvements step still behaves sensibly for the selected artifact

For file mode specifically, verify:

- single JSON file is accepted
- invalid/non-Circe JSON is rejected with a clear error
- imported artifact is cached locally

For directory mode specifically, verify:

- shell lists candidates from the directory
- user can choose one or more valid files as needed
- invalid files in the directory do not silently break selection

For DB mode specifically, verify:

- shell reads from strategus-cohort-source-db-details.json
- shell can search/list candidate cohort definitions
- selected definition is imported and cached
- execution DB settings are not required for the import step itself

---

Phase 3: downstream workflow checks

For each shell, choose at least one scenario from each source family and run farther downstream.

Incidence shell downstream set
Run these for:
- one recommendation-based scenario
- one DB-based scenario
- one file or directory scenario

Verify:

- optional phenotype improvements work or skip cleanly
- time-at-risk configuration still works
- cohort generation script is written
- Keeper step can still be configured
- diagnostics script is written
- incidence spec script is written
- generated scripts use strategus-db-details.json for execution, not cohort-source DB config

Cohort method downstream set
Run these for:
- one recommendation-based scenario
- one DB-based scenario
- one file or directory scenario

Verify:

- target/comparator/outcome role selections persist correctly
- optional phenotype improvements work or skip cleanly
- analytic-settings collection still works
- generated cohort files are correct
- diagnostics script is written
- 07_cm_spec.R is written
- session summary and saved metadata use neutral source identifiers

---

Resume and restart checks

Do this for both shells after at least one partially completed run and one completed build run.

1. finish role selection and script generation
2. exit shell
3. restart shell with same output directory
4. confirm prior state is discovered
5. confirm artifacts can still be inspected
6. confirm selected/imported cohort artifacts are still resolvable
7. confirm DB-imported and file-imported cohorts survive restart without needing re-selection
8. if possible, run one execution step after restart

Also test one stale/missing case:

1. complete a file-import or DB-import run
2. restart shell
3. confirm it still resolves imported cohort artifacts from local cache even without revisiting source selection

That is important because robustness should depend on the cached local artifact, not on re-querying the original source.

---

Negative tests

Run these deliberately.

For both shells:

- run once with `showBanner = FALSE`
- type `h` during study-intent capture
- type `h` during cohort-source selection
- choose db with unfilled strategus-cohort-source-db-details.json
- provide invalid schema name or unreachable DB
- provide nonexistent local file path
- provide directory with no valid cohort JSONs
- provide malformed JSON file
- provide non-Circe JSON file
- attempt to proceed with missing execution DB config when generating/running scripts
- test /back at least once during source selection
- test restart after exiting mid-selection

Pass criteria:

- clear error or warning
- no silent mis-selection
- no crash that leaves unusable state
- retry path is obvious

---

Artifacts to inspect after each scenario

Check at minimum:

- outputs/study_agent_state.json
- outputs/study_agent_runtime_state.json
- outputs/manual_intent.json or outputs/manual_inputs.json where applicable
- imported-cohort-definitions/
- selected cohort folders
- patched cohort folders if improvements applied
- generated scripts/
- strategus-db-details.json
- strategus-cohort-source-db-details.json
- strategus-execution-settings.json

For cohort method specifically also inspect:

- outputs/cm_comparisons.json
- outputs/cohort_roles.json

For incidence specifically inspect:

- role-selection state and TAR settings artifacts

---

Recommended execution order in the airgapped environment

1. incidence shell
2. CohortMethod shell
3. recommendation mode first
4. file mode second
5. directory mode third
6. DB mode last

Reason:
- recommendation/file/directory modes isolate shell logic first
- DB mode adds environmental dependency and is easier to debug after the non-DB paths are proven

---

Minimal thorough set if time is limited

If you want a reduced but still disciplined pass:

Incidence
1. recommendation + recommendation
2. file + directory
3. db + db
4. restart/resume after scenario 3

Cohort method
1. recommendation + recommendation + recommendation
2. file + db + directory
3. db + db + db
4. restart/resume after scenario 3

What to record during testing

For each scenario, log:

- shell
- source mode per role
- whether source acquisition succeeded
- whether cache/import artifacts were created
- whether downstream script generation succeeded
- whether restart/resume succeeded
- exact error text for any failure
- whether issue is shell logic, config, or environment


---

Checklist Worksheet

Use one row per executed scenario.

Environment prep checklist

- [ ] Local phenotype index is present and readable.
- [ ] `strategus-db-details.json` execution settings are prepared for the patient-level workflow DB.
- [ ] `strategus-cohort-source-db-details.json` settings are prepared for the cohort-definition source DB.
- [ ] Windows-integrated SQL Server execution config is validated if applicable.
- [ ] `DATABASECONNECTOR_JAR_FOLDER` is available if required locally.
- [ ] At least 2 valid incidence cohort JSON files are available.
- [ ] At least 4 valid CohortMethod cohort JSON files are available.
- [ ] One directory with multiple valid cohort JSON files is available.
- [ ] Known-good cohort definitions exist in the cohort-source DB for planned DB-import tests.

Phase 1 checklist

- [ ] Incidence shell seeds `strategus-db-details.json`.
- [ ] Incidence shell seeds `strategus-cohort-source-db-details.json`.
- [ ] Incidence shell seeds `strategus-execution-settings.json`.
- [ ] CohortMethod shell seeds `strategus-db-details.json`.
- [ ] CohortMethod shell seeds `strategus-cohort-source-db-details.json`.
- [ ] CohortMethod shell seeds `strategus-execution-settings.json`.
- [ ] Incidence shell can start with `showBanner = FALSE` and still present normal prompts.
- [ ] CohortMethod shell can start with `showBanner = FALSE` and still present normal prompts.
- [ ] Build-time `h` help works during study-intent capture.
- [ ] Build-time `h` help works during cohort-source selection.
- [ ] Incidence shell derives a default study intent from direct target/outcome statements.
- [ ] CohortMethod shell derives a default study intent from direct target/comparator/outcome statements.
- [ ] Edited derived study intent persists to saved state.
- [ ] Incidence shell blocks DB cohort import when cohort-source config is still template/blank.
- [ ] CohortMethod shell blocks DB cohort import when cohort-source config is still template/blank.
- [ ] Non-DB source modes are usable before filling `strategus-cohort-source-db-details.json`.

Scenario execution table

| Scenario ID | Shell | Target source | Comparator source | Outcome source | Output dir | Source acquisition passed | Import cache written | Selected cohort copy written | Metadata/summary correct | Downstream build passed | Resume/restart passed | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| INC-01 | Incidence | recommendation | n/a | recommendation |  | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |  |
| INC-02 | Incidence | db | n/a | db |  | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |  |
| INC-03 | Incidence | file | n/a | file |  | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |  |
| INC-04 | Incidence | directory | n/a | directory |  | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |  |
| INC-05 | Incidence | recommendation | n/a | db |  | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |  |
| INC-06 | Incidence | file | n/a | directory |  | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |  |
| CM-01 | CohortMethod | recommendation | recommendation | recommendation |  | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |  |
| CM-02 | CohortMethod | db | db | db |  | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |  |
| CM-03 | CohortMethod | file | file | file |  | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |  |
| CM-04 | CohortMethod | directory | directory | directory |  | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |  |
| CM-05 | CohortMethod | recommendation | db | file |  | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |  |
| CM-06 | CohortMethod | file | recommendation | directory |  | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |  |

Per-scenario detailed checklist

Run this checklist for each scenario you execute.

- [ ] Correct source prompt appears.
- [ ] `h` returns step-specific help and then re-prompts the same design step.
- [ ] Selected role can be acquired from the chosen source.
- [ ] `imported-cohort-definitions/` is populated for db/file/directory sources.
- [ ] Selected cohort JSON files are copied into selected cohort folders.
- [ ] Role metadata is written.
- [ ] Session summary shows `source ... -> cohort ...` wording.
- [ ] Confirmed study intent is populated even when direct acquisition began from a blank study-intent prompt.
- [ ] Cohort ID remap works if enabled.
- [ ] Phenotype improvements step behaves correctly for the selected source artifact.

File-source checks

- [ ] Single JSON file is accepted.
- [ ] Malformed JSON file is rejected clearly.
- [ ] Non-Circe JSON file is rejected clearly.
- [ ] Imported file artifact is cached locally.

Directory-source checks

- [ ] Directory candidates are listed.
- [ ] Valid files can be selected.
- [ ] Invalid files do not silently break selection.

DB-source checks

- [ ] Shell uses `strategus-cohort-source-db-details.json` for cohort-definition import.
- [ ] Cohort definitions can be searched/listed from the DB.
- [ ] Selected DB cohort definition is imported and cached.
- [ ] Execution DB settings are not required for the import step itself.

Downstream checks

Incidence shell downstream

- [ ] Phenotype improvements work or skip cleanly.
- [ ] Time-at-risk configuration works.
- [ ] Cohort generation script is written.
- [ ] Keeper step can be configured.
- [ ] Diagnostics script is written.
- [ ] Incidence spec script is written.
- [ ] Generated scripts use `strategus-db-details.json` for execution.
- [ ] Generated scripts do not use `strategus-cohort-source-db-details.json` for execution.

CohortMethod shell downstream

- [ ] Target/comparator/outcome selections persist correctly.
- [ ] Phenotype improvements work or skip cleanly.
- [ ] Analytic-settings collection works.
- [ ] Generated cohort files are correct.
- [ ] Diagnostics script is written.
- [ ] `07_cm_spec.R` is written.
- [ ] Saved metadata uses neutral source identifiers.

Resume and restart checklist

- [ ] Completed build can be reopened after shell restart.
- [ ] Partially completed build can be reopened after shell restart.
- [ ] Prior state is discovered correctly.
- [ ] Artifact inspection still works after restart.
- [ ] Imported cohort artifacts remain resolvable after restart.
- [ ] DB-imported cohort artifacts remain resolvable after restart.
- [ ] File-imported cohort artifacts remain resolvable after restart.
- [ ] One execution step can be run after restart.

Negative test checklist

- [ ] DB import with unfilled `strategus-cohort-source-db-details.json` is blocked clearly.
- [ ] `showBanner = FALSE` suppresses ASCII art without suppressing normal shell prompts.
- [ ] `h` help is available during study-intent capture.
- [ ] `h` help is available during source selection.
- [ ] Invalid schema name is handled clearly.
- [ ] Unreachable cohort-source DB is handled clearly.
- [ ] Nonexistent local file path is handled clearly.
- [ ] Empty/invalid directory is handled clearly.
- [ ] Malformed JSON file is handled clearly.
- [ ] Non-Circe JSON file is handled clearly.
- [ ] Missing execution DB config is handled clearly during script generation or execution.
- [ ] `/back` works during source selection.
- [ ] Mid-selection exit and restart behave predictably.

Artifact inspection checklist

- [ ] `outputs/study_agent_state.json`
- [ ] `outputs/study_agent_runtime_state.json`
- [ ] `outputs/manual_intent.json` for CohortMethod
- [ ] `outputs/manual_inputs.json` for CohortMethod
- [ ] `imported-cohort-definitions/`
- [ ] selected cohort folders
- [ ] patched cohort folders if improvements were applied
- [ ] generated `scripts/`
- [ ] `strategus-db-details.json`
- [ ] `strategus-cohort-source-db-details.json`
- [ ] `strategus-execution-settings.json`
- [ ] `outputs/cm_comparisons.json` for CohortMethod
- [ ] `outputs/cohort_roles.json` for CohortMethod
- [ ] role-selection and TAR artifacts for incidence

Defect log

| Defect ID | Scenario ID | Shell | Severity | Failure point | Exact error text | Repro steps | Suspected cause | Resolved? | Notes |
|---|---|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |

Run summary

- Total scenarios attempted:
- Total scenarios passed:
- Total scenarios with defects:
- Recommendation-mode verdict:
- File-mode verdict:
- Directory-mode verdict:
- DB-mode verdict:
- Incidence shell overall verdict:
- CohortMethod shell overall verdict:
- Highest-priority follow-up items:
