# Atlas `/ohdsi` concept-set and cohort-assistance sprint — 2026-09-29

## Delivered scope

This sprint integrates review-gated `/ohdsi` assistance into Atlas concept-set and
cohort-definition authoring. It preserves the distinction between reusable concept
sets, how they are bound to a cohort, and the cohort logic that uses those bindings.
No generated candidate or LLM response silently changes a saved expression.

### Concept-set authoring

- `/ohdsi` dialogue can clarify scope and request a bounded local-vocabulary proposal.
- Candidate review occurs in an explicit staging workbench. Users assign policies,
  validate the staged rows, and then apply them to **Selected**; **Included** resolves
  through normal Atlas behavior.
- Proposals remain bounded retrieval slices, not claims of concept-set completeness.
- Review provenance persists with saved concept sets; normal user edits correctly
  identify that the saved expression no longer matches the last reviewed expression.
- The workbench is reusable from cohort workflows and retains intended criterion
  context without putting cohort timing or Boolean logic into the concept-set asset.

### Cohort-definition acquisition and review

- Cohort Definitions provides `/ohdsi` entry points for AI-supported phenotype search,
  direct phenotype-library browsing, and creation of a new computable definition.
- Recommendation cards distinguish **Circe available**, **Conversion required**, and
  source-review status, include details and documentation, and can expose other
  ranked candidates without confusing them with the ACP shortlist.
- A native Circe phenotype can open as an unsaved Atlas draft. Non-computable sources
  can be used as reference evidence for a new review-gated definition.
- New-computable authoring now has a durable cohort specification containing concept
  set slots, criterion bindings, cohort logic, accepted policy snapshots, and
  provenance. It supports resuming unfinished plans.
- Linked concept sets open the existing Atlas concept-set drawer in workflow-linked
  mode; the accepted expression is snapshotted for the cohort plan. Later standalone
  changes do not silently change a saved cohort.
- The currently supported multi-component projections are deliberately narrow:
  - Condition index plus an overlapping Visit restriction.
  - Drug index plus a required supporting Condition in an explicit pre-index window.
  Both require explicit binding and logic confirmation before an unsaved Circe draft
  is generated.
- Unfinished plans can be archived. Archive removes a plan from the resume list while
  retaining its review history and concept-set snapshots for audit.

### Guardrails and known limits

- Concept-policy decisions, binding relationships, timing windows, and exit strategy
  require explicit review.
- Large expansions are not sent to an LLM.
- The local vocabulary candidate retrieval is still a bounded deterministic search;
  concept-search ranking and ingredient-level retrieval quality remain follow-up work.
- Advanced multi-set logic (nested groups, counts, alternate paths, complex recurrence,
  external cohorts) is intentionally not projected yet.
- An archived unfinished plan is retained for audit but has no restore UI in this
  sprint.

## Verification completed

### Automated checks

- Atlas type-check and ESLint completed successfully after the final UI changes.
- WebAPI Java compilation completed successfully with Java 21.
- Focused `phenotype_make_computable` tests passed, including Drug index plus
  supporting Condition and Condition index plus Visit-overlap projection fixtures.
- Scoped diff checks completed without whitespace errors.

### Manual Atlas checks

- Created and saved simple Condition cohorts for first anemia record and all
  bronchitis events; generated person counts for one case.
- Tested AI phenotype search, direct phenotype-library browse, native Circe draft
  opening, recommendation details, ranked alternatives, and source-status labels.
- Tested concept-set proposal review, Selected/Included initialization, expression
  edits, persistence, provenance mismatch notices, deletion, and recreation.
- Tested a multi-component acute cystitis plus inpatient/ER Visit plan through
  concept-set review, criterion-binding confirmation, and unsaved draft projection.
- Tested a Drug-index esketamine plus supporting major depressive disorder plan with
  365-day observation, explicit evidence window, fixed exit after exposure end, and
  successful unsaved-draft generation.
- Tested incomplete-plan resume, no-candidate recovery, archive/discard, and deletion
  regression. After archive, the plan disappeared from the resume list while linked
  concept sets remained intact; the esketamine/MDD cohort could be rebuilt after
  deletion.
- Tested both Atlas dev mode and production-style `npm run build` / `npm run preview`
  against rebuilt WebAPI.

## Checkpoint composition

The implementation checkpoint uses explicit component tags so each tag identifies
one exact release commit. The changes live in these forks and branches:

| Component | Fork | Branch | Commit | Tag |
| --- | --- | --- | --- | --- |
| StudyAgent ACP/MCP | [`vinci-ohdsi/StudyAgent`](https://github.com/vinci-ohdsi/StudyAgent) | `feat/study-agent-demo-implementation` | `eb6f8cf` | `atlas-ohdsi-cohort-assistance-sprint-2026-09-29-studyagent` |
| Atlas3 | [`vinci-ohdsi/Atlas3`](https://github.com/vinci-ohdsi/Atlas3) | `feature/study-agent-demo` | `4c9a0a7` | `atlas-ohdsi-cohort-assistance-sprint-2026-09-29-atlas3` |
| WebAPI3 | [`vinci-ohdsi/WebAPI3`](https://github.com/vinci-ohdsi/WebAPI3) | `feature/study-agent-cohort-defs` | `d286d12f` | `atlas-ohdsi-cohort-assistance-sprint-2026-09-29-webapi3` |
| Sprint documentation | [`vinci-ohdsi/StudyAgent`](https://github.com/vinci-ohdsi/StudyAgent) | `feat/study-agent-demo` | `a67d837` | `atlas-ohdsi-cohort-assistance-sprint-2026-09-29-docs` |

