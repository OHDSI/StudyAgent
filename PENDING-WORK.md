# PENDING SPRINTS PLAN

## Integration of R with MCP tools and ACP management - coordination with SKILLS

Codex> I'm thinking about the architecture of the ACP and MCP tools. I think it's possible that if there is a functional R and the correct renv environment on the same server that's running the ACP and MCP services, then we should be able to run Rscript from Python to do a lot of things that levere the R Hades tools and functions. For example, in the phenotype_improvement flow, it would be possible to run an R CohortGenerator function to test if a change to a cohort definition was valid. One of the planned new flows will be the creation of a cohort definition from a narrative description with the output being an R Capr computable cohort definition. If the ACP ran as a service and a coding model (through the LLM API)  or coding agent like Codex (thorugh a new  SKILL that communicated with the ACP service using REST) created a new Capr definition, the ACP could test if the definition compiles to a valid Circe definition.  Hypotheticaly, is that correct? 
<shell-maker-end-of-prompt>
▶ Thought

▶ . Thinking


**Assessing package specifics for architecture**

Yes in principle. I’ll confirm the relevant capabilities in the active R/HADES environment so I can distinguish “compile a definition safely” from “execute it against a CDM,” which have different operational and security requirements.

▶ Thought, ran a command

▶ ✓ Command Rscript -e 'source("renv/activate.R"); for (pkg in c("Capr", "CohortGenerator", "CirceR")) { cat("\n", pkg, " ", if (requireNamespace(pkg, quietly = TRUE)) as.character(utils::packageVersion(pkg)) else "not installed", "\n", sep = ""); if (requireNamespace(pkg, quietly = TRUE)) print(grep("compile|cohort|json|expression", getNamespaceExports(pkg), value = TRUE, ignore.case = TRUE)) }'

```console
Rscript -e 'source("renv/activate.R"); for (pkg in c("Capr", "CohortGenerator", "CirceR")) { cat("\n", pkg, " ", if (requireNamespace(pkg, quietly = TRUE)) as.character(utils::packageVersion(pkg)) else "not installed", "\n", sep = ""); if (requireNamespace(pkg, quietly = TRUE)) print(grep("compile|cohort|json|expression", getNamespaceExports(pkg), value = TRUE, ignore.case = TRUE)) }'
```

- The project is out-of-sync -- use `renv::status()` for details.

Capr 2.1.1
[1] "as.json"            "makeCohortSet"      "compile"           
[4] ".__T__as.json:Capr" ".__T__compile:Capr" "cohort"            
[7] "writeCohort"       

CohortGenerator 1.1.1
 [1] "getCohortTableNames"                       
 [2] "getCohortValidationCounts"                 
 [3] "createCohortSubset"                        
 [4] "createCohortSubsetOperator"                
 [5] "computeCohortAttrition"                    
 [6] "generateCohortSet"                         
 [7] "CohortSubsetDefinition"                    
 [8] "createCohortTemplateDefintion"             
 [9] "getLastGeneratedCohortChecksums"           
[10] "saveCohortDefinitionSet"                   
[11] "saveCohortSubsetDefinition"                
[12] "dropCohortStatsTables"                     
[13] "createEmptyNegativeControlOutcomeCohortSet"
[14] "createAtcCohortTemplateDefinition"         
[15] "createCohortTables"                        
[16] "addCohortSubsetDefinition"                 
[17] "createUnionCohortTemplate"                 
[18] "sampleCohortDefinitionSet"                 
[19] "createEmptyCohortDefinitionSet"            
[20] "getCohortDefinitionSet"                    
[21] "addSqlCohortDefinition"                    
[22] "createRxNormCohortTemplateDefinition"      
[23] "getCohortStats"                            
[24] "isCohortDefinitionSet"                     
[25] "checkAndFixCohortDefinitionSetDataTypes"   
[26] "getCohortCounts"                           
[27] "SubsetCohortWindow"                        
[28] "CohortSubsetOperator"                      
[29] "createCohortSubsetDefinition"              
[30] "createSubsetCohortWindow"                  
[31] "addUnionCohortDefinition"                  
[32] "runCohortGeneration"                       
[33] "exportCohortStatsTables"                   
[34] "getCohortInclusionRules"                   
[35] "exportCohortSubsetStatsTables"             
[36] "createSnomedCohortTemplateDefinition"      
[37] "generateNegativeControlOutcomeCohorts"     
[38] "CohortTemplateDefinition"                  
[39] "addCohortTemplateDefintion"                

