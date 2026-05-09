# Phenotype Metadata Mapping: OHDSI Cohorts + VA CIPHER

This note compares the current OHDSI Phenotype Library metadata source in `data/Cohorts.csv` with the sample VA CIPHER phenotype JSON records in `data/cipher-phenotypes/`.

The purpose of the index is not only phenotype search. The more important use case is phenotype recommendation in support of cohort generation within the OHDSI study workflow, typically in Atlas or R Hades. That changes the design: the index must capture both topical relevance and how directly a phenotype can be turned into an OHDSI-executable cohort.

## Inputs Reviewed

- `data/Cohorts.csv`
- `data/phenotype_index/catalog.jsonl`
- `mcp_server/scripts/build_phenotype_index.py`
- Sample CIPHER JSON files in `data/cipher-phenotypes/`
- `data/cipher-phenotypes/enumType 1.json`
- `data/cipher-phenotypes/cipher-disease-phenotype-summary.xlsx`

## Revised Design Goal

The shared phenotype index should support three related tasks:

- finding relevant phenotype definitions
- recommending phenotype definitions that are useful starting points for a study design
- preparing accepted recommendations for downstream translation into an OHDSI cohort definition

This means the index should model both:

- `clinical_relevance`: what condition, phenotype, or detection strategy the record represents
- `execution_readiness`: how directly the record can help produce an OHDSI cohort definition

## Current OHDSI Index Shape

The current index builder emits compact rows with this shape:

- `cohortId`
- `name`
- `short_description`
- `tags`
- `ontology_keys`
- `signals`
- `logic_features`
- `pop_keywords`
- `source_meta`

This works for OHDSI because `Cohorts.csv` is already flattened and heavily oriented around cohort logic features such as:

- inclusion rule counts
- concept set counts
- entry-event domains
- status, librarian, dates
- hashtag tags
- recommended concept ids

## CIPHER Structure

Each sample CIPHER phenotype record has a stable two-level structure.

Top level:

- `id`
- `fullName`
- `description`
- `created`
- `lastModified`
- `revision`
- `majorRevision`
- `versionInfo`
- `uqid`
- `vaDeveloped`
- `phenotypeStatusId`
- `categoryTypeId`
- `dbType`
- `phenotypeCategory`
- `sources`
- `roleAnalyses`
- `dataClassifications`
- `keywords`
- `publications`
- `toolLinks`
- `algorithm`

Nested `algorithm` block:

- `algorithmDesc`
- `populationDesc`
- `validated`
- `validationDescription`
- `adjudicationPerformed`
- `adjudicationMethod`
- `adjudicationLevelType`
- `authors`
- `contacts`
- `relatedDiseases`
- `methodsUsed`
- `validations`
- `assocCodes`
- `contextDevs`
- `labSpecimen`
- `labUnits`
- `algorithmCreated`
- `dataUsedStart`
- `dataUsedEnd`
- `publicationAcknowledgement`

## Important Differences

OHDSI and CIPHER differ in where their recommendation value lives:

- OHDSI stores useful retrieval features in flattened cohort-logic columns and executable cohort definitions.
- CIPHER stores useful retrieval features in narrative algorithm text, keyword lists, source lists, validation fields, and associated code systems.
- Most CIPHER records in the provided sample do not contain executable OHDSI logic.

Practical consequence:

- OHDSI is stronger on immediate cohort adaptation.
- CIPHER is stronger on disease relevance, provenance, validation context, and code evidence.
- CIPHER recommendations often need a second step that translates narrative and code evidence into an OHDSI cohort definition.

That means a shared index should not force both sources into the same narrow `logic_features` mold, and it should not treat all recommended phenotypes as equally executable.

## Proposed Shared Metadata Model

Use a source-agnostic phenotype document with a stable core plus source-specific extensions.

### Core Fields

- `phenotype_id`
- `source_dataset`
- `source_record_type`
- `name`
- `short_description`
- `long_description`
- `tags`
- `keywords`
- `signals`
- `ontology_keys`
- `code_systems`
- `concept_evidence`
- `validation_features`
- `population_features`
- `provenance`
- `retrieval_text`
- `source_meta`
- `source_payload_ref`

