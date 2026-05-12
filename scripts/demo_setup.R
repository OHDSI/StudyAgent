### Shared setup helpers for manual R demos under `scripts/`

locate_study_agent_repo_root <- function(start = getwd()) {
  start <- normalizePath(start, winslash = "/", mustWork = FALSE)
  parent <- dirname(start)
  candidates <- unique(c(
    start,
    parent,
    list.dirs(start, recursive = FALSE, full.names = TRUE),
    list.dirs(parent, recursive = FALSE, full.names = TRUE)
  ))

  for (candidate in candidates) {
    if (
      dir.exists(file.path(candidate, "R", "slashOhdsiAcpClient")) &&
      dir.exists(file.path(candidate, "R", "slashOhdsiStrategusAssistant")) &&
      dir.exists(file.path(candidate, "scripts"))
    ) {
      return(normalizePath(candidate, winslash = "/", mustWork = TRUE))
    }
  }

  stop("Could not locate the StudyAgent repo root. Run this script from the repo root or invoke it by path.")
}

set_study_agent_repo_root <- function(start = getwd()) {
  root <- locate_study_agent_repo_root(start = start)
  options(study_agent.repo_root = root)
  root
}

study_agent_repo_root <- function() {
  root <- getOption("study_agent.repo_root", NULL)
  if (is.null(root) || !dir.exists(root)) {
    root <- set_study_agent_repo_root()
  }
  root
}

repo_file <- function(...) {
  file.path(study_agent_repo_root(), ...)
}

load_study_agent_package <- function(package_name, quiet = TRUE) {
  package_dir <- repo_file("R", package_name)
  if (requireNamespace("devtools", quietly = TRUE)) {
    devtools::load_all(package_dir, quiet = quiet)
    return(invisible(TRUE))
  }
  if (!requireNamespace(package_name, quietly = TRUE)) {
    stop(sprintf(
      "Package '%s' is not installed and devtools is unavailable to load '%s'.",
      package_name,
      package_dir
    ))
  }
  invisible(TRUE)
}

load_study_agent_r_packages <- function(include_strategus = FALSE, quiet = TRUE) {
  load_study_agent_package("slashOhdsiAcpClient", quiet = quiet)
  if (isTRUE(include_strategus)) {
    load_study_agent_package("slashOhdsiStrategusAssistant", quiet = quiet)
  }
  invisible(TRUE)
}

connect_study_agent_acp <- function(acp_url = Sys.getenv("ACP_URL", "http://127.0.0.1:8765")) {
  acp_url <- trimws(as.character(if (is.null(acp_url)) "" else acp_url))
  if (!nzchar(acp_url)) stop("Set ACP_URL or pass a non-empty ACP URL.")
  slashOhdsiAcpClient::acp_connect(acp_url)
  slashOhdsiAcpClient::acp_get_default_client()
}

reset_demo_output_dir <- function(path, prompt = interactive(), default = FALSE) {
  path <- normalizePath(path, winslash = "/", mustWork = FALSE)
  if (!dir.exists(path)) return(invisible(FALSE))
  if (isTRUE(prompt)) {
    suffix <- if (isTRUE(default)) "[Y/n]" else "[y/N]"
    answer <- tolower(trimws(readline(sprintf("Delete existing output directory '%s'? %s ", path, suffix))))
    confirmed <- if (!nzchar(answer)) isTRUE(default) else answer %in% c("y", "yes")
    if (!confirmed) return(invisible(FALSE))
  }
  unlink(path, recursive = TRUE, force = TRUE)
  invisible(TRUE)
}
