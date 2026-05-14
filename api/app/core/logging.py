import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone

from app.core.config import Settings


request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get()
        return True


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for field in ["method", "path", "status_code", "duration_ms", "alert_code", "severity", "channel"]:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, default=str)


def configure_logging(settings: Settings) -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if not root_logger.handlers:
        handler = logging.StreamHandler()
        root_logger.addHandler(handler)
    else:
        handler = root_logger.handlers[0]

    request_filter = RequestContextFilter()
    handler.filters = [request_filter]
    if settings.log_json:
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s")
        )

    for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access", "bookkeeping_tax"]:
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        logger.handlers = [handler]
        logger.propagate = False