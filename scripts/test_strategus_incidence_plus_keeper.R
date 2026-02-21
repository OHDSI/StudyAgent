### Demo: `phenotype_improvements` (ACP flow)

## !!!!NOTE!!!! run this from a directory above the OHDSI-Study-Agent where an .renv has the HADES packages loaded  !!!!NOTE!!!!

## !!!!NOTE!!!! `study_agent_acp` should be running under OHDSI-Study-Agent an listening on port 8765  !!!!NOTE!!!!

# Import the R thin api to the ACP server/bridge
Sys.setenv(ACP_TIMEOUT = "280")
devtools::load_all("OHDSI-Study-Agent/R/OHDSIAssistant")

# confirm the ACP server/bridge is running
OHDSIAssistant::acp_connect("http://127.0.0.1:8765")

# Uncomment to reset the state of the output folder 
# Or add `reset = TRUE ` to the function call
#unlink("OHDSI-Study-Agent/demo-strategus-cohort-incidence", recursive = TRUE, force = TRUE)

## Run an interactive agent "shell"

## First enter this study intent which does not really return relevant phenotype definitions:
## "What is the risk of GI bleed in new users of Celecoxib compared to new users of Diclofenac?"
OHDSIAssistant::runStrategusIncidenceShell(
    outputDir = "OHDSI-Study-Agent/demo-strategus-cohort-incidence"
    )


## Rerun the study agent with a study intent that does have relevant phenotype definitions:
OHDSIAssistant::runStrategusIncidenceShell(
    outputDir = "OHDSI-Study-Agent/demo-strategus-cohort-incidence",
    study_intent = "What is the risk of GI bleed in new users of tofacitinib compared to new users of ruxolitinib?"
    )
