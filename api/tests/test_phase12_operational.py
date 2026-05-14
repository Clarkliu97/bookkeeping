import app.documents.service as document_service
from app.core.text_repair import repair_windows_mojibake
from app.main import observability_store


def test_liveness_and_readiness_include_request_id(client):
    observability_store.reset()
    live_response = client.get("/health/live")
    assert live_response.status_code == 200, live_response.text
    assert live_response.json() == {"status": "ok"}
    assert live_response.headers["x-request-id"]

    ready_response = client.get("/health/ready")
    assert ready_response.status_code == 200, ready_response.text
    payload = ready_response.json()
    assert payload["status"] == "ok"
    assert payload["checks"]["database"] == "ok"
    assert payload["checks"]["documents"] == "ok"
    assert ready_response.headers["x-request-id"]


def test_metrics_endpoint_reports_request_and_readiness_totals(client):
    observability_store.reset()
    client.get("/health/live")
    client.get("/health/ready")

    response = client.get("/metrics")
    assert response.status_code == 200, response.text
    assert 'bookkeeping_http_requests_total 2' in response.text
    assert 'bookkeeping_readiness_checks_total 1' in response.text
    assert 'bookkeeping_last_readiness_status 1' in response.text


def test_degraded_readiness_records_alert(client, monkeypatch):
    observability_store.reset()

    def fail_storage_root():
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(document_service, "document_storage_root", fail_storage_root)

    response = client.get("/health/ready")
    assert response.status_code == 503, response.text

    alerts_response = client.get("/alerts/recent")
    assert alerts_response.status_code == 200, alerts_response.text
    payload = alerts_response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["code"] == "readiness_degraded"
    assert payload["items"][0]["severity"] == "warning"


def test_lan_origin_receives_cors_headers(client):
    origin = "http://192.168.1.100:3000"

    response = client.get("/health/live", headers={"Origin": origin})
    assert response.status_code == 200, response.text
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"

    preflight = client.options(
        "/api/auth/bootstrap",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert preflight.status_code == 200, preflight.text
    assert preflight.headers["access-control-allow-origin"] == origin
    assert preflight.headers["access-control-allow-credentials"] == "true"


def test_request_id_is_echoed_when_provided(client):
    observability_store.reset()
    response = client.get("/health/live", headers={"X-Request-ID": "phase12-test-request"})
    assert response.status_code == 200, response.text
    assert response.headers["x-request-id"] == "phase12-test-request"


def test_repair_windows_mojibake_repairs_legacy_windows_transfer_sequences():
    assert repair_windows_mojibake("ATO BAS refund receivable (Oct鈥揇ec 2025)") == "ATO BAS refund receivable (Oct–Dec 2025)"
    assert repair_windows_mojibake("JB Hi鈥慒i purchase - Uniden dash camera & cable") == "JB Hi‑Fi purchase - Uniden dash camera & cable"
    assert repair_windows_mojibake("BAS lodged 鈥?GST credit receivable") == "BAS lodged —GST credit receivable"
    assert repair_windows_mojibake("Normal text — unchanged") == "Normal text — unchanged"


def test_resolve_document_path_supports_legacy_windows_style_restore(tmp_path, monkeypatch):
    storage_root = tmp_path / "documents"
    storage_root.mkdir(parents=True, exist_ok=True)
    legacy_path = storage_root / "ae38ffe8-6624-45ab-aa94-5aca05a7d12d\\52e06205-7e59-4e0d-9b12-f0c94c9298aa.pdf"
    legacy_path.write_bytes(b"%PDF-1.4 legacy")

    monkeypatch.setattr(document_service, "document_storage_root", lambda: storage_root)

    resolved = document_service.resolve_document_path(
        "ae38ffe8-6624-45ab-aa94-5aca05a7d12d/52e06205-7e59-4e0d-9b12-f0c94c9298aa.pdf"
    )

    assert resolved == legacy_path
    assert resolved.read_bytes() == b"%PDF-1.4 legacy"