import json
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
    pdf_document_id = uuid4()
    image_document_id = uuid4()
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
                id=pdf_document_id,
                storage_path="pdf-storage-key",
                original_filename="invoice.pdf",
                media_type="application/pdf",
            ),
            SimpleNamespace(
                id=image_document_id,
                storage_path="image-storage-key",
                original_filename="receipt.png",
                media_type="image/png",
            ),
        ]
    )

    assert items[0]["type"] == "input_text"
    assert '"document_number":1' in items[0]["text"]
    assert f'"document_id":"{pdf_document_id}"' in items[0]["text"]
    assert items[1]["type"] == "input_file"
    assert items[1]["filename"] == "invoice.pdf"
    assert items[1]["file_data"].startswith("data:application/pdf;base64,")
    assert items[2]["type"] == "input_text"
    assert '"document_number":2' in items[2]["text"]
    assert f'"document_id":"{image_document_id}"' in items[2]["text"]
    assert items[3]["type"] == "input_image"
    assert items[3]["detail"] == "high"
    assert items[3]["image_url"].startswith("data:image/png;base64,")


def test_llm_proposal_attributes_schema_forbids_additional_properties():
    schema = recommendation_service.LlmProposalAttributes.model_json_schema()

    assert schema["additionalProperties"] is False
    assert "account_type" in schema["properties"]
    assert "allow_manual_posting" in schema["properties"]


def test_llm_recommendation_schema_limits_free_text_lengths():
    schema = recommendation_service.LlmRecommendation.model_json_schema()
    line_schema = schema["$defs"]["LlmRecommendedLine"]
    entry_schema = schema["$defs"]["LlmJournalRecommendation"]

    assert schema["properties"]["summary"]["maxLength"] == 240
    assert schema["properties"]["warning_text"]["anyOf"][0]["maxLength"] == 300
    assert schema["properties"]["journal_entries"]["minItems"] == 1
    assert schema["properties"]["journal_entries"]["maxItems"] == 50
    assert entry_schema["properties"]["lines"]["minItems"] == 2
    assert entry_schema["properties"]["lines"]["maxItems"] == 12
    assert entry_schema["properties"]["source_document_numbers"]["maxItems"] == 50
    assert "source_document_numbers" in entry_schema["required"]
    assert schema["properties"]["proposals"]["maxItems"] == 5
    assert line_schema["properties"]["description"]["anyOf"][0]["maxLength"] == 160
    assert line_schema["properties"]["explanation"]["anyOf"][0]["maxLength"] == 240


def test_structured_output_schema_uses_numeric_decimals_without_regex_patterns():
    schema = recommendation_service.LlmRecommendation.model_json_schema()

    def collect_pattern_paths(value, path="$"):
        paths = []
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}"
                if key == "pattern":
                    paths.append(child_path)
                paths.extend(collect_pattern_paths(child, child_path))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                paths.extend(collect_pattern_paths(child, f"{path}[{index}]"))
        return paths

    assert collect_pattern_paths(schema) == []
    definitions = schema["$defs"]
    journal_properties = definitions["LlmJournalRecommendation"]["properties"]
    line_properties = definitions["LlmRecommendedLine"]["properties"]
    proposal_properties = definitions["LlmProposalAttributes"]["properties"]
    assert journal_properties["total_amount"]["anyOf"] == [{"type": "number"}, {"type": "null"}]
    assert journal_properties["gst_amount"]["anyOf"] == [{"type": "number"}, {"type": "null"}]
    assert line_properties["debit_amount"]["type"] == "number"
    assert line_properties["credit_amount"]["type"] == "number"
    assert proposal_properties["rate"]["anyOf"] == [{"type": "number"}, {"type": "null"}]

    parsed = recommendation_service.LlmRecommendedLine.model_validate(
        {
            "line_number": 1,
            "description": "Expense",
            "explanation": "Numeric provider value",
            "account_code": "6440",
            "tax_code_code": None,
            "reporting_category_code": None,
            "debit_amount": 110.25,
            "credit_amount": 0,
        }
    )
    assert parsed.debit_amount == Decimal("110.25")
    assert isinstance(parsed.debit_amount, Decimal)


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

    assert context["configuration"]["bas_reporting_basis"] == "accrual"
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
    system_prompt = recommendation_service._build_system_prompt()
    assert "several documents may support one journal" in system_prompt
    assert "existing company library exactly like newly uploaded documents" in system_prompt
    assert "authoritative document_number and document_id" in system_prompt
    assert "never infer or renumber evidence" in system_prompt
    assert "unrelated invoices, receipts, payments, credits, or settlements" in system_prompt
    assert "monthly bank statement's document number on every recommendation" in system_prompt
    assert "Assign every source document number" in system_prompt
    assert "Each journal entry must independently balance" in system_prompt
    assert "never substitute upload, analysis, system, or current dates" in system_prompt
    assert "instructions" not in prefix
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


