#' Create an ACP client object
#' @param url ACP base URL, e.g. "http://127.0.0.1:8765"
#' @param token optional bearer token
#' @param check when TRUE, call `/health` before returning
#' @return ACP client object
#' @export
acp_client <- function(url = "http://127.0.0.1:8765", token = NULL, check = TRUE) {
  client <- structure(
    list(
      url = sub("/$", "", as.character(url)),
      token = token
    ),
    class = "acp_client"
  )
  if (isTRUE(check)) acp_check_health(client)
  client
}

#' Check ACP health
#' @param client ACP client object
#' @return invisible(TRUE) when ACP is reachable
#' @export
acp_check_health <- function(client) {
  client <- .as_acp_client(client)
  resp <- httr::GET(paste0(client$url, "/health"), httr::timeout(.acp_timeout_seconds()))
  if (httr::status_code(resp) != 200) stop("ACP bridge not reachable")
  invisible(TRUE)
}

#' Determine whether an ACP client object appears valid
#' @param client object to inspect
#' @return logical scalar
#' @export
acp_is_connected <- function(client) {
  inherits(client, "acp_client") && is.character(client$url) && nzchar(client$url)
}

.as_acp_client <- function(client) {
  if (!acp_is_connected(client)) {
    stop("Provide an ACP client created with acp_client().")
  }
  client
}

.acp_headers <- function(client) {
  headers <- c(`Content-Type` = "application/json")
  if (!is.null(client$token) && nzchar(as.character(client$token))) {
    headers <- c(headers, Authorization = paste("Bearer", client$token))
  }
  headers
}

.acp_post_json <- function(client, path, body) {
  client <- .as_acp_client(client)
  body <- .normalize_acp_body(body)
  resp <- httr::POST(
    paste0(client$url, path),
    body = body,
    encode = "json",
    httr::add_headers(.headers = .acp_headers(client)),
    httr::timeout(.acp_timeout_seconds())
  )
  if (httr::status_code(resp) >= 300) {
    stop("ACP error: ", httr::content(resp, as = "text", encoding = "UTF-8"))
  }
  jsonlite::fromJSON(httr::content(resp, as = "text", encoding = "UTF-8"), simplifyVector = FALSE)
}

#' Call an ACP flow endpoint
#' @param client ACP client object
#' @param flow_name flow name without the `/flows/` prefix
#' @param body request payload
#' @return parsed ACP response
#' @export
acp_call_flow <- function(client, flow_name, body = list()) {
  .acp_post_json(client, sprintf("/flows/%s", flow_name), body)
}

#' Call an ACP action endpoint
#' @param client ACP client object
#' @param action_name action name without the `/actions/` prefix
#' @param body request payload
#' @return parsed ACP response
#' @export
acp_call_action <- function(client, action_name, body = list()) {
  .acp_post_json(client, sprintf("/actions/%s", action_name), body)
}
