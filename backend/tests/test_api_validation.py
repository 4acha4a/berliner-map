import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.db import get_db
from app.main import app


@pytest.mark.parametrize("query", ["lat=91&lng=0", "lat=-91&lng=0", "lat=0&lng=181", "lat=nan&lng=0", "lat=0&lng=inf", "lng=0", "lat=0&lng=0&extra=1"])
def test_query_validation_without_database(query):
    # Invalid queries must be rejected before executing any spatial operation.
    app.dependency_overrides[get_db] = lambda: object()
    try:
        with TestClient(app) as client:
            assert client.get(f"/api/v1/sectors/identify?{query}").status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_database_failure_is_503():
    def unavailable_db():
        raise SQLAlchemyError("Test failure containing private connection details")

    app.dependency_overrides[get_db] = unavailable_db
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/health")
            assert response.status_code == 503
            assert response.json() == {"detail": "Database unavailable or migrations required."}
    finally:
        app.dependency_overrides.clear()
