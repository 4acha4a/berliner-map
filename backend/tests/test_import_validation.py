import hashlib
import json

import pytest

from app.import_sectors import prepare_records


def edited(raw, manifest, mutate):
    document = json.loads(raw)
    mutate(document)
    raw = json.dumps(document).encode()
    return raw, {**manifest, "sha256": hashlib.sha256(raw).hexdigest()}


def test_empty_dataset_does_not_need_verified_provenance():
    assert prepare_records(b'{"type":"FeatureCollection","features":[]}', {"verified": False}) == []


def test_valid_polygons_normalized_to_multi(synthetic_dataset):
    records = prepare_records(*synthetic_dataset)
    assert len(records) == 4
    assert all(record["geometry"].geom_type == "MultiPolygon" for record in records)
    assert all(record["source_name"] == "SYNTHETIC TEST FIXTURE" for record in records)


def test_unverified_or_changed_dataset_rejected(synthetic_dataset):
    raw, manifest = synthetic_dataset
    with pytest.raises(ValueError):
        prepare_records(raw, {**manifest, "verified": False})
    with pytest.raises(ValueError):
        prepare_records(raw + b" ", manifest)


def test_legacy_crs_rejected(synthetic_dataset):
    with pytest.raises(ValueError, match="CRS"):
        prepare_records(*edited(*synthetic_dataset, lambda doc: doc.update(crs={"type": "name", "properties": {"name": "EPSG:3857"}})))


@pytest.mark.parametrize("bad_point", [[181, 0], [0, 91], [float("nan"), 0], [True, 0], [0, 0, 1]])
def test_invalid_coordinates_rejected(synthetic_dataset, bad_point):
    def mutate(doc):
        doc["features"][0]["geometry"]["coordinates"][0][1] = bad_point
    with pytest.raises(ValueError):
        prepare_records(*edited(*synthetic_dataset, mutate))


def test_unclosed_ring_rejected(synthetic_dataset):
    def mutate(doc):
        doc["features"][0]["geometry"]["coordinates"][0].pop()
    with pytest.raises(ValueError, match="closed"):
        prepare_records(*edited(*synthetic_dataset, mutate))


def test_invalid_topology_rejected(synthetic_dataset):
    def mutate(doc):
        doc["features"][0]["geometry"]["coordinates"] = [[[0, 0], [1, 1], [0, 1], [1, 0], [0, 0]]]
    with pytest.raises(ValueError, match="Invalid geometry"):
        prepare_records(*edited(*synthetic_dataset, mutate))


def test_overlapping_sectors_rejected(synthetic_dataset):
    def mutate(doc):
        doc["features"][1]["geometry"] = doc["features"][0]["geometry"]
    with pytest.raises(ValueError, match="overlap"):
        prepare_records(*edited(*synthetic_dataset, mutate))


def test_incomplete_collection_rejected(synthetic_dataset):
    with pytest.raises(ValueError, match="all four"):
        prepare_records(*edited(*synthetic_dataset, lambda doc: doc["features"].pop()))


def test_missing_attribution_rejected(synthetic_dataset):
    raw, manifest = synthetic_dataset
    with pytest.raises(ValueError):
        prepare_records(raw, {**manifest, "source_url": ""})


def test_multiple_features_in_one_sector_merge(synthetic_dataset):
    def mutate(doc):
        doc["features"].append(doc["features"][0])
    assert len(prepare_records(*edited(*synthetic_dataset, mutate))) == 4
