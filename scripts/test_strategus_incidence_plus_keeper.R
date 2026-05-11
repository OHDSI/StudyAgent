### Demo: `slashOhdsiStrategusAssistant::runStrategusIncidenceShell()`

## Run this from the repo root with ACP listening on `http://127.0.0.1:8765`.
## `scripts/demo_ohdsi_dialogue.R` is the quickest non-interactive `/ohdsi` smoke test.
##
## Useful `/ohdsi` prompts to try once the shell reaches phenotype recommendation steps:
##   /ohdsi why are these candidate target cohorts weak here?
##   /ohdsi what would make this outcome definition more defensible?

script_dir <- local({
  cmd_args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", cmd_args, value = TRUE)
  if (length(file_arg) > 0) {
    return(dirname(normalizePath(sub("^--file=", "", file_arg[[1]]), winslash = "/", mustWork = FALSE)))
  }
  frame_files <- Filter(Negate(is.null), lapply(sys.frames(), function(x) x$ofile))
  if (length(frame_files) > 0) {
    return(dirname(normalizePath(frame_files[[length(frame_files)]], winslash = "/", mustWork = FALSE)))
  }
  normalizePath("scripts", winslash = "/", mustWork = FALSE)
})

source(file.path(script_dir, "demo_setup.R"))
repo_root <- set_study_agent_repo_root(start = dirname(script_dir))
load_study_agent_r_packages(include_strategus = TRUE)

Sys.setenv(ACP_TIMEOUT = "280")
invisible(connect_study_agent_acp())

### CLEAN UP FROM LAST RUN?
# Uncomment to reset the state of the output folder.
# unlink(repo_file("demo-strategus-cohort-incidence"), recursive = TRUE, force = TRUE)

## (NO RELEVANT PHENOTYPE TEST) First enter this study intent, which should not return strong phenotype matches:
## "What is the risk of GI bleed in new users of Celecoxib compared to new users of Diclofenac?"
slashOhdsiStrategusAssistant::runStrategusIncidenceShell(
  outputDir = "demo-strategus-cohort-incidence",
  acpUrl = "http://127.0.0.1:8765",
  studyAgentBaseDir = repo_root,
  indexDir = "data/phenotype_index_cipher_omop"
)

## (RELEVANT PHENOTYPE TEST) This intent should yield stronger phenotype candidates:
slashOhdsiStrategusAssistant::runStrategusIncidenceShell(
  outputDir = "demo-strategus-cohort-incidence",
  acpUrl = "http://127.0.0.1:8765",
  studyAgentBaseDir = repo_root,
  indexDir = "data/phenotype_index_cipher_omop",
  studyIntent = "What is the risk of GI bleed in new users of tofacitinib compared to new users of ruxolitinib?"
)

## Use this to resume from cached artifacts and regenerate output scripts.
slashOhdsiStrategusAssistant::runStrategusIncidenceShell(
  outputDir = "demo-strategus-cohort-incidence",
  acpUrl = "http://127.0.0.1:8765",
  studyAgentBaseDir = repo_root,
  resume = TRUE,
  allowCache = TRUE,
  promptOnCache = FALSE,
  interactive = FALSE,
  indexDir = "data/phenotype_index_cipher_omop"
)
