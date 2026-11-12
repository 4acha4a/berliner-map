"""Build review candidates from evidenced historical boroughs; never publish or attest verification."""
import argparse
import hashlib
import json
import math
from pathlib import Path

import geopandas as gpd
import pyproj
import shapely
from pyproj import CRS, Transformer
from pyproj.exceptions import ProjError
from shapely.errors import ShapelyError
from shapely.geometry import mapping, shape
from shapely.ops import unary_union


def transform(operation, geometry):
    return shapely.transform(geometry, operation, interleaved=False)


DATE = "1945-09-01"
ASSIGNMENT_URL = "https://www.statistischebibliothek.de/mir/servlets/MCRFileNodeServlet/BBMonografie_derivate_00000068/100jahregrossberlin.pdf"
ASSIGNMENTS = {
    "Reinickendorf": "french", "Wedding": "french",
    "Spandau": "british", "Tiergarten": "british", "Charlottenburg": "british", "Wilmersdorf": "british",
    "Steglitz": "american", "Zehlendorf": "american", "Neukölln": "american",
    "Schöneberg": "american", "Tempelhof": "american", "Kreuzberg": "american",
    "Pankow": "soviet", "Prenzlauer Berg": "soviet", "Mitte": "soviet", "Treptow": "soviet",
    "Köpenick": "soviet", "Weißensee": "soviet", "Friedrichshain": "soviet", "Lichtenberg": "soviet",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def url(value):
    return text(value) and value.startswith(("https://", "http://"))


def polygon(document):
    require(isinstance(document, dict) and document.get("type") in ("Polygon", "MultiPolygon") and "crs" not in document,
            "Only explicit 2D polygon geometry is supported")
    polygons = [document["coordinates"]] if document["type"] == "Polygon" else document["coordinates"]
    require(bool(polygons), "Empty geometry")
    for rings in polygons:
        require(bool(rings), "Empty rings")
        for ring in rings:
            require(len(ring) >= 4 and ring[0] == ring[-1], "Rings must be explicitly closed")
            for position in ring:
                require(len(position) == 2 and all(type(v) in (int, float) and math.isfinite(v) for v in position),
                        "Coordinates must be finite, numeric, and 2D")
    result = shape(document)
    require(not result.is_empty and result.is_valid and result.area > 0, "Invalid polygon topology")
    return result


def load_source(spec, base, transformations, allow_approximate=False):
    require(isinstance(spec, dict), "Source descriptor required")
    for key in ("path", "source_name", "license", "review_notes", "crs"):
        require(text(spec.get(key)), f"Source {key} required")
    require(url(spec.get("source_url")), "Source URL required")
    require((spec.get("historically_reviewed") is True or
             (allow_approximate and spec.get("reviewed_for_approximation") is True and spec.get("accuracy") == "approximate"))
            and spec.get("redistribution_permitted") is True,
            "Historical and redistribution review required for every input")
    raw = (base / spec["path"]).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == spec.get("sha256"), "Source checksum mismatch")
    doc = json.loads(raw)
    require(doc.get("type") == "FeatureCollection" and "crs" not in doc and isinstance(doc.get("features"), list),
            "Expected FeatureCollection; declare source CRS only in manifest")
    crs = CRS.from_user_input(spec["crs"])
    transformer = Transformer.from_crs(crs, 4326, always_xy=True, allow_ballpark=False, only_best=True)
    features = []
    for feature in doc["features"]:
        require(feature.get("type") == "Feature" and "crs" not in feature, "Invalid Feature")
        geometry = polygon(feature.get("geometry"))
        if crs.is_geographic:
            require(crs.equals(CRS.from_epsg(4326)), "Geographic inputs must be EPSG:4326; preconvert other angular CRSs explicitly")
            xmin, ymin, xmax, ymax = geometry.bounds
            require(-180 <= xmin <= xmax <= 180 and -90 <= ymin <= ymax <= 90, "Invalid WGS84 coordinate range")
        converted = transform(lambda x, y: transformer.transform(x, y, errcheck=True), geometry)
        polygon(mapping(converted))
        xmin, ymin, xmax, ymax = converted.bounds
        require(-180 <= xmin <= xmax <= 180 and -90 <= ymin <= ymax <= 90, "Transformed coordinates outside WGS84")
        require(isinstance(feature.get("properties"), dict), "Feature properties required")
        features.append({"type": "Feature", "properties": feature["properties"], "geometry": mapping(converted)})
    require(bool(features), "Source contains no polygons")
    transformations.append({"source": spec["path"], "sha256": spec["sha256"], "source_crs": crs.to_string(),
                            "source_name": spec["source_name"], "source_url": spec["source_url"], "license": spec["license"],
                            "target_crs": "EPSG:4326", "always_xy": True,
                            "operation": transformer.get_last_used_operation().description if not crs.equals(CRS.from_epsg(4326)) else "identity",
                            "definition": transformer.get_last_used_operation().definition if not crs.equals(CRS.from_epsg(4326)) else "identity"})
    return features


