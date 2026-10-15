from study_agent_core.workflow_context import MAX_CONTEXT_STRING_CHARS, normalize_workflow_context


def test_normalize_workflow_context_keeps_legacy_fields_and_bounds_text():
    result = normalize_workflow_context({"step_label": "Review", "legacy": "x" * (MAX_CONTEXT_STRING_CHARS + 10)})
    assert result["step_label"] == "Review"
    assert result["legacy"].endswith("[truncated 10 chars]")


def test_normalize_workflow_context_bounds_lists_and_depth():
    result = normalize_workflow_context({"candidates": list(range(30)), "deep": {"a": {"b": {"c": {"d": "value"}}}}})
    assert len(result["candidates"]) == 21
    assert result["deep"]["a"]["b"]["c"] == "[omitted: maximum context depth reached]"
