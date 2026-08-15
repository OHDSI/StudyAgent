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

workflow_dialogue_prompt_width <- function() {
  option_width <- suppressWarnings(as.integer(getOption("studyAgent.promptWidth", 88L)))
  console_width <- suppressWarnings(as.integer(getOption("width", 80L)))
  widths <- c(option_width, console_width)
  widths <- widths[!is.na(widths) & widths > 20L]
  if (length(widths) == 0) return(80L)
  as.integer(min(widths))
}

wrap_workflow_dialogue_prompt <- function(prompt) {
  prompt <- as.character(prompt %||% "")
  if (!nzchar(prompt)) return(prompt)
  trailing_space <- grepl("[[:space:]]$", prompt)
  segments <- strsplit(gsub("", "", prompt), "
", fixed = TRUE)[[1]]
  width <- workflow_dialogue_prompt_width()
  wrapped_segments <- vapply(segments, function(segment) {
    if (!nzchar(segment)) return("")
    paste(strwrap(segment, width = width, exdent = 2), collapse = "
")
  }, character(1))
  wrapped <- paste(wrapped_segments, collapse = "
")
  if (isTRUE(trailing_space) && !grepl("[[:space:]]$", wrapped)) {
    wrapped <- paste0(wrapped, " ")
  }
  wrapped
}

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
  follow_up_plan <- core$follow_up_plan %||% list()
  if (length(follow_up_plan) > 0) {
    cat("Follow-up plan:\n")
    for (item in follow_up_plan) cat(sprintf("  - %s\n", item))
  }
  artifact_requests <- core$artifact_requests %||% list()
  if (length(artifact_requests) > 0) {
    cat("Additional artifacts requested:\n")
    for (item in artifact_requests) {
      artifact_id <- as.character(item$artifact_id %||% "<missing artifact_id>")
      reason <- as.character(item$reason %||% "")
      suffix <- if (isTRUE(item$permission_required %||% FALSE)) " (confirmation may be required)" else ""
      if (nzchar(trimws(reason))) {
        cat(sprintf("  - %s: %s%s\n", artifact_id, reason, suffix))
      } else {
        cat(sprintf("  - %s%s\n", artifact_id, suffix))
      }
    }
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
                                          command_prefix = "/ohdsi",
                                          disabled_command_message = NULL) {
  if (!is.function(study_intent_getter)) stop("study_intent_getter must be a function.")
  if (!is.function(build_stage_context)) stop("build_stage_context must be a function.")
  if (!is.function(call_dialogue)) stop("call_dialogue must be a function.")
  if (!is.function(render_response)) stop("render_response must be a function.")

  dialogue_state <- new_workflow_dialogue_state()

  ask_dialogue <- function(question, render = TRUE) {
    question <- trimws(as.character(question %||% ""))
    if (!nzchar(question)) {
      return(list(status = "error", error = "Provide a non-empty question."))
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
    if (isTRUE(render) && identical(response$status %||% "", "ok")) {
      render_response(response)
    }
    response
  }

  handle_command <- function(entered) {
    trimmed <- trimws(as.character(entered %||% ""))
    if (!isTRUE(interactive) || !startsWith(trimmed, command_prefix)) {
      return(list(handled = FALSE, value = entered))
    }
    if (!is.null(disabled_command_message)) {
      cat(as.character(disabled_command_message), "\n")
      return(list(handled = TRUE, value = ""))
    }
    question <- trimws(sub(paste0("^", command_prefix), "", trimmed))
    if (!nzchar(question)) {
      cat(empty_question_message, "\n")
      return(list(handled = TRUE, value = ""))
    }
    response <- ask_dialogue(question, render = FALSE)
    if (!identical(response$status %||% "", "ok")) {
      cat(sprintf("OHDSI guidance failed: %s\n", as.character(response$error %||% "unknown error")))
      return(list(handled = TRUE, value = ""))
    }
    render_response(response)
    list(handled = TRUE, value = "")
  }

  readline_with_dialogue <- function(prompt, allow_back = FALSE) {
    repeat {
      entered <- readline(wrap_workflow_dialogue_prompt(prompt))
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
    ask = ask_dialogue,
    readline = readline_with_dialogue
  )
}
