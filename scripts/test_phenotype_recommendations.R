### Demo:  `phenotype_recommendations`

## !!!!NOTE!!!! run this from a directory above the OHDSI-Study-Agent where an .renv has the HADES packages loaded  !!!!NOTE!!!! 

# Import the R thin api to the ACP server/bridge
devtools::load_all("OHDSI-Study-Agent/R/OHDSIAssistant")

# confirm the ACP server/bridge is running
OHDSIAssistant::acp_connect("http://127.0.0.1:8765")


############################################################

## -- `phenotype_recommendations` (ACP flow)
protocol <- "OHDSI-Study-Agent/demo/protocol.md"
study_dir <- "OHDSI-Study-Agent/demo"

rec <- OHDSIAssistant::suggestPhenotypes(protocolPath = protocol, maxResults = 10, candidateLimit = 10, interactive = TRUE)
core <- rec$recommendations %||% rec
ids <- OHDSIAssistant::selectPhenotypeRecommendations(core$phenotype_recommendations, select = NULL, interactive = interactive())
# this will write the JSON for the selected cohort definitions to a folder

## -- `phenotype_improvements` - depends on ids having been chosen above
if (length(ids)) {
    paths <- OHDSIAssistant::pullPhenotypeDefinitions(ids, outputDir = study_dir, overwrite = TRUE)
} 

if (length(paths)) {
  OHDSIAssistant::reviewPhenotypes(protocol, paths, interactive = TRUE)
  # To persist improvement notes next to the cohort JSONs, set apply=TRUE:
  # OHDSIAssistant::reviewPhenotypes(protocol, paths, interactive = TRUE, apply = TRUE, select = "all")
} 