CirceR 1.3.3
[1] "cohortPrintFriendly"          "conceptSetExpressionFromJson"
[3] "buildCohortQuery"             "cohortExpressionFromJson"

▶ . Thinking


**Designing ACP-MCP orchestration flow**

**Planning secure R worker sandboxing**

Yes—architecturally that is correct, with one important boundary: the ACP should orchestrate the request, while the R/HADES operation should be a controlled tool execution, ideally exposed through MCP or a dedicated R worker.

The active environment supports the building blocks:

• Capr 2.1.1 exports compile() and as.json().
• CirceR 1.3.3 can parse a cohort JSON expression and build cohort SQL.
• CohortGenerator 1.1.1 can then construct or generate a cohort set when database execution is intentionally enabled.

A safe cohort-definition validation path would be:


text ⧉

Narrative / proposed Capr definition
  → ACP flow orchestrates
  → controlled R validation tool
  → Capr compile
  → Circe JSON serialization
  → CirceR parse + SQL build
  → structured diagnostics returned to ACP


That validates several distinct things without touching patient data:

1. The submitted Capr definition is syntactically valid.
2. It compiles to a Circe-compatible cohort definition.
3. The emitted JSON can be parsed by CirceR.
4. SQL can be generated for the intended dialect.
5. Warnings and compilation errors can be returned to the model/user as structured feedback.

Cohort generation against a CDM is a separate, higher-authority operation. It needs database credentials, writable cohort/result tables, audit logging, and likely user confirmation. A compile-only validation worker should have none of those credentials.

The major safety rule is: do not let an LLM or external coding agent submit arbitrary R source for execution. Instead, the R tool should accept a constrained payload—for example, a Capr expression in an approved declarative format or a specific source artifact—and run a fixed, allowlisted R script. The tool should use temporary directories, timeouts, resource limits, no shell interpolation, and a runtime check against the certified renv profile.

For your Codex example, a new skill could call an ACP REST endpoint such as cohort_definition_compile_validate. ACP would invoke the R-backed tool and return:


json ⧉

{
  "valid": true,
  "capr_version": "2.1.1",
  "circe_valid": true,
  "sql_generated": true,
  "warnings": [],
  "diagnostics": []
}


So yes: this is a strong next capability. It gives AI-assisted authoring a deterministic validation loop before a cohort definition ever reaches a database.


------------------------------------------------------------
## Preparation Note: Service Registry and Integration

### Current finding

`workflow_context_dialogue` is an implemented ACP flow and is documented in `docs/WORKFLOW_CONTEXT_DIALOGUE_SLASH_OHDSI.md`, but it is missing from `docs/SERVICE_REGISTRY.yaml`. That appears to be a real omission rather than an intentional exclusion.

### Why the omission matters

- The flow exists in ACP runtime routing at `/flows/workflow_context_dialogue`.
- It has a real ACP implementation and is used by R wrappers, Strategus shells, and the demo shell.
- If it is missing from the registry, service discovery and integration metadata drift away from the actual implemented surface.

### What the registry does today

The service registry currently has a real but limited role:

- ACP `/services` uses `docs/SERVICE_REGISTRY.yaml` as a metadata source.
- ACP also keeps a separate hard-coded runtime `SERVICES` list.
- `/services` merges the registry-defined services with the runtime-defined services.
- If a flow exists at runtime but is missing from the registry, ACP still exposes it and emits a warning.
- The registry is also used for at least one real runtime configuration purpose outside ACP service listing: `mcp_server/study_agent_mcp/tools/_service_registry.py` reads validation metadata such as controlled identifier keys.

### Current conclusion

The registry is not currently the operational source of truth for implemented services.

It behaves more like:

- a declarative metadata overlay for service discovery
- a partial configuration source for selected validation behavior
- a completeness target for internal/external integration surfaces

