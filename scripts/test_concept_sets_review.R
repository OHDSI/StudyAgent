### Demo: `concept-sets-review` (ACP flow)

## !!!!NOTE!!!! run this from a directory above the OHDSI-Study-Agent where an .renv has the HADES packages loaded  !!!!NOTE!!!!

# Import the R thin api to the ACP server/bridge
devtools::load_all("OHDSI-Study-Agent/R/OHDSIAssistant")

# confirm the ACP server/bridge is running
OHDSIAssistant::acp_connect("http://127.0.0.1:8765")

############################################################

concept_set_path <- "OHDSI-Study-Agent/demo/concept_set.json"
protocol_path <- "OHDSI-Study-Agent/demo/protocol.md"
study_intent <- paste(readLines(protocol_path, warn = FALSE), collapse = " ")
concept_set <- jsonlite::fromJSON(concept_set_path, simplifyVector = FALSE)

body <- list(
  concept_set = concept_set,
  study_intent = study_intent
)

resp <- OHDSIAssistant:::`.acp_post`("/flows/concept_sets_review", body)
cat("\n== Concept Sets Review (ACP flow) ==\n")
print(resp)