def test_multiple_accrual_request_adds_five_day_timing_instruction_only_when_applicable():
    invoice_document_id = uuid4()
    statement_document_id = uuid4()
    run = SimpleNamespace(
        analysis_mode="multiple",
        user_context_note=None,
        target_accounting_period_id=None,
    )
    documents = [
        SimpleNamespace(
            id=invoice_document_id,
            original_filename="invoice.pdf",
            media_type="application/pdf",
            byte_size=100,
        ),
        SimpleNamespace(
            id=statement_document_id,
            original_filename="monthly-bank-statement.pdf",
            media_type="application/pdf",
            byte_size=200,
        ),
    ]
    accrual_payload = json.loads(
        recommendation_service._build_recommendation_request_suffix(
            run=run,
            documents=documents,
            reference_context={"configuration": {"bas_reporting_basis": "accrual"}},
        )
    )["recommendation_request"]

    assert accrual_payload["documents"][0]["document_id"] == str(invoice_document_id)
    assert accrual_payload["documents"][0]["document_number"] == 1
    assert accrual_payload["documents"][1]["document_id"] == str(statement_document_id)
    assert accrual_payload["documents"][1]["document_number"] == 2
    assert "at least five calendar days after the invoice date" in accrual_payload["accounting_policy_instruction"]
    assert "invoice-date recognition entry" in accrual_payload["accounting_policy_instruction"]
    assert "separate clearance-date entry" in accrual_payload["accounting_policy_instruction"]
    assert "bank statement document numbers on every entry they support" in accrual_payload[
        "accounting_policy_instruction"
    ]

    cash_payload = json.loads(
        recommendation_service._build_recommendation_request_suffix(
            run=run,
            documents=documents,
            reference_context={"configuration": {"bas_reporting_basis": "cash"}},
        )
    )["recommendation_request"]
    assert cash_payload["accounting_policy_instruction"] is None

    one_file_payload = json.loads(
        recommendation_service._build_recommendation_request_suffix(
            run=run,
            documents=documents[:1],
            reference_context={"configuration": {"bas_reporting_basis": "accrual"}},
        )
    )["recommendation_request"]
    assert one_file_payload["accounting_policy_instruction"] is None

    run.analysis_mode = "single"
    single_payload = json.loads(
        recommendation_service._build_recommendation_request_suffix(
            run=run,
            documents=documents[:1],
            reference_context={"configuration": {"bas_reporting_basis": "accrual"}},
        )
    )["recommendation_request"]
    assert single_payload["accounting_policy_instruction"] is None


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
    assert '"debit_total":"110.00"' in parse_calls[1]["input"][1]["content"][0]["text"]
    assert '"credit_total":"100.00"' in parse_calls[1]["input"][1]["content"][0]["text"]


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