### Execution-Oriented Fields

- `executable_definition_status`
- `executable_definition_source`
- `execution_readiness_score`
- `adaptation_notes`
- `translation_inputs`

### Recommended Meanings

- `phenotype_id`: Canonical string id, namespaced by source, such as `ohdsi:3` or `cipher:16285`.
- `source_dataset`: `ohdsi_phenotype_library` or `va_cipher`.
- `source_record_type`: `cohort_definition` or `disease_phenotype`.
- `name`: Display name.
- `short_description`: One-sentence summary used in results lists.
- `long_description`: Rich narrative text for ranking and recommendation context.
- `tags`: User-facing labels for faceting and retrieval.
- `keywords`: Expanded search terms from names, tags, keywords, disease labels, authors, source labels, code-system labels.
- `signals`: Compact flags such as status, validated, va-developed, reference, has-publication, has-tool-link.
- `ontology_keys`: Numeric or string identifiers from concept systems when available.
- `code_systems`: Normalized summary of coded algorithm content.
- `concept_evidence`: Compact representation of code-derived evidence that may later be enriched through vocabulary or PHOEBE tools.
- `validation_features`: Structured summary of validation and adjudication signals.
- `population_features`: Structured summary of study population or cohort target information.
- `provenance`: Source and authorship metadata useful for ranking and display.
- `retrieval_text`: Explicit text blob used for sparse and dense indexing.
- `source_meta`: Raw-ish compact metadata for debugging and UI.
- `source_payload_ref`: Path or id pointing back to the original source definition.
- `executable_definition_status`: `native_ohdsi`, `non_ohdsi_logic_only`, `codes_only`, `narrative_only`, or `unknown`.
- `executable_definition_source`: where the executable or semi-executable logic came from, such as `ohdsi_library`, `cipher_json`, or `external_reference`.
- `execution_readiness_score`: coarse ranking signal for recommendation and UI prioritization.
- `adaptation_notes`: short explanation of what still needs to be done before OHDSI execution.
- `translation_inputs`: compact payload intended for a future ACP flow that translates accepted phenotype recommendations into OHDSI cohort candidates.

## Mapping: OHDSI -> Shared Model

- `cohortId` -> `phenotype_id` as `ohdsi:{cohortId}`
- literal source -> `source_dataset=ohdsi_phenotype_library`
- literal type -> `source_record_type=cohort_definition`
- `cohortName` / `cohortNameLong` / `cohortNameFormatted` -> `name`
- `logicDescription` or `notes` -> `short_description`
- `logicDescription`, `notes`, definition JSON description if present -> `long_description`
- `hashTag` -> `tags`
- tokenized `name` + description + tags -> `keywords`
- `recommendedReferentConceptIds` -> `ontology_keys`
- current status/reference/washout booleans -> `signals`
- inclusion/domain/count fields -> `population_features.logic_features`
- librarian/dates/version fields -> `provenance` and `source_meta`
- executable cohort JSON presence -> `executable_definition_status=native_ohdsi`
- OHDSI cohort JSON -> `executable_definition_source=ohdsi_library`
- cohort JSON path, logic summary, domains, referent concepts -> `translation_inputs`

## Mapping: CIPHER -> Shared Model

- `id` -> `phenotype_id` as `cipher:{id}`
- literal source -> `source_dataset=va_cipher`
- literal type -> `source_record_type=disease_phenotype`
- `fullName` -> `name`
- `description` if present else `algorithm.algorithmDesc` -> `short_description`
- concatenate `description`, `algorithm.algorithmDesc`, `algorithm.populationDesc`, `validationDescription`, publication acknowledgement -> `long_description`
- `keywords[*].keyword`, `phenotypeCategory`, inferred source labels, code-system labels -> `tags` and `keywords`
- `algorithm.relatedDiseases[*].relatedDiseaseId` -> provisional `ontology_keys` only after enum expansion; otherwise keep outside `ontology_keys`
- `vaDeveloped`, `phenotypeStatusId`, `majorRevision`, `validated`, publication presence, tool-link presence -> `signals`
- `algorithm.populationDesc`, `contextDevs`, `dataUsedStart`, `dataUsedEnd` -> `population_features`
- `algorithm.validated`, `validationDescription`, `adjudicationPerformed`, `adjudicationMethod`, `adjudicationLevelType`, `validations` -> `validation_features`
- `sources`, `authors`, `contacts`, `publications`, `versionInfo`, `revision`, `created`, `lastModified`, `uqid` -> `provenance` and `source_meta`
- `algorithm.assocCodes` -> `code_systems`
- raw JSON path -> `source_payload_ref`
- default executable status for most records -> `codes_only` or `narrative_only`
- future true logical algorithm if present -> `non_ohdsi_logic_only`
- disease summary, algorithm narrative, code evidence, validation, and provenance -> `translation_inputs`

