import shutil
import subprocess

import pytest

from _repo_paths import repo_path


SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "db_details.R")
COHORT_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "strategus_cohort_methods_shell.R")
INCIDENCE_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "strategus_incidence_shell.R")


def _run_r_or_skip(expression: str) -> subprocess.CompletedProcess[str]:
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")
    result = subprocess.run(["Rscript", "-e", expression], check=False, text=True, capture_output=True)
    if result.returncode == 42:
        pytest.skip(result.stderr.strip() or result.stdout.strip() or "required R package is not available")
    return result


def test_db_details_helper_supports_integrated_auth_and_jar_folder() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert 'authType' in source
    assert 'useWindowsAuth' in source
    assert 'DATABASECONNECTOR_JAR_FOLDER' in source
    assert 'do.call(DatabaseConnector::createConnectionDetails, args)' in source
    assert 'unless authType requests integrated Windows authentication' in source


def test_shell_seed_templates_include_auth_type_and_jar_folder() -> None:
    for source in (COHORT_SOURCE.read_text(encoding="utf-8"), INCIDENCE_SOURCE.read_text(encoding="utf-8")):
        assert 'authType = "username_password"' in source
        assert 'DATABASECONNECTOR_JAR_FOLDER = ""' in source


def test_integrated_auth_can_omit_user_and_password_when_databaseconnector_is_available() -> None:
    result = _run_r_or_skip(
        f"""
        if (!requireNamespace('DatabaseConnector', quietly = TRUE)) quit(status = 42)
        source('{SOURCE.as_posix()}')
        td <- createStrategusConnectionDetails(
          dbDetails = list(
            dbms = 'sql server',
            authType = 'windows',
            DB_SERVER = 'example-host',
            DB_PORT = '1433',
            DATABASECONNECTOR_JAR_FOLDER = tempdir(),
            extraSettings = ''
          )
        )
        stopifnot(!is.null(td))
        stopifnot(Sys.getenv('DATABASECONNECTOR_JAR_FOLDER') == tempdir())
        """
    )
    assert result.returncode == 0, result.stderr


def test_username_password_auth_still_requires_credentials() -> None:
    result = _run_r_or_skip(
        f"""
        if (!requireNamespace('DatabaseConnector', quietly = TRUE)) quit(status = 42)
        source('{SOURCE.as_posix()}')
        err <- tryCatch({{
          createStrategusConnectionDetails(
            dbDetails = list(
              dbms = 'postgresql',
              authType = 'username_password',
              DB_SERVER = 'example-host',
              DB_PORT = '5432'
            )
          )
          NULL
        }}, error = function(e) conditionMessage(e))
        if (is.null(err) || !grepl('Database credentials must be provided', err, fixed = TRUE)) quit(status = 1)
        """
    )
    assert result.returncode == 0, result.stderr