def test_analyze_with_openai_uses_model_prompt_cache_settings(monkeypatch):
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

    monkeypatch.setattr(
        recommendation_service,
        "ensure_supported_model",
        lambda _model: SimpleNamespace(reasoning_effort="high", supports_web_search=False, prompt_cache_retention=None),
    )
    sol_run = SimpleNamespace(
        company_id=run.company_id,
        provider_model="gpt-5.6-sol",
        id=uuid4(),
        prompt_version=recommendation_service.PROMPT_VERSION,
    )

    parsed = recommendation_service._analyze_with_openai(
        SimpleNamespace(get=lambda _model, _id: SimpleNamespace()), run=sol_run, documents=[]
    )

    assert parsed.summary == "Cache-compatible run"
    assert len(parse_calls) == 2
    assert "prompt_cache_retention" not in parse_calls[1]
    assert parse_calls[1]["reasoning"] == {"effort": "high"}


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
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "gpt-5.5",
        "gpt-5.4",
        "gpt-5.4-mini",
        "gpt-5",
        "gpt-5-mini",
        "gpt-5-nano",
    ]
    estimated_costs = {item["id"]: item["estimated_cost_per_1000_calls_usd"] for item in models}
    assert estimated_costs == {
        "gpt-5.6-sol": "305.00",
        "gpt-5.6-terra": "152.50",
        "gpt-5.6-luna": "61.00",
        "gpt-5.5": "305.00",
        "gpt-5.4": "152.50",
        "gpt-5.4-mini": "45.75",
        "gpt-5": "85.00",
        "gpt-5-mini": "17.00",
        "gpt-5-nano": "3.40",
    }
    reasoning_efforts = {item["id"]: item["reasoning_effort"] for item in models}
    assert reasoning_efforts["gpt-5.6-sol"] == "high"
    assert reasoning_efforts["gpt-5.6-terra"] == "medium"
    assert reasoning_efforts["gpt-5.6-luna"] == "low"
    assert all(item["max_file_count"] == 50 for item in models)

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
    accepted_journal = accept_response.json()["journals"][0]
    journal_id = accepted_journal["id"]
    assert accepted_journal["status"] == "draft"
    assert accepted_journal["entry_date"] == "2026-07-05"
    assert accepted_journal["description"] == "Office supplies purchase"

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
    journal_id = accept_response.json()["journals"][0]["id"]

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
    assert accept_response.json()["journals"][0]["entry_number"] == "JE-000003"

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
    assert accept_response.json()["journals"][0]["status"] == "draft"

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
    accepted_lines = accept_response.json()["journals"][0]["lines"]
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


