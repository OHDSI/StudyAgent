local_concept_sets_review <- function(conceptSetRef, studyIntent="") {
  cs <- read_json_ref(conceptSetRef)
  items <- if (!is.null(cs$items)) cs$items else cs

  get_item <- function(it) {
    c <- it$concept %||% it
    list(conceptId = c$conceptId %||% c$CONCEPT_ID %||% c$id %||% NA_integer_,
         domainId  = c$domainId %||% c$DOMAIN_ID %||% NA_character_)
  }
  lst <- lapply(items, get_item)

  plan <- sprintf("Local concept set review for %s", conceptSetRef)
  findings <- list(); patches <- list(); risk_notes <- list()

  ids <- vapply(lst, function(x) x$conceptId, integer(1))
  ids <- ids[!is.na(ids)]
  if (length(lst) == 0) {
    findings <- c(findings, list(list(id="empty_concept_set", severity="high", impact="design", message="Concept set is empty.")))
  }
  if (length(ids)) {
    dups <- ids[duplicated(ids)]
    if (length(dups)) {
      findings <- c(findings, list(list(id="duplicate_concepts", severity="medium", impact="design",
                                        message=paste("Duplicate conceptIds:", paste(unique(dups), collapse=", ")))))
      patches <- c(patches, list(list(artifact=conceptSetRef, type="jsonpatch",
                                      ops=list(list(op="note", path="/items", value=list(removeDuplicatesOf=unique(dups)))))))
    }
  }
  domains <- unique(vapply(lst, function(x) x$domainId %||% NA_character_, character(1)))
  domains <- domains[!is.na(domains)]
  if (length(domains) > 1) {
    findings <- c(findings, list(list(id="mixed_domains", severity="low", impact="portability",
                                      message=paste("Multiple domains:", paste(domains, collapse=", ")))))
  }

  list(plan=plan, findings=findings, patches=patches, risk_notes=risk_notes)
}

local_cohort_critique_general <- function(cohortRef) {
  cdef <- read_json_ref(cohortRef)
  plan <- sprintf("Local general cohort design lint for %s", cohortRef)
  findings <- list(); patches <- list(); risk_notes <- list()

  pc <- cdef$PrimaryCriteria %||% list()
  wash <- pc$ObservationWindow %||% list()
  if (is.null(wash$PriorDays) || identical(wash$PriorDays, 0L)) {
    findings <- c(findings, list(list(id="missing_washout", severity="medium", impact="validity",
                                      message="No or zero-day washout; consider >=365 days.")))
    patches <- c(patches, list(list(artifact=cohortRef, type="jsonpatch",
                                    ops=list(list(op="note", path="/PrimaryCriteria/ObservationWindow",
                                                  value=list(ProposedPriorDays=365))))))
  }

  irules <- cdef$InclusionRules %||% list()
  for (i in seq_along(irules)) {
    w <- irules[[i]]$window %||% NULL
    if (!is.null(w) && !is.null(w$start) && !is.null(w$end) && w$start > w$end) {
      findings <- c(findings, list(list(id=paste0("inverted_window_", i), severity="high", impact="validity",
                                        message=sprintf("InclusionRules[%d] has inverted window.", i))))
    }
  }
  list(plan=plan, findings=findings, patches=patches, risk_notes=risk_notes)
}
