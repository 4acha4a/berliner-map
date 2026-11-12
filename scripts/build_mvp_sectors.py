"""Dataset-specific recipe: modern ALKIS locality proxies, not exact historical boroughs."""
import argparse
import hashlib
import json
from pathlib import Path

from shapely.geometry import shape, mapping
from shapely.ops import unary_union

from reconstruct_sectors import DATE, ASSIGNMENT_URL, reconstruct, require


SOURCE_URL = "https://gdi.berlin.de/services/wfs/alkis_ortsteile?service=WFS&version=2.0.0&request=GetFeature&typeNames=alkis_ortsteile%3Aortsteile&srsName=EPSG%3A25833&outputFormat=application%2Fjson"
SOURCE_NAME = "Approximate 1945 sector reconstruction / Geoportal Berlin, ALKIS Berlin Ortsteile (modern proxy; Staaken excluded)"
LICENSE = "Datenlizenz Deutschland - Zero - Version 2.0; https://www.govdata.de/dl-de/zero-2-0"
NOTES = (
    "Historical boundaries are reconstructed and may differ from their exact 1945 locations. "
    "Modern ALKIS locality edges are geographic proxies, not verified 1945 linework. "
    "Entire modern Staaken locality excluded: both British East Staaken and Soviet-zone West Staaken remain unclassified. "
    "Gatow/Seeburger Zipfel exchange outline remains unresolved; modern Gatow/Kladow edges retained only as approximate proxies. "
    "Later exchanges, Steinstuecken corridor, eastern city-limit additions and small internal boundary shifts are not reversed. "
    "Not suitable for building/address-level historical classification, especially near boundaries."
)


def group(name, district):
    # These are aggregation labels for the existing pipeline, NOT reconstructed borough limits.
    if district == "01":
        if name in ("Wedding", "Gesundbrunnen"): return "Wedding"
        return "Mitte" if name == "Mitte" else "Tiergarten"
    if district == "02": return name
    if district == "03":
        if name == "Prenzlauer Berg": return name
        return "Weißensee" if name in ("Weißensee", "Stadtrandsiedlung Malchow") else "Pankow"
    if district == "04": return "Charlottenburg" if name in ("Charlottenburg", "Charlottenburg-Nord", "Westend") else "Wilmersdorf"
    if district == "05": return "Spandau"
    if district == "06": return "Steglitz" if name in ("Steglitz", "Lichterfelde", "Lankwitz") else "Zehlendorf"
    if district == "07": return "Schöneberg" if name in ("Schöneberg", "Friedenau") else "Tempelhof"
    if district == "08": return "Neukölln"
    if district == "09": return "Köpenick" if name in ("Köpenick", "Oberschöneweide", "Grünau", "Rahnsdorf", "Friedrichshagen", "Müggelheim", "Schmöckwitz") else "Treptow"
    if district in ("10", "11"): return "Lichtenberg"
    if district == "12": return "Reinickendorf"
    raise ValueError(f"Unmapped district: {district}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    require(not args.work_dir.exists() and not args.output_dir.exists(), "Choose new work/output directories")
    source_raw = args.source.read_bytes()
    require(hashlib.sha256(source_raw).hexdigest() == "0a832cea5cdc912c658e5c988ee9ab428559f4ee7ee5039874a4b10c664ff45f",
            "Source snapshot changed; review locality assignments and geometry before rebuilding")
    doc = json.loads(source_raw)
    require(doc.get("crs", {}).get("properties", {}).get("name") == "urn:ogc:def:crs:EPSG::25833", "Expected official EPSG:25833 source")
    require(len(doc["features"]) == 97, "Review changed source inventory before rebuilding")
    grouped, excluded, lookup = {}, [], []
    for feature in doc["features"]:
        props = feature["properties"]
        name = props["nam"]
        geometry = shape(feature["geometry"])
        require(geometry.is_valid and not geometry.is_empty, f"Invalid source locality: {name}")
        if name == "Staaken":
            excluded.append(feature)
            continue
        label = group(name, props["sch"][6:8])
        grouped.setdefault(label, []).append(geometry)
        lookup.append({"locality": name, "official_code": props["sch"], "aggregation_label": label})
    require(len(excluded) == 1, "Expected exactly one excluded Staaken locality")
    args.work_dir.mkdir(parents=True)
    def write(name, features):
        raw = (json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False) + "\n").encode()
        (args.work_dir / name).write_bytes(raw)
        return {"path": name, "sha256": hashlib.sha256(raw).hexdigest(), "crs": "EPSG:25833",
                "source_name": SOURCE_NAME, "source_url": SOURCE_URL, "license": LICENSE,
                "historically_reviewed": False, "reviewed_for_approximation": True, "accuracy": "approximate",
                "redistribution_permitted": True, "review_notes": NOTES}
    features = [{"type": "Feature", "properties": {"borough": label, "reference_date": DATE,
                "evidence_url": ASSIGNMENT_URL, "historical_status": "approximate_proxy",
                "source_date": "Modern ALKIS retrieved 2026-11-11; not a 1945 survey"},
                "geometry": mapping(unary_union(parts))} for label, parts in sorted(grouped.items())]
    boroughs = write("locality-aggregation-proxies.geojson", features)
    target = unary_union([shape(f["geometry"]) for f in doc["features"]]).difference(unary_union([shape(f["geometry"]) for f in excluded]))
    coverage = write("declared-modern-proxy-coverage.geojson", [{"type": "Feature", "properties": {"purpose": "Modern source extent minus explicitly excluded Staaken; NOT independent 1945 coverage"}, "geometry": mapping(target)}])
    write("excluded-staaken.geojson", excluded)
    manifest = {"reference_date": DATE, "accuracy": "approximate", "assignment_evidence_url": ASSIGNMENT_URL,
                "uncertainty_notes": NOTES, "excluded_coverage_notes": "Entire modern Staaken locality omitted; no claim of complete 1945 coverage.",
                "enclaves_reviewed": False, "boroughs": boroughs, "coverage": coverage,
                "gatow_staaken": {"status": "unresolved", "notes": NOTES},
                "raw_source_sha256": hashlib.sha256(source_raw).hexdigest(), "locality_mapping": lookup}
    (args.work_dir / "reconstruction-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    raw, provenance, report = reconstruct(manifest, args.work_dir, "approximate")
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "berlin-sectors.geojson").write_bytes(raw)
    (args.output_dir / "berlin-sectors.provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n")
    (args.output_dir / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("Four source-derived approximate sectors generated; Staaken excluded. Release review still required.")


if __name__ == "__main__":
    main()
