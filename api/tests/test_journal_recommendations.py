from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

from conftest import TestingSessionLocal, upsert_test_account
from app.core.security import create_access_token, hash_password
from app.db.models.auth import User, UserCompanyAccess
from app.core.config import get_settings
from app.journal_recommendations import service as recommendation_service
from app.db.models.journal_recommendations import JournalRecommendationProposal, JournalRecommendationRun
from pydantic import ValidationError


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def bootstrap_superuser(client):
    response = client.post(
        "/api/auth/bootstrap",
        json={
            "email": "admin@example.com",
            "full_name": "Initial Admin",
            "password": "StrongPass123",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def create_company(client, token: str):
    response = client.post(
        "/api/companies",
        headers=auth_header(token),
        json={
            "legal_name": "Example Pty Ltd",
            "entity_type": "company",
            "initial_configuration": {
                "effective_from": "2026-07-01",
                "gst_registered": True,
                "bas_frequency": "quarterly",
                "bas_reporting_basis": "accrual",
                "financial_year_start_month": 7,
                "financial_year_start_day": 1,
                "allow_self_approval": True,
                "self_approval_mode": "warn",
                "period_lock_policy": "after_approval",
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_period(client, token: str, company_id: str):
    response = client.post(
        f"/api/companies/{company_id}/periods",
        headers=auth_header(token),
        json={
            "name": "FY26-Q1",
            "period_type": "quarter",
            "start_date": "2026-07-01",
            "end_date": "2026-09-30",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_account(client, token: str, company_id: str, code: str, name: str, account_type: str):
    return upsert_test_account(
        client,
        token,
        company_id,
        account_code=code,
        name=name,
        account_type=account_type,
    )


def create_prepare_only_user(company_id: str) -> str:
    company_uuid = UUID(company_id)
    with TestingSessionLocal() as db:
        user = User(
            email=f"prepare-{uuid4()}@example.com",
            full_name="Prepare Only User",
            password_hash=hash_password("StrongPass123"),
            is_active=True,
            is_superuser=False,
        )
        db.add(user)
        db.flush()
        db.add(
            UserCompanyAccess(
                user_id=user.id,
                company_id=company_uuid,
                can_prepare=True,
                can_review=False,
                can_approve=False,
                can_administer=False,
            )
        )
        db.commit()
        return create_access_token(str(user.id))


def test_build_document_content_items_uses_data_urls_for_pdf_and_images(tmp_path, monkeypatch):
    pdf_path = tmp_path / "invoice.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake invoice")
    image_path = tmp_path / "receipt.png"
    image_path.write_bytes(b"fake-image-bytes")

    paths_by_storage_key = {
        "pdf-storage-key": pdf_path,
        "image-storage-key": image_path,
    }

    monkeypatch.setattr(
        recommendation_service,
        "resolve_document_path",
        lambda storage_path: paths_by_storage_key[storage_path],
    )

    items = recommendation_service._build_document_content_items(
        [
            SimpleNamespace(
                storage_path="pdf-storage-key",
                original_filename="invoice.pdf",
                media_type="application/pdf",
            ),
            SimpleNamespace(
                storage_path="image-storage-key",
                original_filename="receipt.png",
                media_type="image/png",
            ),
        ]
    )

    assert items[0]["type"] == "input_file"
    assert items[0]["filename"] == "invoice.pdf"
    assert items[0]["file_data"].startswith("data:application/pdf;base64,")
    assert items[1]["type"] == "input_image"
    assert items[1]["detail"] == "high"
    assert items[1]["image_url"].startswith("data:image/png;base64,")


def test_llm_proposal_attributes_schema_forbids_additional_properties():
    schema = recommendation_service.LlmProposalAttributes.model_json_schema()

    assert schema["additionalProperties"] is False
    assert "account_type" in schema["properties"]
    assert "allow_manual_posting" in schema["properties"]


def test_llm_recommendation_schema_limits_free_text_lengths():
    schema = recommendation_service.LlmRecommendation.model_json_schema()
    line_schema = schema["$defs"]["LlmRecommendedLine"]

    assert schema["properties"]["summary"]["maxLength"] == 240
    assert schema["properties"]["warning_text"]["anyOf"][0]["maxLength"] == 300
    assert schema["properties"]["lines"]["minItems"] == 2
    assert schema["properties"]["lines"]["maxItems"] == 12
    assert schema["properties"]["proposals"]["maxItems"] == 5
    assert line_schema["properties"]["description"]["anyOf"][0]["maxLength"] == 160
    assert line_schema["properties"]["explanation"]["anyOf"][0]["maxLength"] == 240


def test_llm_reference_proposal_schema_limits_proposal_type_values():
    schema = recommendation_service.LlmReferenceProposal.model_json_schema()
    proposal_type_schema = schema["properties"]["proposal_type"]
    enum_schema = schema["$defs"][proposal_type_schema["$ref"].split("/")[-1]]

    assert enum_schema["enum"] == ["account", "tax_code", "reporting_category"]


def test_reference_context_uses_compact_account_fields(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)

    with TestingSessionLocal() as db:
        context = recommendation_service._build_reference_context(db, UUID(company_id))

    account = next(item for item in context["accounts"] if item["code"] == "1021")

    assert set(account) == {"code", "name", "type", "tax", "posting"}
    assert account["name"] == "Main Business Transaction Account"
    assert account["type"] == "asset"
    assert account["tax"] == "NO_TAX"
    assert account["posting"] is True
    assert "account_code" not in account
    assert "account_type" not in account
    assert "default_tax_code_id" not in account
    assert "allow_manual_posting" not in account


def test_prompt_cache_key_is_stable_for_reference_prefix_and_changes_when_context_changes():
    company_id = uuid4()
    company = SimpleNamespace(
        legal_name="Example Pty Ltd",
        entity_type="company",
        base_currency="AUD",
        country_code="AU",
    )
    reference_context = {
        "configuration": {"gst_registered": True},
        "accounts": [{"code": "1021", "name": "Main Business Transaction Account", "type": "asset", "tax": "NO_TAX", "posting": True}],
        "tax_codes": [{"code": "NO_TAX", "name": "No Tax", "rate": "0.0000", "bas_label": None, "input_output_type": "none"}],
        "reporting_categories": [{"code": "BS_CA_CASH", "name": "Cash", "category_type": "balance_sheet"}],
    }
    prefix = recommendation_service._build_cached_reference_prefix(
        company=company,
        reference_context=reference_context,
    )
    same_prefix = recommendation_service._build_cached_reference_prefix(
        company=company,
        reference_context=reference_context,
    )
    changed_prefix = recommendation_service._build_cached_reference_prefix(
        company=company,
        reference_context={
            **reference_context,
            "accounts": [{**reference_context["accounts"][0], "name": "Renamed Transaction Account"}],
        },
    )

    prefix_hash = recommendation_service._hash_prompt_prefix(prefix)
    same_hash = recommendation_service._hash_prompt_prefix(same_prefix)
    changed_hash = recommendation_service._hash_prompt_prefix(changed_prefix)

    assert prefix_hash == same_hash
    assert prefix_hash != changed_hash
    assert "When GST is visible" in recommendation_service._build_system_prompt()
    assert "When GST is not visible and the user has not provided related context" in recommendation_service._build_system_prompt()
    assert "Assess GST involvement separately for each materially distinct bundle component" in recommendation_service._build_system_prompt()
    assert "Separate materially distinct bundle components" in recommendation_service._build_system_prompt()
    assert "Never set entry_date to the upload date" in recommendation_service._build_system_prompt()
    assert "separate the GST component from the net revenue or expense" in prefix
    assert "If GST is not visible and no related context is provided" in prefix
    assert "Assess GST separately for each materially distinct component in the bundle" in prefix
    assert "For bundles with multiple adjustments, pre-settlement items, charges, credits" in prefix
    assert "operator_note" not in prefix
    assert "documents" not in prefix
    prompt_cache_key = recommendation_service._build_prompt_cache_key(
        company_id=company_id,
        prompt_version=recommendation_service.PROMPT_VERSION,
        reference_context_hash=prefix_hash,
    )

    assert len(prompt_cache_key) <= 64
    assert prompt_cache_key == recommendation_service._build_prompt_cache_key(
        company_id=company_id,
        prompt_version=recommendation_service.PROMPT_VERSION,
        reference_context_hash=same_hash,
    )
    assert recommendation_service._build_prompt_cache_key(
        company_id=company_id,
        prompt_version=recommendation_service.PROMPT_VERSION,
        reference_context_hash=prefix_hash,
    ) != recommendation_service._build_prompt_cache_key(
        company_id=company_id,
        prompt_version=recommendation_service.PROMPT_VERSION,
        reference_context_hash=changed_hash,
    )


def test_analyze_with_openai_retries_once_when_first_recommendation_is_unbalanced(monkeypatch):
    parse_calls: list[dict[str, object]] = []
    unbalanced = recommendation_service.LlmRecommendation(
        summary="First pass",
        entry_date=date(2026, 7, 5),
        vendor_name="Officeworks",
        total_amount=Decimal("110.00"),
        gst_amount=Decimal("10.00"),
        currency_code="AUD",
        recommended_description="Office supplies purchase",
        recommended_reference="INV-1001",
        confidence_summary="Medium",
        warning_text="Check totals.",
        lines=[
            recommendation_service.LlmRecommendedLine(
                line_number=1,
                description="Expense",
                explanation="First pass",
                account_code="6440",
                tax_code_code=None,
                reporting_category_code=None,
                debit_amount=Decimal("110.00"),
                credit_amount=Decimal("0.00"),
            ),
            recommendation_service.LlmRecommendedLine(
                line_number=2,
                description="Bank",
                explanation="First pass",
                account_code="1021",
                tax_code_code=None,
                reporting_category_code=None,
                debit_amount=Decimal("0.00"),
                credit_amount=Decimal("100.00"),
            ),
        ],
        proposals=[],
    )
    balanced = recommendation_service.LlmRecommendation(
        summary="Second pass",
        entry_date=date(2026, 7, 5),
        vendor_name="Officeworks",
        total_amount=Decimal("110.00"),
        gst_amount=Decimal("10.00"),
        currency_code="AUD",
        recommended_description="Office supplies purchase",
        recommended_reference="INV-1001",
        confidence_summary="High",
        warning_text="Review GST coding before posting.",
        lines=[
            recommendation_service.LlmRecommendedLine(
                line_number=1,
                description="Expense",
                explanation="Corrected",
                account_code="6440",
                tax_code_code=None,
                reporting_category_code=None,
                debit_amount=Decimal("110.00"),
                credit_amount=Decimal("0.00"),
            ),
            recommendation_service.LlmRecommendedLine(
                line_number=2,
                description="Bank",
                explanation="Corrected",
                account_code="1021",
                tax_code_code=None,
                reporting_category_code=None,
                debit_amount=Decimal("0.00"),
                credit_amount=Decimal("110.00"),
            ),
        ],
        proposals=[],
    )

    class FakeResponses:
        def __init__(self):
            self._responses = [
                SimpleNamespace(output_parsed=unbalanced, output=[], usage=None, model_dump=lambda mode="json": {"attempt": 1}),
                SimpleNamespace(output_parsed=balanced, output=[], usage=None, model_dump=lambda mode="json": {"attempt": 2}),
            ]

        def parse(self, **kwargs):
            parse_calls.append(kwargs)
            return self._responses.pop(0)

    fake_client = SimpleNamespace(responses=FakeResponses())
    monkeypatch.setattr(
        recommendation_service,
        "import_module",
        lambda _name: SimpleNamespace(OpenAI=lambda **_kwargs: fake_client),
    )
    monkeypatch.setattr(
        recommendation_service,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="test-key", journal_ai_request_timeout_seconds=30),
    )
    monkeypatch.setattr(recommendation_service, "ensure_supported_model", lambda _model: SimpleNamespace(reasoning_effort=None))
    monkeypatch.setattr(recommendation_service, "_build_reference_context", lambda _db, _company_id: {})
    monkeypatch.setattr(recommendation_service, "_build_cached_reference_prefix", lambda **_kwargs: "stable-reference-prefix")
    monkeypatch.setattr(recommendation_service, "_build_recommendation_request_suffix", lambda **_kwargs: "request-suffix")
    monkeypatch.setattr(recommendation_service, "_build_document_content_items", lambda _documents: [])

    fake_db = SimpleNamespace(get=lambda _model, _id: SimpleNamespace())
    run = SimpleNamespace(
        company_id=uuid4(),
        provider_model="gpt-5.4-mini",
        id=uuid4(),
        prompt_version=recommendation_service.PROMPT_VERSION,
    )

    parsed = recommendation_service._analyze_with_openai(fake_db, run=run, documents=[])

    assert parsed.summary == "Second pass"
    assert len(parse_calls) == 2
    assert "temperature" not in parse_calls[0]
    assert parse_calls[0]["max_output_tokens"] == recommendation_service.RECOMMENDATION_MAX_OUTPUT_TOKENS
    assert parse_calls[0]["prompt_cache_retention"] == "in_memory"
    assert len(parse_calls[0]["prompt_cache_key"]) <= 64
    assert parse_calls[0]["prompt_cache_key"].startswith("jr:")
    assert "reference_context_hash" in parse_calls[0]["metadata"]
    assert parse_calls[0]["input"][0]["content"][0]["text"] == "stable-reference-prefix"
    assert parse_calls[0]["input"][0]["content"][1]["text"] == "request-suffix"
    assert len(parse_calls[1]["input"]) == 2
    assert "debit_total=110.00" in parse_calls[1]["input"][1]["content"][0]["text"]
    assert "credit_total=100.00" in parse_calls[1]["input"][1]["content"][0]["text"]


def test_analyze_with_openai_retries_once_when_provider_returns_invalid_json(monkeypatch):
    parse_calls: list[dict[str, object]] = []
    try:
        recommendation_service.LlmRecommendation.model_validate_json('{"summary":"unfinished"')
    except ValidationError as exc:
        parse_error = exc
    else:
        raise AssertionError("Expected invalid JSON fixture to raise")

    balanced = recommendation_service.LlmRecommendation(
        summary="Corrected pass",
        entry_date=date(2026, 7, 5),
        vendor_name="Officeworks",
        total_amount=Decimal("110.00"),
        gst_amount=Decimal("10.00"),
        currency_code="AUD",
        recommended_description="Office supplies purchase",
        recommended_reference="INV-1001",
        confidence_summary="High",
        warning_text=None,
        lines=[
            recommendation_service.LlmRecommendedLine(
                line_number=1,
                description="Expense",
                explanation="Balanced",
                account_code="6440",
                tax_code_code=None,
                reporting_category_code=None,
                debit_amount=Decimal("110.00"),
                credit_amount=Decimal("0.00"),
            ),
            recommendation_service.LlmRecommendedLine(
                line_number=2,
                description="Bank",
                explanation="Balanced",
                account_code="1021",
                tax_code_code=None,
                reporting_category_code=None,
                debit_amount=Decimal("0.00"),
                credit_amount=Decimal("110.00"),
            ),
        ],
        proposals=[],
    )

    class FakeResponses:
        def __init__(self):
            self._failed = False

        def parse(self, **kwargs):
            parse_calls.append(kwargs)
            if not self._failed:
                self._failed = True
                raise parse_error
            return SimpleNamespace(output_parsed=balanced, output=[], usage=None, model_dump=lambda mode="json": {})

    fake_client = SimpleNamespace(responses=FakeResponses())
    monkeypatch.setattr(
        recommendation_service,
        "import_module",
        lambda _name: SimpleNamespace(OpenAI=lambda **_kwargs: fake_client),
    )
    monkeypatch.setattr(
        recommendation_service,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="test-key", journal_ai_request_timeout_seconds=30),
    )
    monkeypatch.setattr(recommendation_service, "ensure_supported_model", lambda _model: SimpleNamespace(reasoning_effort="minimal"))
    monkeypatch.setattr(recommendation_service, "_build_reference_context", lambda _db, _company_id: {})
    monkeypatch.setattr(recommendation_service, "_build_cached_reference_prefix", lambda **_kwargs: "stable-reference-prefix")
    monkeypatch.setattr(recommendation_service, "_build_recommendation_request_suffix", lambda **_kwargs: "request-suffix")
    monkeypatch.setattr(recommendation_service, "_build_document_content_items", lambda _documents: [])

    run = SimpleNamespace(
        company_id=uuid4(),
        provider_model="gpt-5-nano",
        id=uuid4(),
        prompt_version=recommendation_service.PROMPT_VERSION,
    )

    parsed = recommendation_service._analyze_with_openai(
        SimpleNamespace(get=lambda _model, _id: SimpleNamespace()), run=run, documents=[]
    )

    assert parsed.summary == "Corrected pass"
    assert len(parse_calls) == 2
    retry_text = parse_calls[1]["input"][1]["content"][0]["text"]
    assert "not valid structured JSON" in retry_text
    assert "Do not include markdown" in retry_text
    assert "reference_context" in retry_text
    assert "Do not add fields outside the schema" in retry_text
    assert "Always include proposals" in retry_text


def test_analyze_with_openai_disables_web_search_tools_on_structured_retry(monkeypatch):
    parse_calls: list[dict[str, object]] = []
    try:
        recommendation_service.LlmRecommendation.model_validate_json('{"summary":"unfinished"')
    except ValidationError as exc:
        parse_error = exc
    else:
        raise AssertionError("Expected invalid JSON fixture to raise")

    balanced = recommendation_service.LlmRecommendation(
        summary="Retried without tools",
        entry_date=date(2026, 7, 5),
        vendor_name="Officeworks",
        total_amount=Decimal("110.00"),
        gst_amount=Decimal("10.00"),
        currency_code="AUD",
        recommended_description="Office supplies purchase",
        recommended_reference="INV-1001",
        confidence_summary="High",
        warning_text=None,
        lines=[
            recommendation_service.LlmRecommendedLine(
                line_number=1,
                description="Expense",
                explanation="Balanced",
                account_code="6440",
                tax_code_code=None,
                reporting_category_code=None,
                debit_amount=Decimal("110.00"),
                credit_amount=Decimal("0.00"),
            ),
            recommendation_service.LlmRecommendedLine(
                line_number=2,
                description="Bank",
                explanation="Balanced",
                account_code="1021",
                tax_code_code=None,
                reporting_category_code=None,
                debit_amount=Decimal("0.00"),
                credit_amount=Decimal("110.00"),
            ),
        ],
        proposals=[],
    )

    class FakeResponses:
        def __init__(self):
            self._failed = False

        def parse(self, **kwargs):
            parse_calls.append(kwargs)
            if not self._failed:
                self._failed = True
                raise parse_error
            return SimpleNamespace(output_parsed=balanced, output=[], usage=None, model_dump=lambda mode="json": {})

    fake_client = SimpleNamespace(responses=FakeResponses())
    monkeypatch.setattr(
        recommendation_service,
        "import_module",
        lambda _name: SimpleNamespace(OpenAI=lambda **_kwargs: fake_client),
    )
    monkeypatch.setattr(
        recommendation_service,
        "get_settings",
        lambda: SimpleNamespace(
            openai_api_key="test-key",
            journal_ai_request_timeout_seconds=30,
            journal_ai_web_search_enabled=True,
        ),
    )
    monkeypatch.setattr(
        recommendation_service,
        "ensure_supported_model",
        lambda _model: SimpleNamespace(reasoning_effort=None, supports_web_search=True, prompt_cache_retention="in_memory"),
    )
    monkeypatch.setattr(recommendation_service, "_build_reference_context", lambda _db, _company_id: {})
    monkeypatch.setattr(recommendation_service, "_build_cached_reference_prefix", lambda **_kwargs: "stable-reference-prefix")
    monkeypatch.setattr(recommendation_service, "_build_recommendation_request_suffix", lambda **_kwargs: "request-suffix")
    monkeypatch.setattr(recommendation_service, "_build_document_content_items", lambda _documents: [])

    run = SimpleNamespace(
        company_id=uuid4(),
        provider_model="gpt-5.4",
        id=uuid4(),
        prompt_version=recommendation_service.PROMPT_VERSION,
    )

    parsed = recommendation_service._analyze_with_openai(
        SimpleNamespace(get=lambda _model, _id: SimpleNamespace()), run=run, documents=[]
    )

    assert parsed.summary == "Retried without tools"
    assert len(parse_calls) == 2
    assert parse_calls[0]["tools"] == [{"type": "web_search", "search_context_size": "low"}]
    assert "tools" not in parse_calls[1]
    assert "tool_choice" not in parse_calls[1]
    assert "max_tool_calls" not in parse_calls[1]


def test_analyze_with_openai_uses_model_prompt_cache_retention(monkeypatch):
    parse_calls: list[dict[str, object]] = []
    balanced = recommendation_service.LlmRecommendation(
        summary="Cache-compatible run",
        entry_date=date(2026, 7, 5),
        vendor_name="Officeworks",
        total_amount=Decimal("110.00"),
        gst_amount=Decimal("10.00"),
        currency_code="AUD",
        recommended_description="Office supplies purchase",
        recommended_reference="INV-1001",
        confidence_summary="High",
        warning_text=None,
        lines=[
            recommendation_service.LlmRecommendedLine(
                line_number=1,
                description="Expense",
                explanation="Balanced",
                account_code="6440",
                tax_code_code=None,
                reporting_category_code=None,
                debit_amount=Decimal("110.00"),
                credit_amount=Decimal("0.00"),
            ),
            recommendation_service.LlmRecommendedLine(
                line_number=2,
                description="Bank",
                explanation="Balanced",
                account_code="1021",
                tax_code_code=None,
                reporting_category_code=None,
                debit_amount=Decimal("0.00"),
                credit_amount=Decimal("110.00"),
            ),
        ],
        proposals=[],
    )

    class FakeResponses:
        def parse(self, **kwargs):
            parse_calls.append(kwargs)
            return SimpleNamespace(output_parsed=balanced, output=[], usage=None, model_dump=lambda mode="json": {})

    fake_client = SimpleNamespace(responses=FakeResponses())
    monkeypatch.setattr(
        recommendation_service,
        "import_module",
        lambda _name: SimpleNamespace(OpenAI=lambda **_kwargs: fake_client),
    )
    monkeypatch.setattr(
        recommendation_service,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="test-key", journal_ai_request_timeout_seconds=30),
    )
    monkeypatch.setattr(
        recommendation_service,
        "ensure_supported_model",
        lambda _model: SimpleNamespace(reasoning_effort=None, supports_web_search=False, prompt_cache_retention="24h"),
    )
    monkeypatch.setattr(recommendation_service, "_build_reference_context", lambda _db, _company_id: {})
    monkeypatch.setattr(recommendation_service, "_build_cached_reference_prefix", lambda **_kwargs: "stable-reference-prefix")
    monkeypatch.setattr(recommendation_service, "_build_recommendation_request_suffix", lambda **_kwargs: "request-suffix")
    monkeypatch.setattr(recommendation_service, "_build_document_content_items", lambda _documents: [])

    run = SimpleNamespace(
        company_id=uuid4(),
        provider_model="gpt-5.5",
        id=uuid4(),
        prompt_version=recommendation_service.PROMPT_VERSION,
    )

    parsed = recommendation_service._analyze_with_openai(
        SimpleNamespace(get=lambda _model, _id: SimpleNamespace()), run=run, documents=[]
    )

    assert parsed.summary == "Cache-compatible run"
    assert len(parse_calls) == 1
    assert parse_calls[0]["prompt_cache_retention"] == "24h"


def test_analyze_with_openai_omits_temperature_for_all_models(monkeypatch):
    parse_calls: list[dict[str, object]] = []
    balanced = recommendation_service.LlmRecommendation(
        summary="Nano pass",
        entry_date=date(2026, 7, 5),
        vendor_name="Officeworks",
        total_amount=Decimal("110.00"),
        gst_amount=Decimal("10.00"),
        currency_code="AUD",
        recommended_description="Office supplies purchase",
        recommended_reference="INV-1001",
        confidence_summary="High",
        warning_text=None,
        lines=[
            recommendation_service.LlmRecommendedLine(
                line_number=1,
                description="Expense",
                explanation="Balanced",
                account_code="6440",
                tax_code_code=None,
                reporting_category_code=None,
                debit_amount=Decimal("110.00"),
                credit_amount=Decimal("0.00"),
            ),
            recommendation_service.LlmRecommendedLine(
                line_number=2,
                description="Bank",
                explanation="Balanced",
                account_code="1021",
                tax_code_code=None,
                reporting_category_code=None,
                debit_amount=Decimal("0.00"),
                credit_amount=Decimal("110.00"),
            ),
        ],
        proposals=[],
    )

    class FakeResponses:
        def parse(self, **kwargs):
            parse_calls.append(kwargs)
            return SimpleNamespace(output_parsed=balanced, output=[], usage=None, model_dump=lambda mode="json": {})

    fake_client = SimpleNamespace(responses=FakeResponses())
    monkeypatch.setattr(
        recommendation_service,
        "import_module",
        lambda _name: SimpleNamespace(OpenAI=lambda **_kwargs: fake_client),
    )
    monkeypatch.setattr(
        recommendation_service,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="test-key", journal_ai_request_timeout_seconds=30),
    )
    monkeypatch.setattr(
        recommendation_service,
        "ensure_supported_model",
        lambda _model: SimpleNamespace(reasoning_effort="minimal"),
    )
    monkeypatch.setattr(recommendation_service, "_build_reference_context", lambda _db, _company_id: {})
    monkeypatch.setattr(recommendation_service, "_build_cached_reference_prefix", lambda **_kwargs: "stable-reference-prefix")
    monkeypatch.setattr(recommendation_service, "_build_recommendation_request_suffix", lambda **_kwargs: "request-suffix")
    monkeypatch.setattr(recommendation_service, "_build_document_content_items", lambda _documents: [])

    fake_db = SimpleNamespace(get=lambda _model, _id: SimpleNamespace())
    run = SimpleNamespace(
        company_id=uuid4(),
        provider_model="gpt-5-nano",
        id=uuid4(),
        prompt_version=recommendation_service.PROMPT_VERSION,
    )

    parsed = recommendation_service._analyze_with_openai(fake_db, run=run, documents=[])

    assert parsed.summary == "Nano pass"
    assert len(parse_calls) == 1
    assert "temperature" not in parse_calls[0]
    assert parse_calls[0]["reasoning"] == {"effort": "minimal"}


def test_analyze_with_openai_enables_web_search_for_supported_models(monkeypatch):
    parse_calls: list[dict[str, object]] = []
    balanced = recommendation_service.LlmRecommendation(
        summary="Verified settlement bundle",
        entry_date=date(2026, 7, 5),
        vendor_name="Settlement Services",
        total_amount=Decimal("165.00"),
        gst_amount=Decimal("10.00"),
        currency_code="AUD",
        recommended_description="Settlement adjustments bundle",
        recommended_reference="SET-1001",
        confidence_summary="High",
        warning_text=None,
        lines=[
            recommendation_service.LlmRecommendedLine(
                line_number=1,
                description="Legal fees",
                explanation="Verified with web search.",
                account_code="7300",
                tax_code_code="GST_PURCHASE_10",
                reporting_category_code=None,
                debit_amount=Decimal("100.00"),
                credit_amount=Decimal("0.00"),
            ),
            recommendation_service.LlmRecommendedLine(
                line_number=2,
                description="Settlement cleared",
                explanation="Balanced settlement entry.",
                account_code="1021",
                tax_code_code="NO_TAX",
                reporting_category_code=None,
                debit_amount=Decimal("0.00"),
                credit_amount=Decimal("100.00"),
            ),
        ],
        proposals=[],
    )

    class FakeResponses:
        def parse(self, **kwargs):
            parse_calls.append(kwargs)
            return SimpleNamespace(
                output_parsed=balanced,
                output=[SimpleNamespace(type="web_search_call", action=SimpleNamespace(type="search", sources=[{"url": "https://example.com"}]))],
                usage=None,
                model_dump=lambda mode="json": {"status": "completed"},
            )

    fake_client = SimpleNamespace(responses=FakeResponses())
    monkeypatch.setattr(
        recommendation_service,
        "import_module",
        lambda _name: SimpleNamespace(OpenAI=lambda **_kwargs: fake_client),
    )
    monkeypatch.setattr(
        recommendation_service,
        "get_settings",
        lambda: SimpleNamespace(
            openai_api_key="test-key",
            journal_ai_request_timeout_seconds=30,
            journal_ai_web_search_enabled=True,
        ),
    )
    monkeypatch.setattr(
        recommendation_service,
        "ensure_supported_model",
        lambda _model: SimpleNamespace(reasoning_effort=None, supports_web_search=True),
    )
    monkeypatch.setattr(recommendation_service, "_build_reference_context", lambda _db, _company_id: {})
    monkeypatch.setattr(recommendation_service, "_build_cached_reference_prefix", lambda **_kwargs: "stable-reference-prefix")
    monkeypatch.setattr(recommendation_service, "_build_recommendation_request_suffix", lambda **_kwargs: "request-suffix")
    monkeypatch.setattr(recommendation_service, "_build_document_content_items", lambda _documents: [])

    fake_db = SimpleNamespace(get=lambda _model, _id: SimpleNamespace())
    run = SimpleNamespace(
        company_id=uuid4(),
        provider_model="gpt-5.4",
        id=uuid4(),
        prompt_version=recommendation_service.PROMPT_VERSION,
    )

    parsed = recommendation_service._analyze_with_openai(fake_db, run=run, documents=[])

    assert parsed.summary == "Verified settlement bundle"
    assert len(parse_calls) == 1
    assert parse_calls[0]["tools"] == [{"type": "web_search", "search_context_size": "low"}]
    assert parse_calls[0]["tool_choice"] == "auto"
    assert parse_calls[0]["max_tool_calls"] == 3
    assert parse_calls[0]["include"] == ["web_search_call.action.sources"]


def test_extract_search_sources_deduplicates_and_formats_domains():
    run = SimpleNamespace(
        raw_provider_response_json={
            "output": [
                {
                    "type": "web_search_call",
                    "action": {
                        "sources": [
                            {"title": "ATO GST guide", "url": "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst"},
                            {"title": "ATO GST guide", "url": "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst"},
                            {"title": "NSW title search fees", "url": "https://www.nswlrs.com.au/title-search"},
                        ]
                    },
                }
            ]
        }
    )

    assert recommendation_service._extract_search_sources(run) == [
        {
            "title": "ATO GST guide",
            "url": "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst",
            "domain": "www.ato.gov.au",
        },
        {
            "title": "NSW title search fees",
            "url": "https://www.nswlrs.com.au/title-search",
            "domain": "www.nswlrs.com.au",
        },
    ]


def test_analyze_with_openai_keeps_provider_diagnostics_when_structured_output_is_missing(monkeypatch):
    class FakeResponses:
        def parse(self, **_kwargs):
            return SimpleNamespace(
                output_parsed=None,
                output=[SimpleNamespace(type="message", content=[])],
                usage=SimpleNamespace(model_dump=lambda mode="json": {"output_tokens": 5000}),
                status="incomplete",
                incomplete_details=SimpleNamespace(reason="max_output_tokens"),
                model_dump=lambda mode="json": {"status": "incomplete"},
            )

    fake_client = SimpleNamespace(responses=FakeResponses())
    monkeypatch.setattr(
        recommendation_service,
        "import_module",
        lambda _name: SimpleNamespace(OpenAI=lambda **_kwargs: fake_client),
    )
    monkeypatch.setattr(
        recommendation_service,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="test-key", journal_ai_request_timeout_seconds=30),
    )
    monkeypatch.setattr(
        recommendation_service,
        "ensure_supported_model",
        lambda _model: SimpleNamespace(reasoning_effort="minimal"),
    )
    monkeypatch.setattr(recommendation_service, "_build_reference_context", lambda _db, _company_id: {})
    monkeypatch.setattr(recommendation_service, "_build_cached_reference_prefix", lambda **_kwargs: "stable-reference-prefix")
    monkeypatch.setattr(recommendation_service, "_build_recommendation_request_suffix", lambda **_kwargs: "request-suffix")
    monkeypatch.setattr(recommendation_service, "_build_document_content_items", lambda _documents: [])

    run = SimpleNamespace(
        company_id=uuid4(),
        provider_model="gpt-5-nano",
        id=uuid4(),
        prompt_version=recommendation_service.PROMPT_VERSION,
        raw_provider_response_json=None,
        provider_usage_json=None,
    )

    try:
        recommendation_service._analyze_with_openai(SimpleNamespace(get=lambda _model, _id: SimpleNamespace()), run=run, documents=[])
    except Exception as exc:
        assert "provider status=incomplete" in exc.detail
        assert "reason=max_output_tokens" in exc.detail
    else:
        raise AssertionError("Expected structured-output failure")

    assert run.raw_provider_response_json == {"status": "incomplete"}
    assert run.provider_usage_json == {"output_tokens": 5000}


def test_journal_recommendation_models_and_accept_flow(client, monkeypatch):
    settings = get_settings()
    original_api_key = settings.openai_api_key
    settings.openai_api_key = "test-key"

    def fake_analyze(_db, *, run, documents):
        assert len(documents) == 2
        assert run.provider_model == "gpt-5.4-mini"
        return recommendation_service.LlmRecommendation(
            summary="Office supplies purchase from uploaded invoice bundle",
            entry_date=date(2026, 7, 5),
            vendor_name="Officeworks",
            total_amount=Decimal("110.00"),
            gst_amount=Decimal("10.00"),
            currency_code="AUD",
            recommended_description="Office supplies purchase",
            recommended_reference="INV-1001",
            confidence_summary="High confidence based on invoice total and supplier name",
            warning_text="Review GST coding before posting.",
            lines=[
                recommendation_service.LlmRecommendedLine(
                    line_number=1,
                    description="Office supplies expense",
                    explanation="Invoice total coded to office supplies",
                    account_code="6440",
                    tax_code_code=None,
                    reporting_category_code=None,
                    debit_amount=Decimal("110.00"),
                    credit_amount=Decimal("0.00"),
                ),
                recommendation_service.LlmRecommendedLine(
                    line_number=2,
                    description="Paid from operating bank",
                    explanation="Supplier payment settled immediately",
                    account_code="1021",
                    tax_code_code=None,
                    reporting_category_code=None,
                    debit_amount=Decimal("0.00"),
                    credit_amount=Decimal("110.00"),
                ),
            ],
            proposals=[],
        )

    monkeypatch.setattr(recommendation_service, "_analyze_with_openai", fake_analyze)

    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)

    models_response = client.get(
        f"/api/companies/{company_id}/journal-recommendations/models",
        headers=auth_header(token),
    )
    assert models_response.status_code == 200, models_response.text
    models = models_response.json()
    assert [item["id"] for item in models] == [
        "gpt-5.5",
        "gpt-5.4",
        "gpt-5.4-mini",
        "gpt-5",
        "gpt-5-mini",
        "gpt-5-nano",
    ]
    estimated_costs = {item["id"]: item["estimated_cost_per_1000_calls_usd"] for item in models}
    assert estimated_costs == {
        "gpt-5.5": "162.00",
        "gpt-5.4": "81.00",
        "gpt-5.4-mini": "24.30",
        "gpt-5": "44.00",
        "gpt-5-mini": "8.80",
        "gpt-5-nano": "1.76",
    }

    create_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations",
        headers=auth_header(token),
        files=[
            ("files", ("invoice.pdf", b"%PDF-1.4 fake invoice", "application/pdf")),
            ("files", ("receipt.png", b"fake-image-bytes", "image/png")),
        ],
        data={
            "model": "gpt-5.4-mini",
            "user_context_note": "Bought stationery for the office.",
            "target_accounting_period_id": period_id,
        },
    )
    assert create_response.status_code == 201, create_response.text
    run_id = create_response.json()["id"]
    assert create_response.json()["status"] == "draft"
    assert len(create_response.json()["documents"]) == 2

    analyze_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations/{run_id}/analyze",
        headers=auth_header(token),
    )
    assert analyze_response.status_code == 200, analyze_response.text
    analyze_payload = analyze_response.json()
    assert analyze_payload["status"] == "review_ready"
    assert analyze_payload["extracted_entry_date"] == "2026-07-05"
    assert analyze_payload["analysis_summary"] == "Office supplies purchase from uploaded invoice bundle"
    assert len(analyze_payload["lines"]) == 2

    accept_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations/{run_id}/accept",
        headers=auth_header(token),
        json={"accepted_proposal_ids": []},
    )
    assert accept_response.status_code == 200, accept_response.text
    journal_id = accept_response.json()["id"]
    assert accept_response.json()["status"] == "draft"
    assert accept_response.json()["entry_date"] == "2026-07-05"
    assert accept_response.json()["description"] == "Office supplies purchase"

    evidence_response = client.get(
        f"/api/companies/{company_id}/journals/{journal_id}/documents",
        headers=auth_header(token),
    )
    assert evidence_response.status_code == 200, evidence_response.text
    assert len(evidence_response.json()) == 2

    settings.openai_api_key = original_api_key


