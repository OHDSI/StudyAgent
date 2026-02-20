### Demo: `phenotype_validation_review` (ACP flow)

## !!!!NOTE!!!! run this from a directory above the OHDSI-Study-Agent where an .renv has the HADES packages loaded  !!!!NOTE!!!!

# Import the R thin api to the ACP server/bridge
devtools::load_all("OHDSI-Study-Agent/R/OHDSIAssistant")

# confirm the ACP server/bridge is running
OHDSIAssistant::acp_connect("http://127.0.0.1:8765")

############################################################

keeper_row <- list(
  age = 44,
  gender = "Male",
  visitContext = "Inpatient Visit",
  presentation = "Gastrointestinal hemorrhage",
  priorDisease = "Peptic ulcer",
  symptoms = "",
  comorbidities = "",
  priorDrugs = "celecoxib",
  priorTreatmentProcedures = "",
  diagnosticProcedures = "",
  measurements = "",
  alternativeDiagnosis = "",
  afterDisease = "",
  afterDrugs = "Naproxen",
  afterTreatmentProcedures = ""
)

body <- list(
  disease_name = "Gastrointestinal bleeding",
  keeper_row = keeper_row
)

resp <- OHDSIAssistant:::`.acp_post`("/flows/phenotype_validation_review", body)
cat("\n== Phenotype Validation Review (ACP flow) ==\n")
print(resp)
