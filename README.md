# Berliner Map

Explore Berlin’s Allied occupation sectors through an interactive Google Map.

- Historical overlay with visibility and opacity controls.
- Berlin address search and map-click sector identification.
- **Find me**, live location marker, and GPS accuracy circle.
- Sector-colored popups with address details; close with × or Escape to remove the selection marker.

Built with Next.js, React, TypeScript, FastAPI, and PostgreSQL/PostGIS. The frontend calls FastAPI through a same-origin Next.js proxy.

## Quick start

Requires Docker Compose. On Apple Silicon, Docker Desktop must support amd64 emulation for PostGIS.

```sh
cp .env.example .env
# Set NEXT_PUBLIC_GOOGLE_MAPS_API_KEY and POSTGRES_PASSWORD in .env.
docker compose up --build -d
```

Open [the map](http://localhost:3000), [API docs](http://localhost:8000/docs), or [API health](http://localhost:8000/api/v1/health).

There is one development configuration with frontend and backend hot reload. Startup applies migrations and imports the reviewed dataset. Source edits need no rebuild; dependency or Dockerfile changes require `docker compose up --build -d`. Production deployment is deferred.

## Configuration

| Variable | Purpose |
| --- | --- |
| `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` | Browser key for Maps JavaScript API and Places API (New). |
| `POSTGRES_PASSWORD` | Compose database password; use a URL-safe value. |
| `BACKEND_URL` | Next.js API target; Compose sets `http://backend:8000`. |
| `DATABASE_URL` | Backend connection string; Compose builds it from the database password. |
| `TEST_DATABASE_URL` | Optional dedicated PostGIS test database, ending in `_test`. |

Enable billing, **Maps JavaScript API**, and **Places API (New)** in the same Google Cloud project. Allow both APIs on the key and restrict website referrers to your app origins, such as `http://localhost:3000/*`. See [Google’s autocomplete setup](https://developers.google.com/maps/documentation/javascript/place-autocomplete-new).

Compose reads `.env`; local Next.js reads `.env.local`. After changing the Compose key, run:

```sh
docker compose up -d --force-recreate frontend
```

Changing `.env` does not change an existing database password. See [database operations](docs/development.md#database-operations).

## Location behavior and privacy

Geolocation requires **HTTPS or localhost**. First-time permission is requested only when **Find me** is clicked. With permission already granted, the location marker updates automatically while the page is visible.

Find me toggles recentering. Selecting an address or map point stops recentering but keeps the user marker active. Hiding the page stops location updates; returning resumes the marker if permission is granted, with recentering off. Locations outside the Berlin search rectangle show an error when Find me is used. Map panning and zooming are unrestricted.

Coordinates are held in memory, without persisted location history. GPS sector checks are throttled; passive marker updates make no identification requests. Google receives address searches and map viewport information. Identification request URLs are excluded from access logs, and backend logs redact database passwords. `.env` files are Git-ignored; avoid sharing Docker environment/configuration dumps.

## Development and tests

```sh
docker compose logs -f frontend backend
docker compose down  # Preserves database data; adding -v deletes volumes.

npm ci
npm test
npm run typecheck
npm run lint
npm run build

docker compose exec -T backend pytest -m 'not integration' -p no:cacheprovider
```

Frontend unit tests need no live Google credentials. For local app services, full PostGIS tests, migrations, and imports, see [development instructions](docs/development.md).

## Historical accuracy and roadmap

The overlay approximates **1 September 1945** using modern geographic proxies. Coverage is partial: Staaken is excluded, and Gatow and later territorial changes remain uncertain. **Do not use it for building-level historical classification.**

Sources, licenses, reconstruction steps, and release evidence are in the [boundary reconstruction record](data/HISTORICAL_BOUNDARIES.md) and [historical-data investigation](docs/historical-data.md).

- Implemented: PostGIS backend, reviewed approximate overlay, address search, and foreground geolocation (Phases 1.2–1.4).
- Remaining: exact historical geometry, real-device GPS validation, and production deployment. Phase 1.5, authentication, and native clients are not implemented.