def test_journal_recommendation_accept_requires_extracted_document_date(client, monkeypatch):
    settings = get_settings()
    original_api_key = settings.openai_api_key
    settings.openai_api_key = "test-key"

    def fake_analyze(_db, *, run, documents):
        assert len(documents) == 1
        return recommendation_service.LlmRecommendation(
            summary="Receipt without readable transaction date",
            entry_date=None,
            vendor_name="Officeworks",
            total_amount=Decimal("110.00"),
            gst_amount=Decimal("10.00"),
            currency_code="AUD",
            recommended_description="Office supplies purchase",
            recommended_reference="R-1001",
            confidence_summary="Low confidence because the date was not readable.",
            warning_text="Document date could not be extracted.",
            lines=[
                recommendation_service.LlmRecommendedLine(
                    line_number=1,
                    description="Office supplies expense",
                    explanation="Receipt total coded to office supplies",
                    account_code="6440",
                    tax_code_code=None,
                    reporting_category_code=None,
                    debit_amount=Decimal("110.00"),
                    credit_amount=Decimal("0.00"),
                ),
                recommendation_service.LlmRecommendedLine(
                    line_number=2,
                    description="Paid from operating bank",
                    explanation="Payment appears settled immediately",
                    account_code="1021",
                    tax_code_code=None,
                    reporting_category_code=None,
                    debit_amount=Decimal("0.00"),
                    credit_amount=Decimal("110.00"),
                ),
            ],
            proposals=[],
        )

    monkeypatch.setattr(recommendation_service, "_analyze_with_openai", fake_analyze)

    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)

    create_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations",
        headers=auth_header(token),
        files=[("files", ("receipt.pdf", b"%PDF-1.4 receipt without readable date", "application/pdf"))],
        data={"model": "gpt-5.4-mini", "target_accounting_period_id": period_id},
    )
    assert create_response.status_code == 201, create_response.text
    run_id = create_response.json()["id"]

    analyze_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations/{run_id}/analyze",
        headers=auth_header(token),
    )
    assert analyze_response.status_code == 200, analyze_response.text
    assert analyze_response.json()["extracted_entry_date"] is None

    accept_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations/{run_id}/accept",
        headers=auth_header(token),
        json={"accepted_proposal_ids": []},
    )
    assert accept_response.status_code == 400, accept_response.text
    assert "did not include a document transaction date" in accept_response.text

    settings.openai_api_key = original_api_key


