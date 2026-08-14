import logging

from study_agent_core.logging_utils import configure_service_logger, format_log_kv, sanitize_log_value


def test_configure_service_logger_writes_to_file(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    # An explicit file takes precedence over a directory by design. Clear a
    # deployment-level setting so this test exercises the directory fallback.
    monkeypatch.delenv("ACP_LOG_FILE", raising=False)
    monkeypatch.setenv("STUDY_AGENT_LOG_DIR", str(log_dir))
    monkeypatch.setenv("ACP_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ACP_LOG_TO_CONSOLE", "0")

    logger = configure_service_logger(
        "ACP",
        "study_agent.test.acp",
        default_level="INFO",
        stream="stderr",
        default_filename="study-agent-acp.log",
    )
    logger.info("hello file logger")

    log_file = log_dir / "study-agent-acp.log"
    assert log_file.exists()
    assert "hello file logger" in log_file.read_text(encoding="utf-8")


def test_configure_service_logger_off_disables_logger(monkeypatch):
    monkeypatch.setenv("ACP_LOG_LEVEL", "OFF")

    logger = configure_service_logger(
        "ACP",
        "study_agent.test.acp.off",
        default_level="INFO",
        stream="stderr",
        default_filename="study-agent-acp.log",
    )

    assert logger.disabled is True
    assert logger.handlers == []

    logger.disabled = False
    logger.handlers.clear()
    logging.getLogger("study_agent.test.acp.off").handlers.clear()


def test_sanitize_log_value_redacts_credentials_and_phi():
    payload = {
        "database_url": "postgresql://alice:supersecret@db.internal:5432/omop",
        "authorization": "Bearer abc.def.ghi",
        "patient_email": "patient@example.com",
        "dob": "1984-07-15",
        "person_id": "12345",
    }

    sanitized = sanitize_log_value(payload)

    assert sanitized["database_url"] == "[REDACTED]"
    assert sanitized["authorization"] == "[REDACTED]"
    assert sanitized["patient_email"] == "[REDACTED_EMAIL]"
    assert sanitized["dob"] == "[REDACTED_DATE]"
    assert sanitized["person_id"] == "[REDACTED]"


def test_format_log_kv_redacts_helper_fields():
    rendered = format_log_kv(
        {
            "password": "secret123",
            "embed_url": "https://user:pass@example.com/embed",
            "owner_email": "owner@example.com",
        }
    )

    assert "secret123" not in rendered
    assert "user:pass@" not in rendered
    assert "owner@example.com" not in rendered
    assert "[REDACTED]" in rendered
    assert "[REDACTED_CREDENTIALS]" in rendered
    assert "[REDACTED_EMAIL]" in rendered


def test_configure_service_logger_redacts_formatted_args_in_file(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    # An explicit file takes precedence over a directory by design. Clear a
    # deployment-level setting so this test exercises the directory fallback.
    monkeypatch.delenv("ACP_LOG_FILE", raising=False)
    monkeypatch.setenv("STUDY_AGENT_LOG_DIR", str(log_dir))
    monkeypatch.setenv("ACP_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ACP_LOG_TO_CONSOLE", "0")

    logger = configure_service_logger(
        "ACP",
        "study_agent.test.acp.redaction",
        default_level="INFO",
        stream="stderr",
        default_filename="study-agent-acp.log",
    )
    logger.info(
        "dsn=%s auth=%s patient_email=%s dob=%s payload=%s",
        "postgresql://alice:supersecret@db.internal:5432/omop",
        "Bearer abc.def.ghi",
        "patient@example.com",
        "1984-07-15",
        {"password": "swordfish", "person_id": "12345"},
    )

    contents = (log_dir / "study-agent-acp.log").read_text(encoding="utf-8")
    assert "supersecret" not in contents
    assert "abc.def.ghi" not in contents
    assert "patient@example.com" not in contents
    assert "1984-07-15" not in contents
    assert "swordfish" not in contents
    assert "12345" not in contents
    assert "[REDACTED_CREDENTIALS]" in contents
    assert "[REDACTED_TOKEN]" in contents
    assert "[REDACTED_EMAIL]" in contents
    assert "[REDACTED_DATE]" in contents
    assert "[REDACTED]" in contents
