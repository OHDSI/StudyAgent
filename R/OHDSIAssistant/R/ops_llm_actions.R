#' Compatibility wrapper for ACP concept-set LLM actions
#' @inheritParams slashOhdsiAcpClient::applyLLMActionsConceptSet
#' @export
applyLLMActionsConceptSet <- function(conceptSetRef,
                                      actions,
                                      preview = TRUE,
                                      overwrite = FALSE,
                                      backup = TRUE) {
  slashOhdsiAcpClient::applyLLMActionsConceptSet(
    conceptSetRef = conceptSetRef,
    actions = actions,
    preview = preview,
    overwrite = overwrite,
    backup = backup
  )
}
