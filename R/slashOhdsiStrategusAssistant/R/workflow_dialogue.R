compact_workflow_dialogue_context <- function(value) {
  if (!is.list(value) || length(value) == 0) return(list())
  keep <- lapply(value, function(item) {
    if (is.null(item)) return(FALSE)
    if (is.character(item) && length(item) == 1 && !nzchar(trimws(item))) return(FALSE)
    if (is.atomic(item) && length(item) == 0) return(FALSE)
    if (is.list(item) && length(item) == 0) return(FALSE)
    TRUE
  })
  keep_idx <- which(vapply(keep, isTRUE, logical(1)))
  if (length(keep_idx) == 0) return(list())
  value[keep_idx]
}

new_workflow_navigation_signal <- function(action) {
  structure(list(action = as.character(action %||% "")), class = "workflow_navigation_signal")
}

#' Construct mutable dialogue state for interactive workflow guidance
#' @return environment storing current step, role, and compact context
#' @export
new_workflow_dialogue_state <- function() {
  state <- new.env(parent = emptyenv())
  state$current_step <- ""
  state$current_role <- ""
  state$current_context <- list()
  state
}

#' Update dialogue state for the current workflow step
#' @param dialogue_state dialogue state environment
#' @param step current workflow step identifier
#' @param role optional active role identifier
#' @param context optional step context list
#' @return invisible NULL
#' @export
set_workflow_dialogue_context <- function(dialogue_state,
                                          step = "",
                                          role = "",
                                          context = list()) {
  if (!is.environment(dialogue_state)) stop("dialogue_state must be an environment.")
  dialogue_state$current_step <- as.character(step %||% "")
  dialogue_state$current_role <- as.character(role %||% "")
  dialogue_state$current_context <- compact_workflow_dialogue_context(context %||% list())
  invisible(NULL)
}

#' Render a workflow dialogue response in the interactive shell
#' @param response ACP workflow dialogue response
#' @return invisible NULL
#' @export
render_workflow_dialogue_response <- function(response) {
  core <- response$dialogue %||% response
  cat("\n== OHDSI Guidance ==\n")
  answer <- as.character(core$answer %||% "")
  if (nzchar(trimws(answer))) {
    cat(answer, "\n")
  } else {
    cat("No contextual guidance was returned.\n")
  }
  guidance <- core$current_step_guidance %||% list()
  if (length(guidance) > 0) {
    cat("Current step guidance:\n")
    for (item in guidance) cat(sprintf("  - %s\n", item))
  }
  cautions <- core$cautions %||% list()
  if (length(cautions) > 0) {
    cat("Cautions:\n")
    for (item in cautions) cat(sprintf("  - %s\n", item))
  }
  next_actions <- core$suggested_next_actions %||% list()
  if (length(next_actions) > 0) {
    cat("Suggested next actions:\n")
    for (item in next_actions) cat(sprintf("  - %s\n", item))
  }
  cat("\n")
  invisible(NULL)
}

#' Construct interactive /ohdsi dialogue handlers for a workflow shell
#' @param interactive whether shell prompts are interactive
#' @param study_intent_getter function returning current study intent
#' @param build_stage_context function taking studyIntent and dialogue_state
#' @param call_dialogue function taking stage_context and message
#' @param render_response function for displaying response text
#' @param empty_question_message text shown when `/ohdsi` has no question
#' @param command_prefix slash command prefix
#' @return list with `state`, `set_context`, `handle_command`, and `readline`
#' @export
new_workflow_dialogue_session <- function(interactive = TRUE,
                                          study_intent_getter,
                                          build_stage_context,
                                          call_dialogue,
                                          render_response = render_workflow_dialogue_response,
                                          empty_question_message = "Enter a question after /ohdsi.",
                                          command_prefix = "/ohdsi") {
  if (!is.function(study_intent_getter)) stop("study_intent_getter must be a function.")
  if (!is.function(build_stage_context)) stop("build_stage_context must be a function.")
  if (!is.function(call_dialogue)) stop("call_dialogue must be a function.")
  if (!is.function(render_response)) stop("render_response must be a function.")

  dialogue_state <- new_workflow_dialogue_state()

  handle_command <- function(entered) {
    trimmed <- trimws(as.character(entered %||% ""))
    if (!isTRUE(interactive) || !startsWith(trimmed, command_prefix)) {
      return(list(handled = FALSE, value = entered))
    }
    question <- trimws(sub(paste0("^", command_prefix), "", trimmed))
    if (!nzchar(question)) {
      cat(empty_question_message, "\n")
      return(list(handled = TRUE, value = ""))
    }
    stage_context <- build_stage_context(
      studyIntent = study_intent_getter(),
      dialogue_state = dialogue_state
    )
    stage_context$dialogue$last_user_message <- question
    response <- tryCatch(
      call_dialogue(stage_context = stage_context, message = question),
      error = function(e) list(status = "error", error = conditionMessage(e))
    )
    if (!identical(response$status %||% "", "ok")) {
      cat(sprintf("OHDSI guidance failed: %s\n", as.character(response$error %||% "unknown error")))
      return(list(handled = TRUE, value = ""))
    }
    render_response(response)
    list(handled = TRUE, value = "")
  }

  readline_with_dialogue <- function(prompt, allow_back = FALSE) {
    repeat {
      entered <- readline(prompt)
      trimmed <- trimws(as.character(entered %||% ""))
      if (isTRUE(allow_back) && identical(trimmed, "/back")) {
        return(new_workflow_navigation_signal("back"))
      }
      handled <- handle_command(entered)
      if (isTRUE(handled$handled)) next
      return(handled$value)
    }
  }

  list(
    state = dialogue_state,
    set_context = function(step = "", role = "", context = list()) {
      set_workflow_dialogue_context(
        dialogue_state = dialogue_state,
        step = step,
        role = role,
        context = context
      )
    },
    handle_command = handle_command,
    readline = readline_with_dialogue
  )
}
