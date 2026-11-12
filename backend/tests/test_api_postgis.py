import pytest
from sqlalchemy import func, select, text

from app.import_sectors import import_records, prepare_records
from app.models import OccupationSector

pytestmark = pytest.mark.integration


def seed(db, synthetic_dataset):
    return import_records(db, prepare_records(*synthetic_dataset))


def test_health_missing_dataset(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "dataset_status": "missing"}


def test_missing_dataset_is_distinct_from_outside(client):
    assert client.get("/api/v1/sectors").json() == {
        "type": "FeatureCollection", "features": [], "dataset_status": "missing"}
    response = client.get("/api/v1/sectors/identify", params={"lat": 52.52, "lng": 13.405})
    assert response.status_code == 200
    assert response.json() == {"dataset_status": "missing", "sector": None}


@pytest.mark.parametrize("query", ["lat=91&lng=0", "lat=0&lng=-181", "lat=nan&lng=0", "lat=0&lng=inf", "lat=x&lng=0", "lat=0", "lat=0&lng=0&extra=1"])
def test_coordinate_validation(client, query):
    assert client.get(f"/api/v1/sectors/identify?{query}").status_code == 422


def test_geojson_output(client, db, synthetic_dataset):
    seed(db, synthetic_dataset)
    response = client.get("/api/v1/sectors")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert data["dataset_status"] == "ready"
    assert len(data["features"]) == 4
    feature = data["features"][0]
    assert feature["geometry"]["type"] == "MultiPolygon"
    assert feature["properties"]["sector"] == "american"
    assert feature["properties"]["source_name"] == "SYNTHETIC TEST FIXTURE"
    assert feature["properties"]["source_url"] == "https://example.com/test-fixture"


@pytest.mark.parametrize("lat,lng,code", [(0.5, 0.5, "soviet"), (0.5, 1.5, "american"), (1.5, 0.5, "british"), (1.5, 1.5, "french")])
def test_spatial_classification(client, db, synthetic_dataset, lat, lng, code):
    seed(db, synthetic_dataset)
    data = client.get("/api/v1/sectors/identify", params={"lat": lat, "lng": lng}).json()
    assert data["dataset_status"] == "ready"
    assert data["sector"]["code"] == code


def test_outside_coverage(client, db, synthetic_dataset):
    seed(db, synthetic_dataset)
    assert client.get("/api/v1/sectors/identify?lat=52.52&lng=13.405").json() == {
        "dataset_status": "ready", "sector": None}


def test_shared_boundary_uses_stable_code_order(client, db, synthetic_dataset):
    seed(db, synthetic_dataset)
    assert client.get("/api/v1/sectors/identify?lat=0.5&lng=1").json()["sector"]["code"] == "american"


def test_idempotent_import_updates_preserves_ids(db, synthetic_dataset):
    records = prepare_records(*synthetic_dataset)
    assert import_records(db, records) == 4
    before = dict(db.execute(select(OccupationSector.code, OccupationSector.id)).all())
    records[0]["source_name"] = "Updated test source"
    assert import_records(db, records) == 4
    assert dict(db.execute(select(OccupationSector.code, OccupationSector.id)).all()) == before
    assert db.scalar(select(func.count()).select_from(OccupationSector)) == 4
    assert db.scalar(select(OccupationSector.source_name).where(OccupationSector.code == records[0]["code"])) == "Updated test source"
    assert import_records(db, []) == 0
    assert db.scalar(select(func.count()).select_from(OccupationSector)) == 4


def test_partial_database_returns_503(client, db, synthetic_dataset):
    seed(db, synthetic_dataset)
    db.execute(text("DELETE FROM occupation_sectors WHERE code='french'"))
    for path in ("/api/v1/health", "/api/v1/sectors", "/api/v1/sectors/identify?lat=0&lng=0"):
        assert client.get(path).status_code == 503


def test_migration_created_postgis_and_gist(db):
    assert db.scalar(text("SELECT PostGIS_Version()"))
    definition = db.scalar(text("SELECT indexdef FROM pg_indexes WHERE tablename='occupation_sectors' AND indexname='idx_occupation_sectors_geometry'"))
    assert "USING gist" in definition
    assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0001"


def test_import_rolls_back_as_one_transaction(db, synthetic_dataset):
    records = prepare_records(*synthetic_dataset)
    with pytest.raises(RuntimeError):
        with db.begin_nested():
            import_records(db, records)
            raise RuntimeError("Simulated failed import")
    assert db.scalar(select(func.count()).select_from(OccupationSector)) == 0


def test_holes_and_disconnected_parts(client, db, synthetic_dataset):
    from shapely.geometry import MultiPolygon, Polygon

    records = prepare_records(*synthetic_dataset)
    soviet = next(record for record in records if record["code"] == "soviet")
    outer = [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]
    hole = [(0.2, 0.2), (0.4, 0.2), (0.4, 0.4), (0.2, 0.4), (0.2, 0.2)]
    detached = [(3, 3), (4, 3), (4, 4), (3, 4), (3, 3)]
    soviet["geometry"] = MultiPolygon([Polygon(outer, [hole]), Polygon(detached)])
    import_records(db, records)
    assert client.get("/api/v1/sectors/identify?lat=0.3&lng=0.3").json() == {
        "dataset_status": "ready", "sector": None}
    assert client.get("/api/v1/sectors/identify?lat=3.5&lng=3.5").json()["sector"]["code"] == "soviet"
    feature = next(f for f in client.get("/api/v1/sectors").json()["features"] if f["properties"]["sector"] == "soviet")
    assert len(feature["geometry"]["coordinates"]) == 2
    assert len(feature["geometry"]["coordinates"][0]) == 2
    assert db.scalar(text("SELECT ST_SRID(geometry) FROM occupation_sectors LIMIT 1")) == 4326
