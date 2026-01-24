from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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


class PhenotypeImprovementsInput(BaseModel):
    protocol_text: str
    cohorts: List[Dict[str, Any]]
    characterization_previews: List[Dict[str, Any]] = Field(default_factory=list)
    llm_result: Optional[Dict[str, Any]] = None


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
    invalid_ids_filtered: List[int] = Field(default_factory=list)


class PhenotypeImprovementsOutput(BaseModel):
    plan: str
    phenotype_improvements: List[Dict[str, Any]] = Field(default_factory=list)
    code_suggestion: Optional[str] = None
    mode: str
    invalid_targets_filtered: List[int] = Field(default_factory=list)
