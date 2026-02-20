### Demo: `phenotype_improvements` (ACP flow)

## !!!!NOTE!!!! run this from a directory above the OHDSI-Study-Agent where an .renv has the HADES packages loaded  !!!!NOTE!!!!

# Import the R thin api to the ACP server/bridge
devtools::load_all("OHDSI-Study-Agent/R/OHDSIAssistant")

# confirm the ACP server/bridge is running
OHDSIAssistant::acp_connect("http://127.0.0.1:8765")

############################################################

protocol_path <- "OHDSI-Study-Agent/demo/protocol.md"
cohort_path <- "OHDSI-Study-Agent/demo/1197_Acute_gastrointestinal_bleeding.json"

protocol_text <- paste(readLines(protocol_path, warn = FALSE), collapse = "\n")
cohort <- jsonlite::fromJSON(cohort_path, simplifyVector = FALSE)

body <- list(
  protocol_text = protocol_text,
  cohorts = list(cohort)
)

resp <- OHDSIAssistant:::`.acp_post`("/flows/phenotype_improvements", body)
cat("\n== Phenotype Improvements (ACP flow) ==\n")
print(resp)
