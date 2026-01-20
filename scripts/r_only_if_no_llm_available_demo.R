# Run after starting the ACP bridge:
# source("scripts/r_demo_commands.R")

devtools::load_all("./AgenticStudyAssistant/R/OHDSIAssistant")  # or build & install
OHDSIAssistant::acp_connect("http://127.0.0.1:7777")

res <- OHDSIAssistant::lintStudyDesign(
  studyProtocol = "demo/protocol.md",
  studyPackage  = "demo",
  lintTasks     = c("concept-sets-review","cohort-critique-general-design"),
  apply         = FALSE,
  interactive   = TRUE
)
str(res, max.level = 2)

patch <- OHDSIAssistant::proposeIncludeDescendantsPatch("demo/concept_set.json")
OHDSIAssistant::previewConceptSetPatch("demo/concept_set.json", patch)
OHDSIAssistant::applyConceptSetPatch("demo/concept_set.json", patch, backup = TRUE)
