"""Inventory published Histomap WMS metadata; never generate boundary geometry."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET


CATALOGS = {
    "k4": "https://histomapberlin.de/request/k4.xml",
    "k5": "https://histomapberlin.de/request/k5.xml",
}


def bbox(element):
    values = [float(element.attrib[key]) for key in ("minx", "miny", "maxx", "maxy")]
    if not all(math.isfinite(value) for value in values) or values[0] >= values[2] or values[1] >= values[3]:
        raise ValueError("Invalid advertised bounding box")
    return values


def inventory(raw, url, year):
    root = ET.fromstring(raw)
    if root.tag != "WMT_MS_Capabilities" or root.attrib.get("version") != "1.1.1":
        raise ValueError("Expected the published WMS 1.1.1 catalog")
    named = [layer for layer in root.iter("Layer") if layer.findtext("Name")]
    years = Counter()
    selected = []
    for layer in named:
        keywords = [node.text.strip() for node in layer.findall("KeywordList/Keyword") if node.text and node.text.strip()]
        # Use explicit year keywords, not suffixes: some sheet names carry variants.
        years.update(set(word for word in keywords if len(word) == 4 and word.isdigit()))
        if str(year) not in keywords:
            continue
        geographic = layer.find("LatLonBoundingBox")
        if geographic is None:
            raise ValueError(f"Missing geographic extent for {layer.findtext('Name')}")
        extent = bbox(geographic)
        if not (-180 <= extent[0] < extent[2] <= 180 and -90 <= extent[1] < extent[3] <= 90):
            raise ValueError("Geographic extent outside longitude/latitude ranges")
        selected.append({
            "name": layer.findtext("Name"),
            "title": layer.findtext("Title"),
            "keywords": keywords,
            "advertised_srs": [node.text for node in layer.findall("SRS")],
            "advertised_lonlat_bbox": extent,
            "advertised_projected_bboxes": [
                {"srs": node.attrib.get("SRS"), "bbox": bbox(node)}
                for node in layer.findall("BoundingBox")
            ],
        })
    resource = root.find("Capability/Request/GetMap/DCPType/HTTP/Get/OnlineResource")
    return {
        "catalog_url": url,
        "catalog_sha256": hashlib.sha256(raw).hexdigest(),
        "catalog_bytes": len(raw),
        "update_sequence": root.attrib.get("updateSequence"),
        "getmap_url": resource.attrib.get("{http://www.w3.org/1999/xlink}href") if resource is not None else None,
        "named_layer_count": len(named),
        "explicit_year_keyword_counts": dict(sorted(years.items())),
        "selected_layer_count": len(selected),
        "selected_layers": sorted(selected, key=lambda item: item["name"]),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=1945)
    parser.add_argument("--k4-xml", type=Path, help="Read a locally retained catalog instead of fetching it")
    parser.add_argument("--k5-xml", type=Path, help="Read a locally retained catalog instead of fetching it")
    parser.add_argument("--output", type=Path, default=Path("data/research/histomap-inventory.json"))
    args = parser.parse_args()
    try:
        catalogs = {}
        for key, url in CATALOGS.items():
            local = getattr(args, f"{key}_xml")
            if local:
                raw = local.read_bytes()
            else:
                with urllib.request.urlopen(url, timeout=30) as response:
                    raw = response.read(16_000_001)
                if len(raw) > 16_000_000:
                    raise ValueError("Catalog exceeds 16 MB limit")
            catalogs[key] = inventory(raw, url, args.year)
        report = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "year_filter": args.year,
            "status": "research_metadata_only",
            "historically_verified": False,
            "warning": "Sheet extents are NOT sector polygons or proof of historical coverage. Year keywords do not establish an exact reference date. No coordinate transformation or raster georeferencing performed. Source reuse rights unresolved.",
            "catalogs": catalogs,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        for key, result in catalogs.items():
            print(f"{key}: {result['selected_layer_count']} layers with explicit {args.year} keyword")
        print(f"Research metadata written to {args.output}; no geometry generated or imported.")
    except (OSError, ValueError, ET.ParseError) as exc:
        parser.exit(1, f"Inventory failed: {exc}\n")


if __name__ == "__main__":
    main()