def test_delete_draft_journal_clears_recommendation_accept_link(client, monkeypatch):
    settings = get_settings()
    original_api_key = settings.openai_api_key
    settings.openai_api_key = "test-key"

    def fake_analyze(_db, *, run, documents):
        assert len(documents) == 1
        return recommendation_service.LlmRecommendation(
            summary="Office supplies purchase from uploaded invoice",
            entry_date=date(2026, 7, 5),
            vendor_name="Officeworks",
            total_amount=Decimal("110.00"),
            gst_amount=Decimal("10.00"),
            currency_code="AUD",
            recommended_description="Office supplies purchase",
            recommended_reference="INV-DEL-1",
            confidence_summary="High confidence based on invoice total and supplier name",
            warning_text=None,
            lines=[
                recommendation_service.LlmRecommendedLine(
                    line_number=1,
                    description="Office supplies expense",
                    explanation="Invoice total coded to office supplies",
                    account_code="6440",
                    tax_code_code=None,
                    reporting_category_code=None,
                    debit_amount=Decimal("110.00"),
                    credit_amount=Decimal("0.00"),
                ),
                recommendation_service.LlmRecommendedLine(
                    line_number=2,
                    description="Paid from operating bank",
                    explanation="Supplier payment settled immediately",
                    account_code="1021",
                    tax_code_code=None,
                    reporting_category_code=None,
                    debit_amount=Decimal("0.00"),
                    credit_amount=Decimal("110.00"),
                ),
            ],
            proposals=[],
        )

    monkeypatch.setattr(recommendation_service, "_analyze_with_openai", fake_analyze)

    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)

    create_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations",
        headers=auth_header(token),
        files=[("files", ("invoice.pdf", b"%PDF-1.4 fake invoice", "application/pdf"))],
        data={
            "model": "gpt-5.4-mini",
            "target_accounting_period_id": period_id,
        },
    )
    assert create_response.status_code == 201, create_response.text
    run_id = create_response.json()["id"]

    analyze_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations/{run_id}/analyze",
        headers=auth_header(token),
    )
    assert analyze_response.status_code == 200, analyze_response.text

    accept_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations/{run_id}/accept",
        headers=auth_header(token),
        json={"accepted_proposal_ids": []},
    )
    assert accept_response.status_code == 200, accept_response.text
    journal_id = accept_response.json()["id"]

    delete_journal_response = client.delete(
        f"/api/companies/{company_id}/journals/{journal_id}",
        headers=auth_header(token),
    )
    assert delete_journal_response.status_code == 204, delete_journal_response.text

    run_response = client.get(
        f"/api/companies/{company_id}/journal-recommendations/{run_id}",
        headers=auth_header(token),
    )
    assert run_response.status_code == 200, run_response.text
    assert run_response.json()["status"] == "accepted"
    assert run_response.json()["accepted_journal_entry_id"] is None

    journals_response = client.get(
        f"/api/companies/{company_id}/journals",
        headers=auth_header(token),
    )
    assert journals_response.status_code == 200, journals_response.text
    assert all(item["id"] != journal_id for item in journals_response.json())

    settings.openai_api_key = original_api_key


