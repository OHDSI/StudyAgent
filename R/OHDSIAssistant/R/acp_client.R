#' Connect to ACP bridge
#' @param url e.g. "http://127.0.0.1:8765"
#' @param token optional bearer token
#' @return invisible TRUE
#' @export
acp_connect <- function(url = "http://127.0.0.1:8765", token = NULL) {
  if (!requireNamespace("slashOhdsiAcpClient", quietly = TRUE)) {
    stop("slashOhdsiAcpClient must be installed or loaded to use acp_connect().")
  }
  slashOhdsiAcpClient::acp_connect(url = url, token = token)
}
