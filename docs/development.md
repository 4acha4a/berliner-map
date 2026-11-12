# Development and database operations

See the [README](../README.md) for Docker startup, Google API configuration, and location behavior.

## Docker workflow

`compose.yaml` runs Next.js Fast Refresh and Uvicorn reload with polling for Docker Desktop. Source mounts are read-only. Node dependencies stay in the frontend image; `.next` uses a separate volume. Backend commands import the mounted `/app` source through `PYTHONPATH`.

```sh
docker compose up --build -d
docker compose logs -f frontend backend
docker compose config --quiet
```

Rebuild after dependency or Dockerfile changes. Use `docker compose up -d` to apply changed Compose settings; `restart` does not update mounts or environment variables. Recreate affected containers after changing `.env`. Database data persists in `postgres_data`; do not delete volumes to refresh application code.

## App services without containers

Requires Node.js 20.9+ (22 recommended), Python 3.12+, and PostgreSQL with PostGIS.

From the repository root:

```sh
npm ci
cp .env.example .env.local
# Set the Google Maps key in .env.local.
docker compose up -d postgres

python3.12 -m venv backend/.venv
. backend/.venv/bin/activate
pip install -e './backend[test]'
cp backend/.env.example backend/.env
cd backend
# Set DATABASE_URL in backend/.env to match the database credentials.
alembic upgrade head
python -m app.import_sectors ../public/data/berlin-sectors.geojson --manifest ../public/data/berlin-sectors.provenance.json
uvicorn app.main:app --reload --port 8000
```

Run `npm run dev` from the repository root in another terminal. Do not run the Compose backend simultaneously on port 8000. Local Next.js uses `BACKEND_URL=http://127.0.0.1:8000`; backend configuration is read from its working directory’s `.env`.

## Database operations

Migrations and import run on container startup, not on every source reload. To apply them explicitly:

```sh
docker compose exec backend alembic current
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.import_sectors /data/berlin-sectors.geojson --manifest /data/berlin-sectors.provenance.json
```

To change an existing database password, open psql and use its interactive prompt:

```sh
docker compose exec postgres psql -U berliner -d berliner_map
```

```text
\password berliner
\q
```

Set the same password in `.env` as `POSTGRES_PASSWORD`, then run `docker compose up -d --force-recreate postgres backend`. Use a URL-safe password because Compose embeds it in `DATABASE_URL`. Editing `.env` alone does not rotate an initialized database’s password.

Backend settings mask the database URL. Logging and unhandled CLI tracebacks redact configured credentials, SQLAlchemy echo is disabled, and error parameters are hidden. These protections do not hide container environment variables from Docker administrators or redact external log archives. Avoid passing passwords as command arguments or sharing `docker compose config` output; validate with `--quiet` instead.

## Geographic data and API

`occupation_sectors` stores the four sector codes with attributed, valid `MULTIPOLYGON` geometry in SRID 4326 and a GiST spatial index. Schema changes use Alembic; runtime code does not create tables.

The importer requires a WGS84 Polygon/MultiPolygon FeatureCollection plus a reviewed, checksum-matching provenance manifest. It validates all data before transactional upserts; failed imports roll back. Empty datasets are a no-op and do not delete existing rows. See the [reconstruction record](../data/HISTORICAL_BOUNDARIES.md) for data contracts and source review.

| GET endpoint | Purpose |
| --- | --- |
| `/api/v1/health` | Database, PostGIS, migration, and dataset health. |
| `/api/v1/sectors` | Attributed GeoJSON and dataset status. |
| `/api/v1/sectors/identify?lat=52.52&lng=13.405` | Sector identification through PostGIS. |

`dataset_status: "missing"` means no dataset is installed. `ready` means all four sector codes exist, not complete or exact historical coverage. An uncovered point returns `sector: null`; shared boundaries resolve by alphabetical sector code. Invalid coordinates return 422; incomplete datasets or database failures return 503. The Next.js proxy returns 502 for upstream connection failures. Full schemas are in [API docs](http://localhost:8000/docs).

## PostGIS integration tests

Tests require a dedicated database whose name ends in `_test`; each test rolls back its changes. Create it once:

```sh
docker compose exec postgres createdb -U berliner berliner_map_test
```

Run the full suite with the container’s configured credentials without printing them or putting them in shell history:

```sh
docker compose exec -T backend sh -c 'TEST_DATABASE_URL="${DATABASE_URL%/*}/berliner_map_test" pytest -p no:cacheprovider'
```

Without `TEST_DATABASE_URL`, integration tests skip. An explicitly configured but unreachable database fails. Frontend tests mock Google and geolocation; backend spatial tests use synthetic geometry, never the production dataset.

## Troubleshooting

- **Old UI:** run `docker compose up --build -d` to apply mounts and dependencies. Source-only edits hot reload; a browser refresh may be needed after stateful controller changes.
- **Missing map/search:** check billing, enabled Google APIs, key restrictions, and `.env`; recreate the frontend after changing its key.
- **Geolocation unavailable:** use HTTPS or localhost and check browser/device permission. Find me uses a rectangular Berlin search area, not an exact city polygon.
- **Missing historical data:** review the dataset and provenance; do not bypass verification by changing only the manifest flag.
- **API 503:** check backend logs, database health, and `alembic current`; apply missing migrations.
- **Proxy 502:** check backend health and `BACKEND_URL`.
- **Docker socket denied:** ensure Docker Desktop is running and use authorized Docker access; do not change socket permissions.