def test_accept_recommendation_uses_next_highest_entry_number_after_deleted_gap(client, monkeypatch):
    settings = get_settings()
    original_api_key = settings.openai_api_key
    settings.openai_api_key = "test-key"

    def fake_analyze(_db, *, run, documents):
        assert len(documents) == 1
        return recommendation_service.LlmRecommendation(
            summary="Office supplies purchase from uploaded invoice",
            entry_date=date(2026, 7, 5),
            vendor_name="Officeworks",
            total_amount=Decimal("110.00"),
            gst_amount=Decimal("10.00"),
            currency_code="AUD",
            recommended_description="Office supplies purchase",
            recommended_reference="INV-GAP-1",
            confidence_summary="High confidence based on invoice total and supplier name",
            warning_text=None,
            lines=[
                recommendation_service.LlmRecommendedLine(
                    line_number=1,
                    description="Office supplies expense",
                    explanation="Invoice total coded to office supplies",
                    account_code="6440",
                    tax_code_code=None,
                    reporting_category_code=None,
                    debit_amount=Decimal("110.00"),
                    credit_amount=Decimal("0.00"),
                ),
                recommendation_service.LlmRecommendedLine(
                    line_number=2,
                    description="Paid from operating bank",
                    explanation="Supplier payment settled immediately",
                    account_code="1021",
                    tax_code_code=None,
                    reporting_category_code=None,
                    debit_amount=Decimal("0.00"),
                    credit_amount=Decimal("110.00"),
                ),
            ],
            proposals=[],
        )

    monkeypatch.setattr(recommendation_service, "_analyze_with_openai", fake_analyze)

    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    expense_account_id = create_account(client, token, company_id, "6440", "Office supplies", "expense")
    cash_account_id = create_account(client, token, company_id, "1021", "Operating bank", "asset")

    first_journal = client.post(
        f"/api/companies/{company_id}/journals",
        headers=auth_header(token),
        json={
            "entry_date": "2026-07-02",
            "accounting_period_id": period_id,
            "source_type": "manual",
            "description": "First draft journal",
            "reference": "MAN-1",
            "lines": [
                {"account_id": expense_account_id, "description": "Debit", "debit_amount": "50.00", "credit_amount": "0.00", "tax_code_id": None, "reporting_category_id": None, "source_document_reference": None},
                {"account_id": cash_account_id, "description": "Credit", "debit_amount": "0.00", "credit_amount": "50.00", "tax_code_id": None, "reporting_category_id": None, "source_document_reference": None},
            ],
        },
    )
    assert first_journal.status_code == 201, first_journal.text
    assert first_journal.json()["entry_number"] == "JE-000001"

    second_journal = client.post(
        f"/api/companies/{company_id}/journals",
        headers=auth_header(token),
        json={
            "entry_date": "2026-07-03",
            "accounting_period_id": period_id,
            "source_type": "manual",
            "description": "Second draft journal",
            "reference": "MAN-2",
            "lines": [
                {"account_id": expense_account_id, "description": "Debit", "debit_amount": "60.00", "credit_amount": "0.00", "tax_code_id": None, "reporting_category_id": None, "source_document_reference": None},
                {"account_id": cash_account_id, "description": "Credit", "debit_amount": "0.00", "credit_amount": "60.00", "tax_code_id": None, "reporting_category_id": None, "source_document_reference": None},
            ],
        },
    )
    assert second_journal.status_code == 201, second_journal.text
    assert second_journal.json()["entry_number"] == "JE-000002"

    delete_response = client.delete(
        f"/api/companies/{company_id}/journals/{first_journal.json()['id']}",
        headers=auth_header(token),
    )
    assert delete_response.status_code == 204, delete_response.text

    create_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations",
        headers=auth_header(token),
        files=[("files", ("receipt.png", b"fake-image-bytes", "image/png"))],
        data={
            "model": "gpt-5.4-mini",
            "target_accounting_period_id": period_id,
        },
    )
    assert create_response.status_code == 201, create_response.text
    run_id = create_response.json()["id"]

    analyze_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations/{run_id}/analyze",
        headers=auth_header(token),
    )
    assert analyze_response.status_code == 200, analyze_response.text

    accept_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations/{run_id}/accept",
        headers=auth_header(token),
        json={"accepted_proposal_ids": []},
    )
    assert accept_response.status_code == 200, accept_response.text
    assert accept_response.json()["entry_number"] == "JE-000003"

    settings.openai_api_key = original_api_key


