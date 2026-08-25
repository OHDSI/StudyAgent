from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConceptSetDiffInput(BaseModel):
    concept_set: Any
    study_intent: str = ""
    llm_result: Optional[Dict[str, Any]] = None


class CohortLintInput(BaseModel):
    cohort: Dict[str, Any]
    llm_result: Optional[Dict[str, Any]] = None


class PhenotypeRecommendationsInput(BaseModel):
    protocol_text: str
    catalog_rows: List[Dict[str, Any]]
    max_results: int = 5
    llm_result: Optional[Dict[str, Any]] = None


class PhenotypeRecommendationPlanInput(BaseModel):
    study_intent: str
    catalog_rows: List[Dict[str, Any]]
    max_shortlist: int = 5
    llm_result: Optional[Dict[str, Any]] = None


class PhenotypeImprovementsInput(BaseModel):
    protocol_text: str
    cohorts: List[Dict[str, Any]]
    characterization_previews: List[Dict[str, Any]] = Field(default_factory=list)
    llm_result: Optional[Dict[str, Any]] = None


class PhenotypeRecommendationAdviceInput(BaseModel):
    study_intent: str
    llm_result: Optional[Dict[str, Any]] = None


class PhenotypeIntentSplitInput(BaseModel):
    study_intent: str
    llm_result: Optional[Dict[str, Any]] = None


class CohortMethodsIntentSplitInput(BaseModel):
    study_intent: str
    llm_result: Optional[Dict[str, Any]] = None


class WorkflowContextDialogueInput(BaseModel):
    user_prompt: str
    study_intent: str = ""
    workflow_type: str = ""
    current_step: str = ""
    current_role: str = ""
    current_context: Dict[str, Any] = Field(default_factory=dict)
    llm_result: Optional[Dict[str, Any]] = None


class PhenotypeValidationReviewInput(BaseModel):
    disease_name: str = ""
    keeper_row: Dict[str, Any] = Field(default_factory=dict)
    llm_result: Optional[Dict[str, Any]] = None


class CaseCausalReviewInput(BaseModel):
    adverse_event_name: str = ""
    case_row: Dict[str, Any] = Field(default_factory=dict)
    source_type: str = ""
    allowed_domains: List[str] = Field(default_factory=list)
    llm_result: Optional[Dict[str, Any]] = None


class CaseCausalReviewCandidate(BaseModel):
    domain: str
    label: str
    source_record_id: str
    why_it_may_contribute: str
    confidence: str
    rank: int
    candidate_role: str = ""
    evidence_basis: str = ""


KeeperConceptSetDomainKey = Literal[
    "doi",
    "alternativeDiagnosis",
    "symptoms",
    "drugs",
    "diagnosticProcedures",
    "measurements",
    "treatmentProcedures",
    "complications",
]

KeeperConceptTarget = Literal["Disease of interest", "Alternative diagnoses", "Both", "Other"]


class KeeperConceptSetItem(BaseModel):
    conceptId: int
    conceptName: str
    vocabularyId: str
    conceptSetName: KeeperConceptSetDomainKey
    target: KeeperConceptTarget
    domainId: str = ""
    conceptClassId: str = ""
    standardConcept: str = ""
    recordCount: Optional[int] = None
    score: Optional[float] = None
    sourceTerm: str = ""
    sourceStage: str = ""


class KeeperConceptSetStepDiagnostics(BaseModel):
    step: str
    count: int = 0
    details: Dict[str, Any] = Field(default_factory=dict)


class KeeperConceptSetDomainResult(BaseModel):
    domain_key: KeeperConceptSetDomainKey
    target: KeeperConceptTarget
    terms: List[str] = Field(default_factory=list)
    concepts: List[KeeperConceptSetItem] = Field(default_factory=list)
    diagnostics: List[KeeperConceptSetStepDiagnostics] = Field(default_factory=list)


class KeeperConceptSetsGenerateInput(BaseModel):
    phenotype: str
    domain_keys: List[KeeperConceptSetDomainKey] = Field(default_factory=list)
    vocab_search_provider: str = ""
    phoebe_provider: str = ""
    candidate_limit: int = 50
    min_record_count: int = 0
    include_diagnostics: bool = True


class KeeperConceptSetsGenerateOutput(BaseModel):
    phenotype: str
    concept_sets: List[KeeperConceptSetItem] = Field(default_factory=list)
    domains: List[KeeperConceptSetDomainResult] = Field(default_factory=list)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class KeeperProfileRow(BaseModel):
    phenotype: str = ""
    generatedId: str = ""
    age: Any = ""
    sex: str = ""
    gender: str = ""
    observationPeriod: str = ""
    race: str = ""
    ethnicity: str = ""
    presentation: str = ""
    visits: str = ""
    visitContext: str = ""
    symptoms: str = ""
    priorDisease: str = ""
    postDisease: str = ""
    afterDisease: str = ""
    priorDrugs: str = ""
    postDrugs: str = ""
    afterDrugs: str = ""
    priorTreatmentProcedures: str = ""
    postTreatmentProcedures: str = ""
    afterTreatmentProcedures: str = ""
    alternativeDiagnoses: str = ""
    alternativeDiagnosis: str = ""
    diagnosticProcedures: str = ""
    measurements: str = ""
    death: str = ""
    cohortPrevalence: Optional[float] = None


