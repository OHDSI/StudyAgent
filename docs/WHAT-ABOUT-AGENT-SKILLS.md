## How does Study Agent relate to Agent Skills (e.g., SKILL.md)?

Codex, I have a question - this project is build with an ACP/MCP
architecture to provide both the flexibility of organizing MCP tools
into different ACP managed agentic flows. However, many folks are
interested in some of the functionality that is and will be
implemented in this project to be adapted as skills by coding agents
like codex and claude. My understanding of that process typically
followed for skills adoption is to write a skill.md file and possibly
add scripts in a sub-folder that the agent is instructed it may use to
accomplish certain tasks. What are your thoughts about how this
framework could be related to agent skills using that kind of
approach?

───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
```
• Yes—these fit together very naturally, but they solve different layers of the system.

  - MCP exposes granular capabilities and deterministic tools.
  - ACP owns the safe, domain-specific orchestration of those tools into supported flows.
  - A skill is the agent-facing operating manual: when to use a capability, what inputs to collect, what safety checks apply, and how to invoke it.

  For this project, I would generally make skills call ACP flows, not
  compose raw MCP tools themselves. That preserves the orchestration,
  validation, prompt bundles, and PHI/PII guardrails you have already
  established. A coding agent skill should be a thin adapter, not a
  second implementation of clinical workflow logic.

  A useful shape would be:

  .agents/skills/
    ohdsi-phenotype-design/
      SKILL.md
      scripts/
        invoke_acp_flow.py
      references/
        flow-contracts.md
        safety-boundaries.md

  The skill would tell Codex or Claude, for example:

  - Trigger when asked to turn a study question into phenotype recommendations or a phenotype intent split.
  - Collect only safe, non-PHI input.
  - Confirm ACP is reachable and configured.
  - Invoke /flows/phenotype_intent_split or /flows/phenotype_recommendation.
  - Present the returned result as a draft for human clinical/OHDSI review.
  - Do not bypass Keeper sanitization or send row-level data directly to an LLM.

  I would start with a small set of focused skills rather than one “Study Agent” mega-skill:

  1. ohdsi-phenotype-design — intent splitting, recommendation, and improvement.
  2. ohdsi-phenotype-validation — explicitly routes through the ACP/Keeper-safe workflow.
  3. ohdsi-strategus-study-design — guides creation/review of Strategus artifacts, likely with the R layer remaining separately configured.
  4. study-agent-deployment-diagnostics — config validation, service health, and safe smoke-test guidance.

  The important design rule is: keep the authoritative behavior in
  this repository’s ACP/MCP code and maintained prompt/config
  artifacts; keep skills declarative and thin. That prevents logic and
  safety policies from drifting across Codex, Claude, and deployed
  Study Agent services.

  Codex’s current skill model supports exactly this folder pattern: a
  SKILL.md with metadata plus optional scripts, references, and
  assets. Repo-scoped skills can live under .agents/skills, while a
  plugin is the better distribution mechanism once you want others to
  install a curated set. OpenAI’s skill documentation
  (https://learn.chatgpt.com/docs/build-skills) also recommends
  focused, single-job skills with clear trigger descriptions.

  I think this could become a particularly strong “agentic client”
  layer for Study Agent: users get the convenience of skills, while your
  ACP remains the durable, deployable clinical-workflow boundary.
 ```