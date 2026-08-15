### Demo: `slashOhdsiStrategusAssistant::runStrategusCohortMethodsShell()`

## Run this from the repo root with ACP listening on `http://127.0.0.1:8765`.
## If you launch from a parent `renv` project, use the same `.Rprofile` pattern that
## already worked for `scripts/demo_ohdsi_dialogue.R`.
##
## Useful `/ohdsi` prompts to try during analytic-settings and phenotype review steps:
##   /ohdsi why is washout important here?
##   /ohdsi what is weak about this comparator cohort?
##   /ohdsi what should I double-check before accepting these analytic settings?

acp_url = "http://127.0.0.1:8765"
script_dir = "OHDSI-Study-Agent/scripts"

source(file.path(script_dir, "demo_setup.R"))
repo_root <- set_study_agent_repo_root(start = dirname(script_dir))
load_study_agent_r_packages(include_strategus = TRUE)

Sys.setenv(ACP_TIMEOUT = "1800") # set high because of detailed keeper concept set extraction
Sys.setenv(ACP_URL = acp_url)

Sys.setenv(PHENOTYPE_INDEX_DIR = repo_file("data", "phenotype_index_cipher_omop"))
invisible(connect_study_agent_acp())

### Optional reset from a prior run.
#reset_demo_output_dir(repo_file("demo-strategus-cohort-method"), prompt = TRUE)
#
# Note: this clears only `demo-strategus-cohort-method`. If `incidenceOutputDir` points
# at `demo-strategus-cohort-incidence`, you may still see cache prompts for artifacts in
# that separate directory unless you reset it too.
# If you already ran `scripts/test_strategus_incidence_plus_keeper.R`, this shell can
# reuse cached target and outcome artifacts from `demo-strategus-cohort-incidence`.
slashOhdsiStrategusAssistant::runStrategusCohortMethodsShell(
  outputDir = "demo-strategus-cohort-method",
  acpUrl = acp_url, 
  studyAgentBaseDir = repo_root,
  indexDir = "data/phenotype_index_cipher_omop",
  executionTableDisplay = "viewer",
  showBanner = FALSE
)
## possible study intent:
##    Compare new users of GLP-1RA medications vs new users of DPP4-i medications for chronic lower respiratory disease outcomes.
## possible methods statement:
##    Use data from 2010 to 2025. A 180-day washout, intent-to-treat with 180 days follow-up, sIPTW confounder balancing and a Cox model to estimate time-to-event for the primary outcome.

## Use this to resume from cached artifacts and regenerate output scripts.
## slashOhdsiStrategusAssistant::runStrategusCohortMethodsShell(
##   outputDir = "demo-strategus-cohort-method",
##   acpUrl = acp_url,
##   studyAgentBaseDir = repo_root,
##   indexDir = "data/phenotype_index_cipher_omop",
##   incidenceOutputDir = "demo-strategus-cohort-incidence",
##   resume = TRUE,
##   allowCache = TRUE,
##   promptOnCache = TRUE,
##   interactive = TRUE,
##   showBanner = FALSE
## )


## Use this to resume from cached artifacts and regenerate output scripts without prompts.
## slashOhdsiStrategusAssistant::runStrategusCohortMethodsShell(
##   outputDir = "demo-strategus-cohort-method",
##   acpUrl = "http://127.0.0.1:8765",
##   studyAgentBaseDir = repo_root,
##    indexDir = "data/phenotype_index_cipher_omop",
##   incidenceOutputDir = "demo-strategus-cohort-incidence",
##   resume = TRUE,
##   allowCache = TRUE,
##   promptOnCache = FALSE,
##   interactive = FALSE
## )
