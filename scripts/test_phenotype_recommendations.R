### Demo: `phenotype_recommendation` plus follow-up improvements

## Run this from the repo root with ACP listening on `http://127.0.0.1:8765`.

script_dir <- local({
  cmd_args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", cmd_args, value = TRUE)
  if (length(file_arg) > 0) {
    return(dirname(normalizePath(sub("^--file=", "", file_arg[[1]]), winslash = "/", mustWork = FALSE)))
  }
  frame_files <- Filter(Negate(is.null), lapply(sys.frames(), function(x) x$ofile))
  if (length(frame_files) > 0) {
    return(dirname(normalizePath(frame_files[[length(frame_files)]], winslash = "/", mustWork = FALSE)))
  }
  normalizePath("scripts", winslash = "/", mustWork = FALSE)
})

source(file.path(script_dir, "demo_setup.R"))
repo_root <- set_study_agent_repo_root(start = dirname(script_dir))
load_study_agent_r_packages(include_strategus = FALSE)
invisible(connect_study_agent_acp())

Sys.setenv(PHENOTYPE_INDEX_DIR = repo_file("data", "phenotype_index_cipher_omop"))

protocol <- repo_file("demo", "protocol.md")
study_dir <- repo_file("demo")

rec <- slashOhdsiAcpClient::suggestPhenotypes(
  protocolPath = protocol,
  maxResults = 10,
  candidateLimit = 20,
  interactive = TRUE
)

core <- if (!is.null(rec$recommendations)) rec$recommendations else rec
ids <- slashOhdsiAcpClient::selectPhenotypeRecommendations(
  core$phenotype_recommendations,
  select = NULL,
  interactive = interactive()
)

paths <- character(0)
if (length(ids)) {
  paths <- slashOhdsiAcpClient::pullPhenotypeDefinitions(
    ids,
    outputDir = study_dir,
    overwrite = TRUE
  )
}

if (length(paths)) {
  slashOhdsiAcpClient::reviewPhenotypes(protocol, paths, interactive = TRUE)
  # To persist improvement notes next to the cohort JSONs, set apply = TRUE:
  # slashOhdsiAcpClient::reviewPhenotypes(protocol, paths, interactive = TRUE, apply = TRUE, select = "all")
}
