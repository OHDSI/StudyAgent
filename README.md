# Study Design Assistant

### Note

This project is in a design phase. Check out branches for initial coded proof of concepts such as shown [in this video](https://pitt.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=70502f91-3594-4cb6-b776-b3bd012cf637). You may post question issues to this repo as well.   

### Overview 

This project seeks to develop an AI Study Agent to support OHDSI researchers to more rapidly, accurately, and reproducibly determine research feasibility, design research studies, and execute them. The set of services provided by the Study Agent will help a researcher go from a study idea to a well-specified research question, and then from a research question to a computable study specification, complete with computable outcome and exposure phenotypes and parameters for executing the study.

### Design 

The Study Agent will be service-architected, providing AI-informed services to other tools used by researchers through standardized API calls. This will enable integration of the Study Agent into a variety of tools used by OHDSI researchers. The study agent will build on open-source tools and data models from the Observational Health Data Sciences and Informatics (OHDSI) collaborative. See below for a more technical discussion of the initial architecture. 

### Envisioned behavior/role

The Study Agent will behave analogously to modern coding agents which are AI-powered tools designed to assist software developers throughout the development lifecycle. The tools leverage natural language processing and machine learning to assist with generating code development plans, code snippets, and automate repetitive tasks. These agents can suggest optimized solutions, detect bugs, and provide real-time debugging assistance, reducing development time and improving code quality. They integrate seamlessly with IDEs and version control systems, enabling developers to write, test, and deploy code more efficiently. Additionally, coding agents support learning by explaining complex concepts and offering best practices, making them valuable for both novice and experienced programmers.

In a similar way, the Study Agent, through the services it provides, will assist OHDSI researchers throughout the study feasibility, design, and execution lifecycles. It will leverage modern multi-modal transformer-based neural network models and protocols, including as Model Context Protocol (MCP) and Agent Client Protocol (ACP), to understand the user’s study intent and generate concept sets, cohort definitions, diagnostics, extract features, and write a study specification. The Study Agent will also suggest improvements to study artifacts based on summary data about the data source, documentation on ETL processes, and known issues. Additionally, the Study Agent will support learning by offering recommended approaches to generating evidence from observational retrospective data. This will help lower the high technical barrier that exists between clinical domain experts and data scientists.  

### Guardrails

It's important to note that the study agent services will never receive row level patient data. Rather the architecture will be such that the tools that call the services (e.g., R or Atlas) will have authorized access to the data while the information that's passed through the Study Agent services will restricted to be descriptive and aggregated. This will lower the risk of data breaches while enabling a variety of different models, or model configurations (e.g., LoRA tunings) to be used or swapped out depending on the service use case.

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