## Execution Readiness

The recommendation system should distinguish “good conceptual match” from “good starting point for Atlas/Hades implementation.”

Recommended values for `executable_definition_status`:

- `native_ohdsi`: already represented as an OHDSI cohort definition
- `non_ohdsi_logic_only`: contains a logical algorithm, but not in OHDSI-executable form
- `codes_only`: primarily useful because of code evidence
- `narrative_only`: primarily useful because of descriptive or methodological text
- `unknown`: unresolved

Recommended ranking behavior:

- do not suppress CIPHER phenotypes just because they are less executable
- do boost OHDSI phenotypes when user intent strongly implies immediate Atlas/Hades adaptation
- do surface execution status and adaptation notes in recommendation output

Typical `adaptation_notes` examples:

- `Native OHDSI cohort likely requires parameter or concept-set adjustment for local study intent.`
- `CIPHER phenotype provides code evidence and narrative but requires translation into OHDSI cohort entry, exit, and era logic.`
- `Phenotype appears derived from PheCode/MAP methodology and may need concept expansion and validation against available OMOP domains.`

## Translation Inputs

`translation_inputs` should be designed now as the future handoff payload for the ACP flow that converts an accepted recommendation into an OHDSI-oriented cohort draft.

Recommended content for OHDSI records:

- cohort id
- cohort JSON path
- logic description
- referent concept ids
- domain features
- inclusion rule counts
- concept set counts

Recommended content for CIPHER records:

- phenotype id and JSON path
- phenotype name
- disease summary
- algorithm narrative
- population description
- validation description
- code systems and codes
- source family labels
- publication links
- tool links
- source provenance
- code-generation method notes if present

## Normalized `code_systems` Shape

This is the most important CIPHER addition for retrieval, recommendation, and later translation.

Recommended shape:

```json
[
  {
    "system_id": 460,
    "system_name": "ICD-9 Diagnostic Codes",
    "subsystem_id": null,
    "subsystem_name": null,
    "codes": ["309.81"],
    "description": null,
    "va_specific": false
  }
]
```

For the sample, `enumType 1.json` is enough to map at least the associated code systems. Examples already present in the sample:

- `460` -> `ICD-9 Diagnostic Codes`
- `461` -> `ICD-10 Diagnostic Codes`
- `466` -> `Medications`
- `468` -> `Text snippets`
- `469` -> `SNOMED CT, US Edition`
- `519` -> `Other`
- nested `682` -> `Drug class`
- nested `785` appears in sample data but is not defined in `enumType 1.json`; this needs an additional enum source

Recommendation:

- keep both numeric ids and resolved labels
- flatten actual code strings into retrieval text
- add code-system labels into keywords
- preserve `va_specific` for downstream filtering

## Proposed `concept_evidence`

This field is intended to preserve code-derived evidence without turning the phenotype index into a full terminology mirror.

Recommended compact shape:

```json
{
  "coded_terms": [
    {
      "system": "ICD-10 Diagnostic Codes",
      "codes": ["F43.10", "F43.11", "F43.12"],
      "labels": [],
      "omop_candidates": [],
      "embedding_terms": []
    }
  ],
  "coverage_summary": {
    "has_codes": true,
    "has_labels": false,
    "has_omop_mapping": false
  }
}
```

Indexing recommendation:

- always preserve raw codes and code-system labels
- do not require concept names to be present
- if names are present in source data, store them
- if names are absent, leave them empty and enrich later when needed

