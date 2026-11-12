import hashlib
import json
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import app
from app.models import OccupationSector


@pytest.fixture
def synthetic_dataset():
    # Artificial unit squares near (0, 0) are test fixtures, never historical Berlin data.
    origins = {"soviet": (0, 0), "american": (1, 0), "british": (0, 1), "french": (1, 1)}
    features = []
    for code, (x, y) in origins.items():
        features.append({"type": "Feature", "properties": {"sector": code}, "geometry": {
            "type": "Polygon", "coordinates": [[[x, y], [x + 1, y], [x + 1, y + 1], [x, y + 1], [x, y]]],
        }})
    document = {"type": "FeatureCollection", "features": features}
    raw = json.dumps(document).encode()
    manifest = {"verified": True, "sha256": hashlib.sha256(raw).hexdigest(), "reference_date": "1945-09-01",
                "source_name": "SYNTHETIC TEST FIXTURE", "source_url": "https://example.com/test-fixture",
                "license": "Test fixture only", "verification_notes": "Artificial geometry for software tests; not historical data."}
    return raw, manifest


@pytest.fixture(scope="session")
def postgis_engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run real PostGIS integration tests.")
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql" or not (parsed.database or "").endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must point to a dedicated PostgreSQL database ending in _test.")
    engine = create_engine(url, pool_pre_ping=True)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db(postgis_engine):
    with postgis_engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            session.execute(delete(OccupationSector))
            yield session
        transaction.rollback()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
