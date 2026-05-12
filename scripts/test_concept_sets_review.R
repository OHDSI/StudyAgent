### Demo: `concept_sets_review` (ACP flow)

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
client <- connect_study_agent_acp()

protocol_path <- repo_file("demo", "protocol.md")
concept_set_path <- repo_file("demo", "concept_set.json")
study_intent <- paste(readLines(protocol_path, warn = FALSE), collapse = " ")

resp <- slashOhdsiAcpClient::acp_lint_concept_sets(
  client = client,
  concept_set_path = concept_set_path,
  study_intent = study_intent
)
cat("\n== Concept Sets Review (ACP flow) ==\n")
print(resp)