This explains how a mature flow like `workflow_context_dialogue` could be missing without breaking the flow itself.

### Integration concern

If the registry is expected to support integration with other agentic tooling, then a missing flow is not a small documentation issue. It is evidence that the project currently has two service catalogs:

1. runtime truth in ACP code
2. declarative metadata truth in the registry

That split creates drift risk for:

- external orchestration
- service discovery
- client generation
- UI capability introspection
- cross-project integration contracts

### Recommendation for next session

Treat this as part of a broader integration design discussion, not just a one-off registry patch.

Topics to cover:

1. Should the registry become the single source of truth for services?
2. Should runtime `/services` be generated from the registry, or should the registry be generated from runtime definitions?
3. What contract fields are required for serious integration with other agentic tooling?
4. What parity checks or tests should be added so implemented flows cannot be omitted from the registry?
5. How should validation/configuration metadata be separated from service discovery metadata, if at all?

### Immediate factual note

Before editing the registry entry for `workflow_context_dialogue`, confirm:

- the exact MCP tool or prompt-bundle dependency used by the flow
- the exact normalized response shape returned by `run_workflow_context_dialogue_flow(...)`

Those should be captured precisely if and when the registry entry is added.

## Preparation Note: Flexible Cohort Acquisition In R Shells

### Current findings

There are two real gaps in the current R shell design.

1. The incidence shell supports importing existing cohort definitions from a database schema, but the CohortMethod shell does not expose that path.
2. The current Strategus runtime assumes one shared database-connection profile for multiple jobs that may need to be separate in real deployments.

Relevant evidence:

- The incidence shell has explicit source-mode selection and DB cohort import helpers in `R/slashOhdsiStrategusAssistant/R/strategus_incidence_shell.R`.
- The CohortMethod shell currently validates target, comparator, and outcome cohort IDs only against local index-backed cohort JSONs in `R/slashOhdsiStrategusAssistant/R/strategus_cohort_methods_shell.R`.
- Shared DB cohort import helpers already exist in `R/slashOhdsiStrategusAssistant/R/cohort_definition_import.R`.
- Shared Strategus DB connection creation currently centers on a single `strategus-db-details.json` via `createStrategusConnectionDetails()` in `R/slashOhdsiStrategusAssistant/R/db_details.R`.

### Additional deployment requirement

The shell design also needs to support users who already have cohort definition JSON artifacts outside the phenotype index and outside direct database import.

Important real-world cases:

- a user exported or copied a cohort definition JSON from Atlas and wants to point the shell at that file
- a user has one or more cohort definition JSON files from another project directory and wants to reuse them directly
- a user wants to skip study-intent splitting and recommendation entirely and move straight to providing target/comparator/outcome cohort definitions

### Current architectural problem

The current shells treat cohort selection too narrowly.

Today the workflow is biased toward:

- derive role statements from a study intent
- run ACP recommendation or manual ID entry
- resolve selected cohort IDs against local index-backed cohort JSONs

That model is too restrictive for:

- airgapped deployments
- Atlas-derived cohort JSON reuse
- project-to-project cohort reuse
- environments where the cohort-definition source DB differs from the OMOP/patient-data execution DB

### Proposed design shift

Reframe both shells around a shared cohort-acquisition stage rather than around recommendation-only cohort selection.

For each required role, the shell should support multiple cohort-definition acquisition modes:

- `recommend`: ACP recommendation plus index-backed cohort selection
- `database`: import an existing cohort definition from a database schema exposing `cohort_definition` plus `cohort_definition_details`
- `file`: import a single local cohort definition JSON file
- `directory`: choose from a directory of cohort definition JSON files or imported project artifacts
- `reuse`: reuse already normalized local cohort-definition artifacts in the current workflow directory

The key simplification is that all of these sources should normalize into the same local managed artifact format before downstream workflow generation continues.

### Normalized cohort artifact model

Each acquired cohort definition should be represented locally with consistent metadata, regardless of source.

Suggested metadata fields:

- `source_type`: `index` | `database` | `file` | `directory` | `reuse`
- `source_id`
- `source_path`
- `source_schema`
- `cohort_definition_id`
- `cohort_name`
- `logic_description`
- `cache_path`
- `role`

