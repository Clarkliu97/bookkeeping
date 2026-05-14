import json
import logging
from collections import Counter, deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.core.config import Settings


class ObservabilityStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self._http_requests_total = 0
            self._http_request_duration_ms_total = 0.0
            self._http_status_totals: Counter[int] = Counter()
            self._http_route_totals: Counter[tuple[str, str, int]] = Counter()
            self._readiness_checks_total = 0
            self._readiness_failures_total = 0
            self._alerts_total = 0
            self._recent_alerts: deque[dict[str, object]] = deque(maxlen=20)
            self._last_readiness_status = "unknown"
            self._last_readiness_checks: dict[str, str] = {}
            self._last_alert_times: dict[str, datetime] = {}

    def record_request(self, method: str, path: str, status_code: int, duration_ms: float) -> None:
        with self._lock:
            self._http_requests_total += 1
            self._http_request_duration_ms_total += duration_ms
            self._http_status_totals[status_code] += 1
            self._http_route_totals[(method, path, status_code)] += 1

    def record_readiness(self, status: str, checks: dict[str, str]) -> None:
        with self._lock:
            self._readiness_checks_total += 1
            if status != "ok":
                self._readiness_failures_total += 1
            self._last_readiness_status = status
            self._last_readiness_checks = dict(checks)

    def emit_alert(
        self,
        *,
        code: str,
        severity: str,
        message: str,
        details: dict[str, object],
        settings: Settings,
        logger: logging.Logger,
    ) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            last_sent = self._last_alert_times.get(code)
            if last_sent and (now - last_sent) < timedelta(seconds=settings.alert_cooldown_seconds):
                return
            payload = {
                "code": code,
                "severity": severity,
                "message": message,
                "details": details,
                "created_at": now.isoformat(),
            }
            self._alerts_total += 1
            self._last_alert_times[code] = now
            self._recent_alerts.appendleft(payload)

        logger.warning(
            "alert.triggered",
            extra={
                "alert_code": code,
                "severity": severity,
                "channel": "webhook" if settings.alert_webhook_url else "log",
            },
        )

        if not settings.alert_webhook_url:
            return

        request = Request(
            settings.alert_webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=settings.healthcheck_timeout_seconds):
                return
        except URLError:
            logger.exception(
                "alert.delivery_failed",
                extra={"alert_code": code, "severity": severity, "channel": "webhook"},
            )

    def recent_alerts(self) -> list[dict[str, object]]:
        with self._lock:
            return list(self._recent_alerts)

    def render_metrics(self) -> str:
        with self._lock:
            lines = [
                "# TYPE bookkeeping_http_requests_total counter",
                f"bookkeeping_http_requests_total {self._http_requests_total}",
                "# TYPE bookkeeping_http_request_duration_ms_total counter",
                f"bookkeeping_http_request_duration_ms_total {self._http_request_duration_ms_total:.2f}",
                "# TYPE bookkeeping_http_responses_total counter",
            ]
            for status_code, count in sorted(self._http_status_totals.items()):
                lines.append(f'bookkeeping_http_responses_total{{status_code="{status_code}"}} {count}')
            lines.append("# TYPE bookkeeping_http_route_responses_total counter")
            for (method, path, status_code), count in sorted(self._http_route_totals.items()):
                lines.append(
                    "bookkeeping_http_route_responses_total"
                    f'{{method="{method}",path="{path}",status_code="{status_code}"}} {count}'
                )
            lines.extend(
                [
                    "# TYPE bookkeeping_readiness_checks_total counter",
                    f"bookkeeping_readiness_checks_total {self._readiness_checks_total}",
                    "# TYPE bookkeeping_readiness_failures_total counter",
                    f"bookkeeping_readiness_failures_total {self._readiness_failures_total}",
                    "# TYPE bookkeeping_alerts_total counter",
                    f"bookkeeping_alerts_total {self._alerts_total}",
                    "# TYPE bookkeeping_last_readiness_status gauge",
                    f"bookkeeping_last_readiness_status {1 if self._last_readiness_status == 'ok' else 0}",
                ]
            )
            for name, state in sorted(self._last_readiness_checks.items()):
                lines.append(
                    "bookkeeping_last_readiness_check_status"
                    f'{{check="{name}",state="{state}"}} {1 if state == "ok" else 0}'
                )
            return "\n".join(lines) + "\n"


observability_store = ObservabilityStore()