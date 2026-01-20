acp_state <- new.env(parent = emptyenv())

#' Connect to ACP bridge
#' @param url e.g. "http://127.0.0.1:7777"
#' @param token optional bearer token
#' @return invisible(TRUE)
acp_connect <- function(url = "http://127.0.0.1:7777", token = NULL) {
  url <- sub("/$", "", url)
  resp <- httr::GET(paste0(url, "/health"))
  if (httr::status_code(resp) != 200) stop("ACP bridge not reachable")
  acp_state$url <- url
  acp_state$token <- token
  invisible(TRUE)
}

.acp_post <- function(path, body) {
  if (is.null(acp_state$url)) stop("ACP not connected; call acp_connect().")
  if (is.list(body)) {
    if (!is.null(body$protocolRef)) body$protocolRef <- as.character(body$protocolRef)
    if (!is.null(body$cohortsCatalogRef)) body$cohortsCatalogRef <- as.character(body$cohortsCatalogRef)
    if (!is.null(body$cohortRefs)) body$cohortRefs <- as.list(unname(vapply(body$cohortRefs, as.character, character(1))))
    if (!is.null(body$characterizationRefs)) body$characterizationRefs <- as.list(unname(vapply(body$characterizationRefs, as.character, character(1))))
  }
  url <- paste0(acp_state$url, path)
  headers <- c(`Content-Type` = "application/json")
  if (!is.null(acp_state$token)) {
    headers <- c(headers, Authorization = paste("Bearer", acp_state$token))
  }
  resp <- httr::POST(
    url,
    body = body,
    encode = "json",
    httr::add_headers(.headers = headers)
  )
  if (httr::status_code(resp) >= 300) stop("ACP error: ", httr::content(resp, as = "text"))
  jsonlite::fromJSON(httr::content(resp, as = "text"), simplifyVector = FALSE)
}
