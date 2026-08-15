### Demo / test: no-AI `slashOhdsiStrategusAssistant::runStrategusIncidenceShell()`

## This example deliberately runs without ACP/AI support. It uses direct cohort
## import, deterministic in-shell help, and local Strategus execution artifacts.
## Run it from the repo root or use the same parent-renv `.Rprofile` setup as the
## other R demos.

script_dir <- "OHDSI-Study-Agent/scripts"
source(file.path(script_dir, "demo_setup.R"))
repo_root <- set_study_agent_repo_root(start = dirname(script_dir))
load_study_agent_r_packages(include_strategus = TRUE)

## Next line commented out, see https://github.com/OHDSI/StudyAgent/issues/78
### Sys.setenv(PHENOTYPE_INDEX_DIR = repo_file("data", "phenotype_index_cipher_omop"))

### Optional reset from a prior run.
# reset_demo_output_dir(repo_file("demo-strategus-cohort-incidence"), prompt = TRUE)

## Run a local shell workflow to specify and execute an incidence-rate analysis.
slashOhdsiStrategusAssistant::runStrategusIncidenceShell(
  outputDir = "demo-strategus-cohort-incidence",
  aiSupport = "disabled",
  studyAgentBaseDir = repo_root,
  ## Next line commented out, see https://github.com/OHDSI/StudyAgent/issues/78
  ## indexDir = "data/phenotype_index_cipher_omop",
  showBanner = FALSE,
  executionTableDisplay = "viewer"
)

## Resume a local no-AI workflow from cached artifacts.
# slashOhdsiStrategusAssistant::runStrategusIncidenceShell(
#   outputDir = "demo-strategus-cohort-incidence",
#   aiSupport = "disabled",
#   studyAgentBaseDir = repo_root,
#   resume = TRUE,
#   allowCache = TRUE,
#   promptOnCache = TRUE,
#   interactive = TRUE,
#   showBanner = FALSE
# )