class KeeperProfilesGenerateInput(BaseModel):
    cohort_database_schema: str
    cohort_table: str
    cohort_definition_id: int
    cdm_database_schema: str = ""
    sample_size: int = 20
    person_ids: List[str] = Field(default_factory=list)
    keeper_concept_sets: List[KeeperConceptSetItem] = Field(default_factory=list)
    phenotype_name: str = ""
    use_descendants: bool = True
    remove_pii: bool = True


class KeeperProfilesGenerateOutput(BaseModel):
    phenotype_name: str = ""
    rows: List[KeeperProfileRow] = Field(default_factory=list)
    row_count: int = 0
    sample_size_requested: int = 0
    sample_size_returned: int = 0
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class LLMAuditRecord(BaseModel):
    flow_name: str
    tool_name: str = ""
    timestamp: str = ""
    actor_id: str = ""
    provider: str = ""
    model: str = ""
    endpoint: str = ""
    egress_mode: str = ""
    sanitization_status: str = ""
    sanitization_version: str = ""
    policy_decision: str = ""
    prompt_sha256: str = ""
    response_sha256: str = ""
    artifact_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConceptSetDiffOutput(BaseModel):
    plan: str
    findings: List[Dict[str, Any]] = Field(default_factory=list)
    patches: List[Dict[str, Any]] = Field(default_factory=list)
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    risk_notes: List[Dict[str, Any]] = Field(default_factory=list)


class CohortLintOutput(BaseModel):
    plan: str
    findings: List[Dict[str, Any]] = Field(default_factory=list)
    patches: List[Dict[str, Any]] = Field(default_factory=list)
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    risk_notes: List[Dict[str, Any]] = Field(default_factory=list)


class PhenotypeRecommendationsOutput(BaseModel):
    plan: str
    phenotype_recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    mode: str
    catalog_stats: Dict[str, Any] = Field(default_factory=dict)
    invalid_ids_filtered: List[str] = Field(default_factory=list)


class PhenotypeRecommendationPlanOutput(BaseModel):
    plan: str
    intent_facets: Dict[str, Any] = Field(default_factory=dict)
    shortlist_ids: List[str] = Field(default_factory=list)
    needs_more_search: bool = False
    reasoning_notes: List[str] = Field(default_factory=list)
    mode: str
    invalid_ids_filtered: List[str] = Field(default_factory=list)


class PhenotypeImprovementsOutput(BaseModel):
    plan: str
    phenotype_improvements: List[Dict[str, Any]] = Field(default_factory=list)
    code_suggestion: Optional[Dict[str, Any]] = None
    mode: str
    invalid_targets_filtered: List[int] = Field(default_factory=list)


class PhenotypeRecommendationAdviceOutput(BaseModel):
    plan: str
    advice: str
    next_steps: List[str] = Field(default_factory=list)
    questions: List[str] = Field(default_factory=list)
    mode: str


class PhenotypeIntentSplitOutput(BaseModel):
    plan: str
    target_statement: str
    outcome_statement: str
    rationale: str
    questions: List[str] = Field(default_factory=list)
    mode: str


class CohortMethodsIntentSplitOutput(BaseModel):
    status: Literal["ok", "needs_clarification"]
    plan: str
    target_statement: str
    comparator_statement: str
    outcome_statement: str
    outcome_statements: List[str] = Field(default_factory=list)
    rationale: str
    questions: List[str] = Field(default_factory=list)
    mode: str


class WorkflowContextDialogueArtifactRequest(BaseModel):
    artifact_id: str
    reason: str = ""
    permission_required: bool = False


class WorkflowContextDialogueOutput(BaseModel):
    plan: str
    answer: str
    current_step_guidance: List[str] = Field(default_factory=list)
    cautions: List[str] = Field(default_factory=list)
    suggested_next_actions: List[str] = Field(default_factory=list)
    follow_up_plan: List[str] = Field(default_factory=list)
    artifact_requests: List[WorkflowContextDialogueArtifactRequest] = Field(default_factory=list)
    mode: str


class PhenotypeValidationReviewOutput(BaseModel):
    label: str
    rationale: str
    mode: str


class CaseCausalReviewOutput(BaseModel):
    flow_name: str
    mode: str
    candidates_by_domain: Dict[str, List[CaseCausalReviewCandidate]] = Field(default_factory=dict)
    narrative: str
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class CohortMethodSpecsRecommendationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analytic_settings_description: str
    study_intent: Optional[str] = ""
    study_description: Optional[str] = None
    llm_result: Optional[Dict[str, Any]] = None


CohortMethodSpecsStatus = Literal["ok", "llm_parse_error", "schema_validation_error"]


