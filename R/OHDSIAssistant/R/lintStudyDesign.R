#' Compatibility wrapper for study design linting
#' @inheritParams slashOhdsiAcpClient::lintStudyDesign
#' @export
lintStudyDesign <- function(studyProtocol,
                            studyPackage = ".",
                            lintTasks = c("concept-sets-review", "cohort-critique-general-design"),
                            apply = FALSE,
                            interactive = TRUE,
                            streamThoughts = TRUE,
                            handleActions = FALSE,
                            applyActions = FALSE,
                            overwriteActions = FALSE,
                            backupActions = TRUE) {
  slashOhdsiAcpClient::lintStudyDesign(
    studyProtocol = studyProtocol,
    studyPackage = studyPackage,
    lintTasks = lintTasks,
    apply = apply,
    interactive = interactive,
    streamThoughts = streamThoughts,
    handleActions = handleActions,
    applyActions = applyActions,
    overwriteActions = overwriteActions,
    backupActions = backupActions
  )
}
