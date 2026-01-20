#' Apply LLM-proposed actions to a concept set via ACP
#' @param conceptSetRef path to local concept set JSON
#' @param actions list of action objects (from tool response $actions)
#' @param preview logical; TRUE = dry run
#' @param overwrite logical; if FALSE, writes to -assistant-v*.json
#' @param backup logical; if TRUE and overwrite=TRUE, create timestamped .bak
#' @return list server response
applyLLMActionsConceptSet <- function(conceptSetRef, actions, preview = TRUE, overwrite = FALSE, backup = TRUE) {
  if (is.null(acp_state$url)) stop("ACP not connected; call acp_connect() first.")
  body <- list(
    artifactRef = conceptSetRef,
    actions = actions %||% list(),
    write = !isTRUE(preview),
    overwrite = isTRUE(overwrite),
    backup = isTRUE(backup)
  )
  .acp_post("/actions/execute_llm", body)
}
