### Demo: `slashOhdsiStrategusAssistant::runStrategusCohortMethodsShell()`

## Run this from the repo root with ACP listening on `http://127.0.0.1:8765`.
## If you launch from a parent `renv` project, use the same `.Rprofile` pattern that
## already worked for `scripts/demo_ohdsi_dialogue.R`.
##
## Useful `/ohdsi` prompts to try during analytic-settings and phenotype review steps:
##   /ohdsi why is washout important here?
##   /ohdsi what is weak about this comparator cohort?
##   /ohdsi what should I double-check before accepting these analytic settings?

script_dir = "OHDSI-Study-Agent/scripts/" 

source(file.path(script_dir, "demo_setup.R"))
repo_root <- set_study_agent_repo_root(start = dirname(script_dir))
load_study_agent_r_packages(include_strategus = TRUE)

Sys.setenv(ACP_TIMEOUT = "180")
Sys.setenv(PHENOTYPE_INDEX_DIR = repo_file("data", "phenotype_index_cipher_omop"))
invisible(connect_study_agent_acp())

### Optional reset from a prior run.
#reset_demo_output_dir(repo_file("demo-strategus-cohort-method"), prompt = TRUE)
#
# If you already ran `scripts/test_strategus_incidence_plus_keeper.R`, this shell can
# reuse cached target and outcome artifacts from `demo-strategus-cohort-incidence`.
slashOhdsiStrategusAssistant::runStrategusCohortMethodsShell(
  outputDir = "demo-strategus-cohort-method",
  acpUrl = "http://127.0.0.1:8765",
  studyAgentBaseDir = repo_root,
  indexDir = "data/phenotype_index_cipher_omop",
  incidenceOutputDir = "demo-strategus-cohort-incidence",
  studyIntent = paste(
    "Compare olanzapine new users vs risperidone new users for acute myocardial infarction.",
    "Use a 365-day washout, intent-to-treat follow-up, 1:1 propensity score matching",
    "on standardized logit with a caliper of 0.2, and a Cox model."
  )
)

## Use this to resume from cached artifacts and regenerate output scripts.
# slashOhdsiStrategusAssistant::runStrategusCohortMethodsShell(
#   outputDir = "demo-strategus-cohort-method",
#   acpUrl = "http://127.0.0.1:8765",
#   studyAgentBaseDir = repo_root,
#   indexDir = "data/phenotype_index_cipher_omop",
#   incidenceOutputDir = "demo-strategus-cohort-incidence",
#   resume = TRUE,
#   allowCache = TRUE,
#   promptOnCache = FALSE,
#   interactive = FALSE
# )
