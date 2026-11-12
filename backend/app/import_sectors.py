"""Validate an attributed, reviewed RFC 7946 dataset and import it atomically."""
import argparse
import hashlib
import json
import math
from datetime import date
from pathlib import Path
from typing import Annotated

from geoalchemy2.shape import from_shape
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StrictBool
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.ops import unary_union
from shapely.validation import explain_validity
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import get_engine
from app.privacy import redact_database_secrets
from app.models import OccupationSector
from app.repository import SECTOR_NAMES


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verified: StrictBool
    sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    reference_date: date
    source_name: Annotated[str, Field(min_length=1)]
    source_url: HttpUrl
    license: Annotated[str, Field(min_length=1)]
    verification_notes: Annotated[str, Field(min_length=1)]


def validate_polygon(coordinates):
    if not isinstance(coordinates, list) or not coordinates:
        raise ValueError("Polygon must have rings.")
    for ring in coordinates:
        if not isinstance(ring, list) or len(ring) < 4:
            raise ValueError("Each ring must have at least four positions.")
        for point in ring:
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError("Only 2D WGS84 longitude/latitude positions are accepted.")
            if any(type(v) not in (int, float) or not math.isfinite(v) for v in point):
                raise ValueError("Coordinates must be finite numbers.")
            if not (-180 <= point[0] <= 180 and -90 <= point[1] <= 90):
                raise ValueError("Coordinates are outside WGS84 longitude/latitude ranges.")
        if ring[0] != ring[-1]:
            raise ValueError("GeoJSON rings must be explicitly closed.")


def prepare_records(raw: bytes, manifest: dict) -> list[dict]:
    document = json.loads(raw)
    if not isinstance(document, dict) or document.get("type") != "FeatureCollection" or not isinstance(document.get("features"), list):
        raise ValueError("Expected a GeoJSON FeatureCollection.")
    # RFC 7946 fixes the CRS to WGS84; legacy CRS declarations require explicit conversion first.
    if "crs" in document:
        raise ValueError("Legacy CRS declarations are not accepted; convert to RFC 7946 WGS84 first.")
    if not document["features"]:
        return []
    provenance = Provenance.model_validate(manifest)
    if not provenance.verified or provenance.sha256 != hashlib.sha256(raw).hexdigest():
        raise ValueError("Dataset must be historically verified and match the provenance SHA-256.")
    if any(not value.strip() for value in (provenance.source_name, provenance.license, provenance.verification_notes)):
        raise ValueError("Source, license and review notes must not be blank.")
    grouped = {}
    for feature in document["features"]:
        if not isinstance(feature, dict) or feature.get("type") != "Feature" or "crs" in feature:
            raise ValueError("Invalid GeoJSON Feature.")
        properties = feature.get("properties")
        if not isinstance(properties, dict) or not isinstance(properties.get("sector"), str) or properties["sector"] not in SECTOR_NAMES:
            raise ValueError("Each feature must have a recognized properties.sector.")
        code = properties["sector"]
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("type") not in ("Polygon", "MultiPolygon") or "crs" in geometry:
            raise ValueError("Only Polygon/MultiPolygon geometries are accepted.")
        coordinates = geometry.get("coordinates")
        if geometry["type"] == "Polygon":
            validate_polygon(coordinates)
        else:
            if not isinstance(coordinates, list) or not coordinates:
                raise ValueError("MultiPolygon must have polygons.")
            for polygon in coordinates:
                validate_polygon(polygon)
        polygon = shape(geometry)
        if polygon.is_empty or not polygon.is_valid or polygon.area <= 0:
            raise ValueError(f"Invalid geometry for {code}: {explain_validity(polygon)}")
        source_name = properties.get("source_name", provenance.source_name)
        source_url = str(HttpUrl(properties.get("source_url", str(provenance.source_url))))
        if not isinstance(source_name, str) or not source_name.strip():
            raise ValueError("Source name must not be blank.")
        entry = grouped.setdefault(code, {"source_name": source_name, "source_url": source_url, "polygons": []})
        if (entry["source_name"], entry["source_url"]) != (source_name, source_url):
            raise ValueError("Features in the same sector must have consistent attribution.")
        entry["polygons"].append(polygon)
    if set(grouped) != set(SECTOR_NAMES):
        raise ValueError("A nonempty import must contain all four sectors.")
    records = []
    for code, entry in sorted(grouped.items()):
        merged = unary_union(entry["polygons"])
        if isinstance(merged, Polygon):
            merged = MultiPolygon([merged])
        if not isinstance(merged, MultiPolygon) or not merged.is_valid:
            raise ValueError(f"Invalid merged geometry for {code}.")
        records.append({"code": code, "name": SECTOR_NAMES[code], "geometry": merged,
                        "source_name": entry["source_name"], "source_url": entry["source_url"]})
    for index, left in enumerate(records):
        for right in records[index + 1:]:
            if left["geometry"].intersection(right["geometry"]).area > 0:
                raise ValueError(f"Sector interiors overlap: {left['code']} and {right['code']}.")
    return records


def import_records(session: Session, records: list[dict]) -> int:
    if not records:
        return 0
    # The caller owns the transaction. Concurrent importers serialize their updates.
    session.execute(text("SELECT pg_advisory_xact_lock(19450901)"))
    for record in records:
        values = {**record, "geometry": from_shape(record["geometry"], srid=4326)}
        statement = insert(OccupationSector).values(**values)
        session.execute(statement.on_conflict_do_update(
            index_elements=[OccupationSector.code],
            set_={key: getattr(statement.excluded, key) for key in values if key != "code"},
        ))
    return len(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        records = prepare_records(args.dataset.read_bytes(), json.loads(args.manifest.read_text()))
        if not records:
            print("Historical dataset missing: empty placeholder; nothing imported or deleted.")
            return
        with Session(get_engine()) as session, session.begin():
            count = import_records(session, records)
        print(f"Imported {count} verified historical sectors.")
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Import rejected: {redact_database_secrets(str(exc))}\n")


if __name__ == "__main__":
    main()
