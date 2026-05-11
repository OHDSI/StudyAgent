#' Suggest phenotypes for a study protocol (compatibility wrapper)
#' @inheritParams slashOhdsiAcpClient::suggestPhenotypes
#' @return list response from ACP flow or local stub
#' @export
suggestPhenotypes <- function(protocolPath = NULL,
                              studyIntent = NULL,
                              topK = 20,
                              maxResults = 3,
                              candidateLimit = 10,
                              interactive = TRUE) {
  if (!requireNamespace("slashOhdsiAcpClient", quietly = TRUE)) {
    stop("slashOhdsiAcpClient must be installed or loaded to use suggestPhenotypes().")
  }
  slashOhdsiAcpClient::suggestPhenotypes(
    protocolPath = protocolPath,
    studyIntent = studyIntent,
    topK = topK,
    maxResults = maxResults,
    candidateLimit = candidateLimit,
    interactive = interactive
  )
}

#' Pull phenotype definitions to a local folder (compatibility wrapper)
#' @inheritParams slashOhdsiAcpClient::pullPhenotypeDefinitions
#' @return character vector of written file paths
#' @export
pullPhenotypeDefinitions <- function(cohortIds,
                                     outputDir = ".",
                                     overwrite = FALSE) {
  if (!requireNamespace("slashOhdsiAcpClient", quietly = TRUE)) {
    stop("slashOhdsiAcpClient must be installed or loaded to use pullPhenotypeDefinitions().")
  }
  slashOhdsiAcpClient::pullPhenotypeDefinitions(
    cohortIds = cohortIds,
    outputDir = outputDir,
    overwrite = overwrite
  )
}

#' Review phenotype definitions for improvements (compatibility wrapper)
#' @inheritParams slashOhdsiAcpClient::reviewPhenotypes
#' @return list response from ACP flow or local stub
#' @export
reviewPhenotypes <- function(protocolPath,
                             cohortJsonPaths,
                             characterizationPaths = NULL,
                             interactive = TRUE,
                             apply = FALSE,
                             select = NULL,
                             outputDir = NULL) {
  if (!requireNamespace("slashOhdsiAcpClient", quietly = TRUE)) {
    stop("slashOhdsiAcpClient must be installed or loaded to use reviewPhenotypes().")
  }
  slashOhdsiAcpClient::reviewPhenotypes(
    protocolPath = protocolPath,
    cohortJsonPaths = cohortJsonPaths,
    characterizationPaths = characterizationPaths,
    interactive = interactive,
    apply = apply,
    select = select,
    outputDir = outputDir
  )
}

#' Select phenotype recommendations (compatibility wrapper)
#' @inheritParams slashOhdsiAcpClient::selectPhenotypeRecommendations
#' @return character vector of chosen phenotype ids
#' @export
selectPhenotypeRecommendations <- function(recommendations,
                                           select = NULL,
                                           interactive = interactive()) {
  if (!requireNamespace("slashOhdsiAcpClient", quietly = TRUE)) {
    stop("slashOhdsiAcpClient must be installed or loaded to use selectPhenotypeRecommendations().")
  }
  slashOhdsiAcpClient::selectPhenotypeRecommendations(
    recommendations = recommendations,
    select = select,
    interactive = interactive
  )
}

#' Select phenotype improvements (compatibility wrapper)
#' @inheritParams slashOhdsiAcpClient::selectPhenotypeImprovements
#' @return list with selected improvements and written file paths
#' @export
selectPhenotypeImprovements <- function(improvements,
                                        cohortJsonPaths,
                                        select = NULL,
                                        apply = FALSE,
                                        outputDir = NULL,
                                        interactive = interactive()) {
  if (!requireNamespace("slashOhdsiAcpClient", quietly = TRUE)) {
    stop("slashOhdsiAcpClient must be installed or loaded to use selectPhenotypeImprovements().")
  }
  slashOhdsiAcpClient::selectPhenotypeImprovements(
    improvements = improvements,
    cohortJsonPaths = cohortJsonPaths,
    select = select,
    apply = apply,
    outputDir = outputDir,
    interactive = interactive
  )
}
