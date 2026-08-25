# Current Sprint Plan



Build phenotype_make_computable in two comparable tracks:

1. Baseline branch: use current StudyAgent vocabulary tools and the existing R environment.
2. Groundworkers branch: upgrade the OMOP stack and evaluate Groundworkers-backed concept grounding against the same test corpus.

The ACP flow’s required output is an auditable Capr R definition plus Circe JSON that has executed successfully and compiled to Circe SQL.


text ⧉

Narrative cohort statement
  → clarification / confirmed design decisions
  → concept-set candidate retrieval and review
  → constrained computable cohort plan
  → deterministic Capr R emission
  → R execution with Capr
  → CirceR SQL-compilation validation
  → Capr source, Circe JSON, validation/provenance response


1. Define the public flow contract

Add POST /flows/phenotype_make_computable.

It accepts:

• a narrative cohort statement;
• optional explicit scope answers for index event, domains, entry limit, observation/washout, time windows, and exit strategy;
• optional concept-set selections or review decisions;
• optional selected phenotype context when called from phenotype_definition.

It returns either:

• needs_clarification, with the skill-derived checklist and proposed defaults;
• needs_concept_review, with grounded concept-set candidates and evidence;
• ok, containing capr_code, circe_json, canonical hash, validation evidence, assumptions, concept provenance, and clinical-review warning; or
• unavailable, with structured errors and no partial Circe output.

The flow remains stateless: the client resubmits the narrative with its answers rather than ACP storing a conversation session.

2. Preserve the Capr skill’s safeguards

Bring the demonstrated skill’s behavior into maintained MCP prompt artifacts:

• mandatory clarification before generation;
• explicit scope-check block in every emitted R script;
• no clinical concept IDs invented by the model;
• clear separation of index-event restrictions from attrition logic;
• refusal/decomposition guidance for logic Circe cannot faithfully express;
• executable function-form Capr output.

The project should use the supplied CAPR_REFERENCE.md as the supported Capr surface and version it deliberately with the prompt bundle.

3. Use a constrained cohort-plan model

Do not ask the LLM to produce arbitrary executable R.

Have it produce a validated cohort-plan JSON model describing:

• named concept sets and their selected concepts;
• OMOP domains;
• entry events;
• nested temporal conditions;
• attrition rules;
• observation windows;
• exit and era strategy;
• assumptions and unresolved choices.

A deterministic emitter converts that plan into readable Capr R. This avoids arbitrary-code execution while preserving the required Capr source artifact.

4. Add MCP capabilities

Required MCP additions:

• phenotype_make_computable_prompt_bundle — loads the Capr workflow, constraints, and response schemas.
• phenotype_make_computable_concept_candidates — returns normalized, active, standard concept candidates with provenance.
• phenotype_make_computable_validate — writes only controlled temporary artifacts, emits/executes Capr, validates Circe, and returns structured diagnostics.

Reuse existing vocabulary/PHOEBE tools in the baseline branch. The new flow should use a provider interface so the concept-candidate tool can later use Groundworkers without changing ACP orchestration.

5. Validate with the existing R library

Use the supplied project R library explicitly through R_LIBS_USER.

Each generated artifact must pass:

1. R parse and controlled execution.
2. Capr object construction and JSON serialization.
3. CirceR parse and SQL generation.
4. Structural checks: required Circe fields, concept-set references, no placeholder IDs, canonical JSON hash.
5. Cohort-plan-to-output consistency checks: e.g. intended fixed exit, required temporal overlap, entry/event domains.

This is technical/executability validation—not clinical validation or validation against patient-level results. Responses must say so clearly.

6. Test and evaluate safely

Use the 11 retained cohorts for development only:

• hide reference_circe.json during generation;
• assess concept-root recovery, selected domains, temporal/exit semantics, Capr execution, Circe compilation, and structural agreement;
• report the corpus as AI-screened development evidence, not clinical gold.

Keep the 16 held-out cohorts entirely untouched until the baseline design is stable.

7. Groundworkers comparison branch

Create a separate branch later for:

• upgrading omop-alchemy and orm-loader to 1.x;
• deploying/configuring the vector-store and graph stack;
• connecting Groundworkers as an external MCP/REST vocabulary provider;
• retaining StudyAgent configuration/secrets policy unless a separately approved configuration migration is made.

Compare the baseline and Groundworkers branches on the same 11 cases. Adopt Groundworkers only if it materially improves difficult concept-set recovery, provenance, or concept-review workflow without unacceptable airgapped deployment and maintenance cost.

8. Integrate with existing phenotype retrieval later

After direct narrative generation is stable, update phenotype_definition so a selected conversion_required phenotype can invoke this flow. Preserve its current indexed-definition retrieval behavior and return the same validated inline Circe contract in either path.

## Agreed v1 decisions (added after design review)

- `phenotype_make_computable` is a public direct-narrative ACP endpoint in v1. Integration with `phenotype_definition` and `docs/PROMPT_PHENOTYPE_DEFINITION_CIRCE_CONTRACT.md` is explicitly deferred to a separate session after the direct flow is stable.
- The flow is stateless and returns `capr_code` and `circe_json` inline only. The caller owns saving `.R` and `.json` artifacts; v1 accepts no local paths and persists no caller artifacts to an ACP result root.
- `confirmed_scope` defaults to `false`. When false, the flow returns the Capr-skill-derived `needs_clarification` checklist for missing or vague design decisions. When true, a complete structured scope may bypass that response only after completeness and consistency validation; it never bypasses feasibility, OMOP-domain, or Capr/Circe validation.
- A future narrative-refinement ACP flow may help direct callers improve vague or overly broad statements. It is not part of this sprint.
- `concept_review_mode` is an extensible enum: `required` returns candidates and waits for selections; `propose` permits provisional generation with review flags and evidence; `provided_only` validates and uses caller-supplied concept sets.
- Every concept-set response exposes selected concepts, inclusion/exclusion flags, descendant and mapped-concept choices, the general definition, and retrieval provenance. Deeper review is performed against caller-saved artifacts.
- The maintained prompt bundle will live under `mcp_server/prompts/phenotype_make_computable/` and include a repository-owned, versioned `CAPR_REFERENCE.md`; runtime behavior must not depend on the sandbox copy.
- V1 uses the existing StudyAgent vocabulary/PHOEBE tools behind a provider boundary. The Groundworkers/OMOP-stack upgrade remains a separately tested comparison branch, not a prerequisite for this flow.
- The supplied project R library is the validation runtime. The flow must explicitly use `R_LIBS_USER=/ai-agent/HadesProject/OHDSI-Study-Agent/renv/library/linux-ubuntu-noble/R-4.5/x86_64-pc-linux-gnu` for Capr/CirceR execution; no `renv` mutation or snapshot is authorized.
