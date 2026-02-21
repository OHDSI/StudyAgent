### Demo: `phenotype_improvements` (ACP flow)

## !!!!NOTE!!!! run this from a directory above the OHDSI-Study-Agent where an .renv has the HADES packages loaded  !!!!NOTE!!!!

## !!!!NOTE!!!! `study_agent_acp` should be running under OHDSI-Study-Agent an listening on port 8765  !!!!NOTE!!!!

# Import the R thin api to the ACP server/bridge
Sys.setenv(ACP_TIMEOUT = "280")
devtools::load_all("OHDSI-Study-Agent/R/OHDSIAssistant")

# confirm the ACP server/bridge is running
OHDSIAssistant::acp_connect("http://127.0.0.1:8765")

OHDSIAssistant::runStrategusIncidenceShell(
    outputDir = "OHDSI-Study-Agent/demo-strategus-cohort-incidence",
    studyIntent = "What is the risk of GI bleed in new users of Celecoxib compared to new users of Diclofenac?"
  )
