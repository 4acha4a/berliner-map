import logging

from app.privacy import IdentificationAccessFilter, suppress_identification_access_logs


def test_identification_access_logs_are_suppressed():
    filter_ = IdentificationAccessFilter()
    for path in ("/api/v1/sectors/identify?lat=52.52&lng=13.405", "/api/v1/sectors/identify", "/api/v1/sectors/identify/?lat=0&lng=0"):
        record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, "%s %s %s %s %s", ("client", "GET", path, "1.1", 200), None)
        assert not filter_.filter(record)
    record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, "%s %s %s %s %s", ("client", "GET", "/api/v1/health", "1.1", 200), None)
    assert filter_.filter(record)


def test_filter_installation_is_idempotent():
    suppress_identification_access_logs()
    suppress_identification_access_logs()
    assert sum(isinstance(item, IdentificationAccessFilter) for item in logging.getLogger("uvicorn.access").filters) == 1


def test_database_settings_mask_credentials_and_hide_validation_input(monkeypatch):
    import json
    import pytest
    from pydantic import ValidationError
    from app.config import Settings

    monkeypatch.delenv("DATABASE_URL", raising=False)
    secret = "DummySettingsPassword_39"
    url = f"postgresql+psycopg://tester:{secret}@localhost/example"
    settings = Settings(database_url=url, _env_file=None)
    assert settings.database_url.get_secret_value() == url
    assert secret not in repr(settings)
    assert secret not in str(settings.model_dump())
    assert secret not in settings.model_dump_json()
    with pytest.raises(ValidationError) as error:
        Settings(database_url={"password": secret}, _env_file=None)
    assert secret not in str(error.value)
    assert secret not in json.dumps(settings.model_dump(mode="json"))


def test_database_password_redacted_from_logging_arguments_and_chained_tracebacks(monkeypatch):
    import io
    from app.privacy import install_database_redaction

    secret = "DummyLoggingPassword_72"
    url = f"postgresql+psycopg://tester:{secret}@localhost/example"
    monkeypatch.setenv("DATABASE_URL", url)
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    logger = logging.getLogger("test.database.redaction")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    try:
        install_database_redaction()
        logger.info("Connection %s; password=%s", url, secret)
        logger.info("Password %(password)s", {"password": secret})
        logger.info({"nested": [url, {"password": secret}]})
        try:
            try:
                raise ValueError(f"Cannot connect with {url}")
            except ValueError as error:
                raise RuntimeError(f"Failed with {secret}") from error
        except RuntimeError:
            logger.exception("Database failure")
        rendered = output.getvalue()
        assert secret not in rendered
        assert url not in rendered
        assert "[REDACTED]" in rendered
        assert "ValueError" in rendered
        assert "RuntimeError" in rendered
        assert "Traceback" in rendered
    finally:
        logger.removeHandler(handler)


def test_encoded_and_unregistered_url_passwords_are_redacted(monkeypatch):
    from urllib.parse import quote
    from app.privacy import redact_database_secrets

    secret = "DummyEncoded!Password@73"
    encoded = quote(secret, safe="")
    monkeypatch.setenv("DATABASE_URL", f"postgresql+psycopg://tester:{encoded}@localhost/example")
    assert secret not in redact_database_secrets(f"password={secret}")
    assert encoded not in redact_database_secrets(f"password={encoded}")
    assert "UnregisteredDummyPassword" not in redact_database_secrets(
        "postgresql://user:UnregisteredDummyPassword@localhost/example")


def test_uvicorn_access_formatter_preserves_status_and_route_while_redacting(monkeypatch):
    from uvicorn.logging import AccessFormatter
    from app.privacy import install_database_redaction

    secret = "DummyAccessPassword_84"
    monkeypatch.setenv("POSTGRES_PASSWORD", secret)
    install_database_redaction()
    record = logging.getLogger("uvicorn.access").makeRecord(
        "uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
        ("client", "GET", f"/example?password={secret}", "1.1", 200), None)
    rendered = AccessFormatter('%(client_addr)s - "%(request_line)s" %(status_code)s', use_colors=False).format(record)
    assert secret not in rendered
    assert "200" in rendered
    assert "/example" in rendered


def test_unhandled_exception_hook_redacts_cli_tracebacks(monkeypatch):
    import io
    import sys
    from app.privacy import install_database_redaction

    secret = "DummyCliPassword_95"
    monkeypatch.setenv("POSTGRES_PASSWORD", secret)
    output = io.StringIO()
    monkeypatch.setattr(sys, "stderr", output)
    install_database_redaction()
    hook = sys.excepthook
    install_database_redaction()
    assert sys.excepthook is hook
    try:
        raise RuntimeError(f"Startup failed with {secret}")
    except RuntimeError:
        sys.excepthook(*sys.exc_info())
    assert secret not in output.getvalue()
    assert "RuntimeError" in output.getvalue()
    assert "[REDACTED]" in output.getvalue()


def test_preformatted_escaped_passwords_are_redacted(monkeypatch):
    import json
    from app.privacy import redact_database_secrets

    secret = 'Dummy\\Escaped"Password_28'
    monkeypatch.setenv("POSTGRES_PASSWORD", secret)
    assert secret not in redact_database_secrets(secret)
    assert json.dumps(secret)[1:-1] not in redact_database_secrets(json.dumps(secret))
    assert repr(secret)[1:-1] not in redact_database_secrets(repr(secret))