def no_overlap(geometries):
    for i, left in enumerate(geometries):
        for right in geometries[i + 1:]:
            require(left.intersection(right).area <= 1e-14, "Input or resulting interiors overlap")


def reconstruct(manifest, base, mode):
    require(mode in ("complete", "partial", "approximate"), "Unknown build mode")
    if mode == "approximate":
        require(manifest.get("accuracy") == "approximate" and text(manifest.get("excluded_coverage_notes")),
                "Approximate build requires accuracy and explicit coverage exclusions")
    require(manifest.get("reference_date") == DATE, "Reference date must be 1945-09-01")
    require(text(manifest.get("uncertainty_notes")), "Uncertainty notes required")
    require(url(manifest.get("assignment_evidence_url")), "Assignment evidence required")
    transformations = []
    features = load_source(manifest.get("boroughs"), base, transformations, mode == "approximate")
    adjustments = []
    boroughs = {}
    for feature in features:
        props = feature["properties"]
        name = props.get("borough")
        require(name in ASSIGNMENTS and name not in boroughs, "Unknown or duplicate borough; use one multipart feature per borough")
        require(props.get("reference_date") == DATE and url(props.get("evidence_url")), "Each borough needs exact-date evidence")
        allowed = ("approximate_proxy",) if mode == "approximate" else ("verified_historical", "supported_reconstruction")
        require(props.get("historical_status") in allowed, "Unresolved or approximate borough geometry cannot be included in strict builds")
        boroughs[name] = shape(feature["geometry"])
    no_overlap(list(boroughs.values()))
    missing = sorted(set(ASSIGNMENTS) - set(boroughs))
    exception = manifest.get("gatow_staaken", {})
    status = exception.get("status")
    require(status in ("unresolved", "included_in_boroughs", "reviewed_adjustments"), "Explicit Gatow/Staaken status required")
    require(text(exception.get("notes")), "Exception notes required")
    require(not (mode == "partial" and status == "unresolved" and "Spandau" in boroughs),
            "Exclude Spandau from partial input until its Gatow/Staaken extent is resolved")
    if status != "unresolved":
        require(url(exception.get("evidence_url")), "Exception evidence required")
        require(text(exception.get("occupation_vs_administration")), "Document occupation versus municipal administration")
    if status == "reviewed_adjustments":
        adjustments = load_source(exception.get("adjustments"), base, transformations)
        for feature in adjustments:
            props = feature["properties"]
            name, operation = props.get("borough"), props.get("operation")
            require(name in boroughs and operation in ("add", "remove") and url(props.get("evidence_url")), "Invalid evidenced adjustment")
            geometry = shape(feature["geometry"])
            original = boroughs[name]
            if operation == "remove":
                require(original.covers(geometry), "Removal must be within target borough")
                boroughs[name] = original.difference(geometry)
            else:
                require(original.intersection(geometry).area <= 1e-14, "Addition overlaps its target borough")
                boroughs[name] = original.union(geometry)
            polygon(mapping(boroughs[name]))
        no_overlap(list(boroughs.values()))
    if mode == "complete":
        require(not missing, f"Missing boroughs: {', '.join(missing)}")
        require(status != "unresolved", "Gatow/Staaken unresolved")
        require(manifest.get("enclaves_reviewed") is True, "Enclave coverage review required")
    rows = [{"borough": name, "sector": ASSIGNMENTS[name], "geometry": geometry} for name, geometry in sorted(boroughs.items())]
    frame = gpd.GeoDataFrame(rows, crs=4326)
    dissolved = frame.dissolve(by="sector").sort_index()
    no_overlap(list(dissolved.geometry))
    if mode == "approximate":
        require(set(dissolved.index) == set(ASSIGNMENTS.values()), "Approximate MVP requires all four sectors")
    coverage = None
    if manifest.get("coverage") is not None:
        coverage_features = load_source(manifest["coverage"], base, transformations, mode == "approximate")
        coverage = unary_union([shape(f["geometry"]) for f in coverage_features])
        polygon(mapping(coverage))
    require(mode != "complete" or coverage is not None, "Complete build requires independently reviewed coverage")
    require(mode != "approximate" or coverage is not None, "Approximate build requires a declared source-based coverage outline")
    difference = None
    if coverage is not None:
        project = Transformer.from_crs(4326, 25833, always_xy=True).transform
        expected, actual = transform(project, coverage), transform(project, unary_union(list(dissolved.geometry)))
        difference = {"missing_m2": expected.difference(actual).area, "excess_m2": actual.difference(expected).area}
        if mode in ("complete", "approximate"):
            require(max(difference.values()) <= 0.01, f"Coverage mismatch: {difference}")
    source = manifest["boroughs"]
    output = []
    for code, row in dissolved.iterrows():
        geometry = row.geometry
        polygon(mapping(geometry))
        output.append({"type": "Feature", "properties": {
            "sector": code, "code": code, "name": f"{code.title()} sector", "reference_date": DATE,
            "source_name": source["source_name"], "source_url": source["source_url"],
            "reconstruction_method": "Historical borough assignment and dissolve; reviewed adjustments only",
            "historical_status": "approximate_reconstruction" if mode == "approximate" else "supported_reconstruction", "coverage_status": "partial" if mode == "approximate" else mode,
            "accuracy": "approximate" if mode == "approximate" else "review_candidate",
            "excluded_coverage_notes": manifest.get("excluded_coverage_notes", ""),
            "uncertainty_notes": manifest["uncertainty_notes"],
            "sources": [{"source_name": item["source_name"], "source_url": item["source_url"], "license": item["license"], "sha256": item["sha256"]} for item in transformations],
            "borough_evidence": [f["properties"] for f in features if ASSIGNMENTS[f["properties"]["borough"]] == code],
        }, "geometry": mapping(geometry)})
    collection = {"type": "FeatureCollection", "features": output}
    raw = (json.dumps(collection, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode()
    provenance = {"verified": False, "sha256": hashlib.sha256(raw).hexdigest(), "reference_date": DATE,
                  "source_name": source["source_name"], "source_url": source["source_url"],
                  "license": source["license"], "verification_notes": "REVIEW CANDIDATE ONLY. Production import prohibited until independent historical and licensing release review."}
    report = {"mode": mode, "release_verified": False, "missing_boroughs": missing,
              "versions": {"geopandas": gpd.__version__, "pyproj": pyproj.__version__, "proj": pyproj.proj_version_str, "shapely": shapely.__version__},
              "unresolved_exception": status == "unresolved", "enclaves_reviewed": manifest.get("enclaves_reviewed") is True,
              "coverage_difference": difference, "transformations": transformations, "input_evidence": manifest,
              "assignment_table": ASSIGNMENTS, "assignment_reference": ASSIGNMENT_URL,
              "adjustment_evidence": [f["properties"] for f in adjustments],
              "sector_codes": [f["properties"]["sector"] for f in output]}
    return raw, provenance, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--mode", choices=("complete", "partial", "approximate"), default="partial")
    parser.add_argument("--output-dir", type=Path, help="Must be a new directory; use data/research for partial output")
    args = parser.parse_args()
    try:
        require(args.output_dir is not None, "Choose a new output directory explicitly")
        require(not args.output_dir.exists(), "Output directory exists; refusing to overwrite any previous build")
        manifest = json.loads(args.manifest.read_text())
        raw, provenance, report = reconstruct(manifest, args.manifest.resolve().parent, args.mode)
        args.output_dir.mkdir(parents=True)
        (args.output_dir / "berlin-sectors.geojson").write_bytes(raw)
        (args.output_dir / "berlin-sectors.provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
        (args.output_dir / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(f"{args.mode} review candidate written; provenance remains verified=false. No database writes.")
    except (OSError, ValueError, KeyError, TypeError, IndexError, ProjError, ShapelyError) as exc:
        parser.exit(1, f"Reconstruction rejected: {exc}\n")


if __name__ == "__main__":
    main()
