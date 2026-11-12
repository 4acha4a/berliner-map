"""Artificial unit squares near (0, 0); these tests contain no historical geometry."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from pyproj import Transformer
from shapely.geometry import box, mapping, shape, MultiPolygon
from shapely.ops import unary_union

from reconstruct_sectors import ASSIGNMENTS, DATE, reconstruct, transform


def source(tmp_path, name, features, crs="EPSG:4326"):
    raw = json.dumps({"type": "FeatureCollection", "features": features}).encode()
    (tmp_path / name).write_bytes(raw)
    return {"path": name, "sha256": hashlib.sha256(raw).hexdigest(), "crs": crs,
            "source_name": "SYNTHETIC TEST FIXTURE", "source_url": "https://example.com/synthetic",
            "license": "Test fixture only", "historically_reviewed": True, "redistribution_permitted": True,
            "review_notes": "Artificial unit squares near zero, not historical data"}


def feature(geometry, **props):
    return {"type": "Feature", "properties": props, "geometry": mapping(geometry)}


@pytest.fixture
def dataset(tmp_path):
    geometries = [box(i % 5, i // 5, i % 5 + 1, i // 5 + 1) for i in range(20)]
    features = [feature(g, borough=name, reference_date=DATE, evidence_url="https://example.com/synthetic",
                        historical_status="supported_reconstruction") for name, g in zip(ASSIGNMENTS, geometries)]
    manifest = {"reference_date": DATE, "uncertainty_notes": "SYNTHETIC FIXTURE; no historical accuracy",
                "assignment_evidence_url": "https://example.com/synthetic", "enclaves_reviewed": True,
                "boroughs": source(tmp_path, "boroughs.json", features),
                "coverage": source(tmp_path, "coverage.json", [feature(unary_union(geometries))]),
                "gatow_staaken": {"status": "included_in_boroughs", "notes": "Synthetic test only",
                                 "evidence_url": "https://example.com/synthetic", "occupation_vs_administration": "Synthetic convention"}}
    return manifest, features


def test_complete_dissolves_and_preserves_evidence_without_release_attestation(tmp_path, dataset):
    manifest, _ = dataset
    raw, provenance, report = reconstruct(manifest, tmp_path, "complete")
    assert len(json.loads(raw)["features"]) == 4
    assert provenance["sha256"] == hashlib.sha256(raw).hexdigest()
    assert provenance["verified"] is False
    assert report["missing_boroughs"] == []
    assert max(report["coverage_difference"].values()) <= .01
    for f in json.loads(raw)["features"]:
        assert f["properties"]["borough_evidence"]
        assert f["properties"]["sources"][0]["license"] == "Test fixture only"


def test_partial_preserves_missing_boroughs_and_exception(tmp_path, dataset):
    manifest, features = dataset
    manifest["boroughs"] = source(tmp_path, "partial.json", features[:1])
    manifest["gatow_staaken"] = {"status": "unresolved", "notes": "Not known"}
    raw, provenance, report = reconstruct(manifest, tmp_path, "partial")
    assert len(report["missing_boroughs"]) == 19 and report["unresolved_exception"]
    assert provenance["verified"] is False and len(json.loads(raw)["features"]) == 1
    with pytest.raises(ValueError, match="Missing boroughs"):
        reconstruct(manifest, tmp_path, "complete")


@pytest.mark.parametrize("field,value,match", [("reference_date", "1945-08-01", "Reference date"),
    ("enclaves_reviewed", False, "Enclave"), ("coverage", None, "coverage")])
def test_complete_release_prerequisites(tmp_path, dataset, field, value, match):
    manifest, _ = dataset
    manifest[field] = value
    with pytest.raises(ValueError, match=match): reconstruct(manifest, tmp_path, "complete")


@pytest.mark.parametrize("key,value,match", [("sha256", "bad", "checksum"),
    ("historically_reviewed", False, "review"), ("redistribution_permitted", False, "review")])
def test_source_evidence_rejected(tmp_path, dataset, key, value, match):
    manifest, _ = dataset
    manifest["boroughs"][key] = value
    with pytest.raises(ValueError, match=match): reconstruct(manifest, tmp_path, "complete")


def test_overlap_and_coverage_gap_rejected(tmp_path, dataset):
    manifest, features = dataset
    overlap = copy.deepcopy(features)
    overlap[1]["geometry"] = overlap[0]["geometry"]
    manifest["boroughs"] = source(tmp_path, "overlap.json", overlap)
    with pytest.raises(ValueError, match="overlap"): reconstruct(manifest, tmp_path, "complete")
    manifest["boroughs"] = source(tmp_path, "boroughs.json", features)
    manifest["coverage"] = source(tmp_path, "wrong-coverage.json", [feature(box(0, 0, 6, 4))])
    with pytest.raises(ValueError, match="Coverage mismatch"): reconstruct(manifest, tmp_path, "complete")


def test_projected_input_reprojects_with_longitude_first(tmp_path, dataset):
    manifest, features = dataset
    project = Transformer.from_crs(4326, 3857, always_xy=True).transform
    projected = [{**f, "geometry": mapping(transform(project, shape(f["geometry"])))} for f in features]
    manifest["boroughs"] = source(tmp_path, "projected.json", projected, "EPSG:3857")
    raw, _, report = reconstruct(manifest, tmp_path, "complete")
    assert report["transformations"][0]["source_crs"] == "EPSG:3857"
    assert unary_union([shape(f["geometry"]) for f in json.loads(raw)["features"]]).symmetric_difference(box(0, 0, 5, 4)).area < 1e-12


def test_reviewed_remove_and_add_adjustments(tmp_path, dataset):
    manifest, features = dataset
    first, second = list(ASSIGNMENTS)[:2]
    patch = box(0, 0, .25, 1)
    adjustments = [feature(patch, borough=first, operation="remove", evidence_url="https://example.com/synthetic"),
                   feature(patch, borough=second, operation="add", evidence_url="https://example.com/synthetic")]
    manifest["gatow_staaken"]["status"] = "reviewed_adjustments"
    manifest["gatow_staaken"]["adjustments"] = source(tmp_path, "adjustments.json", adjustments)
    _, _, report = reconstruct(manifest, tmp_path, "complete")
    assert len(report["adjustment_evidence"]) == 2
    assert max(report["coverage_difference"].values()) <= .01


def test_unresolved_exception_blocks_complete_build(tmp_path, dataset):
    manifest, _ = dataset
    manifest["gatow_staaken"] = {"status": "unresolved", "notes": "No geometry"}
    with pytest.raises(ValueError, match="Gatow/Staaken unresolved"): reconstruct(manifest, tmp_path, "complete")
    with pytest.raises(ValueError, match="Exclude Spandau"): reconstruct(manifest, tmp_path, "partial")


def test_invalid_topology_rejected(tmp_path, dataset):
    manifest, features = dataset
    features[0]["geometry"] = {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]}
    manifest["boroughs"] = source(tmp_path, "invalid.json", features)
    with pytest.raises(ValueError, match="topology"): reconstruct(manifest, tmp_path, "complete")


def test_holes_and_disconnected_parts_survive(tmp_path, dataset):
    manifest, features = dataset
    original = shape(features[0]["geometry"])
    geometry = MultiPolygon([original.difference(box(.2, .2, .4, .4)), box(-2, -2, -1, -1)])
    features[0]["geometry"] = mapping(geometry)
    manifest["boroughs"] = source(tmp_path, "multipart.json", features)
    manifest["coverage"] = source(tmp_path, "coverage.json", [feature(unary_union([shape(f["geometry"]) for f in features]))])
    raw, _, _ = reconstruct(manifest, tmp_path, "complete")
    result = next(shape(f["geometry"]) for f in json.loads(raw)["features"] if f["properties"]["sector"] == "french")
    assert not result.covers(box(.25, .25, .3, .3))
    assert result.covers(box(-1.8, -1.8, -1.2, -1.2))


def test_cli_writes_review_bundle_and_refuses_overwrite(tmp_path, dataset):
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(dataset[0]))
    output = tmp_path / "candidate"
    command = [sys.executable, str(Path(__file__).with_name("reconstruct_sectors.py")), str(manifest_file),
               "--mode", "complete", "--output-dir", str(output)]
    first = subprocess.run(command, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    assert json.loads((output / "berlin-sectors.provenance.json").read_text())["verified"] is False
    before = (output / "berlin-sectors.geojson").read_bytes()
    second = subprocess.run(command, capture_output=True, text=True)
    assert second.returncode != 0 and "refusing to overwrite" in second.stderr
    assert (output / "berlin-sectors.geojson").read_bytes() == before


def test_rejected_cli_build_writes_no_candidate(tmp_path, dataset):
    manifest = dataset[0]
    manifest["gatow_staaken"] = {"status": "unresolved", "notes": "Fixture"}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    output = tmp_path / "rejected"
    result = subprocess.run([sys.executable, str(Path(__file__).with_name("reconstruct_sectors.py")), str(path),
                             "--mode", "complete", "--output-dir", str(output)], capture_output=True, text=True)
    assert result.returncode != 0 and not output.exists()


def test_explicit_approximation_mode_keeps_strict_modes_and_release_gate(tmp_path, dataset):
    manifest, features = dataset
    for f in features: f["properties"]["historical_status"] = "approximate_proxy"
    manifest["boroughs"] = source(tmp_path, "approximate.json", features)
    manifest["boroughs"].update(historically_reviewed=False, reviewed_for_approximation=True, accuracy="approximate")
    manifest.update(accuracy="approximate", excluded_coverage_notes="Synthetic exclusion only", enclaves_reviewed=False)
    manifest["gatow_staaken"] = {"status": "unresolved", "notes": "Synthetic proxy test only"}
    raw, provenance, report = reconstruct(manifest, tmp_path, "approximate")
    assert provenance["verified"] is False and report["unresolved_exception"]
    assert all(f["properties"]["accuracy"] == "approximate" and f["properties"]["coverage_status"] == "partial" for f in json.loads(raw)["features"])
    with pytest.raises(ValueError, match="review"):
        reconstruct(manifest, tmp_path, "complete")
    manifest["coverage"] = None
    with pytest.raises(ValueError, match="coverage"):
        reconstruct(manifest, tmp_path, "approximate")


@pytest.mark.integration
def test_candidate_through_unchanged_importer_and_real_postgis(tmp_path, dataset):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, delete, select
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session
    from app.db import get_db
    from app.import_sectors import prepare_records, import_records
    from app.main import app
    from app.models import OccupationSector

    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Dedicated PostGIS TEST_DATABASE_URL required")
    parsed = make_url(url)
    assert parsed.get_backend_name() == "postgresql" and parsed.database.endswith("_test")
    raw, provenance, _ = reconstruct(dataset[0], tmp_path, "complete")
    # The workflow must not make review candidates production-importable itself.
    with pytest.raises(ValueError, match="verified"):
        prepare_records(raw, provenance)
    # Synthetic test attestation only, in a dedicated rolled-back test transaction.
    records = prepare_records(raw, {**provenance, "verified": True})
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
                    db.execute(delete(OccupationSector))
                    assert import_records(db, records) == 4
                    before = dict(db.execute(select(OccupationSector.code, OccupationSector.id)).all())
                    assert import_records(db, records) == 4
                    assert dict(db.execute(select(OccupationSector.code, OccupationSector.id)).all()) == before
                    app.dependency_overrides[get_db] = lambda: db
                    try:
                        with TestClient(app) as client:
                            result = client.get("/api/v1/sectors")
                            assert result.status_code == 200 and len(result.json()["features"]) == 4
                            assert all(f["properties"]["source_name"] == "SYNTHETIC TEST FIXTURE" for f in result.json()["features"])
                            for record in records:
                                point = record["geometry"].representative_point()
                                response = client.get("/api/v1/sectors/identify", params={"lat": point.y, "lng": point.x})
                                assert response.status_code == 200 and response.json()["sector"]["code"] == record["code"]
                    finally:
                        app.dependency_overrides.clear()
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
