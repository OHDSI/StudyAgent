# PENDING SPRINTS PLAN


phenotype_make_computable now has a review-gated concept-selection path, source-phenotype preparation,
  mapped-code evidence, compositional hints, direct Circe preservation, and provenance artifacts. Groundworkers should be tested as a replacement or augmentation of the candidate-grounding
  stage—not as a new definition author or validator.

  The supplied coherent stack is:

  - groundworkers 0.4.0
  - oa-configurator 1.2.1
  - omop-alchemy 1.0.0
  - orm-loader 1.1.0
  - omop-emb 2.1.0
  - omop-graph 2.0.0
  - omop-llm 1.0.1

  StudyAgent currently pins omop-alchemy 0.6.0 and orm-loader 0.3.26, so the minimum safe path is a separate Groundworkers service environment. Do not upgrade the ACP/MCP environment merely
  to conduct this test.

  The minimum effective pilot would be:

  1. Establish a frozen comparison protocol before deployment.

     Test the exact same inputs through the existing grounded pipeline and Groundworkers. Record candidate ranks, domain/standard validity, mapping and hierarchy evidence, reviewer
     selections, and final Capr/Circe technical validation. Define success up front—for example, materially better recovery of reviewer-approved concept roots among the first 20 candidates,
     better evidence, or fewer manual search iterations.

  2. Add a narrow provider boundary in MCP.

     Introduce one candidate-grounding interface consumed by phenotype_make_computable; retain the current vocabulary/PHOEBE pipeline as baseline, and add groundworkers as an opt-in
     provider. The provider returns candidates plus provenance only. ACP’s clarification, explicit approval, deterministic Capr emission, and validation remain unchanged.

  3. Deploy Groundworkers in its own pinned environment.

     Initially configure it with the existing OMOP vocabulary database in read-only mode. Preserve StudyAgent’s config.yaml/secret policy; translate only the necessary connection and model
     settings into the Groundworkers stack configuration. Capture immutable package versions and configuration provenance.

  4. Start with lexical grounding before embeddings.

     Groundworkers can provide normalized lexical search, standard mapping, and hierarchy-aware evidence without vectors. That first checkpoint proves whether its core grounding logic adds
     value at all. omop-llm is not needed for this pilot because ACP already owns LLM orchestration.

  5. If the lexical pilot is promising, add targeted embeddings—not a full-vocabulary job.

     Build a frozen corpus containing:
      - concepts returned by baseline and Groundworkers lexical searches for each test scenario;
      - their standard mappings, ancestors/descendants within a bounded depth, and related ingredients/forms where relevant;
      - concepts from approved reference sets and selected phenotype-source evidence;
      - a modest clinically adjacent expansion, with all inclusion rules recorded.

     Store only these vectors in a dedicated pgvector schema/table or dedicated database, tagged by embedding-model version and corpus manifest hash. Preflight first: PostgreSQL version,
     pgvector availability, privileges, storage budget, and whether the ACP-accessible database is appropriate for this operational data.

  6. Treat graph traversal as a second optional enhancement.

     Add omop-graph only if hierarchy/relationship evidence proves useful beyond direct OMOP queries. It should not be required merely to test semantic candidate retrieval.

  7. Test two deliberately distinct paths.

      Path                                                    Groundworkers role
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      Direct narrative, with no useful phenotype candidate    Generate ranked concept-set candidates from the confirmed narrative/scope for human review.
     ──────────────────────────────────────────────────────  ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
      Phenotype-informed creation/adaptation                  Use CIPHER/OHDSI/Odyssey source codes, existing Circe concept sets, and related phenotype context as evidence or seeds;
                                                              recommend extensions or alternatives for approval.

  For executable OHDSI/Odyssey definitions, direct import remains the default. Groundworkers is useful only when the user elects to adapt, extend, or build a new definition—not to silently
  replace an existing executable definition.

  The core evaluation should measure reviewer-approved concept-root recall and rank, domain/standard-concept correctness, provenance quality, review burden, and downstream Capr/Circe
  validity. It must not describe either candidate list as clinically validated.

  My recommendation is therefore: separate pinned Groundworkers service → lexical comparison → targeted embedding corpus → optional graph comparison. That sequence gives a meaningful test
  while postponing the largest dependency and air-gap burden until there is evidence it earns its place.