def test_journal_recommendation_can_create_new_account_proposal(client, monkeypatch):
    settings = get_settings()
    original_api_key = settings.openai_api_key
    settings.openai_api_key = "test-key"

    def fake_analyze(_db, *, run, documents):
        assert len(documents) == 1
        return recommendation_service.LlmRecommendation(
            summary="Special software purchase",
            entry_date=date(2026, 7, 7),
            vendor_name="Software Vendor",
            total_amount=Decimal("330.00"),
            gst_amount=Decimal("30.00"),
            currency_code="AUD",
            recommended_description="Special software purchase",
            recommended_reference="SOFT-77",
            confidence_summary="Medium confidence; new expense account proposed.",
            warning_text="Review whether the software should be expensed or capitalized.",
            lines=[
                recommendation_service.LlmRecommendedLine(
                    line_number=1,
                    description="Specialized software expense",
                    explanation="No current software-specific expense account was available.",
                    account_code="7777",
                    tax_code_code=None,
                    reporting_category_code=None,
                    debit_amount=Decimal("330.00"),
                    credit_amount=Decimal("0.00"),
                ),
                recommendation_service.LlmRecommendedLine(
                    line_number=2,
                    description="Paid from operating bank",
                    explanation="Payment cleared immediately",
                    account_code="1021",
                    tax_code_code=None,
                    reporting_category_code=None,
                    debit_amount=Decimal("0.00"),
                    credit_amount=Decimal("330.00"),
                ),
            ],
            proposals=[
                recommendation_service.LlmReferenceProposal(
                    proposal_type="account",
                    suggested_code="7777",
                    suggested_name="Specialized Software Expense",
                    rationale="The current chart does not include a software-specific expense account.",
                    suggested_attributes_json={"account_type": "expense", "allow_manual_posting": True},
                )
            ],
        )

    monkeypatch.setattr(recommendation_service, "_analyze_with_openai", fake_analyze)

    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)

    create_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations",
        headers=auth_header(token),
        files=[("files", ("receipt.pdf", b"%PDF-1.4 software receipt", "application/pdf"))],
        data={"model": "gpt-5.4-mini", "target_accounting_period_id": period_id},
    )
    assert create_response.status_code == 201, create_response.text
    run_id = create_response.json()["id"]

    analyze_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations/{run_id}/analyze",
        headers=auth_header(token),
    )
    assert analyze_response.status_code == 200, analyze_response.text
    proposal_id = analyze_response.json()["proposals"][0]["id"]

    accept_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations/{run_id}/accept",
        headers=auth_header(token),
        json={"accepted_proposal_ids": [proposal_id]},
    )
    assert accept_response.status_code == 200, accept_response.text
    assert accept_response.json()["status"] == "draft"

    accounts_response = client.get(f"/api/companies/{company_id}/accounts", headers=auth_header(token))
    assert accounts_response.status_code == 200, accounts_response.text
    assert any(account["account_code"] == "7777" for account in accounts_response.json())

    settings.openai_api_key = original_api_key


