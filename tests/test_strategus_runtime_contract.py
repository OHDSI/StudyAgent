import json

from _repo_paths import repo_path


PACKAGE_ROOT = repo_path("R", "slashOhdsiStrategusAssistant")
PROFILE = PACKAGE_ROOT / "inst" / "hades-runtime.json"
RUNTIME_SOURCE = PACKAGE_ROOT / "R" / "runtime_compatibility.R"
INCIDENCE_SOURCE = PACKAGE_ROOT / "R" / "strategus_incidence_shell.R"
COHORT_METHOD_SOURCE = PACKAGE_ROOT / "R" / "strategus_cohort_methods_shell.R"


def test_runtime_profile_is_lockfile_style_and_declares_current_hades_stack() -> None:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))

    assert profile["profile"] == "hades-r4.5.3-2026-08-17"
    assert profile["r_version"] == ">= 4.4.0"
    assert profile["packages"]["Strategus"] == "1.5.0"
    assert profile["packages"]["Characterization"] == "4.0.0"
    assert profile["packages"]["CohortMethod"] == "6.0.3"


def test_shells_and_generated_specifications_enforce_runtime_profile() -> None:
    runtime_source = RUNTIME_SOURCE.read_text(encoding="utf-8")
    incidence_source = INCIDENCE_SOURCE.read_text(encoding="utf-8")
    cohort_method_source = COHORT_METHOD_SOURCE.read_text(encoding="utf-8")

    assert "checkStrategusRuntime <- function(strict = TRUE)" in runtime_source
    assert "strategusRuntimeReport <- function()" in runtime_source

    for source in (incidence_source, cohort_method_source):
        assert "checkRuntime = TRUE" in source
        assert "if (isTRUE(checkRuntime)) checkStrategusRuntime()" in source
        assert "runtime_report <- slashOhdsiStrategusAssistant::checkStrategusRuntime()" in source
        assert "hades-runtime.json" in source


def test_cohort_method_uses_current_characterization_settings_adapter() -> None:
    source = COHORT_METHOD_SOURCE.read_text(encoding="utf-8")

    assert "Characterization::createStudyPopulationSettings(" in source
    assert "Characterization::createTargetBaselineSettings(" in source
    assert "characterizationModule$.__enclos_env__$super$createModuleSpecifications(" in source
    assert "trimByPsToEquipoiseArgs" not in source


def test_artifact_browser_previews_the_dropdown_selection() -> None:
    browser = repo_path(
        "R", "slashOhdsiStrategusAssistant", "R", "strategus_artifact_browser.R"
    ).read_text(encoding="utf-8")
    incidence = INCIDENCE_SOURCE.read_text(encoding="utf-8")

    assert 'verbatimTextOutput("selected_artifact_preview")' in browser
    assert 'output$selected_artifact_preview <- shiny::renderText(preview_artifact(input$artifact))' in browser
    assert "Artifact browser (optional, run in second R session):" in incidence
    assert "Rscript scripts/09_launch_artifact_browser.R" in incidence