class CohortMethodSpecsRecommendationOutput(BaseModel):
    status: CohortMethodSpecsStatus
    recommendation: Dict[str, Any] = Field(default_factory=dict)
    cohort_methods_specifications: Optional[Dict[str, Any]] = None
    section_rationales: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class LLMAuditEnvelope(BaseModel):
    records: List[LLMAuditRecord] = Field(default_factory=list)

ConceptReviewMode = Literal["required", "propose", "provided_only"]


class PhenotypePriorObservationScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    days: int = Field(ge=0)


class PhenotypeFixedExitScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["fixed"]
    index: Literal["startDate", "endDate"] = "endDate"
    offset_days: int = 0


class PhenotypeTemporalFollowupScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index_concept_set: str = ""
    trigger_concept_set: str = ""
    followup_days: int = Field(default=30, ge=0)
    washout_days: int = Field(default=365, ge=1)


class PhenotypeMakeComputableScope(BaseModel):
    """Declared v1 scope surface accepted by the computable phenotype flow."""

    model_config = ConfigDict(extra="forbid")

    index_event: Optional[str] = None
    criterion_domains: Dict[str, str] = Field(default_factory=dict)
    entry_limit: Optional[Literal["First", "All"]] = None
    prior_observation: Optional[int | PhenotypePriorObservationScope] = None
    index_day_boundary: Optional[Literal["included", "excluded"]] = None
    windows: Optional[Literal["none"] | Dict[str, Any] | List[Any]] = None
    exit_strategy: Optional[Literal["observation", "end_of_observation"] | PhenotypeFixedExitScope] = None
    era_days: int = Field(default=0, ge=0)
    visit_overlap: bool = False
    visit_overlap_mode: Optional[Literal["entry", "attrition"]] = None
    temporal_followup: Optional[PhenotypeTemporalFollowupScope] = None
    multi_domain_entry_policy: Optional[Literal["diagnosis_only", "any_qualifying_domain", "supporting_evidence_only"]] = None


class PhenotypeReviewedConceptItem(BaseModel):
    """One user-reviewed vocabulary item and its inclusion policy."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    concept_id: int = Field(alias="conceptId")
    domain: Optional[str] = Field(default=None, alias="domainId")
    include_descendants: bool = Field(default=False, alias="includeDescendants")
    include_mapped: bool = Field(default=False, alias="includeMapped")
    is_excluded: bool = Field(default=False, alias="isExcluded")


class PhenotypeReviewedConceptSet(BaseModel):
    """A reviewed set represented by policy-bearing items or direct concept IDs."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = ""
    domain: Optional[str] = Field(default=None, alias="domainId")
    items: List[PhenotypeReviewedConceptItem] = Field(default_factory=list)
    concept_ids: List[int] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_ohdsi_aliases(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        if "concepts" in normalized and "items" not in normalized:
            normalized["items"] = normalized.pop("concepts")
        if "conceptIds" in normalized and "concept_ids" not in normalized:
            normalized["concept_ids"] = normalized.pop("conceptIds")
        return normalized

    @model_validator(mode="after")
    def require_one_concept_representation(self) -> "PhenotypeReviewedConceptSet":
        if bool(self.items) == bool(self.concept_ids):
            raise ValueError("concept_set_requires_exactly_one_of_items_or_concept_ids")
        return self


class PhenotypeMakeComputableProposalPlan(BaseModel):
    """Machine-checkable plan returned by proposal mode before human review."""

    model_config = ConfigDict(extra="forbid")

    mode: Optional[Literal["condition_entry", "visit_overlap", "temporal_followup", "mixed_domain_clarification"]] = None
    entry_limit: Optional[Literal["First", "All"]] = None
    prior_observation_days: Optional[int] = Field(default=None, ge=0)
    exit_strategy: Optional[Literal["observation", "end_of_observation"] | PhenotypeFixedExitScope] = None
    era_days: Optional[int] = Field(default=None, ge=0)
    visit_overlap_mode: Optional[Literal["entry", "attrition"]] = None
    temporal_followup: Optional[PhenotypeTemporalFollowupScope] = None
    multi_domain_entry_policy: Optional[Literal["diagnosis_only", "any_qualifying_domain", "supporting_evidence_only"]] = None


class PhenotypeMakeComputableProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "needs_clarification", "not_expressible"]
    scope_check: Dict[str, Any]
    concept_sets: List[PhenotypeReviewedConceptSet] = Field(default_factory=list)
    cohort_plan: PhenotypeMakeComputableProposalPlan
    assumptions: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class PhenotypeMakeComputableInput(BaseModel):
    """Stateless direct-narrative request for a computable cohort definition."""

    model_config = ConfigDict(extra="forbid")

    narrative_statement: str
    confirmed_scope: bool = False
    scope: PhenotypeMakeComputableScope = Field(default_factory=PhenotypeMakeComputableScope)
    concept_review_mode: ConceptReviewMode = "required"
    concept_sets: List[PhenotypeReviewedConceptSet] = Field(default_factory=list)
