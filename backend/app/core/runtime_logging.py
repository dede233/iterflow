import json
import logging
import sys
from datetime import UTC, datetime
from traceback import format_tb


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        for key in ("request_id", "method", "path", "status_code", "duration_ms", "client_ip"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            exception_class = record.exc_info[0]
            payload["exception_type"] = exception_class.__name__ if exception_class else "Unknown"
            # Traceback frames are useful; exception messages may contain credentials
            # or request-derived values and must not be copied to production logs.
            payload["stack_trace"] = "".join(format_tb(record.exc_info[2]))
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str) -> logging.Logger:
    logger = logging.getLogger("iterflow.runtime")
    logger.setLevel(level)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    return logger
