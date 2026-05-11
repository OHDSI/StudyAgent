from pathlib import Path


SOURCE = Path("R/slashOhdsiStrategusAssistant/R/strategus_incidence_shell.R")


def test_outcome_selection_state_is_initialized_before_target_mapping_prompt() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    init = source.index("selected_ids_outcome <- character(0)")
    first_target_prompt = source.index(
        'selected_outcome_ids = as.list(selected_ids_outcome %||% list())'
    )

    assert init < first_target_prompt
