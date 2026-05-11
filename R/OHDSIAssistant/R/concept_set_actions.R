#' Compatibility wrapper for concept set patch proposal
#' @inheritParams slashOhdsiAcpClient::proposeIncludeDescendantsPatch
#' @export
proposeIncludeDescendantsPatch <- function(conceptSetRef) {
  slashOhdsiAcpClient::proposeIncludeDescendantsPatch(conceptSetRef)
}

#' Compatibility wrapper for concept set patch preview
#' @inheritParams slashOhdsiAcpClient::previewConceptSetPatch
#' @export
previewConceptSetPatch <- function(conceptSetRef, patch) {
  slashOhdsiAcpClient::previewConceptSetPatch(conceptSetRef, patch)
}

#' Compatibility wrapper for concept set patch application
#' @inheritParams slashOhdsiAcpClient::applyConceptSetPatch
#' @export
applyConceptSetPatch <- function(conceptSetRef,
                                 patch,
                                 backup = TRUE,
                                 outputPath = NULL,
                                 useActions = NULL,
                                 overwrite = TRUE) {
  slashOhdsiAcpClient::applyConceptSetPatch(
    conceptSetRef = conceptSetRef,
    patch = patch,
    backup = backup,
    outputPath = outputPath,
    useActions = useActions,
    overwrite = overwrite
  )
}