def test_multi_document_analysis_reuses_existing_evidence_across_correct_journals(client, monkeypatch):
    settings = get_settings()
    original_api_key = settings.openai_api_key
    settings.openai_api_key = "test-key"

    def balanced_entry(
        *,
        sequence_number: int,
        source_document_numbers: list[int],
        entry_date: date,
        reference: str,
        description: str,
        amount: str,
        debit_account_code: str = "6440",
        credit_account_code: str = "1021",
    ) -> recommendation_service.LlmJournalRecommendation:
        return recommendation_service.LlmJournalRecommendation(
            sequence_number=sequence_number,
            source_document_numbers=source_document_numbers,
            summary=description,
            entry_date=entry_date,
            vendor_name="Example Supplier",
            total_amount=Decimal(amount),
            gst_amount=None,
            currency_code="AUD",
            recommended_description=description,
            recommended_reference=reference,
            confidence_summary="Source documents agree.",
            warning_text=None,
            lines=[
                recommendation_service.LlmRecommendedLine(
                    line_number=1,
                    description=description,
                    explanation="Expense recognised from source evidence.",
                    account_code=debit_account_code,
                    tax_code_code=None,
                    reporting_category_code=None,
                    debit_amount=Decimal(amount),
                    credit_amount=Decimal("0.00"),
                ),
                recommendation_service.LlmRecommendedLine(
                    line_number=2,
                    description="Operating bank",
                    explanation="Balancing payment line.",
                    account_code=credit_account_code,
                    tax_code_code=None,
                    reporting_category_code=None,
                    debit_amount=Decimal("0.00"),
                    credit_amount=Decimal(amount),
                ),
            ],
        )

    def fake_analyze(_db, *, run, documents):
        assert run.analysis_mode == "multiple"
        assert [document.original_filename for document in documents] == [
            "monthly-bank-statement.pdf",
            "invoice.pdf",
            "parking-receipt.pdf",
        ]
        return recommendation_service.LlmRecommendation(
            summary="Accrual recognition, later clearance, and parking journals found across three documents.",
            confidence_summary="The invoice and bank statement show a five-day recognition-to-clearance gap.",
            warning_text=None,
            journal_entries=[
                balanced_entry(
                    sequence_number=1,
                    source_document_numbers=[2],
                    entry_date=date(2026, 7, 5),
                    reference="INV-1001",
                    description="Recognise office supplies invoice",
                    amount="110.00",
                    credit_account_code="2011",
                ),
                balanced_entry(
                    sequence_number=2,
                    source_document_numbers=[1, 2],
                    entry_date=date(2026, 7, 10),
                    reference="INV-1001-PAY",
                    description="Clear office supplies payable",
                    amount="110.00",
                    debit_account_code="2011",
                ),
                balanced_entry(
                    sequence_number=3,
                    source_document_numbers=[1, 3],
                    entry_date=date(2026, 7, 11),
                    reference="PARK-22",
                    description="Client parking",
                    amount="24.00",
                ),
            ],
            proposals=[],
        )

    monkeypatch.setattr(recommendation_service, "_analyze_with_openai", fake_analyze)

    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    statement_response = client.post(
        f"/api/companies/{company_id}/documents",
        headers=auth_header(token),
        files={
            "file": (
                "monthly-bank-statement.pdf",
                b"%PDF-1.4 previously uploaded statement",
                "application/pdf",
            )
        },
    )
    assert statement_response.status_code == 201, statement_response.text
    statement_id = statement_response.json()["id"]
    create_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations",
        headers=auth_header(token),
        files=[
            ("files", ("invoice.pdf", b"%PDF-1.4 invoice", "application/pdf")),
            ("files", ("parking-receipt.pdf", b"%PDF-1.4 parking", "application/pdf")),
        ],
        data={
            "analysis_mode": "multiple",
            "model": "gpt-5.4-mini",
            "existing_document_ids": statement_id,
            "user_context_note": "The bank statement contains the invoice clearance and a separate parking payment.",
            "target_accounting_period_id": period_id,
        },
    )
    assert create_response.status_code == 201, create_response.text
    assert create_response.json()["analysis_mode"] == "multiple"

    analyze_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations/{create_response.json()['id']}/analyze",
        headers=auth_header(token),
    )
    assert analyze_response.status_code == 200, analyze_response.text
    recommendations = analyze_response.json()["entries"]
    assert len(recommendations) == 3
    assert [document["original_filename"] for document in recommendations[0]["documents"]] == ["invoice.pdf"]
    assert [document["original_filename"] for document in recommendations[1]["documents"]] == [
        "monthly-bank-statement.pdf",
        "invoice.pdf",
    ]
    assert [document["original_filename"] for document in recommendations[2]["documents"]] == [
        "monthly-bank-statement.pdf",
        "parking-receipt.pdf",
    ]
    assert [len(entry["lines"]) for entry in recommendations] == [2, 2, 2]

    accept_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations/{create_response.json()['id']}/accept",
        headers=auth_header(token),
        json={"accepted_proposal_ids": []},
    )
    assert accept_response.status_code == 200, accept_response.text
    journals = accept_response.json()["journals"]
    assert len(journals) == 3
    assert [journal["reference"] for journal in journals] == ["INV-1001", "INV-1001-PAY", "PARK-22"]

    first_evidence = client.get(
        f"/api/companies/{company_id}/journals/{journals[0]['id']}/documents",
        headers=auth_header(token),
    )
    second_evidence = client.get(
        f"/api/companies/{company_id}/journals/{journals[1]['id']}/documents",
        headers=auth_header(token),
    )
    third_evidence = client.get(
        f"/api/companies/{company_id}/journals/{journals[2]['id']}/documents",
        headers=auth_header(token),
    )
    assert [item["original_filename"] for item in first_evidence.json()] == ["invoice.pdf"]
    assert {item["original_filename"] for item in second_evidence.json()} == {
        "invoice.pdf",
        "monthly-bank-statement.pdf",
    }
    assert {item["original_filename"] for item in third_evidence.json()} == {
        "monthly-bank-statement.pdf",
        "parking-receipt.pdf",
    }
    second_evidence_by_name = {item["original_filename"]: item for item in second_evidence.json()}
    third_evidence_by_name = {item["original_filename"]: item for item in third_evidence.json()}
    assert first_evidence.json()[0]["note"] == "AI recommendation source document #2"
    assert second_evidence_by_name["monthly-bank-statement.pdf"]["document_id"] == statement_id
    assert third_evidence_by_name["monthly-bank-statement.pdf"]["document_id"] == statement_id
    assert second_evidence_by_name["monthly-bank-statement.pdf"]["note"] == (
        "AI recommendation source document #1"
    )
    assert second_evidence_by_name["invoice.pdf"]["note"] == "AI recommendation source document #2"
    assert third_evidence_by_name["monthly-bank-statement.pdf"]["note"] == (
        "AI recommendation source document #1"
    )
    assert third_evidence_by_name["parking-receipt.pdf"]["note"] == (
        "AI recommendation source document #3"
    )
    settings.openai_api_key = original_api_key


