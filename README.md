# Study Design Assistant

### Note

This project is in a design phase. Check out branches for initial coded proof of concepts such as shown [in this video](https://pitt.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=70502f91-3594-4cb6-b776-b3bd012cf637). You may post question issues to this repo as well.   

### Overview 

This project seeks to develop an AI Study Agent to support OHDSI researchers to more rapidly, accurately, and reproducibly determine research feasibility, design research studies, and execute them. The set of services provided by the Study Agent will help a researcher go from a study idea to a well-specified research question, and then from a research question to a computable study specification, complete with computable outcome and exposure phenotypes and parameters for executing the study.

### Design 

The Study Agent will be service-architected, providing AI-informed services to other tools used by researchers through standardized API calls. This will enable integration of the Study Agent into a variety of tools used by OHDSI researchers. The study agent will build on open-source tools and data models from the Observational Health Data Sciences and Informatics (OHDSI) collaborative. 

### Envisioned behavior/role

The Study Agent will behave analogously to modern coding agents which are AI-powered tools designed to assist software developers throughout the development lifecycle. The tools leverage natural language processing and machine learning to assist with generating code development plans, code snippets, and automate repetitive tasks. These agents can suggest optimized solutions, detect bugs, and provide real-time debugging assistance, reducing development time and improving code quality. They integrate seamlessly with IDEs and version control systems, enabling developers to write, test, and deploy code more efficiently. Additionally, coding agents support learning by explaining complex concepts and offering best practices, making them valuable for both novice and experienced programmers.

In a similar way, the Study Agent, through the services it provides, will assist OHDSI researchers throughout the study feasibility, design, and execution lifecycles. It will leverage modern multi-modal transformer-based neural network models and protocols, including as Model Context Protocol (MCP) and Agent Client Protocol (ACP), to understand the user’s study intent and generate concept sets, cohort definitions, diagnostics, extract features, and write a study specification. The Study Agent will also suggest improvements to study artifacts based on summary data about the data source, documentation on ETL processes, and known issues. Additionally, the Study Agent will support learning by offering recommended approaches to generating evidence from observational retrospective data. This will help lower the high technical barrier that exists between clinical domain experts and data scientists.  

### Guardrails

It's important to note that the study agent services will never receive row level patient data. Rather the architecture will be such that the tools that call the services (e.g., R or Atlas) will have authorized access to the data while the information that's passed through the Study Agent services will restricted to be descriptive and aggregated. This will lower the risk of data breaches while enabling a variety of different models, or model configurations (e.g., LoRA tunings) to be used or swapped out depending on the service use case.
