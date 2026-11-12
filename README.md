# Berliner Map

**Explore Berlin Through Time**

Phases 1.3–1.4 add Berlin address search, map-point identification, permission-aware location display, and Find me to the existing Next.js map and FastAPI/PostGIS identification service. The four sector colors, overlay controls, explorer animation, and responsive layout are preserved. Location results animate and remain visible until closed.

**The approximate historical overlay is operational, with partial coverage.** Phase 1.2.4 supplies four source-derived sector polygons using official modern ALKIS locality geometry as explicitly approximate proxies for the September 1945 arrangement. Entire Staaken is excluded; Gatow and later territorial changes remain uncertain. This is not exact 1945 or cadastral geometry and must not be used for building/address-level classification. See [data, provenance, and limitations](data/HISTORICAL_BOUNDARIES.md#phase-124-approximate-mvp-release). Software tests use artificial unit squares near (0, 0), never production data.

## Architecture

```mermaid
flowchart TD
  A["Browser and Google Maps"] --> B["Next.js API proxy"]
  B --> C["FastAPI"]
  C --> D["PostgreSQL and PostGIS"]
  E["Verified GeoJSON import"] --> D
  F["Alembic migrations"] --> D
```

The browser requests `/api/v1/sectors`. Next.js forwards only the supported GET API routes to FastAPI using the server-only `BACKEND_URL`. The browser never needs to resolve Docker service names; no CORS configuration is required. Android/iOS clients can use FastAPI directly. There is no fallback to the local GeoJSON when the API fails.

- `app/`, `components/`, `lib/`: Next.js App Router, Google Maps integration, controls, and response validation.
- `app/api/v1/[...path]/route.ts`: bounded, uncached same-origin API proxy with an eight-second timeout.
- `backend/app/`: configuration, SQLAlchemy model/session, Pydantic schemas, spatial repository, FastAPI routes, import CLI.
- `backend/alembic/`: schema migrations; tables are **not** created at application runtime.
- `backend/tests/`: import validation and real PostGIS integration tests.
- `public/data/`: historical interchange file and its review/provenance manifest.

## Quick start: Docker Compose

Docker Compose runs a single development configuration with frontend and backend hot reload. Requires Docker with Compose and a working image/package network connection. The PostGIS service explicitly uses `linux/amd64`; on Apple Silicon, Docker Desktop must support amd64 emulation. The frontend and backend build for the host platform.

```sh
cp .env.example .env
# Edit .env: set NEXT_PUBLIC_GOOGLE_MAPS_API_KEY and optionally POSTGRES_PASSWORD.
docker compose up --build
```

Open [localhost:3000](http://localhost:3000), [API docs](http://localhost:8000/docs), and [API health](http://localhost:8000/api/v1/health).

Three services start in order:

1. `postgres`: PostGIS-enabled PostgreSQL 16, persistent `postgres_data` volume, `pg_isready` health check.
2. `backend`: waits for PostgreSQL, runs `alembic upgrade head`, validates/imports data, starts Uvicorn, checks database/PostGIS/schema health.
3. `frontend`: starts the Next.js development server with Fast Refresh, waits for API health, serves on port 3000, and health-checks the proxied API.

An empty dataset is a non-destructive import no-op and does not prevent startup. Invalid or nonempty unverified data fails startup rather than publishing unreviewed boundaries. Database and backend ports bind to localhost. The development default password is `berliner`; choose a URL-safe password in `.env` for your environment. Changing it after initialization does not change the password in an existing volume.

Compose supplies Google's public key from `.env` when the development server starts. After changing it, run `docker compose up -d --force-recreate frontend`. Local Next.js reads `.env.local`; keep the values aligned when switching workflows. Environment files are ignored by Git and excluded from image build contexts.

```sh
docker compose down                 # Keep persistent database data
docker compose logs backend
docker compose exec backend alembic current
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.import_sectors /data/berlin-sectors.geojson --manifest /data/berlin-sectors.provenance.json
```

Use `docker compose down -v` only when intentionally deleting all local database data.

## Local development

### Hot reload in Docker

```sh
docker compose up --build -d
docker compose logs -f frontend backend
```

There is one configuration: `compose.yaml`. Plain `docker compose up` uses the same hot-reload setup; no extra files or flags are needed. Production deployment is deferred.

Open [localhost:3000](http://localhost:3000). Next.js Fast Refresh uses Webpack and Uvicorn reloads Python application changes. Source directories and frontend configuration files are mounted read-only, with polling enabled for Docker Desktop reliability. New files inside the mounted directories are immediately available. Frontend tests, scripts, and package manifests are also mounted. Backend source, tests, migrations, and configuration are mounted together at `/app`; `PYTHONPATH=/app` ensures application commands and tests import this source instead of an older image-installed copy.

Linux Node dependencies remain in the frontend image. Next.js output uses the `frontend_dev_next` volume, separate from host `.next` and `node_modules`. The existing `postgres_data` volume is preserved. Do not use `down -v` to refresh code. Rebuild with `docker compose up --build -d` after changing dependency manifests or Dockerfiles; hot reload does not install dependencies. Recreate the frontend after editing Compose's `.env` values. Config-file changes may restart Next.js automatically.

Backend migration and import run at container startup, not on source reload. Apply new migrations with `docker compose exec backend alembic upgrade head`; changed geographic files require the documented import command. `docker compose restart` restarts existing containers but does not apply Compose environment or mount changes; use `docker compose up -d` for those.

Verified on 12 November 2026: a temporary frontend API route served “before” then “after” after a source edit, and the backend served a temporary version change then its restored version, without rebuilding or recreating either container. Probes were removed. All 20 frontend and 46 backend/PostGIS tests passed inside these containers.

### Development without containers for the app services

Requires Node.js 20.9+ (22 recommended), Python 3.12+ (Docker uses 3.12), and PostgreSQL with PostGIS.

```sh
npm ci
cp .env.example .env.local
# Set the Google Maps key; BACKEND_URL defaults to http://127.0.0.1:8000.
docker compose up -d postgres

python3.12 -m venv backend/.venv
. backend/.venv/bin/activate
pip install -e './backend[test]'
cp backend/.env.example backend/.env
cd backend
# Set DATABASE_URL in backend/.env to match your database credentials.
alembic upgrade head
python -m app.import_sectors ../public/data/berlin-sectors.geojson --manifest ../public/data/berlin-sectors.provenance.json
uvicorn app.main:app --reload --port 8000
```

In a second terminal at the repository root:

```sh
npm run dev
```

Do not run the Compose backend on port 8000 simultaneously with local Uvicorn. Backend commands below assume the working directory is `backend/` and its virtual environment is active. The backend reads its working directory's `.env`; Compose supplies configuration directly.

### Environment variables

| Variable                          | Used by                      | Default / meaning                                                                |
| --------------------------------- | ---------------------------- | -------------------------------------------------------------------------------- |
| `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` | Browser / frontend build     | Google Maps JavaScript API key; empty shows configuration guidance               |
| `BACKEND_URL`                     | Next.js server               | Local `http://127.0.0.1:8000`; Compose `http://backend:8000`                     |
| `DATABASE_URL`                    | Backend / Alembic / importer | `postgresql+psycopg://berliner:berliner@localhost:5432/berliner_map`             |
| `POSTGRES_PASSWORD`               | Compose                      | Local development default `berliner`; must be URL-safe for the connection string |
| `TEST_DATABASE_URL`               | pytest                       | Dedicated PostGIS database whose name ends in `_test`                            |

Enable billing and **Maps JavaScript API** for your Google Cloud project. Restrict the browser key to this API and HTTP website referrers such as `http://localhost:3000/*` and your production origin. The browser key is public by design; website/API restrictions matter. Never commit `.env.local`. See [Google's API key guide](https://developers.google.com/maps/documentation/javascript/get-api-key).

Missing keys, script errors, authentication errors, API failures, empty historical data, and delayed map loading have visible UI states. Live Google authentication and billing verification require a valid key and network access.

## Database schema and migrations

`occupation_sectors` stores one row per sector, with multiple disconnected parts and holes supported:

| Column        | Type / constraint                                   |
| ------------- | --------------------------------------------------- |
| `id`          | Integer primary key                                 |
| `code`        | Unique `soviet`, `american`, `british`, or `french` |
| `name`        | Sector display name                                 |
| `geometry`    | Nonempty, valid `MULTIPOLYGON`, SRID 4326           |
| `source_name` | Nonempty source attribution                         |
| `source_url`  | Nonempty source link                                |

The migration enables PostGIS and creates `idx_occupation_sectors_geometry` as a GiST index. Polygon inputs normalize to MultiPolygon; coordinates stay longitude/latitude. Database constraints enforce supported codes, nonempty valid geometry, and nonblank source fields. The importer additionally validates coordinates and source URLs.

```sh
alembic upgrade head
alembic current
# Destructive: removes the sectors table and all rows.
alembic downgrade base
```

Downgrade leaves the potentially shared PostGIS extension installed. The migration user needs permission to enable PostGIS (the local Compose user has it). There is no `create_all()` path.

## Verified geographic import

The current release is the reviewed **approximate MVP** in `data/processed/berlin-sectors.geojson`, copied to the existing `public/data` import paths with checksum-bound provenance. All four codes are present, but historical geographic coverage is partial. The `verified` flag attests review for this explicitly approximate MVP use, **not exact 1945 positional accuracy**; read `verification_notes` and the reconstruction record. An empty FeatureCollection still imports zero rows and **does not delete existing records**.

Before importing nonempty data:

1. Obtain geometry verified against historical sources for a specific reference date, including enclaves, territorial exchanges, positional uncertainty, and redistribution rights. Never present modern geometry as exact historical boundaries. The current user-approved MVP uses modern geographic proxies with an explicit approximation disclaimer and known Staaken exclusion.
2. Save an RFC 7946 FeatureCollection using 2D WGS84 `[longitude, latitude]` coordinates. Features must be Polygon/MultiPolygon with closed rings and `properties.sector`. Include all four sector codes. Multiple features in one sector merge into a single MultiPolygon, with consistent attribution.
3. Fill `public/data/berlin-sectors.provenance.json`: `verified: true`, exact file `sha256`, `reference_date`, `source_name`, HTTP(S) `source_url`, `license`, and meaningful `verification_notes`. Do not mark data verified until historical and license review is complete. Optional per-feature `source_name`/`source_url` override the manifest defaults and are preserved in the database/API.
4. Record the reconstruction method, source version, attribution requirements, and limitations in this README. The manifest is a review attestation, not automated proof of historical accuracy; keep it with the dataset.
5. Run the importer after migration.

```sh
# From the repository root: compute the checksum after finalizing the file.
shasum -a 256 public/data/berlin-sectors.geojson

# From backend/:
python -m app.import_sectors ../public/data/berlin-sectors.geojson --manifest ../public/data/berlin-sectors.provenance.json
```

Validation rejects unverified/checksum-mismatched files, legacy CRS declarations, nonfinite/out-of-range coordinates, open rings, invalid/empty geometry, missing sectors, inconsistent attribution, and overlapping sector interiors. It does not reproject, invent, or silently repair geometry. Coordinate ranges alone cannot prove a CRS or historical accuracy; source review must establish both. Shared boundaries are allowed. Source licensing and reconstruction notes live alongside the file; source name/URL persist in each database row.

All validation finishes before database writes. Import uses one transaction, a transaction-scoped advisory lock, and upserts on unique `code`. Repeated imports preserve row IDs and update geometry/attribution without duplicates. Errors roll back the entire import. A partially populated database is considered unavailable (503), rather than reporting misleading spatial results.

## REST API

FastAPI OpenAPI documentation: [localhost:8000/docs](http://localhost:8000/docs). Responses are versioned and independent of the web UI.

| Method | Endpoint                                        | Response                                                                                                         |
| ------ | ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| GET    | `/api/v1/health`                                | `status`, `database`, `dataset_status`; checks PostGIS and migrated table                                        |
| GET    | `/api/v1/sectors`                               | GeoJSON FeatureCollection with `dataset_status`; each feature includes ID, code, `sector`, name, source name/URL |
| GET    | `/api/v1/sectors/identify?lat=52.52&lng=13.405` | `{ "dataset_status": "ready" or "missing", "sector": object or null }`                                           |

Missing data returns an empty FeatureCollection and `dataset_status: "missing"`; identification also returns `sector: null`. `ready` means all four sector codes exist, **not complete or exact historical coverage**. Outside coverage and in the intentional Staaken gap, identification returns `dataset_status: "ready", sector: null`. The unchanged API has no accuracy field; current `source_name` explicitly identifies the approximate/Staaken-excluded dataset, and the UI and published provenance explain limitations. Coordinates must be finite, with latitude in [-90, 90] and longitude in [-180, 180]; invalid/missing/extra identify parameters return 422.

Spatial classification executes PostGIS `ST_Covers(geometry, ST_SetSRID(ST_MakePoint(lng, lat), 4326))`, using the spatial index. `ST_Covers` includes boundary points and excludes holes. A shared edge can belong to two sectors; the single-result API deterministically chooses the alphabetically first sector code. This tie-break is a software convention, not a historical claim about a boundary address.

Database failures, missing migrations, and datasets with fewer than all four sector codes return 503. The Next.js proxy preserves upstream HTTP status codes and returns 502 for upstream network/timeouts/non-JSON responses. Health remains 200 for a migrated, reachable database with no dataset, so the map can show the documented missing-data state.

```sh
curl http://localhost:8000/api/v1/health
curl http://localhost:3000/api/v1/sectors
curl 'http://localhost:8000/api/v1/sectors/identify?lat=52.52&lng=13.405'
```

## Tests and verification

```sh
# Repository root:
npm test
npm run typecheck
npm run lint
npm run build

# backend/ with the virtual environment active:
pytest -m 'not integration'
```

PostGIS integration tests require a **dedicated** real database. They apply the actual Alembic migration, then isolate each test with rolled-back transactions. They never use SQLite or mock spatial operations. Integration tests skip when `TEST_DATABASE_URL` is absent; supplying an unreachable database fails instead of silently skipping.

```sh
# Repository root, with postgres running:
docker compose exec postgres createdb -U berliner berliner_map_test

# backend/:
TEST_DATABASE_URL=postgresql+psycopg://berliner:berliner@localhost:5432/berliner_map_test pytest
```

Or run inside the backend container (database creation above is still required):

```sh
docker compose exec -e TEST_DATABASE_URL=postgresql+psycopg://berliner:berliner@postgres:5432/berliner_map_test backend pytest
```

Adjust credentials if you changed the password. Tests reject database names not ending in `_test`. Coverage includes import provenance, coordinate/topology validation, GeoJSON output/attribution, coordinate API validation, four spatial classifications, shared boundaries, outside coverage, missing and partial datasets, index/migration presence, idempotent updates, and transactional rollback. Synthetic geometry never enters the production importer startup path.

Manual browser checks: load Google Maps, pan/zoom at desktop and mobile sizes; check loading, missing-data, and backend-offline states. Once verified historical data is supplied, check all four colors, toggle, opacity, and sector selection. Google attribution must remain visible.

Frontend unit tests use the built-in Node test runner and TypeScript compiler, with mocked Places details, browser geolocation, and API responses. No live Google Maps credentials are required. Coverage includes all selection sources, API validation/missing coverage, stale responses and place details, GPS errors, permission changes, Find me throttling, stopping/cleanup, deactivation, and request timeouts. Node 22 may print an experimental warning for mock timers.

Authentication, Phase 1.5, and native clients remain out of scope.

## Address search and geolocation (Phases 1.3–1.4)

Enable **Maps JavaScript API** and **Places API (New)** with billing in the same Google Cloud project as `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`. Allow both APIs in the key's API restrictions and restrict website referrers to your deployment and localhost development origins. No additional key or cloud map ID is required. Recreate the frontend after changing Compose environment settings or its public key.

Search uses Google's current `PlaceAutocompleteElement`, with German results restricted to a Berlin bounding box (52.33–52.68 latitude, 13.08–13.77 longitude). This is a geographic search envelope, not an exact Berlin administrative polygon. Keyboard navigation and suggestions are handled by the Google widget; request scheduling/session handling is delegated to it rather than duplicating requests on every input. Select a suggestion to request only location and formatted address, center the map, place a selection marker, and identify through `/api/v1/sectors/identify`. Unselected/free-form input never calls the backend. Google attribution remains part of the widget. See [Google autocomplete setup](https://developers.google.com/maps/documentation/javascript/place-autocomplete-new).

Map and polygon clicks use the same identification workflow, including clicks outside overlay coverage. Polygon events stop propagation to avoid duplicate map requests. Frontend code does not classify polygons. The backend distinguishes missing data from an uncovered point; shared edges resolve deterministically by sector code, so no separate ambiguity flag is available. All results retain the reconstructed-boundary warning.

Map navigation has no Berlin-specific pan or zoom restriction. **Find me** still uses the Berlin search rectangle (not the exact administrative border): an outside GPS fix displays an error and disables recentering before any map movement or sector request. Crossing out of this area also cancels pending GPS identification and stops recentering; passive marker updates remain active. Returning inside clears the error but requires another Find me click to resume recentering.

**Find me** requests location permission when clicked and enables automatic recentering and sector identification. Clicking it again stops recentering. Selecting an address or map location also stops recentering, while the user marker and accuracy circle continue updating independently and never overwrite a manual selection. There is no separate Locate Me button.

When location access is already granted, the app automatically starts a foreground `watchPosition` session to display the user marker. It checks permission without prompting. First-time visitors are prompted only after clicking **Find me**. Revoking permission removes the user marker and stops the watcher. Browsers without support for querying geolocation permission wait for a Find me click rather than risking an automatic permission prompt.

Hiding/leaving the page clears the watcher, cancels pending identification work, and invalidates stale callbacks. Returning to a visible page checks permission again and resumes passive location display if access is still granted. Automatic recentering remains off until Find me is clicked. High-accuracy GPS requests time out after 15 seconds. Location errors appear beside Find me independently of historical-sector results; a GPS error does not replace an address/map result.

Geolocation requires **HTTPS or localhost**. A phone accessing an ordinary HTTP LAN IP cannot use browser geolocation. Browser and operating-system location permission must both be available. The blue marker shows the current accepted GPS fix; its circle shows the reported accuracy radius in meters. Search/map selection uses a distinct pin. GPS updates filter insignificant motion. While Find me is enabled, historical identification is limited to at most one request per 10 seconds with accuracy-aware movement filtering. Passive marker updates make no identification requests. A result can describe the last checked position while the live marker continues moving; the card explains this delay. Results remain visible until explicitly closed; closing the card does not turn Find me off.

### Location privacy

Coordinates and current selection state are held only in browser memory, never local storage, cookies, analytics, or a location-history database. Coordinates go to the same-origin Next.js proxy and existing FastAPI identification endpoint only for historical identification. The Google map provider receives map viewport information as part of displaying the map; address queries and selected-place details use Google Places. Identification responses are not cached. Uvicorn and Next.js development access logging suppress identification request URLs so their query parameters do not enter normal access logs. Configure any deployment proxy/CDN/APM to suppress or redact that route's query parameters too; external infrastructure logging is outside this repository.

### Verification status

Automated validation on 12 November 2026: 38 frontend tests and 46 backend tests (including real PostGIS) passed, along with TypeScript, ESLint, and the production build.

Browser checks on 12 November 2026: desktop and 390px mobile layouts, polygon selection marker and backend sector result, result persistence, explorer opening/closing, and the Places configuration error card. The configured project currently reports **Places API (New) disabled**, so live suggestions and address selection cannot be accepted until it is enabled. Actual device GPS permission and movement were not exercised; their success/error/start/stop/cleanup paths are covered by credential-free unit tests. For manual acceptance, test a Berlin address with arrow keys/Enter, an uncovered map point, Find me permission denial/success, and movement followed by hiding the page. Verify that returning resumes the marker only when permission is granted, manual selection stops recentering while the marker continues updating, permission revocation removes the marker, and Google attribution remains accessible.

## Historical sources and data status

Research checked on 11 November 2026. Intended snapshot: **1 September 1945**, rather than an assertion that boundaries remained geometrically identical throughout 1945–1990.

- [German History in Documents and Images: Berlin (September 1, 1945)](https://germanhistorydocs.org/en/occupation-and-the-emergence-of-two-states-1945-1961/berlin-september-1-1945). Historical reference map; original cartography by IEG-MAPS, Institut für Europäische Geschichte, Mainz, A. Kunz (2004), revised by Gabriel Moss (2021). This is a reference image, not a verified GeoJSON dataset. No geometry was extracted or redistributed. A license permitting derived vector redistribution has not been established; source terms require review before use.
- [Landesdenkmalamt Berlin: Berlin unter Verwaltung der Vier Mächte 1945–1948](https://www.berlin.de/landesdenkmalamt/denkmale/highlight-denkmale-der-alliierten/die-alliierten-in-berlin/berlin-unter-verwaltung-der-vier-maechte-1945-1948-646239.php). Official historical context, not a polygon dataset. No content or geometry redistributed; no data license inferred.
- [Berliner Stadtplansammlung: 1945 Umgebung von Berlin](https://www.berliner-stadtplansammlung.de/index.php/karten/1945-umgebung-von-berlin). Historical map description documents the Staaken/Gatow territorial exchange, illustrating why present-day boundaries cannot be substituted. No map copied; reuse rights not established.
- [Berlin geodata catalog](https://gdi.berlin.de/geonetwork/geonetwork/search). Discovery source. Modern ALKIS borough boundaries are not verified 1945 sector boundaries and are not used.

These references establish historical context, **not positional accuracy for an overlay**. The shipped geographic coordinates now derive from Geoportal Berlin / ALKIS Berlin Ortsteile under Datenlizenz Deutschland Zero 2.0, retrieved 11 November 2026. The modern coordinates are explicitly approximate historical proxies; no protected reference-map imagery was committed. See the Phase 1.2.4 reconstruction record for source snapshots, mapping, exclusions, and tests.

## Earlier implementation-session verification (before the MVP data release)

- `npm run typecheck`: passed.
- `npm run lint`: passed.
- Production build: passed with Webpack. The build script explicitly selects Webpack because this execution sandbox denies the internal port binding used by Turbopack's CSS worker.
- `docker compose config --quiet`: passed.
- Python 3.12 syntax compilation: passed for app, migrations, and tests.
- Local backend dependency installation: blocked by pip DNS resolution. Backend tests ran successfully in the existing backend container, which already had the dependencies installed.
- Backend test suite: all 44 tests passed, including 21 real PostGIS integration tests against the dedicated `berliner_map_test` database. Tests applied the actual Alembic migration. Non-failing warnings remain for Starlette's HTTPX test-client integration and Alembic's legacy path-separator configuration.
- Docker Engine 29.9.1: reachable using authorized Docker access. `docker compose up --build -d` completed successfully, rebuilding images with available cached dependency layers. PostgreSQL, backend, and frontend were all healthy afterward. `alembic upgrade head` succeeded and the running backend reported revision `0001 (head)`.
- Live database inspection: PostGIS 3.5 installed; `occupation_sectors.geometry` is `MULTIPOLYGON` with SRID 4326; `idx_occupation_sectors_geometry` uses GiST.
- Live backend health, sectors, and identification endpoints, plus frontend-proxied health and sectors endpoints: passed. Responses correctly reported `dataset_status: "missing"`, empty features, and no identified sector for the current placeholder dataset.
- Live invalid-coordinate checks: backend and frontend proxy returned 422 for out-of-range latitude, NaN, and missing longitude. An isolated TestClient with a real unreachable database returned 503 for health, sectors, and identification without changing the running server's database configuration.
- Browser checks: Google Maps loaded with the configured key; map panning worked; the missing-data notice and disabled overlay controls were visible at desktop and 390px mobile widths, with Google attribution visible. Historical polygon rendering, visibility/opacity interactions, and selection remain unverified because no verified geometry is available. Backend-offline browser behavior was not exercised.

The checks above describe the earlier empty-data state on 11 November 2026, superseded by the Phase 1.2.4 approximate-data release below. Exact historical linework remains unresolved. See [historical data investigation](docs/historical-data.md) for additional source evaluation and reconstruction requirements.

Phase 1.2.2 preserved a reproducible Histomap sheet inventory and a [boundary reconstruction record](data/HISTORICAL_BOUNDARIES.md), including licensing conflicts, borough assignments, and the 30 August 1945 Gatow/Staaken exception. The published catalogs contain nine K4 sheets explicitly labeled 1945 and no matching K5 sheets. No sector geometry was derived from sheet extents. Run `python3 scripts/inventory_histomap.py` to reproduce the metadata inventory; source rights and exact-date coverage remain unresolved.

## Phase 1 roadmap

- [x] Phase 1.2 backend: migrations, PostGIS schema/index, import validation, spatial API, Next.js proxy, and Compose startup verified.
- [x] Phase 1.2 automated checks: 44 backend tests including real PostGIS integration, TypeScript, ESLint, and production build passed.
- [x] Phase 1.2 base-map browser checks: Google Maps, panning, responsive layout, and missing-data UI verified.
- [x] Phase 1.2.2 research workflow: published Histomap catalog inventory executed; source URLs/checksums, sheet CRS/extents, historical assignments, and reconstruction blockers recorded.
- [ ] Phase 1.2.2 reconstruction: source rights, dated segment coverage, exchange/enclave geometry, georeferencing, digitization, and independent historical validation outstanding; see `data/HISTORICAL_BOUNDARIES.md`.
- [x] Phase 1.2.3 processing workflow: evidenced borough validation, CRS transformation, reviewed exception operations, sector dissolve, complete/partial coverage checks, and candidate provenance implemented; synthetic PostGIS round trip verified.
- [ ] Phase 1.2.3 exact historical output: all 20 exact historical borough polygons, exchange/enclave linework, and independent snapshot coverage still missing. Phase 1.2.4 separately uses explicitly approximate modern proxies, with no protected map imagery copied.
- [ ] Phase 1.1 data prerequisite / Phase 1.2 overlay: obtain redistributable, reviewed sector geometry for **1 September 1945**.
- [x] Phase 1.2.4: produce real source-derived `data/processed/berlin-sectors.geojson` and reviewed approximate-release provenance; preserve the open source snapshot and recipe.
- [x] Phase 1.2.4: validate actual geometry against its declared source-derived extent, import twice, verify stored geometry/attribution, and check broad historically supported locality classifications.
- [ ] Exact historical release: validate against an independent 1945 coverage outline and resolve later exchanges/enclaves.
- [x] Phase 1.2.4 browser: all four colors render; visibility toggle, 35%→70% opacity, and selection of each sector verified on desktop; responsive overlay and full uncertainty notice verified at 390px mobile width. Short desktop panels scroll to keep the full notice accessible.
- [ ] Browser API-failure state: remains a separate manual check; not re-exercised for this data release.
- [x] Phase 1.2.4 data/API MVP: four approximate sectors operational, intentional Staaken gap explicit.
- [ ] Exact Phase 1.2 historical reconstruction: unresolved; approximate MVP acceptance does not establish exact 1945 geometry.
- [x] Phase 1.3: Berlin Places autocomplete and shared map/address sector identification implemented, with persistent result cards and stale-response protection. Live autocomplete acceptance requires Places API (New) to be enabled.
- [x] Phase 1.4: Find me with explicit first-time permission, independent foreground location display, user marker/accuracy circle, movement filtering, throttled identification, cleanup, and privacy handling implemented and unit tested.
- [ ] Phase 1.3–1.4 live acceptance: enable Places API (New), verify suggestion selection with the configured project, and verify GPS permission/accuracy and movement on a real device.
- [ ] Phase 1.5, authentication, and native clients: not implemented.

Current release validation: 18 reconstruction tests and 44 backend tests passed, including real PostGIS; TypeScript, ESLint, production builds, and Compose startup passed. The saved pinned-source recipe reproduced the released GeoJSON byte-for-byte. See `data/processed/integration-verification.json` for actual API classification checks and `data/processed/release-review.json` for accuracy/coverage review scope.

## Troubleshooting

For the historical borough build's input contract, GIS dependencies, commands, and validation evidence, see [Phase 1.2.3 reconstruction instructions](data/HISTORICAL_BOUNDARIES.md#phase-123-executable-borough-reconstruction). Both complete and partial builds remain unverified review candidates until a historical release review; the production importer and API contracts are unchanged.

- **Docker socket denied:** check `docker info` and that Docker Desktop is running. Use the environment's authorized Docker-access mechanism; do not change socket permissions or run blanket permission commands. This session required authorized access outside the filesystem sandbox.
- **Docker shows old UI:** run `docker compose up --build -d` to apply the single hot-reload configuration and rebuild changed dependencies. Both app services must use source mounts; the frontend command is `next dev` and the backend uses `uvicorn --reload`. There is no separate production Compose mode. Source edits require no rebuild; environment, dependency, Dockerfile, or mount changes require recreation/rebuild as described above. Do not delete database volumes to refresh application code.
- **Local pip DNS failures:** check connectivity to your configured package index and proxy/DNS settings. The existing backend image includes test dependencies, so `docker compose exec -T backend pytest -p no:cacheprovider` can run without a local install. Integration tests still require the documented dedicated test database. Cached image layers do not prove a clean dependency download works.
- **pytest cache permission warning in the container:** use `-p no:cacheprovider`; the application user cannot write the image's `/app` directory. This does not affect test execution.
- **API reports `missing`:** the database is reachable but has no historical dataset. Do not enable unreviewed data by changing only `verified` in the manifest. Follow the source-review/import procedure above.
- **API returns 503:** inspect backend logs and run `docker compose exec backend alembic current`; confirm database health and apply `alembic upgrade head`. Missing sector codes make the dataset unavailable; geographic gaps within a four-code approximate release are instead documented in provenance and the UI.
- **Proxy returns 502:** confirm backend health and server-only `BACKEND_URL`; Compose uses `http://backend:8000`, local Next.js uses `http://127.0.0.1:8000`.
- **Map does not load:** check Google Cloud API/referrer restrictions and billing without sharing the key. Recreate the frontend after changing the public key in `.env`: `docker compose up -d --force-recreate frontend`.

### Database credential logging

Backend settings keep the connection URL as a masked secret and hide input values in validation errors. Application, Uvicorn, migration, and importer processes install database-password redaction before reading settings. Logging messages, arguments, stack information, logged exceptions, and unhandled CLI tracebacks redact configured passwords and their URL/JSON-escaped representations. SQLAlchemy query echo is explicitly disabled and bound parameters are hidden in errors. PostgreSQL currently has statement logging disabled and error parameter logging set to zero.

On 12 November 2026, a local in-memory scan found no configured database-password text in the current frontend, backend, or PostgreSQL Docker logs; neither credentials nor matching lines were printed. This is a check of the current containers, not old containers, exported logs, or shell history. Docker administrators can still inspect container environment variables, and plain `docker compose config` can display interpolated secrets: use `docker compose config --quiet` for validation and avoid sharing environment/configuration dumps. Use psql's interactive `\password` command when changing the database password.
