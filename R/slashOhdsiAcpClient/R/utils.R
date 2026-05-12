`%||%` <- function(a, b) if (is.null(a)) b else a

.normalize_acp_body <- function(body) {
  if (!is.list(body)) return(body)
  if (!is.null(body$protocolRef)) body$protocolRef <- as.character(body$protocolRef)
  if (!is.null(body$cohortsCatalogRef)) body$cohortsCatalogRef <- as.character(body$cohortsCatalogRef)
  if (!is.null(body$cohortRefs)) {
    body$cohortRefs <- as.list(unname(vapply(body$cohortRefs, as.character, character(1))))
  }
  if (!is.null(body$characterizationRefs)) {
    body$characterizationRefs <- as.list(unname(vapply(body$characterizationRefs, as.character, character(1))))
  }
  body
}

.acp_timeout_seconds <- function(default = 180) {
  timeout_seconds <- as.numeric(Sys.getenv("ACP_TIMEOUT", as.character(default)))
  if (is.na(timeout_seconds) || timeout_seconds <= 0) timeout_seconds <- default
  timeout_seconds
}
