Task: `phenotype_make_computable`.

Translate a well-specified narrative OHDSI cohort statement into an auditable, computable cohort plan. The final deliverable is function-form Capr R source and validated Circe JSON; this task produces only the structured cohort plan used by deterministic emitters.

Never invent clinical concept identifiers. Use only candidate concepts and concept-set policies supplied by the workflow. Surface ambiguity, missing scope, or unsupported Circe logic instead of silently approximating it.
