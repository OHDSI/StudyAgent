### Demo / test: `slashOhdsiStrategusAssistant::runStrategusIncidenceShell()`

## Run this from the repo root with ACP listening on `http://127.0.0.1:8765`.
## If you launch from a parent `renv` project, use the same `.Rprofile` pattern that
## already worked for `scripts/demo_ohdsi_dialogue.R`.
## `scripts/demo_ohdsi_dialogue.R` is still the quickest non-interactive `/ohdsi` smoke test.
##
## Useful `/ohdsi` prompts to try once the shell reaches phenotype recommendation and TAR steps:
##   /ohdsi what should I do if none of the candidate cohorts are relevant?
##   /ohdsi what happens if I accept the phenotype improvement recommendations?
##   /ohdsi how should I specify TAR so that denominators are coherent across strata?

acp_url = "http://127.0.0.1:8765"
script_dir = "OHDSI-Study-Agent/scripts"

source(file.path(script_dir, "demo_setup.R"))
repo_root <- set_study_agent_repo_root(start = dirname(script_dir))
load_study_agent_r_packages(include_strategus = TRUE)

Sys.setenv(ACP_TIMEOUT = "1800")
Sys.setenv(ACP_URL = acp_url)
Sys.setenv(PHENOTYPE_INDEX_DIR = repo_file("data", "phenotype_index_cipher_omop"))
invisible(connect_study_agent_acp())

### Optional reset from a prior run.
#reset_demo_output_dir(repo_file("demo-strategus-cohort-incidence"), prompt = TRUE)
#
# Note: this clears only `demo-strategus-cohort-incidence`. If you plan to reuse its
# cached artifacts during resume, leave the directory intact.

## Run a shell-based workflow to specify and execute an incidence-rate analysis
slashOhdsiStrategusAssistant::runStrategusIncidenceShell(
  outputDir = "demo-strategus-cohort-incidence",
  acpUrl = acp_url,
  studyAgentBaseDir = repo_root,
  indexDir = "data/phenotype_index_cipher_omop",
  showBanner = FALSE,
  executionTableDisplay = "viewer"
)

############
## Use this to resume from cached artifacts and regenerate output scripts.
slashOhdsiStrategusAssistant::runStrategusIncidenceShell(
  outputDir = "demo-strategus-cohort-incidence",
  acpUrl = acp_url,
  studyAgentBaseDir = repo_root,
  resume = TRUE,
  allowCache = TRUE,
  promptOnCache = TRUE,
  showBanner = FALSE,
  interactive = TRUE,
  indexDir = "data/phenotype_index_cipher_omop"
)

## Use this to resume from cached artifacts and regenerate output scripts without prompts.
## slashOhdsiStrategusAssistant::runStrategusIncidenceShell(
##   outputDir = "demo-strategus-cohort-incidence",
##   acpUrl = acp_url,
##   studyAgentBaseDir = repo_root,
##   resume = TRUE,
##   allowCache = TRUE,
##   promptOnCache = FALSE,
##   interactive = FALSE,
##   indexDir = "data/phenotype_index_cipher_omop"
## )

## (NO RELEVANT PHENOTYPE TEST) First enter this study intent, which should not return strong phenotype matches:
## "What is the risk of GI bleed in new users of Celecoxib compared to new users of Diclofenac?"
# slashOhdsiStrategusAssistant::runStrategusIncidenceShell(
#   outputDir = "demo-strategus-cohort-incidence",
#   acpUrl = acp_url,
#   studyAgentBaseDir = repo_root,
#   indexDir = "data/phenotype_index_cipher_omop"
# )
