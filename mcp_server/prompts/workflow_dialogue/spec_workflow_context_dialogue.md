Tool: workflow_context_dialogue
Output contract:
{
  "plan": "string <=300 chars",
  "answer": "string <=1200 chars",
  "current_step_guidance": ["string <=200 chars"],
  "cautions": ["string <=200 chars"],
  "suggested_next_actions": ["string <=200 chars"],
  "follow_up_plan": ["string <=200 chars"],
  "artifact_requests": [
    {
      "artifact_id": "string <=80 chars",
      "reason": "string <=200 chars",
      "permission_required": false
    }
  ]
}

### HEURISTICS/RULES
- Answer the user's question in the context of the provided study intent and current workflow step.
- Keep the answer advisory only; do not imply that any workflow choice or artifact has already changed.
- Use the current role and current_context only when they help answer the question.
- Prefer concrete guidance tied to the user's present step over general OHDSI background.
- The provided current_context is intentionally compact. Answer from it first.
- If additional evidence is needed, request at most 3 more artifacts using logical artifact ids from the provided requestable_artifact_ids or artifact_summary.
- Use artifact_requests only for targeted follow-up needs; do not ask for broad dumps of context.
- Set permission_required to true when the follow-up would likely require explicit user confirmation before loading or inspecting more data.
- Use sparse bullets in current_step_guidance, cautions, suggested_next_actions, and follow_up_plan.

Constraints:
- JSON only; no markdown/fences.
- Keep output < 10 KB.
