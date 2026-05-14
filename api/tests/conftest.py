from collections.abc import Generator
from pathlib import Path
import shutil

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.config import get_settings
from app.db.base import Base
from app.main import app


SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def upsert_test_account(
    client: TestClient,
    token: str,
    company_id: str,
    *,
    account_code: str,
    name: str,
    account_type: str,
    reporting_category_id: str | None = None,
    default_tax_code_id: str | None = None,
    is_active: bool = True,
    allow_manual_posting: bool = True,
) -> str:
    payload = {
        "account_code": account_code,
        "name": name,
        "account_type": account_type,
        "reporting_category_id": reporting_category_id,
        "default_tax_code_id": default_tax_code_id,
        "is_active": is_active,
        "allow_manual_posting": allow_manual_posting,
    }
    response = client.post(
        f"/api/companies/{company_id}/accounts",
        headers=auth_header(token),
        json=payload,
    )
    if response.status_code == 201:
        return response.json()["id"]

    assert response.status_code == 409, response.text
    accounts_response = client.get(
        f"/api/companies/{company_id}/accounts",
        headers=auth_header(token),
    )
    assert accounts_response.status_code == 200, accounts_response.text
    existing_account = next(
        (item for item in accounts_response.json() if item["account_code"] == account_code),
        None,
    )
    assert existing_account is not None, f"Expected existing account {account_code} after conflict"

    update_response = client.put(
        f"/api/companies/{company_id}/accounts/{existing_account['id']}",
        headers=auth_header(token),
        json=payload,
    )
    assert update_response.status_code == 200, update_response.text
    return update_response.json()["id"]


@pytest.fixture(autouse=True)
def reset_database() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def isolate_document_storage(tmp_path: Path) -> Generator[None, None, None]:
    settings = get_settings()
    original_path = settings.document_storage_path
    storage_path = tmp_path / "documents"
    settings.document_storage_path = str(storage_path)
    yield
    settings.document_storage_path = original_path
    shutil.rmtree(storage_path, ignore_errors=True)


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
