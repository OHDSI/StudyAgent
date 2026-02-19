read_json_ref <- function(ref) {
  if (grepl("^https?://", ref)) {
    txt <- readLines(ref, warn = FALSE)
    return(jsonlite::fromJSON(paste(txt, collapse="\n"), simplifyVector = FALSE))
  }
  jsonlite::fromJSON(ref, simplifyVector = FALSE)
}

print_findings <- function(findings) {
  if (length(findings) == 0) {
    cat("  [OK] No findings.\n"); return(invisible(NULL))
  }
  for (f in findings) {
    cat(sprintf("  - [%s][%s] %s\n",
                toupper((f$severity %||% "INFO")),
                (f$impact %||% ""),
                (f$message %||% jsonlite::toJSON(f, auto_unbox=TRUE))))
  }
}

`%||%` <- function(a,b) if (is.null(a)) b else a
