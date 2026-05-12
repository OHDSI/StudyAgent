### Demo: shell-equivalent `/ohdsi` workflow dialogue

## Run this from the repo root with ACP listening on `http://127.0.0.1:8765`.
## This does not launch the full shell. It exercises the same exported dialogue
## helpers that `runStrategusIncidenceShell()` and `runStrategusCohortMethodsShell()`
## use for `/ohdsi`.

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
client <- connect_study_agent_acp()

`%||%` <- function(a, b) if (is.null(a)) b else a

run_ohdsi_dialogue_demo <- function(workflow = c("incidence", "cohort_methods"),
                                    study_intent,
                                    step,
                                    role = "",
                                    context = list(),
                                    question) {
  workflow <- match.arg(workflow)
  build_stage_context <- switch(
    workflow,
    incidence = slashOhdsiStrategusAssistant::build_incidence_workflow_stage_context,
    cohort_methods = slashOhdsiStrategusAssistant::build_cohort_methods_workflow_stage_context
  )

  dialogue <- slashOhdsiStrategusAssistant::new_workflow_dialogue_session(
    interactive = TRUE,
    study_intent_getter = function() study_intent,
    build_stage_context = function(studyIntent, dialogue_state) {
      build_stage_context(
        study_intent = studyIntent,
        dialogue_state = dialogue_state,
        interactive = TRUE
      )
    },
    call_dialogue = function(stage_context, message) {
      slashOhdsiAcpClient::acp_workflow_context_dialogue(
        client = client,
        stage_context = stage_context,
        message = message
      )
    },
    render_response = slashOhdsiStrategusAssistant::render_workflow_dialogue_response
  )

  dialogue$set_context(step = step, role = role, context = context)

  stage_context <- build_stage_context(
    study_intent = study_intent,
    dialogue_state = dialogue$state,
    interactive = TRUE
  )

  cat(sprintf("\n== %s /ohdsi demo ==\n", gsub("_", " ", workflow, fixed = TRUE)))
  cat(sprintf("Slash command: /ohdsi %s\n", question))
  cat("Stage context sent to ACP:\n")
  cat(jsonlite::toJSON(stage_context, pretty = TRUE, auto_unbox = TRUE, null = "null"), "\n")

  validation_response <- slashOhdsiAcpClient::acp_workflow_context_dialogue(
    client = client,
    stage_context = stage_context,
    message = question
  )

  if (!identical(validation_response$status %||% "", "ok")) {
    stop(sprintf(
      "workflow_context_dialogue failed for %s: %s",
      workflow,
      validation_response$error %||% "unknown error"
    ))
  }

  cat("Validated direct ACP call. Replaying through the shell-equivalent `/ohdsi` handler...\n")
  handled <- dialogue$handle_command(paste("/ohdsi", question))
  if (!isTRUE(handled$handled)) {
    stop("The /ohdsi command was not handled by the dialogue session.")
  }

  invisible(validation_response)
}

run_ohdsi_dialogue_demo(
  workflow = "incidence",
  study_intent = "What is the incidence of hospitalized gastrointestinal bleeding after starting tofacitinib?",
  step = "target_recommendation",
  role = "target",
  context = list(
    target_statement = "New users of tofacitinib",
    outcome_statement = "Hospitalized gastrointestinal bleeding"
  ),
  question = "why are these candidate target cohorts weak here?"
)

run_ohdsi_dialogue_demo(
  workflow = "cohort_methods",
  study_intent = "What is the risk of GI bleed in new users of celecoxib compared with diclofenac?",
  step = "analytic_settings_step_by_step",
  role = "comparator",
  context = list(
    target_statement = "New users of celecoxib",
    comparator_statement = "New users of diclofenac",
    outcome_statements = list("Hospitalized gastrointestinal bleeding"),
    selected_target_ids = c("ohdsi:demo-target"),
    selected_comparator_ids = c("ohdsi:demo-comparator"),
    selected_outcome_ids = c("ohdsi:demo-outcome"),
    analysis_settings_path = repo_file("demo", "strategus-execution-settings.json")
  ),
  question = "why is washout important here?"
)
