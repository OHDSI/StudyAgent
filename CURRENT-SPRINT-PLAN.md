# Current Sprint Plan

## CIPHER-informed phenotype acquisition and composition

### Sprint objective

Make phenotype recommendations understandable and actionable for Strategus users
when the best evidence is an OHDSI Circe definition, a non-computable VA CIPHER
phenotype, or a combination of phenotype sources. A user must be able to inspect a
plain-language account of a candidate, choose an appropriate use path, and—where
supported—produce a reviewed, validated, workflow-local Circe definition.

This sprint does **not** treat CIPHER narratives or code lists as executable OHDSI
cohort definitions. Technical validation remains distinct from clinical validation.

### Desired user experience

The recommendation experience becomes:

```text
recommendations -> inspect understandable candidate definition -> choose how to use it
```

Each candidate should present a short, source-cited card rather than only a title,
CSV, or provider-shaped JSON. The card should clearly distinguish:

- what the source explicitly defines;
- what usable evidence it supplies (Circe logic, coded evidence, narrative logic);
- what ACP infers only as a possible OMOP implementation; and
- what the user must still decide.

Available actions are determined by a readiness assessment:

- **Use directly**: ACP can retrieve and validate a complete Circe definition.
- **Use as a starting point**: source evidence can seed a review-gated conversion
  or composition workflow.
- **Review as evidence only**: relevant source material exists, but terminology or
  logic is insufficient for supported conversion.
- **Not convertible in this environment**: explain the unsupported vocabulary,
  unavailable mappings, or missing logic; retain normal `create` acquisition.

The presentation must stay concise by default. Users can inspect the original source
snapshot, detailed mappings, full Circe JSON, and review artifacts when needed.

### Architecture and responsibility boundaries

| Concern | Owner |
|---|---|
| Retrieve, normalize, snapshot, hash, and present indexed source records | MCP |
| Deterministically render Circe logic into readable text | MCP |
| Assess source/mapping/logic readiness and produce mapping evidence | MCP |
| Orchestrate public contracts, review stages, and provenance | ACP |
| Confirm scope and concept policies; persist/resume local artifacts; import final Circe | Strategus R shells |
| Provide the same stable ACP workflow to non-R clients after contracts settle | Optional agent skill |

`phenotype_make_computable` remains the only Capr/Circe emitter. It must receive
explicitly approved OMOP concept policies and confirmed scope; it must not accept raw
CIPHER codes, text snippets, or an LLM proposal as approved concept sets.

### Source-neutral phenotype presentation

Add an MCP presentation capability, backed by the indexed record and, when needed,
its immutable full source snapshot. It should return a stable structured object such
as:

```json
{
  "phenotype_id": "cipher:29197",
  "title": "ACE Inhibitor Induced Cough (PheKB)",
  "source": "VA CIPHER",
  "use_mode": "seed_for_composition",
  "plain_language_summary": "...",
  "clinical_pattern": {},
  "source_evidence": {},
  "important_gaps": [],
  "available_actions": [],
  "provenance": {}
}
```

For native OHDSI cohorts, use a deterministic Circe-to-readable conversion as the
primary explanation and link it to the exact executable definition. For CIPHER and
future sources, render known source fields—including `algorithmDesc`, narrative,
code-system identity, validation, and revision—from the full snapshot. Do not use an
LLM as the authoritative renderer. Any later fluent LLM wording must remain clearly
derived from and traceable to deterministic source facts.

### Readiness assessment and supported paths

Replace the current overly broad CIPHER `codes_only` interpretation with a
deterministic conversion-readiness assessment. Report separately:

- source terminology recognition and deployment-specific mapping support; Note that the ACP has a database connection to the OMOP vocabulary and a query could identify what vocabularies are available in the @vocabulary_schema.vocabulary table.  The relationship `Non-standard to Standard map (OMOP)` (`concept_id=44818977`) might be helpful for deterministic run-time checking for mapping feasibility;
- per-code mapping coverage, ambiguity, standard status, and provenance;
- narrative/algorithm-logic richness;
- recovered logic elements: event, occurrence count, timing, care setting,
  exclusions, first-event/era rules, and control logic;
- source-method cautions (PheCode, MAP, classifier, text mining, local codes); and
- an action class: `not_supported`, `source_informed_review`,
  `mapping_and_scope_review`, or `conversion_candidate`.

Examples that must guide the design:

- CIPHER GPRD product-code records with no supported mapping or useful logic are
  `not_supported`.
- ACE-inhibitor-induced-cough narrative evidence is `source_informed_review` and a
  seed for composition, not a direct concept set.
- Read v2/OXMIS records can be `mapping_and_scope_review` only where those
  vocabularies and mappings are installed; mapped codes do not recreate omitted
  logic.
- CIPHER records with mappable codes plus explicit temporal/eligibility logic are
  `conversion_candidate`s after human review.
- PheCode records can be candidates when their exact map/version, ICD source codes,
  count rules, exclusions, and mapping provenance are preserved. PheCode mappings
  are evidence, not native OMOP logic.

### Composition from phenotype evidence

Support a source-informed composition branch for records that describe a clinical
relationship rather than a single reusable cohort. A selected source can seed a
`phenotype_composition_plan`; it must not cause opaque Circe definitions to be merged.

