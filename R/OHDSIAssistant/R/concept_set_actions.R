#' Propose includeDescendants patch for concept set
#' @param conceptSetRef path or URL to concept_set.json
#' @return list patch payload
proposeIncludeDescendantsPatch <- function(conceptSetRef) {
  payload <- list(
    artifactRef = conceptSetRef,
    ops = list(list(
      op = "set_include_descendants",
      where = list(domainId = "Drug", conceptClassId = "Ingredient", includeDescendants = FALSE),
      value = TRUE
    )),
    write = FALSE
  )
  if (!is.null(acp_state$url)) {
    res <- .acp_post("/actions/concept_set_edit", payload)
    if (is.null(res$ops)) res$ops <- payload$ops
    res$artifactRef <- conceptSetRef
    return(res)
  }
  res <- local_apply_concept_set_action(payload, write = FALSE)
  res$ops <- payload$ops
  res$artifactRef <- conceptSetRef
  res
}

#' Preview concept set patch
#' @param conceptSetRef path or URL
#' @param patch patch object from proposeIncludeDescendantsPatch
previewConceptSetPatch <- function(conceptSetRef, patch) {
  if (!is.null(patch$actions)) {
    prev <- applyLLMActionsConceptSet(conceptSetRef, patch$actions, preview = TRUE)
    cat(prev$plan %||% "LLM actions preview", "\n")
    if (length(prev$preview_changes) == 0) {
      cat("No matching items found.\n"); return(invisible(prev))
    }
    df <- do.call(rbind, lapply(prev$preview_changes, as.data.frame))
    print(df)
    return(invisible(prev))
  }
  if (is.null(patch$preview_changes)) {
    cat("No preview available.\n"); return(invisible(NULL))
  }
  cat(patch$plan, "\n")
  if (length(patch$preview_changes) == 0) {
    cat("No matching items found.\n"); return(invisible(NULL))
  }
  df <- do.call(rbind, lapply(patch$preview_changes, as.data.frame))
  print(df)
  invisible(df)
}

#' Apply concept set patch (writes file)
#' @param conceptSetRef path or URL
#' @param patch patch object
#' @param backup logical; if TRUE, create .bak before overwrite
#' @param outputPath optional output path
applyConceptSetPatch <- function(conceptSetRef, patch, backup = TRUE, outputPath = NULL, useActions = NULL, overwrite = TRUE) {
  # Choose mode: actions vs deterministic ops
  if (is.null(useActions)) useActions <- !is.null(patch$actions)
  if (isTRUE(useActions)) {
    res <- applyLLMActionsConceptSet(
      conceptSetRef,
      patch$actions %||% list(),
      preview = FALSE,
      overwrite = overwrite,
      backup = backup
    )
    return(invisible(res))
  }

  patch$write <- TRUE
  patch$artifactRef <- conceptSetRef
  patch$backup <- backup
  if (!is.null(outputPath)) patch$outputPath <- outputPath
  if (is.null(patch$ops)) {
    patch$ops <- list(list(
      op = "set_include_descendants",
      where = list(domainId = "Drug", conceptClassId = "Ingredient", includeDescendants = FALSE),
      value = TRUE
    ))
  }

  pre_hash <- tryCatch(tools::md5sum(conceptSetRef), error = function(e) NA_character_)
  res <- if (!is.null(acp_state$url)) {
    .acp_post("/actions/concept_set_edit", patch)
  } else {
    local_apply_concept_set_action(patch, write = TRUE)
  }
  post_hash <- tryCatch(tools::md5sum(res$written_to %||% conceptSetRef), error = function(e) NA_character_)

  outdir <- file.path(dirname(conceptSetRef), "inst", "assistant")
  if (!dir.exists(outdir)) dir.create(outdir, recursive = TRUE)
  log_entry <- list(
    plan = res$plan,
    preview_changes = res$preview_changes,
    applied = res$applied,
    written_to = res$written_to %||% conceptSetRef,
    pre_hash = unname(pre_hash),
    post_hash = unname(post_hash),
    ts = format(Sys.time(), "%Y%m%dT%H%M%S")
  )
  jsonlite::write_json(log_entry, file.path(outdir, paste0("concept_set_edit_", log_entry$ts, ".json")), auto_unbox = TRUE, pretty = TRUE)
  if (isTRUE(res$applied)) {
    cat(sprintf("Applied concept set patch to %s\n", res$written_to %||% conceptSetRef))
    if (isTRUE(backup) && !is.null(res$backup_file)) {
      cat(sprintf("Backup created at %s\n", res$backup_file))
    }
  } else {
    cat("No changes applied.\n")
  }
  invisible(res)
}


local_apply_concept_set_action <- function(payload, write = FALSE) {
  ref <- payload$artifactRef
  cs <- read_json_ref(ref)
  ops <- payload$ops %||% list()
  all_preview <- list()

  for (op in ops) {
    if (identical(op$op, "set_include_descendants")) {
      where <- op$where %||% list()
      value <- op$value %||% TRUE
      res <- local_set_include_descendants(cs, where, value)
      cs <- res$cs
      all_preview <- c(all_preview, res$preview)
    }
  }

  written_to <- NULL
  applied <- FALSE
  backup_file <- NULL
  if (isTRUE(write)) {
    target <- payload$outputPath %||% ref
    if (isTRUE(payload$backup) && file.exists(target)) {
      ts <- format(Sys.time(), "%Y%m%dT%H%M%S")
      backup_file <- paste0(target, ".bak_", ts)
      file.copy(target, backup_file, overwrite = TRUE)
    }
    jsonlite::write_json(cs, target, auto_unbox = TRUE, pretty = TRUE)
    written_to <- target
    applied <- TRUE
  }

  list(
    plan = "Set includeDescendants=true for Drug/Ingredient entries that lack it.",
    preview_changes = all_preview,
    applied = applied,
    written_to = written_to,
    backup_file = backup_file
  )
}


local_set_include_descendants <- function(cs, where, value = TRUE) {
  items <- if (!is.null(cs$items)) cs$items else cs
  preview <- list()
  for (i in seq_along(items)) {
    it <- items[[i]]
    concept <- it$concept %||% list()
    cid <- concept$conceptId %||% concept$CONCEPT_ID %||% NA_integer_
    dom <- concept$domainId %||% concept$DOMAIN_ID %||% NA_character_
    cls <- concept$conceptClassId %||% concept$CONCEPT_CLASS_ID %||% NA_character_
    inc <- it$includeDescendants %||% FALSE
    if (!is.na(where$domainId %||% NA_character_) && !identical(dom, where$domainId)) next
    if (!is.na(where$conceptClassId %||% NA_character_) && !identical(cls, where$conceptClassId)) next
    if (!is.null(where$includeDescendants) && !identical(isTRUE(inc), isTRUE(where$includeDescendants))) next
    preview <- c(preview, list(list(
      conceptId = cid,
      from = list(includeDescendants = inc),
      to = list(includeDescendants = value)
    )))
    it$includeDescendants <- isTRUE(value)
    items[[i]] <- it
  }
  if (!is.null(cs$items)) {
    cs$items <- items
  } else {
    cs <- items
  }
  list(cs = cs, preview = preview)
}
