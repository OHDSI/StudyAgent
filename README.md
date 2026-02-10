# Study Design Assistant

### Overview 

This project seeks to develop an AI Study Agent to support OHDSI researchers to more rapidly, accurately, and reproducibly determine research feasibility, design research studies, and execute them. The set of services provided by the Study Agent will help a researcher go from a study idea to a well-specified research question, and then from a research question to a computable study specification, complete with computable outcome and exposure phenotypes and parameters for executing the study.


### Preliminary Note and initial roadmap
This project is in a design phase. Check out the tag `proof_of_concept` for the code for the initial coded proof of concepts such as shown [in this video](https://pitt.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=70502f91-3594-4cb6-b776-b3bd012cf637). See [this branch](https://github.com/OHDSI/StudyAgent/blob/proof-of-concept-mcp-plus-acp/) for demonstration of clean separation between an ACP server (agent UX + policy) and MCP servers (tools). It demonstrates how an interactive client can rely on the emerging [Agent Client Protocol](https://agentclientprotocol.com/overview/introduction) (ACP) for orchestration while keeping tool logic portable and reusable via MCP. These illustrate part of the main architectural concepts. The steps in process now are 1) fleshing out a much larger set of potential Study Agent services, and 2) building out more completely two initial service `phenotype_recommendations` and `phenotype_improvements`.

#### Want to contribute? 

Here are some ways:
- Create a for of the projct, branch the new project's main branch, edit the README.md and do a pull request back this main branch. Your changes could be integrated very quickly that way!
- Join the [discussion on the OHDSI Forums](https://forums.ohdsi.org/t/seeking-input-on-services-that-the-ohdsi-study-agent-will-provide/24890)
- Attend the Generative AI WG monthly calls (currently 2nd Tuesdays of the month at 12 Eastern) or reach out directly to Rich Boyce on the OHDSI Teams.
- You may also post "question" issues on this repo.

### Design 

The Study Agent will be service-architected, providing AI-informed services to other tools used by researchers through standardized API calls. This will enable integration of the Study Agent into a variety of tools used by OHDSI researchers. The study agent will build on open-source tools and data models from the Observational Health Data Sciences and Informatics (OHDSI) collaborative. See below for a more technical discussion of the initial architecture. 

### Envisioned behavior/role

The Study Agent will behave analogously to modern coding agents which are AI-powered tools designed to assist software developers throughout the development lifecycle. The tools leverage natural language processing and machine learning to assist with generating code development plans, code snippets, and automate repetitive tasks. These agents can suggest optimized solutions, detect bugs, and provide real-time debugging assistance, reducing development time and improving code quality. They integrate seamlessly with IDEs and version control systems, enabling developers to write, test, and deploy code more efficiently. Additionally, coding agents support learning by explaining complex concepts and offering best practices, making them valuable for both novice and experienced programmers.

In a similar way, the Study Agent, through the services it provides, will assist OHDSI researchers throughout the study feasibility, design, and execution lifecycles. It will leverage modern multi-modal transformer-based neural network models and protocols, including as Model Context Protocol (MCP) and Agent Client Protocol (ACP), to understand the user’s study intent and generate concept sets, cohort definitions, diagnostics, extract features, and write a study specification. The Study Agent will also suggest improvements to study artifacts based on summary data about the data source, documentation on ETL processes, and known issues. Additionally, the Study Agent will support learning by offering recommended approaches to generating evidence from observational retrospective data. This will help lower the high technical barrier that exists between clinical domain experts and data scientists.  

### Guardrails

It's important to note that the study agent services will never receive row level patient data. Rather the architecture will be such that the tools that call the services (e.g., R or Atlas) will have authorized access to the data while the information that's passed through the Study Agent services will restricted to be descriptive and aggregated. This will lower the risk of data breaches while enabling a variety of different models, or model configurations (e.g., LoRA tunings) to be used or swapped out depending on the service use case.

In one mode of operation, the study agent will have access to output from Data Quality Dashboard, Achilles Heel data quality checks, and Achilles data source characterizations over one or more sources that a user intends to use within a study.  In this mode, specifically designed OHDSI study agent MCP tools will derive insights from those sources based on the user's study intent.  This is important because it will make the information in the characterizations and QC reports more relevant and actionable to users than static and broad-scope reports (current state). 

### Initial Services (draft!)

Below is the first draft of study agent services based on what I am calling "study intent" (a narrative description of the research question) : 

NOTE: at no time for any of the services would an LLM see row-level data (this can be accomplished through the careful use of protocols (MCP for tooling, Agent Client Protocol for OHDSI tool <-> LLM communication) and a security layer). 

#### High level Conceptual
* `protocol_generator`: given the PICO/TAR for a study intent, **write a templated protocol**
* `background_writer`: based on PICO/TAR and hypothesis **do (systematic) research and write document justifying study**
* `protocol_critique`: given a protocol, **write a critique reviewing the protocol for required components and consistency**

#### High level operational
* `strategus_*`: compose/compare/edit/critique/debug study specification **all of these services edit Strategus .json)** and may utilize one or more of the other services listed below.


#### Search and suggest
* `phenotype_recommendations`: Suggest relevant phenotypes from the thousands of phenotype definitions available from various credible sources (OHDSI Phenotype library, VA CIPHER, a user's own Atlas cohort definitions) for the study intent. **Write cohort definition artifacts** for any phenotype definitions the user accepts as relecant.
* `phenotype_improvements` or `phenotype fit`: Review *already selected* phenotypes for improvements against study intent. Of the use accepts, **write the new artifacts** (JSON cohort definitions or Atlas cohort records)
* `concept_set_recommendations`:Based on a phenotype or covariate relevant to the study intent for which a cohort definition has not been defined, suggest relevant concept sets from sources available to the user (concept set JSON, Atlas) to use in a new cohort definition. **If the user accepts, create the concept set artifacts.** 
* `propose_negative_control_outcomes`: Given a target (and optionally a comparator) recommend outcomes that are unlikely to be caused by the target (nor by the comparator). **If the user accepts, create the cohort definitions for the negative control outcomes**
* `propose_comparator`: Given a target, propose a comparator. This could leverage the [OHDSI Comparator Selector tool](https://data.ohdsi.org/ComparatorSelectionExplorer/). **If the user accepts, create the cohort definition for the comparator**


#### Study component testing, improvement, and linting  
* `propose_concept_set_diff`: Review concept set for gaps and inconsistencies given the study intent.  **If the user accepts, patch the concept set artifacts.**
* `phenotype_characterize`: **Generate R code** that the user will run, or request the user's permission to **run Atlas services**, to characterize the population of individuals that match a selected phenotype (i.e., same as a cohort characterization)  
* `phenotype_data_quality_review`: Check for likely issues with a set of phenotype definitions and propose mitigation based on information from the Data Quality Dashboard, Achilles Heel data quality checks, and Achilles data source characterizations over the one or more sources that a user intends to use within the study. For issues that the use acknowledges ,  **patch the artifacts** (JSON cohort definitions or Atlas cohort records)
* `phenotype_dataset_profiler`: **Generate R code** to execute a given phenotype definition on multiple datasets (possibly using [Cohort Diagnostics](https://ohdsi.github.io/CohortDiagnostics/)) and **write an brief summary** that compares which phenotype definition elements cause the biggest differences in variation in cohort size (CohortDiagnostics)
* `phenotype_validation_review`: Generate Keeper code for the use to run that will enable them to review case samples from the population of patients meeting a selected phenotype definition. **The agen will write the code to make the sample** such that the user can compare performance characteristics with their sample to known for the phenotype from other sources where it was tested.   
* `cohort_definition_build`: **Write the Capr code** for a use to define a phenotype or covariate relevant to the study intent for which a cohort definition has not yet been defined.
* `cohort_definition_lint`: Review cohort JSON for general design issues (washout/time-at-risk, inverted windows, empty or conflicting criteria) and for execution efficiency (unnecessary criterion nesting, sub-optimal logical ordering of criteria) and **write the proposed patches** (new JSON or new cohort definitions in Atlas)
* `review_negative_control`: Given a target and an outcome, judge whether they are unlikely to be causally related. **Provide a clear explanation for the judgement with accurate citations**

### Initial Architecture - Existing OHDSI tools + Agent Client Protocol (ACP) + Model Context Protocol (MCP)

Research datasets are messy and require multiple tools to work with. There already exists a rich and effective set of tools to assist, including the OMOP CDM, standardized vocabulary, OHDSI HADES (R-based), Atlas/WebAPI (Java and web services), and a growing set of Python tools. One of the Study Agent's primary purposes is to help users orchistrate these tools more effectively and with greater insight into considerations that apply to the data sources they work with. Architecturally, this breaks down into two separate but related concerns: 

1) The interaction between an interactive client (e.g., an R session within RStudio, use of Atlas) and an agent that streams updates, request permissions, etc. To address this concern, we will use [Agent Client Protocol](https://agentclientprotocol.com/overview/introduction) to control the:
   - conversation/session lifecycle
   - streaming updates (“I’m thinking / running / waiting…”)
   - permission prompts (“may I run this?”)
   - edits to local artifacts (files, notebooks, reports)
  
2) How the AI model (we don't dictate which one!) calls tools/resources/prompts from external systems. This is the role of the [Model Context Protocol](https://modelcontextprotocol.io/docs/getting-started/intro) , which uses JSON-RPC over stdio or Streamable HTTP as a tool bus for:
   - database query tools
   - R session tools
   - cohort definition / harmonization utilities
   - access to safey summaries of governed datasets

To summarize: 
- ACP defines the agent interface to the user environment, providing a consistent interactive agent experience across those environments
- MCP defines the tool interface to external capabilities, providing a consistent tool contract to reuse across agents and institutions.

Practically speaking, **the Study Agent is an ACP server that is also an MCP client**. The tool surface area resides in project MCP servers while the internal orchestration logic resides in the AI mode, the project ACP server mostly provides transport + UX contract. 

Note that, because ACP is early in development and evolving, we will treat ACP as an integration layer we can later swap or bridge rather than an unchangable foundation. 