## Vocabulary and PHOEBE Enrichment Strategy

The Study Agent now has MCP tools such as vocabulary vector search and PHOEBE related concept retrieval. That should influence the design, but not force large up-front enrichment.

Recommended staged strategy:

1. Base indexing:
- raw codes
- raw keywords
- narrative text
- execution-readiness metadata

2. Lightweight enrichment at index build time when cheap:
- add code-system labels
- add any source-provided code descriptions
- derive embedding text from names, keywords, code-system names, and available labels

3. Deferred enrichment after shortlist or acceptance:
- use `vocab_search_standard` to find likely OMOP standard concepts and labels
- use `phoebe_related_concepts` to gather nearby standard concepts useful for concept-set drafting or adaptation
- attach only compact summaries to the recommendation or downstream translation payload

This keeps indexing tractable for 7K phenotypes while leaving room for stronger recommendation and translation support later.

## PheCode / MAP / MVP / GWPheWAS Phenotypes

Many CIPHER phenotypes appear to be derived from PheCode-based or related analytical methods. The tags mentioned for these kinds of records include:

- `MAP`
- `MVP`
- `GW`
- `GWPheWAS`
- `PheCode`

These should be treated as important methodological metadata, not just search tags.

Why this matters:

- they tell the user that the phenotype may have been generated from a statistical or analytical grouping process rather than from a hand-authored executable cohort definition
- they may imply different expectations for portability, specificity, and direct cohort executability
- they provide useful context for the later translation step into OHDSI logic

Recommended handling:

- preserve these tags in `tags`
- normalize them into `signals`, for example `method_family:phecode`, `method_family:map`, `method_family:gwphewas`
- extract short methodology blurbs from `description` or `algorithm.algorithmDesc` into a dedicated note inside `translation_inputs`
- boost their visibility in UI output so users understand what kind of phenotype evidence they are accepting

Recommended optional field inside `translation_inputs`:

```json
{
  "methodology_context": {
    "family_tags": ["MAP", "PheCode"],
    "summary": "Phenotype appears derived from PheCode-based analytical grouping with NLP and coding-frequency augmentation.",
    "translation_cautions": [
      "May require OMOP concept-set expansion rather than direct code copy.",
      "May represent a probabilistic or empirically derived grouping rather than a directly executable cohort algorithm."
    ]
  }
}
```

This is especially important because some phenotype descriptions include short blurbs describing how the codes were generated. Those blurbs should be preserved as user-facing context and downstream translation context.

## Proposed `signals`

Keep `signals` as cheap ranking and filtering hints, but expand them to support both sources:

- `source:ohdsi`
- `source:cipher`
- `status:<label-or-id>`
- `validated`
- `not_validated`
- `va_developed`
- `major_revision`
- `has_publication`
- `has_tool_link`
- `has_contact`
- `has_code_system:icd9`
- `has_code_system:icd10`
- `has_code_system:snomed`
- `has_code_system:medication`
- `reference`
- `washout`
- `method_family:phecode`
- `method_family:map`
- `method_family:mvp`
- `method_family:gw`
- `method_family:gwphewas`
- `execution:native_ohdsi`
- `execution:codes_only`
- `execution:narrative_only`

## Proposed `provenance`

Recommended compact shape:

```json
{
  "created_at": "...",
  "modified_at": "...",
  "version": "...",
  "status": "...",
  "authors": ["..."],
  "contacts": ["..."],
  "sources": ["..."],
  "publications": [
    {"title": "...", "link": "..."}
  ],
  "maintainer": "..."
}
```

OHDSI can populate this from librarian/version/date fields.

CIPHER can populate this from:

- `created`
- `lastModified`
- `versionInfo`
- `phenotypeStatusId`
- `algorithm.authors`
- `algorithm.contacts`
- `sources`
- `publications`

## Retrieval Text Strategy

The current builder embeds only:

- `name`
- `short_description`
- `pop_keywords`

That is too narrow for CIPHER and too narrow for execution-aware recommendation.

Recommended `retrieval_text` should include:

