**Overview**
This document defines the `phenotype_recommendation` design in the ACP + MCP architecture. The MCP service owns the phenotype index on local disk and exposes read-only retrieval tools. ACP orchestrates retrieval, multiple LLM calls, deterministic shortlist enforcement, and final response assembly. Core remains pure and deterministic for schema validation and final filtering.

The current ACP request accepts these commonly used fields:
- required: `study_intent`
- retrieval controls: `top_k`, `candidate_offset`
- planning / output controls: `candidate_limit`, `max_results`
- optional routing / filtering: `recommendation_role`, `workflow_type`, `exclude_metadata`


```mermaid
sequenceDiagram
    autonumber
    actor U as User / Client
    participant A as ACP HTTP Server
    participant G as ACP StudyAgent
    participant M as MCP Server
    participant L as LLM
    participant C as Core Validators

    U->>A: POST /flows/phenotype_recommendation<br/>{study_intent, top_k, candidate_offset, max_results, candidate_limit, ...}
    A->>G: run_phenotype_recommendation_flow(...)

    Note over G: Stage 1: Candidate retrieval
    G->>M: phenotype_search(query=study_intent, top_k, offset=candidate_offset)
    M-->>G: search results + scores<br/>(dense/sparse hybrid retrieval)
    G->>G: apply exclude_metadata filters

    Note over G: Stage 2: Intent-facet extraction
    G->>M: phenotype_prompt_bundle(task="phenotype_recommendation_intent_facets")
    M-->>G: overview + spec + output_schema
    G->>L: intent facets prompt<br/>(study_intent only)
    L-->>G: {plan, intent_facets, reasoning_notes}
    G->>G: normalize intent facets and aliases

    Note over G: Stage 3: Planning shortlist
    G->>G: derive effective planning budget<br/>(candidate_limit, planning_window)
    G->>M: phenotype_fetch_summary(...) x N
    M-->>G: hydrated candidate summaries
    G->>G: rerank planning candidates using intent facets + metadata
    G->>G: derive planner-visible band<br/>(planning_top_band)
    G->>M: phenotype_prompt_bundle(task="phenotype_recommendation_plan")
    M-->>G: overview + spec + output_schema
    G->>L: planning prompt<br/>(study_intent + planner candidate band)
    L-->>G: {plan, shortlist_ids, needs_more_search, reasoning_notes}
    G->>C: phenotype_recommendation_plan(...)
    C-->>G: validated planning payload
    G->>G: enforce shortlist deterministically<br/>block unsafe rows, dedupe, suppress weak filler<br/>within strict_top_k enforcement pool
    G->>M: phenotype_fetch_summary(...) x shortlist
    M-->>G: hydrated shortlist rows
    G->>G: rebuild planning reasoning_notes from enforced shortlist

    Note over G: Stage 4: Final recommendation text
    G->>M: phenotype_prompt_bundle(task="phenotype_recommendations")
    M-->>G: overview + spec + output_schema
    G->>L: final recommendation prompt<br/>(study_intent + final compact candidates)
    L-->>G: {plan, phenotype_recommendations}

    Note over G: Stage 5: Deterministic finalization
    G->>G: validate LLM payload against shortlist/catalog
    G->>G: build deterministic final payload<br/>ids come from enforced shortlist, LLM supplies usable justifications
    G->>C: phenotype_recommendations(...)
    C-->>G: final grounded response
    G->>G: emit diagnostics including<br/>effective_limits and stage_counts

    G-->>A: {status, search, intent_facets, planning,<br/>recommendations, diagnostics}
    A-->>U: HTTP 200 JSON
```

A compact swimlane version with the main responsibility split:

```mermaid
flowchart LR
    subgraph User
        U1[Submit study intent and tuning controls]
    end

    subgraph ACP
        A1[HTTP flow handler]
        A2[Run phenotype recommendation flow]
        A3[Intent facet extraction]
        A4[Planning rerank and shortlist enforcement]
        A5[Final deterministic recommendation assembly]
        A6[Diagnostics and effective limits]
    end

    subgraph MCP
        M1[phenotype_search]
        M2[phenotype_fetch_summary]
        M3[phenotype_prompt_bundle]
    end

    subgraph LLM
        L1[Intent facets call]
        L2[Planning call]
        L3[Final recommendation call]
    end

    subgraph Core
        C1[Plan validator]
        C2[Final recommendation validator]
    end

    U1 --> A1
    A1 --> A2
    A2 --> M1
    M1 --> A3
    A3 --> M3
    M3 --> L1
    L1 --> A3
    A3 --> M2
    M2 --> A4
    A4 --> M3
    M3 --> L2
    L2 --> C1
    C1 --> A4
    A4 --> M2
    M2 --> A5
    A5 --> M3
    M3 --> L3
    L3 --> A5
    A5 --> C2
    C2 --> A6
    A6 --> A1
    A1 --> U1
```

A few implementation notes worth keeping in mind:
- MCP does not rank finally; it only retrieves candidates and prompt assets.
- ACP owns the real decision logic now: reranking, blocking, shortlist enforcement, dedupe, deterministic final ids.
- The final LLM call is advisory for text/justification, not for unconstrained id selection.
- ACP now reports compact guardrail diagnostics in `diagnostics.effective_limits` and `diagnostics.stage_counts` so testing tools can inspect planning and enforcement behavior without re-deriving those limits client-side.
