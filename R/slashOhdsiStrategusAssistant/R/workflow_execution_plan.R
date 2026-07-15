.studyAgentSlashNewPlanStep <- function(step_id,
                                        label,
                                        script_name,
                                        stage_context_step,
                                        depends_on = character(0),
                                        produces_artifacts = character(0),
                                        review_required = FALSE) {
  list(
    step_id = as.character(step_id),
    label = as.character(label),
    script_name = as.character(script_name),
    script_path = file.path("scripts", as.character(script_name)),
    stage_context_step = as.character(stage_context_step),
    depends_on = as.list(as.character(depends_on %||% character(0))),
    produces_artifacts = as.list(as.character(produces_artifacts %||% character(0))),
    review_required = isTRUE(review_required),
    status = "not_started",
    updated_at = NULL,
    error = NULL
  )
}

.studyAgentSlashBuildIncidenceExecutionPlan <- function() {
  list(
    .studyAgentSlashNewPlanStep(
      step_id = "recommend_and_select",
      label = "Recommend and select cohorts",
      script_name = "01_recommend_and_select.R",
      stage_context_step = "target_selection",
      produces_artifacts = c("outputs/cohort_roles.json", "outputs/cohort_id_map.json")
    ),
    .studyAgentSlashNewPlanStep(
      step_id = "apply_improvements",
      label = "Apply phenotype improvements",
      script_name = "02_apply_improvements.R",
      stage_context_step = "phenotype_review",
      depends_on = "recommend_and_select",
      produces_artifacts = c("outputs/improvements_target.json", "outputs/improvements_outcome.json")
    ),
    .studyAgentSlashNewPlanStep(
      step_id = "generate_cohorts",
      label = "Generate cohort artifacts",
      script_name = "03_generate_cohorts.R",
      stage_context_step = "incidence_design_setup",
      depends_on = "recommend_and_select",
      produces_artifacts = c("selected-cohorts", "outputs/cohort_id_map.json")
    ),
    .studyAgentSlashNewPlanStep(
      step_id = "keeper_concept_sets",
      label = "Run Keeper concept-set workflow",
      script_name = "04_keeper_concept_sets.R",
      stage_context_step = "keeper_concept_set_generation",
      depends_on = "generate_cohorts",
      produces_artifacts = c("keeper-case-review/concept-sets-generated", "keeper-case-review/concept-sets-approved"),
      review_required = TRUE
    ),
    .studyAgentSlashNewPlanStep(
      step_id = "keeper_case_review",
      label = "Run Keeper case review",
      script_name = "05_keeper_case_review.R",
      stage_context_step = "keeper_case_review",
      depends_on = "keeper_concept_sets",
      produces_artifacts = c("keeper-case-review/rows", "keeper-case-review/reviews"),
      review_required = TRUE
    ),
    .studyAgentSlashNewPlanStep(
      step_id = "diagnostics",
      label = "Run diagnostics",
      script_name = "06_diagnostics.R",
      stage_context_step = "diagnostics_review",
      depends_on = "generate_cohorts",
      produces_artifacts = character(0),
      review_required = TRUE
    ),
    .studyAgentSlashNewPlanStep(
      step_id = "incidence_spec",
      label = "Run incidence specification",
      script_name = "07_incidence_spec.R",
      stage_context_step = "strategus_spec_execution",
      depends_on = "recommend_and_select",
      produces_artifacts = character(0),
      review_required = TRUE
    )
  )
}

.studyAgentSlashBuildCohortMethodsExecutionPlan <- function() {
  list(
    .studyAgentSlashNewPlanStep(
      step_id = "recommend_and_select",
      label = "Recommend and select cohorts",
      script_name = "01_recommend_and_select.R",
      stage_context_step = "target_selection",
      produces_artifacts = c("outputs/cohort_roles.json", "outputs/cohort_id_map.json")
    ),
    .studyAgentSlashNewPlanStep(
      step_id = "apply_improvements",
      label = "Apply phenotype improvements",
      script_name = "02_apply_improvements.R",
      stage_context_step = "phenotype_review",
      depends_on = "recommend_and_select",
      produces_artifacts = c("outputs/improvements_target.json", "outputs/improvements_comparator.json", "outputs/improvements_outcome.json")
    ),
    .studyAgentSlashNewPlanStep(
      step_id = "generate_cohorts",
      label = "Generate cohort artifacts",
      script_name = "03_generate_cohorts.R",
      stage_context_step = "cohort_method_spec_confirmation",
      depends_on = "recommend_and_select",
      produces_artifacts = c("selected-cohorts", "outputs/cohort_id_map.json")
    ),
    .studyAgentSlashNewPlanStep(
      step_id = "keeper_concept_sets",
      label = "Run Keeper concept-set workflow",
      script_name = "04_keeper_concept_sets.R",
      stage_context_step = "keeper_concept_set_generation",
      depends_on = "generate_cohorts",
      produces_artifacts = c("keeper-case-review/concept-sets-generated", "keeper-case-review/concept-sets-approved"),
      review_required = TRUE
    ),
    .studyAgentSlashNewPlanStep(
      step_id = "keeper_case_review",
      label = "Run Keeper case review",
      script_name = "05_keeper_case_review.R",
      stage_context_step = "keeper_case_review",
      depends_on = "keeper_concept_sets",
      produces_artifacts = c("keeper-case-review/rows", "keeper-case-review/reviews"),
      review_required = TRUE
    ),
    .studyAgentSlashNewPlanStep(
      step_id = "diagnostics",
      label = "Run diagnostics",
      script_name = "06_diagnostics.R",
      stage_context_step = "diagnostics_review",
      depends_on = "generate_cohorts",
      produces_artifacts = character(0),
      review_required = TRUE
    ),
    .studyAgentSlashNewPlanStep(
      step_id = "cm_spec",
      label = "Run cohort method specification",
      script_name = "07_cm_spec.R",
      stage_context_step = "strategus_spec_execution",
      depends_on = "recommend_and_select",
      produces_artifacts = character(0),
      review_required = TRUE
    )
  )
}
