### Demo: no-AI `slashOhdsiStrategusAssistant::runStrategusCohortMethodsShell()`

## This example deliberately runs without ACP/AI support. It uses direct cohort
## import and the step-by-step analytic-settings wizard.

script_dir <- "OHDSI-Study-Agent/scripts"
source(file.path(script_dir, "demo_setup.R"))
repo_root <- set_study_agent_repo_root(start = dirname(script_dir))
load_study_agent_r_packages(include_strategus = TRUE)

  ## Next line commented out, see https://github.com/OHDSI/StudyAgent/issues/78
  ### Sys.setenv(PHENOTYPE_INDEX_DIR = repo_file("data", "phenotype_index_cipher_omop"))

### Optional reset from a prior run.
# reset_demo_output_dir(repo_file("demo-strategus-cohort-method"), prompt = TRUE)

## Run a local shell workflow to specify and execute a CohortMethod analysis.
slashOhdsiStrategusAssistant::runStrategusCohortMethodsShell(
  outputDir = "demo-strategus-cohort-method",
  aiSupport = "disabled",
  studyAgentBaseDir = repo_root,
  ## Next line commented out, see https://github.com/OHDSI/StudyAgent/issues/78
  ### indexDir = "data/phenotype_index_cipher_omop",
  executionTableDisplay = "viewer",
  showBanner = FALSE
)

## Resume a local no-AI workflow from cached artifacts.
# slashOhdsiStrategusAssistant::runStrategusCohortMethodsShell(
#   outputDir = "demo-strategus-cohort-method",
#   aiSupport = "disabled",
#   studyAgentBaseDir = repo_root,
#   incidenceOutputDir = "demo-strategus-cohort-incidence",
#   resume = TRUE,
#   allowCache = TRUE,
#   promptOnCache = TRUE,
#   interactive = TRUE,
#   showBanner = FALSE
# )
