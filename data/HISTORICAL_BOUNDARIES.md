# Historical boundary reconstruction — Phase 1.2.4 MVP

Reference date: **1 September 1945**. Investigation: **11 November 2026**.

**Current status: approximate four-sector MVP released and imported, with an intentional Staaken gap.** `data/processed/berlin-sectors.geojson` contains real source-derived geographic polygons. These are modern locality proxies for the historical arrangement, not exact 1945 or cadastral boundaries. Read the [Phase 1.2.4 release](#phase-124-approximate-mvp-release) first. The earlier investigation sections below preserve the exact-reconstruction work and its limitations; their original empty-data results are historical session records.

## Source findings and reuse status

### Berliner Stadtplansammlung

- [1945 Umgebung von Berlin](https://www.berliner-stadtplansammlung.de/index.php/karten/1945-umgebung-von-berlin): Reichsamt für Landesaufnahme, scale 1:100,000; 1940 base with 1945 boundary overprint. The description shows West Staaken in the British sector before the described exchange. It cannot be assumed to depict the exact requested date.
- [Publisher's site explanation](https://www.berliner-stadtplansammlung.de/index.php/ueber/ueber-die-seite): high-resolution viewing uses tiles; direct downloads are deliberately not provided. The owner offers research files on request, subject to third-party rights. No open derivative-redistribution license established. Tiles were not harvested, and no source image was placed in the repository.

### German History in Documents and Images

- [Berlin, September 1, 1945](https://germanhistorydocs.org/en/occupation-and-the-emergence-of-two-states-1945-1961/berlin-september-1-1945): dated reference map, IEG-MAPS / A. Kunz (2004), revised Gabriel Moss (2021). An [SVG image](https://germanhistorydocs.org/media/volume-8/map-522/64731_ca_object_representations_media_5151_original.svg) is linked. SVG drawing coordinates are not geographic coordinates or a georeferencing model.
- [Terms](https://germanhistorydocs.org/en/terms) distinguish source-specific rights and direct republishers to the relevant rightsholder. The CC BY-NC-ND license described for editorial texts does not establish a license for this map or an adapted geographic dataset. No SVG was copied or converted to polygons.

### HistoMap Berlin / Landesarchiv

- [English application](https://histomapberlin.de/en/), [official metadata](https://gdi.berlin.de/geonetwork/srv/api/records/ef04ec78-c7d8-3113-92c6-d9c46e38932d), [official legal information](https://histomapberlin.de/en/content/contact.html).
- The application's [configuration](https://histomapberlin.de/lib/overrides.js) links published WMS 1.1.1 catalogs: [K4](https://histomapberlin.de/request/k4.xml), [K5](https://histomapberlin.de/request/k5.xml). Historical rasters are available through [K4 GetCapabilities](https://histomapberlin.de:8443/geoserver/histomap/wms?service=WMS&version=1.1.1&request=GetCapabilities).
- The published K4 catalog has **2,351 named layers**, including **9 with an explicit 1945 keyword**. K5 has **447 named layers**, with **0 matching 1945**. See the checksum-bound [inventory](research/histomap-inventory.json). These are catalog results, not a claim about all archive holdings. Other years may support individual unchanged boundary segments only after historical review.
- K4 1945 sheet IDs: `1017`, `1018`, `3035`, `4028`, `4056`, `4128`, `4337`, `4422`, `4431`. Their dispersed advertised rectangles do not provide citywide 1945 coverage. A year keyword does not identify survey date, revision date, or whether the August exchange is depicted.
- Catalog sheet metadata advertises EPSG:3068 and longitude/latitude extents. This is more specific than the application's EPSG:25833 discovery metadata. Neither bounding box supplies raster rectification accuracy or a boundary trace. The current district vector layer is 2023 ALKIS, not 1945 geometry.
- Live capabilities were retrieved (update sequence `39459`) and contained the same nine `_1945` layer names. Live keyword metadata differs from the published static catalog, so counts from the static inventory must not be silently applied to live capabilities. A sample `GetMap` for `1017_1945`, using its advertised EPSG:3068 bounds, returned HTTP 200 and a valid PNG signature (25,458 bytes at 256×384). The raster was not retained or redistributed; this checks service availability only.
- **Rights remain unresolved:** official legal information restricts reproduction/adaptation beyond statutory allowances without written consent. A [third-party alternative viewer](https://www.histo.blnmap.de/info.php) reports a 2022 archive statement permitting extracts with attribution. That report is useful evidence to seek clarification, but does not resolve the exact permission for redistributed traced sector vectors. `AccessConstraints: NONE` and software GPL notices are not a source-data license.

## Historical assignments and exceptions

The [statistical offices' 100 Jahre Groß-Berlin publication](https://www.statistischebibliothek.de/mir/servlets/MCRFileNodeServlet/BBMonografie_derivate_00000068/100jahregrossberlin.pdf), section on the 1938 reform, supplies this borough-to-sector cross-check:

| Sector | Historical boroughs |
| --- | --- |
| French | Reinickendorf, Wedding |
| British | Spandau, Tiergarten, Charlottenburg, Wilmersdorf |
| American | Steglitz, Zehlendorf, Neukölln, Schöneberg, Tempelhof, Kreuzberg |
| Soviet | Pankow, Prenzlauer Berg, Mitte, Treptow, Köpenick, Weißensee, Friedrichshain, Lichtenberg |

This is an assignment table, not geometry. It does not establish that contemporary boundaries match 1938/1945 boundaries.

The [official Spandau history](https://www.berlin.de/ba-spandau/ueber-den-bezirk/historisches/artikel.193987.php) dates the Seeburger Zipfel / West Staaken exchange to **30 August 1945**. The [Spandau museum account](https://www.zitadelle-berlin.de/ihr-besuch/archiv/veranstaltungen/100-jahre-bezirk-spandau-1920-2020/spandau-geschichte/) describes the division along Nennhauser Damm and the addition of parts of Groß Glienicke for Gatow. These descriptions establish an exception to investigate; they are insufficient for drawing the full exchanged-area outline.

Military occupation, municipal administration, and later incorporation must be distinguished. West Staaken must not simply be labeled Soviet *sector* because it passed to Soviet occupation authority: Soviet zone and Soviet Berlin sector are different spatial categories. Exact treatment for this release needs the dated agreement/map and a documented inclusion rule. Enclaves, waterways, boundary-side conventions, and any later exchanges likewise require explicit evidence. No unsupported exception geometry has been generated.

## Reproducible work completed

`scripts/inventory_histomap.py` uses only Python's standard library. It downloads the two published catalogs, checks WMS version, inventories explicit year keywords, validates finite ordered metadata extents, and writes a JSON report with source URLs, source SHA-256, byte lengths, catalog update sequences, sheet identifiers, and advertised CRS/extents. It performs **no geometry reconstruction, raster georeferencing, reprojection, repair, or simplification**. Output is research metadata, deliberately not GeoJSON.

From the repository root:

```sh
python3 scripts/inventory_histomap.py
# Optional: other years, still research metadata only.
python3 scripts/inventory_histomap.py --year 1944 --output /tmp/histomap-1944.json
# Offline replay with lawfully retained catalog files:
python3 scripts/inventory_histomap.py --k4-xml /path/to/k4.xml --k5-xml /path/to/k5.xml --output /tmp/inventory.json
```

Network-free replay requires the same source bytes for matching checksums. Generation timestamps will differ. Raw third-party catalogs and map imagery are not bundled; the repository preserves extracted factual metadata and checksums. If upstream changes, preserve the old report and compare hashes before replacing it.

Host Python DNS failed during this run. The existing backend container had working network access, so the same script executed there:

```sh
docker compose exec -T backend python - --output /tmp/histomap-inventory.json < scripts/inventory_histomap.py
mkdir -p data/research
docker compose cp backend:/tmp/histomap-inventory.json data/research/histomap-inventory.json
```

Shapely is installed in the backend container; GeoPandas, PyProj, and Rasterio are not. They were not needed for metadata inventory and were not added to runtime dependencies. No coordinate transformation parameters exist because no transformation was performed.

## Reconstruction procedure still required

1. Obtain explicit source rights for tracing and distributing vectors, or a suitably licensed historical vector release. Record exact terms, attribution, source version, checksum, and date evidence. No permission request was sent on the user's behalf.
2. Obtain adequate dated sheets covering every intended boundary segment, plus the Gatow/Staaken agreement geometry and enclave evidence. Identify which mapped symbols actually denote borough/sector limits. Record conflicts with an independent source rather than extrapolating.
3. For an unrectified map, select well-distributed stable control points, record pixel/reference coordinates and reference sources, choose and justify a transformation, retain independent checkpoints and residuals, and review local distortion. Corner assignment alone is insufficient. For existing georeferenced rasters, verify their CRS/model and independent checkpoints rather than assuming WMS alignment proves accuracy.
4. Digitize shared boundary linework once, attach segment-level source/date/uncertainty evidence, construct faces, and dissolve only supported faces by historical sector assignment. Preserve holes, islands, and exclaves. Keep incomplete research linework outside the production path; do not close polygons across undocumented gaps.
5. Export reviewed Polygon/MultiPolygon features in RFC 7946 WGS84 `[longitude, latitude]`, recording source and destination CRS, actual transformation operation and parameters, tool versions, and any datum-grid limitations. Include reference date and uncertainty in properties and release documentation.
6. Check structure, finite coordinate ranges, closed rings, validity/self-intersections, all four codes, pairwise interior overlaps, and coverage difference against an independently verified snapshot extent. Gap checks need that extent; intentional holes/exclusions require an explicit inventory. Geometry validity alone is not historical verification.
7. Cross-check documented locations and exception boundaries against independent historical evidence. Then produce `data/processed/berlin-sectors.geojson` and a matching reviewed provenance manifest. Use the existing importer, import twice, compare IDs/geometries/attribution, and run the API/browser acceptance checks before releasing to the public-data paths.

## Earlier validation and integration results (before Phase 1.2.4)

- **Inventory workflow:** executed against both real published catalogs. Offline checks passed for explicit keyword selection (including a variant sheet suffix), year filtering, nonfinite bounding-box rejection, and WMS version rejection. The nine selected metadata extents are finite, ordered, and within longitude/latitude ranges.
- **Sector GeoJSON:** absent; geometry validity, overlap/gap/coverage checks and historical location checks cannot be run on a nonexistent reconstruction. No empty processed file was created to imply otherwise.
- **PostGIS:** no reconstructed-data import, idempotency check, or historical classification performed. Earlier 44 passing backend tests use clearly identified synthetic fixtures and remain software evidence only.
- **Frontend:** no reconstructed overlays available to render, align, toggle, change opacity, or click. Earlier Google Maps and responsive missing-data checks do not verify historical overlay behavior.

The current geographic blockers are incomplete dated boundary coverage, unverified exchange/enclave geometry and occupation-versus-administration treatment, and lack of a reviewed digitization result. Original factual GIS reconstruction is permitted by the project: absence of permission to reproduce map imagery is not treated as a blanket prohibition on independently reconstructing geographic facts. Actual input-data licenses must still permit the intended use, and protected imagery/expression must not be copied into the dataset. No API or application behavior changed.

## Phase 1.2.3: executable borough reconstruction

Implemented [reconstruction script](../scripts/reconstruct_sectors.py), [GIS requirements](../scripts/requirements-gis.txt), and [input manifest template](research/reconstruction-manifest.template.json). This now performs actual coordinate transformation and polygon processing when defensible input is provided; it does not infer historical linework from borough names or map-sheet rectangles.

Additional targeted source checks:

- [Mosaic historical GIS](https://mosaic.ipums.org/historical-gis-datafiles) offers German Empire administrative series to 1945, but its published terms limit use to registered non-commercial scientific users with citation. No download was incorporated, and Berlin's internal borough coverage has not been verified. This is not accepted as an openly redistributable application input.
- [berlin-shapes](https://github.com/m-hoerz/berlin-shapes) documents CC BY source data but explicitly describes **12 modern boroughs**. It cannot be used as the historical 20 without independently proving correspondence; no geometry incorporated.
- [Brandenburg's historical administrative API catalog](https://data.gov.de/suche/daten/digitale-verwaltungsgrenzen9dc6b) lists Berlin borough geometry for 2009–2023, not 1945. No historical correspondence assumed.
- [NARA-hosted 1938 administrative map](https://www.archives.gov/files/research/foreign-policy/cold-war/berlin-wall-1962-1987/dvd/pdfs/maps/Map-07.pdf) is an independent cartographic lead depicting new and previous limits. Web retrieval hit a 51.6 MB tool limit; it was not georeferenced, digitized, or accepted as a GIS input. Hosting alone is not evidence of an image's rights or its fit to September 1945.

### Missing geometry, precisely

No accepted **exact 1945** polygon exists for any of the 20 boroughs in the assignment table above. The Phase 1.2.4 approximate proxies do not resolve that exact-linework gap. Within Spandau, the post-exchange Gatow/Seeburger Zipfel addition and West Staaken exclusion/inclusion convention lack accepted exact linework. Enclave outlines and an independent 1 September 1945 coverage outline also remain missing. The software now supports preserving a subset once a specific historical borough polygon is supported; there is currently no such accepted subset. This is a source-evidence gap, not a geometry-validation failure.

### Input contract

Each input artifact is a polygon FeatureCollection. Its descriptor supplies `path` relative to the manifest, exact `sha256`, `crs`, `source_name`, HTTP(S) `source_url`, `license`, `review_notes`, and explicit `historically_reviewed` / `redistribution_permitted` attestations. These require real review; changing flags cannot establish historical truth. A source CRS must come from source documentation. Geographic input is restricted to EPSG:4326; projected data can use a documented projected CRS. Legacy inline GeoJSON CRS declarations are rejected to avoid conflicting declarations.

Each borough has one feature (multipart allowed), canonical `properties.borough` matching the assignment table, `reference_date: "1945-09-01"`, `evidence_url`, and `historical_status` equal to `verified_historical` or `supported_reconstruction`. Approximate/unresolved geometry must be held separately, not included as supported geometry. Multiple fragments of a borough must be independently reviewed and assembled into its input MultiPolygon first.

`gatow_staaken.status` is one of:

- `unresolved`: allowed in partial mode only if **Spandau is excluded**; preserves the unresolved exception in the report.
- `included_in_boroughs`: reviewed input already depicts the chosen snapshot; requires evidence, notes, and `occupation_vs_administration` explanation.
- `reviewed_adjustments`: additionally supplies an `adjustments` artifact descriptor. Each feature names its target `borough`, `operation: "remove"` or `"add"`, and `evidence_url`. Operations apply in input order: remove first before adding the same area elsewhere. Removed geometry must lie within the target; additions cannot overlap it. No geometry is silently repaired.

Complete mode also requires all 20 boroughs, `enclaves_reviewed: true`, and a `coverage` artifact descriptor with an independently reviewed snapshot outline. Coverage must not be derived from the same borough union merely to pass the check. Intentional exclusions must already be reflected in this independently evidenced outline.

### Processing and output

1. Check hashes, historical/rights attestations, feature/date/status fields, closed finite 2D rings, valid positive-area Polygon/MultiPolygon topology, and source attribution.
2. Transform with PyProj (`always_xy`, no ballpark, best operation required) into EPSG:4326. Retain the used operation, definition, source hashes, and tool versions in the report.
3. Apply only supplied evidenced exception geometry, reject overlapping borough interiors, and dissolve through GeoPandas using the documented assignment table. Preserve holes and disconnected parts.
4. Check sector overlap and compare coverage in EPSG:25833 square metres. Complete output permits at most **0.01 m²** numerical difference for missing or excess coverage; this computational tolerance is not a positional-accuracy claim. The degree-area overlap threshold is `1e-14`, used only for floating-point slivers, not to justify historical overlaps.
5. Write a new explicitly selected directory containing `berlin-sectors.geojson`, checksum-bound `berlin-sectors.provenance.json`, and `validation.json`. Existing output directories are refused. All validation precedes file creation.

Both modes remain **review candidates with `verified: false`**. Partial mode reports missing boroughs, unresolved exchange status, enclave review status, and coverage difference if an outline exists. A partial union with all four sector codes is still not a complete historical release. The unchanged production importer rejects the candidate manifest until a separate release review. Output properties preserve source/license records, borough evidence, reference date, method, uncertainty, and mode; the report preserves adjustment evidence and the full input manifest.

### Reproduction

```sh
python3 -m venv /tmp/berliner-gis
/tmp/berliner-gis/bin/pip install -r scripts/requirements-gis.txt
# Populate a COPY of the template with real reviewed artifact descriptors.
/tmp/berliner-gis/bin/python scripts/reconstruct_sectors.py /path/to/reviewed-manifest.json \
  --mode partial --output-dir data/research/candidate-001
# Only once every complete-mode prerequisite has been established:
/tmp/berliner-gis/bin/python scripts/reconstruct_sectors.py /path/to/reviewed-manifest.json \
  --mode complete --output-dir data/processed
/tmp/berliner-gis/bin/python -m pytest scripts/test_reconstruct_sectors.py -m 'not integration' -p no:cacheprovider
```

The strict-mode template intentionally fails without actual reviewed historical source data. Phase 1.2.4 adds a separately explicit approximate mode and a real modern-proxy build; it does not make the exact reconstruction prerequisites disappear. No synthetic output is saved in production data.

For container verification, install the GIS requirements in a temporary venv with `python -m venv --system-site-packages /tmp/berliner-gis`, copy the script and tests into `/tmp`, and run them with that venv's Python. The system packages supply the existing backend app and test dependencies; the GIS install does not change the application environment. Set `TEST_DATABASE_URL` to the migrated dedicated `_test` database and run `python -m pytest /tmp/test_reconstruct_sectors.py -c /app/pyproject.toml -p no:cacheprovider` for the real PostGIS test. Do not put credentials in reports.

The PostGIS test deliberately uses artificial unit squares near (0, 0), rejects the unverified output first, then applies a synthetic-only attestation inside a dedicated rolled-back database transaction. It imports through the existing importer twice, checks stable IDs/attribution, and queries both API endpoints for all four synthetic sectors. It establishes no historical location classification. No production database or frontend data was replaced.

Executed results on 11 November 2026: **17 reconstruction tests passed**, including CLI bundle generation/overwrite refusal, invalid-build no-output behavior, projected CRS conversion, missing/overlapping coverage, partial mode, unresolved Spandau rejection, reviewed adjustments, holes/multipart geometry, source-review/checksum rejection, and the real PostGIS round trip. The existing **44 backend tests also passed**, including their PostGIS integration tests. Only existing Starlette/Alembic deprecation warnings remain. Frontend checks were not rerun for this GIS-only change; no historical overlay rendering claim is made.


## Phase 1.2.4: approximate MVP release

**Deliverable:** [four-sector GeoJSON](processed/berlin-sectors.geojson), [release provenance](processed/berlin-sectors.provenance.json), [build validation](processed/validation.json), and [actual API/PostGIS checks](processed/integration-verification.json). The same GeoJSON/provenance is shipped under `public/data` for the unchanged importer. Historical target: 1 September 1945. Geographic source: **modern**, retrieved 11 November 2026. Accuracy: **approximate reconstruction**. Historical coverage: **partial**.

### Actual geographic source and license

[Geoportal Berlin / ALKIS Berlin Ortsteile WFS](https://gdi.berlin.de/services/wfs/alkis_ortsteile?SERVICE=WFS&REQUEST=GetCapabilities&VERSION=2.0.0) supplies actual locality polygons, not map-sheet rectangles. The [official source metadata](https://gdi.berlin.de/geonetwork/srv/api/records/0a7c53a5-b29d-3f45-9734-1c811045e6c2) states **Datenlizenz Deutschland Zero 2.0** ([license](https://www.govdata.de/dl-de/zero-2-0)). The metadata response was inspected directly; it includes October 2026 metadata/revision dates. Do not confuse these dates with a 1945 survey.

The exact 97-feature EPSG:25833 response is retained as `data/sources/berlin-ortsteile-2026.geojson` (2,072,818 bytes), SHA-256 `0a832cea5cdc912c658e5c988ee9ab428559f4ee7ee5039874a4b10c664ff45f`. Its declared CRS and original attributes are preserved. The pinned recipe refuses a changed source snapshot without review. No protected historical-map imagery is included in the repository.

The historical assignment table above supplies the sector membership basis. The GHDI September 1, 1945 SVG reference was actually retrieved into temporary storage, rendered, and visually inspected to independently cross-check the broad French northwest, British west, American southwest, and Soviet east arrangement and their named boroughs. No coordinates were extracted from it; its cartographic expression was not used as polygon linework. This visual cross-check does **not** verify positional coincidence of modern and historical edges.

### Approximation method and exclusions

`scripts/build_mvp_sectors.py` is the dataset-specific recipe using the existing `reconstruct_sectors.py`, with an explicitly selected `approximate` mode. It aggregates 96 modern localities into sector groupings and dissolves them. The 20 names used as intermediate aggregation labels are pipeline compatibility labels, **not reconstructed exact historical borough polygons**. Internal subdivisions within a single sector have no effect on the sector union; the retained `locality_mapping` lists every source locality and aggregation label for review.

The modern Mitte district is split by its locality polygons: Wedding/Gesundbrunnen to French; Tiergarten/Moabit/Hansaviertel to British; Mitte to Soviet. Kreuzberg is American and Friedrichshain Soviet. Modern Reinickendorf is French; Charlottenburg-Wilmersdorf and the included Spandau localities are British; Steglitz-Zehlendorf, Tempelhof-Schöneberg and Neukölln are American; eastern localities are Soviet. These are explicitly approximate geographic proxies supported by historical borough assignments, not proof that each modern edge existed in 1945.

**Entire modern Staaken is excluded by explicit user choice.** This omits both British East Staaken and the exchanged West Staaken, rather than falsely classifying their unresolved split. The omitted official-source polygon is preserved in `data/interim/mvp-1945/excluded-staaken.geojson` (EPSG:25833, declared by its accompanying manifest). Source area is 890.667841 km²; omitted Staaken is 10.882761 km²; intended modern-proxy coverage is approximately 879.785079 km². These are computational source areas, not claimed historical Berlin areas.

Gatow/Kladow use modern locality outlines only as approximate post-exchange proxies. The exact Gatow/Seeburger Zipfel exchange perimeter remains unresolved. Later border exchanges, the Steinstücken corridor, eastern city-limit additions, and local boundary shifts have **not** been reversed. Small enclaves and edge details may therefore be historically incorrect. No fixed positional error bound has been established. Do not infer building-level or address-level historical classification, especially near any edge.

EPSG:25833 source geometry is transformed to WGS84 EPSG:4326 using PyProj with longitude first, preserving topology and coordinate detail without simplification. The report records the actual operation and tool versions. No raster georeferencing, manual corner assignment, line tracing, arbitrary coordinates, or geometry repair was used.

### Validation, release review, and API semantics

Actual source and output geometries are nonempty and valid; all four codes exist; the unchanged production importer accepted the GeoJSON. Sector interiors have no positive-area overlap. The comparison with **declared modern source extent minus Staaken** has 0 m² missing and 0 m² excess coverage. That is a topology/recipe check, not a comparison against an independently verified 1945 outline. The intentional historical coverage gap remains explicit.

Every output feature carries `accuracy: "approximate"`, `historical_status: "approximate_reconstruction"`, `coverage_status: "partial"`, reference date, method, source/license records, and uncertainty/exclusion notes. The builder still emits `verified: false`. After source/license, broad assignment, topology, coverage, and unchanged importer checks, the release manifest was separately marked reviewed for the **user-approved approximate MVP**. Its `verified: true` does **not** assert exact 1945 geometry; `verification_notes` states the scope. The [release review](processed/release-review.json) records that distinction. Strict `complete`/`partial` modes still reject approximate proxy inputs. Production validation was not weakened.

The existing database stores four sector rows and preserves source attribution; the API contract has no accuracy or gap field, so its source name explicitly says approximate and Staaken-excluded. `dataset_status: "ready"` means four sector codes are present, not complete historical coverage. `sector: null` includes the Staaken gap and outside coverage. All clients must read the source/provenance limitations before interpreting classifications.

The dataset was imported twice with stable IDs; PostGIS `ST_Equals` confirmed equality with each input sector. Both direct and Next.js-proxied API checks passed for interior representative points of Mitte (Soviet), Tempelhof (American), Charlottenburg (British), and Reinickendorf (French), plus null results in Staaken and outside Berlin. These points come from official modern locality geometry; their broad historical borough assignments are supported independently, but their exact historical boundary positions are not validated. Coordinates/results are preserved in the integration report.

### Reproduction

Install `scripts/requirements-gis.txt` in a separate GIS environment as described above. From the repository root, use new directories:

```sh
python scripts/build_mvp_sectors.py data/sources/berlin-ortsteile-2026.geojson \
  --work-dir /tmp/berliner-mvp-inputs --output-dir /tmp/berliner-mvp-candidate
python scripts/reconstruct_sectors.py /tmp/berliner-mvp-inputs/reconstruction-manifest.json \
  --mode approximate --output-dir /tmp/berliner-mvp-replay
```

The exact source URL is in the recipe and manifests. `data/interim/mvp-1945` preserves the actual aggregation proxies, declared coverage, exclusion polygon, source hash, and locality mapping from this build. All intermediate coordinates are EPSG:25833 as declared in the manifest; final GeoJSON is WGS84. Replay produces the unverified candidate; release approval and copying to `public/data` are deliberately separate. Review the changes and scope before any future release attestation, never just flip a flag to bypass review.

For the already reviewed bundled release:

```sh
docker compose exec -T backend python -m app.import_sectors /data/berlin-sectors.geojson --manifest /data/berlin-sectors.provenance.json
curl http://localhost:3000/api/v1/sectors
curl 'http://localhost:3000/api/v1/sectors/identify?lat=52.52212481963285&lng=13.400861929665426'
```

Phase 1.2.4 checks: **18 reconstruction tests passed**, **44 backend tests passed**, real PostGIS integration passed, TypeScript/ESLint passed, and frontend production builds passed, including the final scroll-panel change. The pinned-source recipe reproduced the released GeoJSON byte-for-byte (SHA-256 `9143fa5e998fcfbf698874ef019e138b12bb5b1fb874823abfce60d88b9b54e9`).

Live Google Maps browser verification: Soviet red, American blue, British green, and French purple overlays rendered with plausible modern-source geographic alignment. The visibility toggle removed/restored the overlays, the opacity slider changed 35%→70%, and clicks in all four sectors displayed the expected sector with an Approximate label. The required historical-accuracy sentence and Staaken/partial-coverage/address-use notice were visible. A short desktop side panel was made scrollable and the full notice checked; at 390px mobile width the overlay, controls, legend, and full notice remained accessible in normal page flow. Google attribution remained visible. This is visual/functional validation of the approximate source-derived overlay, not exact historical alignment. Backend-offline browser behavior was not re-exercised.

Exact 1945 geometry remains a separate unfinished research objective; the approximate MVP is usable with the stated exclusions.