This extends the same general pattern already used for database imports in `cohort_definition_import.R` and the incidence-shell selection records.

### Intent-split and recommendation should become optional earlier

The shells should expose an explicit workflow-entry mode instead of making users discover skip behavior only later.

Recommended entry modes:

1. `guided`
   - derive role statements from study intent
   - continue into cohort acquisition per role
2. `semi_guided`
   - user enters role statements manually
   - skip ACP intent split
   - continue into cohort acquisition per role
3. `direct`
   - skip study-intent splitting and role-statement derivation entirely
   - go straight to cohort acquisition per role

This should apply to both shells:

- CohortMethod: target, comparator, outcome
- Incidence: target, outcome

### Separate database connection roles

Treat these as separate first-class configuration surfaces.

1. Execution DB connection
- used by generated Strategus scripts
- used for CDM / work / results / vocabulary access
- used for diagnostics and cohort-method execution
- should continue to use `strategus-db-details.json`

2. Cohort source DB connection
- used only to import existing cohort definitions from a database schema
- should use a separate file such as `strategus-cohort-source-db-details.json`

Do not overload one JSON file with both roles. The airgapped deployment case is a strong reason to keep them separate:

- cohort-definition source DB may be postgres with username/password
- patient/work/results execution DB may be SQL Server with Windows auth

### Important additional connection nuance

There is also an ACP/MCP-side OMOP connectivity surface used by Keeper profile generation.

That means there are effectively three relevant connection concepts in some deployments:

- R Strategus execution DB
- cohort-definition source DB
- MCP OMOP DB used by Keeper flows

The shells and docs should make this distinction clearer, especially because Keeper profile generation needs to point at the same effective cohort/work database context used by the generated workflow artifacts.

### Shared helper direction

Do not duplicate source-mode logic separately in each shell.

Recommended shared helper areas:

- source-mode prompt / dispatch
- file import helper
- directory import helper
- database import helper reuse from `cohort_definition_import.R`
- cohort-definition validation and normalization
- selection-record metadata helpers

The incidence shell already provides useful patterns for:

- `choose_selection_source_mode()`
- `selection_record_from_recommendation()`
- `selection_record_from_import()`
- `imported-cohort-definitions/` caching

These should be generalized and reused by the CohortMethod shell rather than reimplemented from scratch.

### Recommended implementation phases

1. Introduce a shared cohort-acquisition abstraction
- shared source modes
- shared normalized artifact metadata
- shared cache conventions

2. Add local file and directory acquisition modes first
- lower operational complexity than DB import
- immediately useful in airgapped settings
- supports Atlas-export and cross-project reuse scenarios

3. Add separate cohort-source DB config support
- introduce `strategus-cohort-source-db-details.json`
- reuse `cohort_definition_import.R`
- wire DB cohort import into the CohortMethod shell

4. Move intent split behind an explicit shell-start mode choice
- `guided`
- `semi_guided`
- `direct`

5. Update docs and state/resume behavior
- document the new acquisition modes
- document the split DB configuration roles
- persist normalized cohort-source metadata so resume and inspection remain coherent

### Practical UX recommendation

Keep prompts shallow.

For each role, the shell should ask only one initial acquisition question, for example:

- `Source for target cohort [Enter=recommend, db=database, file=JSON file, dir=directory, reuse=existing local]:`

Then branch only into the prompts required for that mode.

Defaults should follow the shell-start mode:

- `guided` defaults to `recommend`
- `direct` defaults to `file` or `dir`
- if reusable local artifacts already exist, surface `reuse` clearly

### Important behavioral decision to preserve clarity

When a cohort definition is imported from a database, file, or directory and later modified by shell-side improvement steps, the shell should make it explicit that it is editing a local managed working copy, not mutating the upstream Atlas definition or the original source file automatically.

### Recommendation for next implementation session

Treat this as a shared shell-design improvement, not a one-off CohortMethod patch.

Immediate concrete target:

1. define the normalized cohort-acquisition model
2. add file / directory acquisition support in shared helpers
3. add separate cohort-source DB config support
4. port database acquisition into the CohortMethod shell using the incidence-shell pattern
5. only then refine the shell-start mode UX for optional intent splitting
