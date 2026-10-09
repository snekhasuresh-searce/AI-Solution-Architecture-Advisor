"""Log setup. ADVISOR_LOG_FORMAT=json writes one JSON object per line (Google Cloud
Logging reads `severity` and `message`, and every key in `fields` is searchable,
e.g. jsonPayload.run_id="1bda47f0"). Anything else: readable text."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **getattr(record, "fields", {}),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def setup() -> None:
    handler = logging.StreamHandler()
    if os.getenv("ADVISOR_LOG_FORMAT", "text").strip().lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(os.getenv("ADVISOR_LOG_LEVEL", "INFO").upper())
    # Token-usage warnings are noise (and always fire with the mock model).
    logging.getLogger("google_adk.google.adk.telemetry._metrics").setLevel(logging.ERROR)


def event(logger: logging.Logger, level: int, message: str, **fields) -> None:
    """A log line whose fields are readable in text and separate keys in JSON."""
    shown = " ".join(f"{k}={v}" for k, v in fields.items() if v is not None)
    logger.log(level, f"{message} {shown}".strip(), extra={"fields": fields})