For ACE-inhibitor-induced cough, ACP should propose an unconfirmed pattern:

```text
ACE-inhibitor exposure -> cough after exposure
```

The preparation response should identify proposed components, their source evidence,
the relationship, and unresolved decisions. It should retrieve focused evidence for
each component (for example, ACE-inhibitor exposure concepts and a cough cohort), not
run another generic title-only recommendation pass. The user must confirm such
decisions as the risk window, baseline cough exclusion, required outcome occurrences,
and whether the desired artifact is a case cohort, outcome, or target/comparator/
outcome study design.

Generalize composition only through declared, reviewable relationship templates:

- exposure followed by outcome/adverse event (or vice versa);
- procedure followed by complication (or vice versa);
- infection followed by sequela;
- index event with supporting condition/laboratory/medication evidence;
- concurrent condition; and
- prior condition as eligibility or exclusion evidence.

Each component has independent concept review. The approved composition plan and
approved component policies are then supplied to `phenotype_make_computable` for the
single final Capr/Circe artifact.

### ACP and MCP contracts

1. Add MCP tools for source snapshot retrieval, source-neutral presentation,
   terminology/code mapping evidence, and conversion-readiness assessment.
2. Add an ACP preparation flow (name to settle during implementation, e.g.
   `phenotype_conversion_prepare`) that accepts a selected `phenotype_id`, creates
   or returns an immutable source package, and produces an unconfirmed conversion or
   composition proposal.
3. Evolve public `phenotype_definition` into the executable-definition boundary:
   `circe_available` returns complete, validated Circe JSON; non-direct sources
   return structured `conversion_required` or `not_computable` domain outcomes.
   Do not expose provider-shaped definition payloads as its public result.
4. Preserve the selected ID, source revision, canonical JSON SHA-256, source hash,
   mapping coverage, approved policies, and technical validation provenance.
5. Keep public naming consistent: use `circe_available`, `conversion_required`, and
   `not_computable`; readiness/action classes are additional preparation metadata,
   not replacements for the public computability contract.

### R-client and shell integration

Update `slashOhdsiAcpClient` with the new presentation/preparation calls and typed,
validated response handling. Update the shared Strategus acquisition component first,
then apply it to incidence (target/outcome) and cohort-methods (target/comparator/
outcome).

The shell should display candidate cards and actions, prompt for composition decisions
in plain language, and persist resumable artifacts under
`phenotype-conversion/<role>/`, including:

- immutable source snapshot and hashes;
- presentation/readiness result;
- mapping evidence and user review materials;
- confirmed scope and composition plan;
- approved concept policies and approval record; and
- resulting make-computable Capr, Circe, and validation evidence.

The final Circe JSON is imported exactly like the existing `create` path: as a
workflow-local cohort artifact. The generated Strategus workflow must not depend on
the ACP phenotype index or PhenotypeLibrary at execution time.

### Development reference set and test strategy

Create a small, versioned CIPHER conversion reference set before implementing broad
support. Start with 10–20 records deliberately spanning unsupported vocabularies,
text snippets, code-only records, narrative-rich algorithms, PheCodes, and clearly
convertible examples. Include the discussed records where licensing/data handling
permits: `cipher:30687`, `cipher:29197`, `cipher:29218`, `cipher:29772`,
`cipher:17527`, and `cipher:14189`.

For each reference record, define expected source fields, readiness/action class,
mapping expectations, required human decisions, and whether Circe emission is
prohibited or possible after review. In particular, test that `algorithmDesc` and
other useful source logic survive indexing and source-snapshot retrieval.

Add focused tests for:

- deterministic Circe and CIPHER presentations;
- source snapshot/revision/content-hash integrity;
- mapping coverage and unsupported-vocabulary outcomes;
- no automatic concept approval from source codes, text snippets, or LLM output;
- composition-plan relationship and unresolved-decision requirements;
- direct Circe retrieval, canonical-hash matching, and malformed provider-data
  rejection;
- conversion failure returning no `circe_json`; and
- shell artifact persistence and resume behavior for all cohort roles.

### Delivery sequence

1. Define the reference set and readiness/presentation schemas.
2. Fix/verify indexing and snapshot fidelity, particularly CIPHER `algorithmDesc`.
3. Implement deterministic MCP presentation, snapshot, and readiness tools.
4. Implement mapping-evidence support for a narrow, configured initial vocabulary
   set; report unsupported sources explicitly.
5. Add ACP preparation and public executable-definition contracts with provenance.
6. Add source-informed composition for one relationship template: exposure followed
   by outcome.
7. Integrate the shared shell acquisition UX in incidence first, then cohort methods.
8. Expand source families and relationship templates only after reference-set and
   workflow tests demonstrate stable, review-gated behavior.

### Non-negotiable guardrails

- No PHI/PII is sent to an LLM.
- A candidate limit is retrieval convenience, never evidence that a concept set is
  complete.
- CIPHER source codes, PheCodes, mappings, and narrative are review evidence, not
  clinical approval or executable cohort logic.
- No Capr/Circe artifact is emitted before explicit scope and concept-set approval.
- Successful technical validation does not establish clinical or database-level
  phenotype validity.
- Unsupported, ambiguous, or incompletely specified sources fail closed into
  explanation and clarification rather than partial executable JSON.
