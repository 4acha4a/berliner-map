"""Keep database credentials and identification coordinates out of logs."""
import json
import logging
import os
import re
import sys
import traceback
from urllib.parse import quote, unquote, urlsplit


class IdentificationAccessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Uvicorn access args: client, method, path with query, HTTP version, status.
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            return args[2].split("?", 1)[0].rstrip("/") != "/api/v1/sectors/identify"
        return True


def suppress_identification_access_logs() -> None:
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, IdentificationAccessFilter) for item in logger.filters):
        logger.addFilter(IdentificationAccessFilter())


# Installed before settings are read, including migration/import CLI processes.
_database_secrets: set[str] = set()
_database_url_pattern = re.compile(r"(postgres(?:ql)?(?:\+[a-zA-Z0-9_]+)?://[^\s/@:]+:)[^\s@]*(@)")


def _secret_variants(value: str) -> set[str]:
    return {value, quote(value, safe=""), repr(value)[1:-1], json.dumps(value)[1:-1]}


def register_database_url(value: str) -> None:
    _database_secrets.update(_secret_variants(value))
    try:
        password = urlsplit(value).password
    except ValueError:
        return
    if password:
        _database_secrets.update(_secret_variants(password) | _secret_variants(unquote(password)))


def redact_database_secrets(value: str) -> str:
    for name in ("DATABASE_URL", "TEST_DATABASE_URL"):
        if os.environ.get(name):
            register_database_url(os.environ[name])
    password = os.environ.get("POSTGRES_PASSWORD")
    secrets = _database_secrets | (_secret_variants(password) if password else set())
    for secret in sorted(secrets, key=len, reverse=True):
        if secret:
            value = value.replace(secret, "[REDACTED]")
    return _database_url_pattern.sub(r"\1[REDACTED]\2", value)


def _redact_argument(value):
    if isinstance(value, str):
        return redact_database_secrets(value)
    if isinstance(value, tuple):
        return tuple(_redact_argument(item) for item in value)
    if isinstance(value, list):
        return [_redact_argument(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact_argument(item) for key, item in value.items()}
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return redact_database_secrets(str(value))


def install_database_redaction() -> None:
    previous_factory = logging.getLogRecordFactory()
    if not getattr(previous_factory, "_database_redaction", False):
        def factory(*args, **kwargs):
            record = previous_factory(*args, **kwargs)
            # Preserve argument shapes required by Uvicorn's access formatter.
            record.msg = _redact_argument(record.msg)
            record.args = _redact_argument(record.args)
            if record.exc_info:
                record.exc_text = redact_database_secrets("".join(traceback.format_exception(*record.exc_info)))
                record.exc_info = None
            if record.stack_info:
                record.stack_info = redact_database_secrets(record.stack_info)
            return record
        factory._database_redaction = True
        logging.setLogRecordFactory(factory)

    if not getattr(sys.excepthook, "_database_redaction", False):
        def exception_hook(kind, value, tb):
            sys.stderr.write(redact_database_secrets("".join(traceback.format_exception(kind, value, tb))))
        exception_hook._database_redaction = True
        sys.excepthook = exception_hook