def test_journal_recommendation_prepare_user_can_accept_selected_account_proposal(client, monkeypatch):
    settings = get_settings()
    original_api_key = settings.openai_api_key
    settings.openai_api_key = "test-key"

    def fake_analyze(_db, *, run, documents):
        assert len(documents) == 1
        return recommendation_service.LlmRecommendation(
            summary="Prepare user recommendation with proposed account",
            entry_date=date(2026, 7, 7),
            vendor_name="Software Vendor",
            total_amount=Decimal("330.00"),
            gst_amount=Decimal("30.00"),
            currency_code="AUD",
            recommended_description="Special software purchase",
            recommended_reference="SOFT-88",
            confidence_summary="Medium confidence; new expense account proposed.",
            warning_text=None,
            lines=[
                recommendation_service.LlmRecommendedLine(
                    line_number=1,
                    description="Specialized software expense",
                    explanation="New account proposal should resolve this line.",
                    account_code="7777",
                    tax_code_code=None,
                    reporting_category_code=None,
                    debit_amount=Decimal("330.00"),
                    credit_amount=Decimal("0.00"),
                ),
                recommendation_service.LlmRecommendedLine(
                    line_number=2,
                    description="Paid from operating bank",
                    explanation="Payment cleared immediately",
                    account_code="1021",
                    tax_code_code=None,
                    reporting_category_code=None,
                    debit_amount=Decimal("0.00"),
                    credit_amount=Decimal("330.00"),
                ),
            ],
            proposals=[
                recommendation_service.LlmReferenceProposal(
                    proposal_type="account",
                    suggested_code="7777",
                    suggested_name="Specialized Software Expense",
                    rationale="The current chart does not include a software-specific expense account.",
                    suggested_attributes_json={"account_type": "expense", "allow_manual_posting": True},
                )
            ],
        )

    monkeypatch.setattr(recommendation_service, "_analyze_with_openai", fake_analyze)

    admin_token = bootstrap_superuser(client)
    company_id = create_company(client, admin_token)
    period_id = create_period(client, admin_token, company_id)
    prepare_token = create_prepare_only_user(company_id)

    create_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations",
        headers=auth_header(prepare_token),
        files=[("files", ("receipt.pdf", b"%PDF-1.4 software receipt", "application/pdf"))],
        data={"model": "gpt-5.4-mini", "target_accounting_period_id": period_id},
    )
    assert create_response.status_code == 201, create_response.text
    run_id = create_response.json()["id"]

    analyze_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations/{run_id}/analyze",
        headers=auth_header(prepare_token),
    )
    assert analyze_response.status_code == 200, analyze_response.text
    proposal_id = analyze_response.json()["proposals"][0]["id"]

    accept_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations/{run_id}/accept",
        headers=auth_header(prepare_token),
        json={"accepted_proposal_ids": [proposal_id]},
    )
    assert accept_response.status_code == 200, accept_response.text

    accounts_response = client.get(f"/api/companies/{company_id}/accounts", headers=auth_header(admin_token))
    assert accounts_response.status_code == 200, accounts_response.text
    assert any(account["account_code"] == "7777" for account in accounts_response.json())

    settings.openai_api_key = original_api_key


