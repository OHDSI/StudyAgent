### Demo: `phenotype_validation_review` (ACP flow)

## Run this from the repo root with ACP listening on `http://127.0.0.1:8765`.

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
load_study_agent_r_packages(include_strategus = FALSE)
client <- connect_study_agent_acp()

keeper_row <- list(
  age = 44,
  gender = "Male",
  visitContext = "Inpatient Visit",
  presentation = "Gastrointestinal hemorrhage",
  priorDisease = "Peptic ulcer",
  symptoms = "",
  comorbidities = "",
  priorDrugs = "celecoxib",
  priorTreatmentProcedures = "",
  diagnosticProcedures = "",
  measurements = "",
  alternativeDiagnosis = "",
  afterDisease = "",
  afterDrugs = "Naproxen",
  afterTreatmentProcedures = ""
)

body <- list(
  disease_name = "Gastrointestinal bleeding",
  keeper_row = keeper_row
)

resp <- slashOhdsiAcpClient::acp_call_flow(
  client = client,
  flow_name = "phenotype_validation_review",
  body = body
)
cat("\n== Phenotype Validation Review (ACP flow) ==\n")
print(resp)
