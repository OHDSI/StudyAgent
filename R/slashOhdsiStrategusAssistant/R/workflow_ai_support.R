#' Resolve optional AI/ACP support for a Strategus workflow
#'
#' `disabled` is intentionally the default: it makes the workflow a local,
#' deterministic wizard and guarantees that it will not create an ACP client
#' or make an ACP request. `enabled` requires the optional ACP client package;
#' `auto` uses ACP when the client package is installed and otherwise behaves as
#' the local wizard.
#'
#' @param aiSupport one of `disabled`, `enabled`, or `auto`
#' @return a list describing the resolved support policy
.studyAgentSlashResolveAiSupport <- function(aiSupport = c("disabled", "enabled", "auto")) {
  if (is.null(aiSupport)) aiSupport <- "disabled"
  requested <- match.arg(as.character(aiSupport), c("disabled", "enabled", "auto"))
  client_installed <- requireNamespace("slashOhdsiAcpClient", quietly = TRUE)
  if (identical(requested, "enabled") && !client_installed) {
    stop(
      "aiSupport='enabled' requires the optional slashOhdsiAcpClient package. ",
      "Install it or use aiSupport='disabled' for the local workflow wizard."
    )
  }
  list(
    requested = requested,
    enabled = !identical(requested, "disabled") && client_installed,
    client_installed = client_installed,
    mode = if (identical(requested, "auto") && !client_installed) "disabled" else requested,
    reason = if (identical(requested, "disabled")) "disabled_by_user" else if (!client_installed) "optional_acp_client_not_installed" else "enabled"
  )
}

.studyAgentSlashAiSupportAllowsAcp <- function(policy) {
  isTRUE(policy$enabled)
}

.studyAgentSlashAiSupportDisabledMessage <- function(policy, capability = "AI support") {
  sprintf(
    "%s is unavailable because aiSupport is %s (%s).",
    capability,
    as.character(policy$mode %||% "disabled"),
    as.character(policy$reason %||% "disabled_by_user")
  )
}