def test_journal_recommendation_accepts_multi_adjustment_bundle_with_separate_gst_components(client, monkeypatch):
    settings = get_settings()
    original_api_key = settings.openai_api_key
    settings.openai_api_key = "test-key"

    def fake_analyze(_db, *, run, documents):
        assert len(documents) == 3
        return recommendation_service.LlmRecommendation(
            summary="Settlement letter bundle with legal fee, GST, and GST-free title search item separated.",
            entry_date=date(2026, 7, 9),
            vendor_name="Settlement Services Pty Ltd",
            total_amount=Decimal("165.00"),
            gst_amount=Decimal("10.00"),
            currency_code="AUD",
            recommended_description="Settlement adjustments bundle",
            recommended_reference="SETTLE-9001",
            confidence_summary="High confidence because the legal fee and title search items were separated from the settlement total.",
            warning_text="Review the title search item if the source document suggests a different GST outcome.",
            lines=[
                recommendation_service.LlmRecommendedLine(
                    line_number=1,
                    description="Legal fee adjustment",
                    explanation="Taxable legal fee component from the pre-settlement letter.",
                    account_code="7300",
                    tax_code_code="GST_PURCHASE_10",
                    reporting_category_code=None,
                    debit_amount=Decimal("100.00"),
                    credit_amount=Decimal("0.00"),
                ),
                recommendation_service.LlmRecommendedLine(
                    line_number=2,
                    description="GST on legal fee",
                    explanation="Separate GST claimable on the taxable legal fee component.",
                    account_code="2200",
                    tax_code_code="GST_CONTROL",
                    reporting_category_code=None,
                    debit_amount=Decimal("10.00"),
                    credit_amount=Decimal("0.00"),
                ),
                recommendation_service.LlmRecommendedLine(
                    line_number=3,
                    description="Title search adjustment",
                    explanation="GST-free disbursement item separated from the taxable fee component.",
                    account_code="7310",
                    tax_code_code="GST_FREE_PURCHASE",
                    reporting_category_code=None,
                    debit_amount=Decimal("55.00"),
                    credit_amount=Decimal("0.00"),
                ),
                recommendation_service.LlmRecommendedLine(
                    line_number=4,
                    description="Settlement cleared through operating bank",
                    explanation="Balancing settlement payment line.",
                    account_code="1021",
                    tax_code_code="NO_TAX",
                    reporting_category_code=None,
                    debit_amount=Decimal("0.00"),
                    credit_amount=Decimal("165.00"),
                ),
            ],
            proposals=[],
        )

    monkeypatch.setattr(recommendation_service, "_analyze_with_openai", fake_analyze)

    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    create_account(client, token, company_id, code="2200", name="GST Control", account_type="liability")
    create_account(client, token, company_id, code="7300", name="Legal Fees", account_type="expense")
    create_account(client, token, company_id, code="7310", name="Title Search Fees", account_type="expense")

    tax_codes_response = client.get(f"/api/companies/{company_id}/tax-codes", headers=auth_header(token))
    assert tax_codes_response.status_code == 200, tax_codes_response.text
    tax_codes = {item["code"]: item for item in tax_codes_response.json()}

    create_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations",
        headers=auth_header(token),
        files=[
            ("files", ("settlement-letter.pdf", b"%PDF-1.4 settlement letter", "application/pdf")),
            ("files", ("adjustment-sheet.pdf", b"%PDF-1.4 adjustment sheet", "application/pdf")),
            ("files", ("title-search.pdf", b"%PDF-1.4 title search", "application/pdf")),
        ],
        data={
            "model": "gpt-5.4-mini",
            "user_context_note": "Three-file bundle containing a settlement letter, adjustment sheet, and title search item.",
            "target_accounting_period_id": period_id,
        },
    )
    assert create_response.status_code == 201, create_response.text
    run_id = create_response.json()["id"]
    assert len(create_response.json()["documents"]) == 3

    analyze_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations/{run_id}/analyze",
        headers=auth_header(token),
    )
    assert analyze_response.status_code == 200, analyze_response.text
    analyze_payload = analyze_response.json()
    assert analyze_payload["status"] == "review_ready"
    assert len(analyze_payload["lines"]) == 4

    accept_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations/{run_id}/accept",
        headers=auth_header(token),
        json={"accepted_proposal_ids": []},
    )
    assert accept_response.status_code == 200, accept_response.text
    accepted_lines = accept_response.json()["lines"]
    assert len(accepted_lines) == 4

    accepted_by_description = {line["description"]: line for line in accepted_lines}
    assert accepted_by_description["Legal fee adjustment"]["tax_code_id"] == tax_codes["GST_PURCHASE_10"]["id"]
    assert accepted_by_description["GST on legal fee"]["tax_code_id"] == tax_codes["GST_CONTROL"]["id"]
    assert accepted_by_description["Title search adjustment"]["tax_code_id"] == tax_codes["GST_FREE_PURCHASE"]["id"]
    assert accepted_by_description["Settlement cleared through operating bank"]["tax_code_id"] == tax_codes["NO_TAX"]["id"]

    settings.openai_api_key = original_api_key


