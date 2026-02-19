### Demo: apply LLM-proposed actions for the tools we are prototyping:
## - Lint tools
## -- `concept-sets-review`
## -- `cohort-critique-general-design`

## - Study artifact selection/improvement
## -- `phenotype_recommendations`
## -- `phenotype_improvements`

## NOTE: running from a directory above the AgenticStudyAssistant so that we can reuse the .renv

# Import the R thin api to the ACP server/bridge
devtools::load_all("OHDSI-Study-Agent/R/OHDSIAssistant") # was under AgenticStudyAssistant/

# confirm the ACP server/bridge is running
OHDSIAssistant::acp_connect("http://127.0.0.1:7777")

############################################################
## Test: -- `concept-sets-review`
 this concept set has no descendant concepts specified
concept_set_ref <- "demo/concept_set.json"  # This path is relative to the ACP server's base folder
                                        
# Ask tool for findings and actions
resp <- OHDSIAssistant:::`.acp_post`("/tools/propose_concept_set_diff", list(
  conceptSetRef = concept_set_ref,
  studyIntent   = paste(readLines("./OHDSI-Study-Agent/demo/protocol.md", warn = FALSE), collapse = " ") # this path is relative the start of the R session
))
actions <- resp$actions
cat("LLM actions:\n");
print(actions)

# Preview execution of actions
prev <- OHDSIAssistant::applyLLMActionsConceptSet(concept_set_ref, actions, preview = TRUE)
cat("LLM preview counts:\n"); print(prev$counts)
cat("Preview rows (first few):\n"); print(head(prev$preview_changes))

## Apply (writes new file if overwrite = FALSE) Note: this is an
## overite fix and so you will need to replace the concept_set.json
## with concept_set.json-no-descendants to rerun this test
applied <- OHDSIAssistant::applyLLMActionsConceptSet(concept_set_ref, actions, preview = FALSE, overwrite = FALSE, backup = TRUE)
cat("LLM applied written_to:\n"); print(applied$written_to)

############################################################

## -- `cohort-critique-general-design` (LLM-backed cohort lint demo)
cohort_ref <- "OHDSI-Study-Agent/demo/cohort_definition.json"
cohort_body <- list(cohortRef = cohort_ref)
cohort_resp <- OHDSIAssistant:::`.acp_post`("/tools/cohort_lint", cohort_body)
cat("\n== Cohort Critique (general design) ==\n")
cat(cohort_resp$plan, "\n")
if (length(cohort_resp$findings)) {
  print(cohort_resp$findings)
} else {
  cat("No findings returned.\n")
}
### Output from a prior run
## == Cohort Critique (general design) ==
## > Review cohort JSON for general design issues (washout/time-at-risk, inverted windows, empty or conflicting criteria). 
## > . + > [[1]]
## [[1]]$evidence
## [[1]]$evidence[[1]]
## [[1]]$evidence[[1]]$note
## [1] "The current `PriorDays` is not specified, potentially leading to inclusion of patients with recent, irrelevant exposures."

## [[1]]$evidence[[1]]$ref
## [1] "/PrimaryCriteria/ObservationWindow.PriorDays"

## [[1]]$id
## [1] "missing_washout"

## [[1]]$impact
## [1] "validity"

## [[1]]$message
## [1] "Consider adding a washout period to the `ObservationWindow` to account for prior exposure. A typical washout period is 365 days."

## [[1]]$severity
## [1] "medium"

## [[2]]
## [[2]]$evidence
## [[2]]$evidence[[1]]
## [[2]]$evidence[[1]]$note
## [1] "Lack of an explicitly stated time-at-risk might lead to inconsistent interpretation and application of the cohort criteria."

## [[2]]$evidence[[1]]$ref
## [1] "/PrimaryCriteria"

## [[2]]$id
## [1] "unclear_time_at_risk"

## [[2]]$impact
## [1] "validity"

## [[2]]$message
## [1] "The definition of 'time at risk' is not explicit. Consider explicitly defining this within the cohort criteria to ensure clarity and consistency in patient selection."

## [[2]]$severity
## [1] "low"


if (length(cohort_resp$patches)) {
  cat("Suggested patches:\n"); print(cohort_resp$patches)
}
## Suggested patches:
## [[1]]
## [[1]]$artifact
## [1] "cohort_definition.json"

## [[1]]$ops
## [[1]]$ops[[1]]
## [[1]]$ops[[1]]$op
## [1] "note"

## [[1]]$ops[[1]]$path
## [1] "/PrimaryCriteria/ObservationWindow.PriorDays"

## [[1]]$ops[[1]]$value
## [[1]]$ops[[1]]$value$details
## [1] "To account for prior exposure, add a `PriorDays` value to the `ObservationWindow`. A typical washout period is 365 days. This can help ensure that only patients with a relevant history are included."

## [[1]]$ops[[1]]$value$summary
## [1] "Add a washout period"

## [[1]]$type
## [1] "jsonpatch"


if (length(cohort_resp$actions)) {
  cat("Actions (if any):\n"); print(cohort_resp$actions)
}
## None at this time

############################################################

## -- `phenotype_recommendations`
protocol <- "OHDSI-Study-Agent/demo/protocol.md"
catalog  <- "OHDSI-Study-Agent/demo/Cohorts.csv"
study_dir <- "OHDSI-Study-Agent/demo"

rec <- OHDSIAssistant::suggestPhenotypes(protocol, catalog, maxResults = 10, interactive = TRUE)
ids <- OHDSIAssistant::selectPhenotypeRecommendations(rec$phenotype_recommendations, select = NULL, interactive = interactive())
# this will write the JSON for the selected cohort definitions to a folder

## -- `phenotype_improvements` - depends on ids having been chosen above
if (length(ids)) {
  paths <- OHDSIAssistant::pullPhenotypeDefinitions(ids, outputDir = study_dir, overwrite = FALSE)
  OHDSIAssistant::reviewPhenotypes(protocol, paths, interactive = TRUE)
  # To persist improvement notes next to the cohort JSONs, set apply=TRUE:
  # OHDSIAssistant::reviewPhenotypes(protocol, paths, interactive = TRUE, apply = TRUE, select = "all")
} else {
  cat("No phenotype recommendations returned (likely stub mode).\n")
}