- `name`
- `short_description`
- `long_description`
- tags and keywords
- code-system labels
- actual code strings
- source labels
- author labels when institution-like
- validation summary
- population summary
- execution-readiness cues
- PheCode or MAP methodology blurbs when present

This should improve:

- phenotype search by disease name
- recommendation by methodological similarity
- retrieval by terminology system
- retrieval by VA-specific provenance
- shortlist quality for later translation into OHDSI cohort logic

## Batch Import Notes

The workbook `cipher-disease-phenotype-summary.xlsx` does not appear to be the full metadata source for indexing.

Observed properties:

- first sheet has 3 columns: path, name, description
- another sheet has 2 columns for records missing descriptions
- additional sheets appear grouped by source family such as `CCW`, `SNOMED`, `Read code`, `PheCode`, `CART`, `ICD`, `HDR UK`, `Elixhauser`, `MAP`

This workbook looks useful for:

- inventory reconciliation
- coverage checks
- missing-description handling
- source-family grouping

But the JSON files should remain the primary indexing source because they carry the richer metadata.

## Gaps / Follow-Up Needed

Some CIPHER ids in the sample are coded but not fully resolvable from `enumType 1.json` alone.

Examples:

- `phenotypeStatusId`
- `categoryTypeId`
- `phenotypeSourceId`
- `phenotypeRoleId`
- `phenotypeClassId`
- `visualToolId`
- `contextId`
- `methodUsedId`
- `relatedDiseaseId`
- some `subCodeType` values such as `785`

Recommendation:

1. Look for additional enum exports in the full CIPHER metadata dump.
2. Keep raw ids in the schema even when labels are unavailable.
3. Add best-effort labels only where the enum file is authoritative.

## Recommended Indexer Direction

Minimal-disruption path:

1. Rename the internal concept from `cohort` to `phenotype` in catalog rows while keeping backward-compatible aliases if needed.
2. Introduce a new source-aware builder layer:
- OHDSI row parser
- CIPHER JSON parser
3. Emit one shared catalog schema for both sources.
4. Expand sparse and dense text inputs to use `retrieval_text`.
5. Add execution-readiness fields and `translation_inputs` so recommendation output is future-compatible with an ACP translation flow.
6. Preserve source-specific detail inside `source_meta`, `population_features`, `validation_features`, `code_systems`, and `concept_evidence`.
7. Keep vocabulary and PHOEBE enrichment lightweight during indexing and use deeper enrichment later during shortlist or acceptance.

This keeps the current retrieval architecture intact while broadening the metadata foundation enough for mixed-source search, recommendation, and later cohort-translation workflows.

## Next Sprint

The current implementation now supports a mixed OHDSI + CIPHER catalog with shared `phenotype_id`-based rows, execution-readiness metadata, source-aware retrieval text, and lightweight CIPHER code-system normalization.

The next sprint should focus on improving retrieval quality rather than expanding workflow scope.

### Priorities

1. Add derived retrieval keywords.
- Keep raw tags and raw source keywords.
- Add a new compact `retrieval_keywords` field produced from a constrained LLM extraction step.
- Optimize for short clinically meaningful terms, phenotype method terms, population cues, and execution cues.
- Avoid stop words, long narrative fragments, and generic filler.

2. Add human-readable labels for coded evidence.
- Preserve raw codes as canonical structured data.
- Add concept or code labels wherever they can be resolved cheaply.
- Include those labels in retrieval-oriented text fields so ANN and sparse matching benefit from human-readable clinical language.

3. Add OHDSI concept-set evidence to the index.
- Parse OHDSI cohort JSON concept sets during indexing.
- Retain concept ids, vocabulary ids, concept names, and lightweight grouping information.
- Represent OHDSI concept evidence in a normalized way parallel to CIPHER `code_systems` / `concept_evidence`.
- Use this mainly for disambiguation and scope refinement, not just direct matching.

4. Separate raw metadata from derived retrieval metadata.
- Keep source-faithful fields such as raw tags, raw keywords, raw code systems, and provenance.
- Add derived fields such as `retrieval_keywords`, `retrieval_concept_labels`, and `methodology_summary`.
- Treat retrieval-facing derived fields as index optimization artifacts, not replacements for source metadata.