def test_journal_recommendation_upload_modes_enforce_single_and_fifty_file_limits(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)

    single_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations",
        headers=auth_header(token),
        files=[
            ("files", ("one.pdf", b"%PDF-1.4 one", "application/pdf")),
            ("files", ("two.pdf", b"%PDF-1.4 two", "application/pdf")),
        ],
        data={"analysis_mode": "single", "model": "gpt-5.4-mini"},
    )
    assert single_response.status_code == 400, single_response.text
    assert single_response.json()["detail"] == "Single-document analysis requires exactly one evidence document"

    too_many_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations",
        headers=auth_header(token),
        files=[
            ("files", (f"document-{number:02}.pdf", b"%PDF-1.4 tiny", "application/pdf"))
            for number in range(1, 52)
        ],
        data={"analysis_mode": "multiple", "model": "gpt-5.4-mini"},
    )
    assert too_many_response.status_code == 400, too_many_response.text
    assert too_many_response.json()["detail"] == "Select at most 50 evidence documents per recommendation run"


def test_journal_recommendation_can_reuse_existing_documents_and_mix_new_uploads(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)

    statement_response = client.post(
        f"/api/companies/{company_id}/documents",
        headers=auth_header(token),
        files={"file": ("existing-bank-statement.pdf", b"%PDF-1.4 existing statement", "application/pdf")},
    )
    invoice_response = client.post(
        f"/api/companies/{company_id}/documents",
        headers=auth_header(token),
        files={"file": ("existing-invoice.png", b"existing invoice image", "image/png")},
    )
    assert statement_response.status_code == 201, statement_response.text
    assert invoice_response.status_code == 201, invoice_response.text
    statement_id = statement_response.json()["id"]
    invoice_id = invoice_response.json()["id"]

    existing_only_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations",
        headers=auth_header(token),
        data={
            "analysis_mode": "multiple",
            "model": "gpt-5.4-mini",
            "existing_document_ids": [statement_id, invoice_id],
        },
    )
    assert existing_only_response.status_code == 201, existing_only_response.text
    existing_only_documents = existing_only_response.json()["documents"]
    assert [item["document_id"] for item in existing_only_documents] == [statement_id, invoice_id]
    assert [item["display_order"] for item in existing_only_documents] == [1, 2]

    mixed_response = client.post(
        f"/api/companies/{company_id}/journal-recommendations",
        headers=auth_header(token),
        files={"files": ("new-receipt.pdf", b"%PDF-1.4 new receipt", "application/pdf")},
        data={
            "analysis_mode": "multiple",
            "model": "gpt-5.4-mini",
            "existing_document_ids": statement_id,
        },
    )
    assert mixed_response.status_code == 201, mixed_response.text
    mixed_documents = mixed_response.json()["documents"]
    assert [item["document_id"] for item in mixed_documents[:1]] == [statement_id]
    assert [item["original_filename"] for item in mixed_documents] == [
        "existing-bank-statement.pdf",
        "new-receipt.pdf",
    ]
    assert [item["display_order"] for item in mixed_documents] == [1, 2]


def test_journal_recommendation_rejects_existing_document_from_another_company(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    other_company_id = create_company(client, token)
    foreign_document_response = client.post(
        f"/api/companies/{other_company_id}/documents",
        headers=auth_header(token),
        files={"file": ("foreign-statement.pdf", b"%PDF-1.4 foreign", "application/pdf")},
    )
    assert foreign_document_response.status_code == 201, foreign_document_response.text

    response = client.post(
        f"/api/companies/{company_id}/journal-recommendations",
        headers=auth_header(token),
        data={
            "analysis_mode": "single",
            "model": "gpt-5.4-mini",
            "existing_document_ids": foreign_document_response.json()["id"],
        },
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Existing evidence document not found"


def test_journal_recommendation_model_enums_bind_database_values():
    run_status_labels = list(JournalRecommendationRun.__table__.c.status.type.enums)
    proposal_type_labels = list(JournalRecommendationProposal.__table__.c.proposal_type.type.enums)
    proposal_status_labels = list(JournalRecommendationProposal.__table__.c.status.type.enums)

    assert run_status_labels == ["draft", "analyzing", "review_ready", "accepted", "rejected", "failed"]
    assert proposal_type_labels == ["account", "tax_code", "reporting_category"]
    assert proposal_status_labels == ["proposed", "accepted", "rejected", "created"]
