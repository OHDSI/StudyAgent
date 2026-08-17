.studyAgentSlashRuntimeProfilePath <- function() {
  path <- system.file("hades-runtime.json", package = "slashOhdsiStrategusAssistant")
  if (!nzchar(path)) {
    stop("Cannot locate hades-runtime.json in slashOhdsiStrategusAssistant.", call. = FALSE)
  }
  path
}

.studyAgentSlashRuntimeProfile <- function() {
  jsonlite::fromJSON(.studyAgentSlashRuntimeProfilePath(), simplifyVector = TRUE)
}

#' Report the installed HADES and Strategus runtime
#'
#' Returns the package versions required by the package release alongside the
#' versions installed in the current R session. The profile is generated from
#' the renv.lock environment used to test this package release.
#'
#' @return A list suitable for JSON serialization.
#' @export
strategusRuntimeReport <- function() {
  profile <- .studyAgentSlashRuntimeProfile()
  expected <- unlist(profile$packages, use.names = TRUE)
  installed <- vapply(names(expected), function(package_name) {
    if (!requireNamespace(package_name, quietly = TRUE)) return(NA_character_)
    as.character(utils::packageVersion(package_name))
  }, character(1))
  list(
    profile = as.character(profile$profile),
    expected_r_version = as.character(profile$r_version),
    installed_r_version = as.character(getRversion()),
    r_version_matches = getRversion() >= numeric_version(sub("^>=\\s*", "", as.character(profile$r_version))),
    packages = lapply(names(expected), function(package_name) {
      list(
        package = package_name,
        expected = unname(expected[[package_name]]),
        installed = unname(installed[[package_name]]),
        matches = identical(unname(installed[[package_name]]), unname(expected[[package_name]]))
      )
    })
  )
}

#' Check that the HADES runtime matches this package release
#'
#' The generated Strategus scripts target the tested HADES versions and minimum R version recorded
#' from this release's tested renv.lock. By default, a different HADES version is
#' rejected before a workflow writes or executes a specification. Set strict
#' to FALSE only when deliberately evaluating a new runtime.
#'
#' @param strict Require exact tested package versions and the minimum tested R version.
#' @return Invisibly, a runtime report.
#' @export
checkStrategusRuntime <- function(strict = TRUE) {
  report <- strategusRuntimeReport()
  package_rows <- report$packages
  missing <- vapply(package_rows, function(row) is.na(row$installed), logical(1))
  mismatched <- vapply(package_rows, function(row) !isTRUE(row$matches), logical(1))
  r_matches <- isTRUE(report$r_version_matches)

  if (any(missing) || (isTRUE(strict) && (!r_matches || any(mismatched)))) {
    details <- c(
      if (!r_matches) sprintf("R expected %s; found %s", report$expected_r_version, report$installed_r_version),
      vapply(package_rows[mismatched], function(row) {
        sprintf("%s expected %s; found %s", row$package, row$expected, ifelse(is.na(row$installed), "not installed", row$installed))
      }, character(1))
    )
    stop(
      sprintf(
        "Unsupported HADES runtime for profile %s. %s. Activate or restore the release-tested renv.lock before running this shell.",
        report$profile,
        paste(details, collapse = "; ")
      ),
      call. = FALSE
    )
  }
  invisible(report)
}
