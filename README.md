# Study Design Assistant - proof of concept - MCP + ACP  

This is a complete refactoring of the initial proof of concept to concretely advance the specification of the architecture (see the [README.md on the main branch](https://github.com/OHDSI/StudyAgent/blob/main/README.md)) 

A) Study Agent (ACP server)

owns: conversation, permission prompts, “apply changes?”, file edits, audit trail

talks to: model providers (OpenAI, local, etc.)

calls: MCP tools

B) Study Tools (MCP servers)

expose: cohort_lint, concept_set_diff, phenotype_recommendations, phenotype_improvements

pure/portable; no local file access unless explicitly designed for it

This is the same overall direction you’re seeing in ACP ecosystem work: ACP agents commonly support “client MCP servers” to expand tool availability
