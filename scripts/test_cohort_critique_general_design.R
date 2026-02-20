### Demo: `cohort-critique-general-design` (ACP flow)

## !!!!NOTE!!!! run this from a directory above the OHDSI-Study-Agent where an .renv has the HADES packages loaded  !!!!NOTE!!!!

# Import the R thin api to the ACP server/bridge
devtools::load_all("OHDSI-Study-Agent/R/OHDSIAssistant")

# confirm the ACP server/bridge is running
OHDSIAssistant::acp_connect("http://127.0.0.1:8765")

############################################################

cohort_path <- "OHDSI-Study-Agent/demo/cohort_definition.json"
cohort <- jsonlite::fromJSON(cohort_path, simplifyVector = FALSE)

body <- list(
  cohort = cohort
)

resp <- OHDSIAssistant:::`.acp_post`("/flows/cohort_critique_general_design", body)
cat("\n== Cohort Critique (ACP flow) ==\n")
print(resp)