def test_journal_recommendation_returns_503_when_openai_runtime_is_missing(client, monkeypatch):
    settings = get_settings()
    original_api_key = settings.openai_api_key
    settings.openai_api_key = "test-key"

    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)

    create_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations",
        headers=auth_header(token),
        files=[("files", ("invoice.pdf", b"%PDF-1.4 fake invoice", "application/pdf"))],
        data={
            "model": "gpt-5.4-mini",
            "user_context_note": "Bought stationery for the office.",
            "target_accounting_period_id": period_id,
        },
    )
    assert create_response.status_code == 201, create_response.text
    run_id = create_response.json()["id"]

    def missing_runtime(_module_name: str):
        raise ImportError("No module named 'openai'")

    monkeypatch.setattr(recommendation_service, "import_module", missing_runtime)

    analyze_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations/{run_id}/analyze",
        headers=auth_header(token),
    )
    assert analyze_response.status_code == 503, analyze_response.text
    assert analyze_response.json()["detail"] == "Journal AI dependencies are not available in the current API runtime"

    run_response = client.get(
        f"/api/companies/{company_id}/journal-recommendations/{run_id}",
        headers=auth_header(token),
    )
    assert run_response.status_code == 200, run_response.text
    assert run_response.json()["status"] == "failed"

    settings.openai_api_key = original_api_key


def test_journal_recommendation_model_enums_bind_database_values():
    run_status_labels = list(JournalRecommendationRun.__table__.c.status.type.enums)
    proposal_type_labels = list(JournalRecommendationProposal.__table__.c.proposal_type.type.enums)
    proposal_status_labels = list(JournalRecommendationProposal.__table__.c.status.type.enums)

    assert run_status_labels == ["draft", "analyzing", "review_ready", "accepted", "rejected", "failed"]
    assert proposal_type_labels == ["account", "tax_code", "reporting_category"]
    assert proposal_status_labels == ["proposed", "accepted", "rejected", "created"]