5. Keep enrichment staged.
- Stage 1: source parsing plus cheap label extraction.
- Stage 2: offline LLM keyword derivation with caching.
- Stage 3: optional deeper vocabulary and PHOEBE enrichment for shortlist or acceptance flows rather than bulk index-time expansion.

### Design Guidance

- Do not let concept-level detail overwhelm phenotype-level meaning.
- Do not depend on full OMOP mapping completeness before adding label enrichment.
- Prefer compact derived features over verbose copied prose.
- Preserve enough structure so a future cohort-translation ACP flow can reuse the same indexed evidence.

### Suggested Evaluation

Before another major schema revision, assemble a small set of representative phenotype recommendation queries and compare:

- current mixed-source index
- index plus derived retrieval keywords
- index plus concept-label enrichment
- index plus both

Use that comparison to decide how much weight should come from narrative similarity versus concept evidence versus execution readiness.

## Recommendation Flow Refactor: Bounded Agentic Retrieval

The current `phenotype_recommendation` flow is a one-shot reranker:

- run `phenotype_search`
- truncate to a small candidate list
- send thin candidate rows to the LLM
- ask for final recommendations in one pass

This is not a good fit for a small local chat-completion model. With `candidate_limit` kept low for latency and context reasons, the model often does not see the best executable OHDSI candidates. If `candidate_limit` is raised, the model receives more noise but not enough structured evidence to discriminate among phenotype types.

### Current Limitation

The recommendation LLM currently sees only the thin search payload:

- `phenotype_id`
- `source_dataset`
- `name`
- `short_description`
- `tags`
- `signals`
- `executable_definition_status`
- `execution_readiness_score`
- search scores

It does **not** see the richer indexed evidence already available in the catalog and definitions:

- `retrieval_keywords`
- `retrieval_concept_labels`
- `methodology_summary`
- `code_systems`
- `concept_evidence`
- `adaptation_notes`
- full definition payloads under `definitions/`

This causes several failure patterns:

- complication or severity phenotypes can outrank diagnosis phenotypes for disease-identification intents
- repair/procedure phenotypes can outrank diagnosis phenotypes
- HDR UK / Read-code-centric phenotypes can outrank more locally useful OHDSI or VA-compatible alternatives
- medication-based intents are poorly separated from diagnosis-code phenotypes
- execution readiness is present but under-informed because the model lacks the phenotype details needed for discrimination

### Design Goal

Refactor recommendation into a **bounded agentic retrieval flow** that lets a small model request more evidence only for promising candidates.

This should remain tightly controlled:

- no open-ended tool loop
- bounded number of tool calls
- bounded prompt sizes
- explicit intermediate JSON schemas
- deterministic fallbacks still available

### Recommended Flow

#### Stage 1: Intent Facet Extraction

Use a small LLM or deterministic parser to extract compact facets from the study intent.

Suggested facets:

- condition or topic
- phenotype role: diagnosis, outcome, screening, severity, procedure, medication-based, risk score
- care setting: outpatient, inpatient, ED, any
- population cue: VA, veteran, older adults, pediatric, etc.
- validation preference
- OHDSI executability preference
- geography or coding preference if inferable: US/OMOP vs UK/Read-code

This output should be small and cheap.

#### Stage 2: Broad Recall Search

Run `phenotype_search` as a recall step, not the final ranking step.

Recommended changes:

- use a larger search window than the final LLM shortlist, for example `top_k=20..40`
- keep the returned search rows compact
- allow optional search-time boosts or filters later based on extracted facets

The goal here is to avoid losing the best OHDSI candidate before the model can inspect it.

#### Stage 3: LLM Shortlist Decision

Ask the LLM to select a small shortlist of phenotype ids for deeper inspection, not final recommendations yet.

Output should include:

- inferred facet summary
- shortlist phenotype ids
- optional reasons each candidate needs more evidence
- optional indication that another search page or reformulated query is needed

This first reasoning step should operate over compact rows only.

#### Stage 4: Targeted Evidence Hydration

For the shortlisted ids, fetch richer evidence using existing MCP tools:

- `phenotype_fetch_summary`
- `phenotype_fetch_definition` for only the most ambiguous finalists

Recommended fetch policy:

- summary fetches: up to 6 to 8 candidates
- definition fetches: up to 2 to 3 candidates
- at most 2 search rounds total

The summary payload is likely sufficient for most decisions if it includes:

- `retrieval_keywords`
- `retrieval_concept_labels`
- `methodology_summary`
- `signals`
- `code_systems`
- `executable_definition_status`
- `execution_readiness_score`
- `adaptation_notes`

Definition fetches should be reserved for cases such as:

- OHDSI candidates with similar names but different inclusion logic
- CIPHER candidates whose methodology or scope is ambiguous
- medication-based or multi-domain intents where code evidence matters

#### Stage 5: Final Recommendation Synthesis

Ask the LLM for the final recommendation only after evidence hydration.

Final output should still remain compact:

- up to `max_results`
- concise justification
- optional confidence
- ideally an indication of whether the phenotype is immediately executable or requires translation

### Suggested Tool / Flow Changes

This does not require inventing an unrestricted autonomous agent. It requires a controlled multi-step ACP flow.

#### Keep Existing Tools

- `phenotype_search`
- `phenotype_fetch_summary`
- `phenotype_fetch_definition`
- `phenotype_prompt_bundle`

#### Add or Refactor ACP Stages

Add a new intermediate ACP planning task for phenotype recommendation, for example:

- `phenotype_recommendation_plan`

Possible output shape:

- `intent_facets`
- `shortlist_ids`
- `needs_more_search`
- `reasoning_notes`

Then keep the current final task, but rename conceptually to:

- `phenotype_recommendations_finalize`

Its input should be hydrated candidate summaries rather than thin search rows.

### Why This Is Better for a 4B Model

A small model is more reliable when it must:

- compare a modest number of compact candidates
- request richer evidence selectively
- reason over a short hydrated shortlist

A small model is less reliable when it must:

- rerank a large noisy list in one pass
- infer phenotype type from minimal text
- compensate for missing structured evidence

The bounded agentic design shifts difficulty away from long-context semantic reranking and toward staged discrimination, which is a better fit for air-gapped small-model deployment.

### Immediate Implementation Priority

The next implementation step should be a **two-pass ACP refactor**, not a full free-form loop.

Recommended first increment:

1. add an intermediate planning schema for shortlist selection
2. run `phenotype_search` with broader recall
3. fetch summaries for shortlisted ids
4. run a second LLM call for final recommendation

This is simpler than a full agent loop and should address the main current failure modes without materially increasing model size requirements.

## Offline Recommendation Metadata Extraction

The next indexing revision should add a second compact offline LLM extraction pass focused specifically on phenotype recommendation quality.

This is different from the existing `retrieval_keywords` pass:

- `retrieval_keywords` improves lexical and embedding retrieval surfaces
- recommendation metadata should improve semantic discrimination between primary phenotype topic, phenotype role, care setting, and misleading study-context mentions

### Design Rationale

The current recommendation failures are not only caused by retrieval weights. They are caused by the index still mixing:

- phenotypes that are primarily about a disease or diagnosis
- phenotypes that are primarily about a complication, severity index, or downstream outcome
- phenotypes that are primarily baseline covariates or comorbidities used in a study about another condition
- phenotypes whose source narrative mentions a disease only as study context rather than as the target phenotype topic

A brittle rule-based classifier is not the preferred fix. The better approach is to use an offline constrained LLM extraction step during indexing, similar in spirit to the current keyword derivation pass, and then store compact structured fields that can be used deterministically at recommendation time.

### Proposed Extracted Fields

Recommended recommendation-oriented fields:

- `primary_clinical_topic`
- `secondary_topics`
- `phenotype_role`
- `care_setting_scope`
- `population_scope`
- `topic_mentions.primary_topics`
- `topic_mentions.context_only_topics`
- `topic_mentions.downstream_or_related_topics`
- `target_vs_context_conditions.target_conditions`
- `target_vs_context_conditions.context_conditions`
- `exclude_from_primary_topic_match`
- `recommendation_summary`

Recommended meanings:

- `primary_clinical_topic`: the narrow main phenotype topic the definition is intended to identify or characterize
- `secondary_topics`: clinically relevant related topics that are not the main phenotype topic
- `phenotype_role`: one of `diagnosis`, `outcome`, `complication`, `severity`, `screening`, `procedure`, `medication_based`, `risk_score`, `comorbidity_covariate`, `mixed`, or `unknown`
- `care_setting_scope`: `outpatient`, `inpatient`, `ed`, `mixed`, or `unspecified`
- `population_scope`: compact population cue if explicit, such as veterans or older adults
- `topic_mentions.primary_topics`: topics that are genuinely central to the phenotype itself
- `topic_mentions.context_only_topics`: topics mentioned only because of study context or deployment context
- `topic_mentions.downstream_or_related_topics`: complications, sequelae, outcomes, or closely related topics that should not be confused with the primary topic
- `target_vs_context_conditions.target_conditions`: conditions the phenotype is actually targeting
- `target_vs_context_conditions.context_conditions`: conditions present only as study background, index disease context, or downstream follow-up context
- `exclude_from_primary_topic_match`: short phrases useful for down-weighting misleading topic matches at recommendation time
- `recommendation_summary`: a compact recommendation-oriented statement of the phenotype's real focus

### Expected Input To The Extraction Prompt

The offline extraction step should be grounded in compact source-aware evidence already available in the index build:

- `name`
- `short_description`
- `methodology_summary`
- `retrieval_keywords`
- `retrieval_concept_labels`
- `signals`
- `executable_definition_status`
- `execution_readiness_score`
- optionally a compact `long_description` excerpt if short description is sparse

It should not require the full raw source JSON for every pass unless later evaluation shows that more context is necessary.

### Expected Runtime Use

These extracted fields should support recommendation in three ways:

1. candidate display and summary hydration
- expose them through `phenotype_fetch_summary`
- use them in the hydrated candidate payload sent to the final recommendation step

2. planner grounding
- the recommendation planning prompt should rely on these fields instead of inferring everything from noisy source narratives
- the planner should be able to distinguish primary topic from study context without having to reconstruct that distinction itself

3. retrieval text and ranking
- selected fields such as `primary_clinical_topic`, `secondary_topics`, `phenotype_role`, and `recommendation_summary` should contribute to `retrieval_text`
- `context_only_topics` and `exclude_from_primary_topic_match` should not be treated as positive primary-topic evidence

### Example Failure This Should Fix

For a phenotype like `Hypertension (VA CAUSAL Methods)` that was used in a COVID-19 vaccine effectiveness study, the extracted metadata should look conceptually like:

- `primary_clinical_topic`: hypertension
- `phenotype_role`: comorbidity_covariate
- `topic_mentions.context_only_topics`: COVID-19
- `target_vs_context_conditions.target_conditions`: hypertension
- `target_vs_context_conditions.context_conditions`: COVID-19
- `exclude_from_primary_topic_match`: used in COVID-19 outcomes study; baseline covariate phenotype

That would let the recommendation stack avoid treating it as a COVID-19 diagnosis phenotype.

For a phenotype like `Long COVID-19 (LATCH)`, the extracted metadata should preserve that it is a COVID-related phenotype while distinguishing it from incident acute COVID-19 diagnosis.

### Prompt Artifacts

The design prompt bundle for this extraction lives under:

- `mcp_server/prompts/phenotype/overview_phenotype_index_recommendation_metadata.md`
- `mcp_server/prompts/phenotype/spec_phenotype_index_recommendation_metadata.md`
- `mcp_server/prompts/phenotype/output_schema_phenotype_index_recommendation_metadata.json`

### Recommended Next Implementation Step

Implement this as a second offline cached LLM pass in `build_phenotype_index.py`, parallel to the current keyword derivation flow:

- build a compact source-aware prompt payload per phenotype
- cache results by phenotype id plus source hash
- write normalized fields into each catalog row
- expose them in `phenotype_fetch_summary`
- update the two-pass recommendation flow to use these fields during planning and final recommendation

This should be attempted before adding brittle deterministic phenotype-role heuristics.
