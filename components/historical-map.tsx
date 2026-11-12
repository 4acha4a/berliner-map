"use client";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { importLibrary, setOptions } from "@googlemaps/js-api-loader";
import {
  loadSectors,
  sectors,
  type SectorData,
  type SectorId,
} from "@/lib/sectors";
import { MapControls } from "./map-controls";
import { AddressSearch } from "./address-search";
import { LocationController, initialLocation, observeLocationPermission } from "@/lib/location";
import { isWithinBerlin } from "@/lib/berlin";
import { locationMarker, selectMapPoint } from "@/lib/map-location";

type DataState = {
  status: "loading" | "missing" | "error" | "ready";
  data?: SectorData;
};
export function HistoricalMap() {
  const container = useRef<HTMLDivElement>(null);
  const [map, setMap] = useState<google.maps.Map>();
  const [mapStatus, setMapStatus] = useState("Loading map…");
  const [dataset, setDataset] = useState<DataState>({ status: "loading" });
  const [visible, setVisible] = useState(true);
  const [opacity, setOpacity] = useState(0.25);
  const [location] = useState(() => new LocationController());
  const selection = useSyncExternalStore(location.subscribe, location.getSnapshot, () => initialLocation);
  const [closing, setClosing] = useState<number>();
  const [explorerState, setExplorerState] = useState<"closed" | "open" | "closing">("closed");
  const explorerOpen = explorerState !== "closed";
  const key = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;

  const toggleExplorer = () => {
    if (explorerState !== "open") {
      setExplorerState("open");
    } else {
      setExplorerState(
        window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "closed"
          : "closing",
      );
    }
  };

  useEffect(() => {
    if (explorerState !== "closing") return;
    // Finish even if animation events are interrupted or the tab is in the background.
    const timeout = window.setTimeout(
      () => setExplorerState((state) => state === "closing" ? "closed" : state),
      220,
    );
    return () => window.clearTimeout(timeout);
  }, [explorerState]);

  useEffect(() => {
    if (selection.status === "idle") return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !event.isComposing) setClosing(selection.revision);
    };
    // Capture also catches Escape when focus is inside a Google Maps control.
    document.addEventListener("keydown", closeOnEscape, true);
    return () => document.removeEventListener("keydown", closeOnEscape, true);
  }, [selection.status, selection.revision]);

  useEffect(() => {
    if (closing === undefined || closing !== selection.revision) return;
    const timeout = window.setTimeout(() => {
      location.dismiss();
      setClosing(undefined);
    }, window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 220);
    return () => window.clearTimeout(timeout);
  }, [closing, location, selection.revision]);

  useEffect(() => {
    let stopObserving: (() => void) | undefined;
    const deactivate = () => {
      stopObserving?.();
      stopObserving = undefined;
      location.deactivate();
    };
    const sync = () => {
      stopObserving?.();
      if (document.hidden) { deactivate(); return; }
      stopObserving = observeLocationPermission(location, navigator.permissions, navigator.geolocation,
        window.isSecureContext, () => !document.hidden);
    };
    sync();
    document.addEventListener("visibilitychange", sync);
    window.addEventListener("pagehide", deactivate);
    window.addEventListener("pageshow", sync);
    return () => {
      document.removeEventListener("visibilitychange", sync);
      window.removeEventListener("pagehide", deactivate);
      window.removeEventListener("pageshow", sync);
      deactivate();
    };
  }, [location]);

  useEffect(() => {
    if (!map) return;
    const listener = map.addListener("click", (event: google.maps.MapMouseEvent) => {
      selectMapPoint(event, (point) => { void location.manual(point, "map"); });
    });
    return () => listener.remove();
  }, [map, location]);

  useEffect(() => {
    if (!map || !selection.coordinates) return;
    if (selection.source === "address") {
      map.panTo(selection.coordinates);
      map.setZoom(16);
    }
    if (selection.source === "follow") return;
    return locationMarker(map, selection.coordinates, "selected");
  }, [map, selection.coordinates, selection.source]);

  useEffect(() => {
    if (!map || !selection.user) return;
    const remove = locationMarker(map, selection.user, "user");
    const circle = selection.user.accuracy === undefined ? undefined : new google.maps.Circle({
      map, center: selection.user, radius: selection.user.accuracy,
      fillColor: "#3478d4", fillOpacity: 0.12, strokeColor: "#3478d4",
      strokeOpacity: 0.4, strokeWeight: 1, clickable: false,
    });
    if (selection.following && isWithinBerlin(selection.user)) map.panTo(selection.user);
    return () => { remove(); circle?.setMap(null); };
  }, [map, selection.user, selection.following]);

  useEffect(() => {
    const controller = new AbortController();
    loadSectors(controller.signal)
      .then((data) =>
        setDataset({
          status: data.features.length ? "ready" : "missing",
          data,
        }),
      )
      .catch(() => {
        if (!controller.signal.aborted) setDataset({ status: "error" });
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!key) return;
    let active = true;
    const authWindow = window as Window & { gm_authFailure?: () => void };
    const previousAuthFailure = authWindow.gm_authFailure;
    authWindow.gm_authFailure = () => {
      if (active)
        setMapStatus(
          "Google Maps could not authenticate. Check the API key, billing, API access, and allowed website referrers.",
        );
    };
    const timeout = window.setTimeout(() => {
      if (active)
        setMapStatus(
          "Google Maps is taking longer than expected. Check your connection and API configuration, then reload.",
        );
    }, 20000);
    setOptions({ key, v: "quarterly" });
    importLibrary("maps")
      .then((library) => {
        if (!active || !container.current) return;
        const { Map } = library as google.maps.MapsLibrary;
        const instance = new Map(container.current, {
          center: { lat: 52.52, lng: 13.405 },
          zoom: 11,
          mapTypeControl: false,
          streetViewControl: false,
          fullscreenControl: false,
          clickableIcons: false,
          gestureHandling: "greedy",
        });
        setMap(instance);
        setMapStatus("");
        window.clearTimeout(timeout);
      })
      .catch(() => {
        if (active) {
          window.clearTimeout(timeout);
          setMapStatus(
            "Google Maps could not load. Check your connection and API configuration, then reload.",
          );
        }
      });
    return () => {
      active = false;
      window.clearTimeout(timeout);
      authWindow.gm_authFailure = previousAuthFailure;
    };
  }, [key]);

  useEffect(() => {
    if (!map || !dataset.data?.features.length) return;
    const layer = new google.maps.Data({ map });
    layer.addGeoJson(dataset.data);
    const listener = layer.addListener(
      "click",
      (event: google.maps.Data.MouseEvent) => {
        selectMapPoint(event, (point) => { void location.manual(point, "map"); });
      },
    );
    const tokens = getComputedStyle(container.current ?? document.documentElement);
    const color = (feature: google.maps.Data.Feature) =>
      tokens.getPropertyValue(sectors[feature.getProperty("sector") as SectorId].colorToken).trim();
    layer.setStyle((feature) => ({
      fillColor: color(feature),
      strokeColor: color(feature),
      strokeWeight: 2,
      fillOpacity: opacity,
      visible,
    }));
    return () => {
      listener.remove();
      layer.setMap(null);
    };
  }, [map, dataset, visible, opacity, location]);

  const message = !key
    ? "Add your Google Maps API key to .env.local to explore the map."
    : mapStatus;
  return (
    <main className="shell">
      <div className={`workspace ${explorerOpen ? "explorer-open" : "explorer-closed"}`}>
        {map && <div className="location-tools">
          <AddressSearch controller={location} />
          <div className="geolocation-controls">
            <button type="button" className="button-secondary" aria-pressed={selection.following}
              onClick={() => selection.following ? location.stopFollowing() : location.findMe(navigator.geolocation, window.isSecureContext)}>
              Find me
            </button>
          </div>
          {selection.locationError && <p className="location-error" role="status">{selection.locationError}</p>}
        </div>}
        <button
          className="explorer-toggle button-secondary"
          type="button"
          aria-label="Explore data"
          title="Explore data"
          aria-expanded={explorerState === "open"}
          aria-controls="data-explorer"
          onClick={toggleExplorer}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M2 3.5h12M2 8h12M2 12.5h12M6 2v3M10 6.5v3M6 11v3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
        <div
          ref={container}
          className="map"
          aria-label="Interactive Google Map centered on Berlin"
        />
        {message && (
          <div className="map-message" role="status">
            <span className="eyebrow">BERLIN · 52.5200° N, 13.4050° E</span>
            <h2>
              {key ? "Connecting you to Berlin" : "Your journey starts here"}
            </h2>
            <p>{message}</p>
            {!key && <code>NEXT_PUBLIC_GOOGLE_MAPS_API_KEY</code>}
          </div>
        )}
        <aside
          id="data-explorer"
          aria-label="Data explorer"
          hidden={!explorerOpen}
          data-state={explorerState}
          inert={explorerState === "closing"}
          aria-hidden={explorerState === "closing" ? true : undefined}
          onAnimationEnd={(event) => {
            if (event.target === event.currentTarget && event.animationName === "explorer-exit") {
              setExplorerState((state) => state === "closing" ? "closed" : state);
            }
          }}
        >
          <MapControls
            visible={visible}
            opacity={opacity}
            available={dataset.status === "ready"}
            onVisible={setVisible}
            onOpacity={setOpacity}
          />
          <section className="data-notice card" aria-live="polite">
            <span className="status-dot" />
            <div>
              <h2>
                {dataset.status === "ready"
                  ? "Approximate historical overlay"
                  : dataset.status === "loading"
                    ? "Checking historical data…"
                    : dataset.status === "error"
                      ? "Historical data unavailable"
                      : "Verified boundaries pending"}
              </h2>
              <p>
                {dataset.status === "ready"
                  ? "Historical boundaries are reconstructed and may differ from their exact 1945 locations."
                  : dataset.status === "error"
                    ? "The historical API could not be reached or returned invalid data. Please reload to retry."
                    : dataset.status === "loading"
                      ? "Fetching historical sector boundaries from the API…"
                      : "The historical overlay is incomplete. No sector boundaries are displayed until verified geographic data is available."}
              </p>
              {dataset.status === "ready" && (
                <p>
                  Staaken is excluded while its historical split remains unresolved.
                  Coverage is partial; Gatow and later territorial changes remain
                  uncertain. Do not use this map for building-level or address-level
                  historical classification.
                </p>
              )}
              <a
                href="https://germanhistorydocs.org/en/occupation-and-the-emergence-of-two-states-1945-1961/berlin-september-1-1945"
                target="_blank"
                rel="noreferrer"
              >
                View historical reference ↗
              </a>
            </div>
          </section>
        </aside>
        {selection.status !== "idle" && (
          <section
            key={selection.revision}
            className="selection location-result card"
            data-sector={selection.status === "ready" ? selection.result?.sector?.code : undefined}
            data-state={closing === selection.revision ? "closing" : "open"}
            aria-live="polite"
            aria-atomic="true"
            aria-keyshortcuts="Escape"
            inert={closing === selection.revision}
          >
            <div>
              <strong>
                {selection.status === "loading" ? "Finding historical sector…"
                  : selection.status === "error" ? "Location unavailable"
                  : selection.result?.dataset_status === "missing" ? "Historical dataset unavailable"
                  : selection.result?.sector ? `${selection.result.sector.name} sector`
                  : "Outside historical coverage"}
              </strong>
              {selection.label && <p className="selection-address">{selection.label}</p>}
              {selection.error && <p>{selection.error}</p>}
              {selection.status === "ready" && <p>{selection.result?.dataset_status === "missing"
                ? "No historical geographic dataset is available for identification."
                : "Approximate reconstructed boundaries; gaps and uncertain areas remain. Not suitable for building-level classification."}</p>}
              {selection.following && selection.result && <p>Sector shown for the last checked GPS position; checks are limited while moving.</p>}
              {(selection.following ? selection.user?.accuracy : selection.accuracy) !== undefined &&
                <p>GPS accuracy: ±{Math.round((selection.following ? selection.user?.accuracy : selection.accuracy)!)} m</p>}
            </div>
            <button type="button" onClick={() => setClosing(selection.revision)} aria-label="Close sector details">×</button>
          </section>
        )}
        <div className="map-caption">
          A contemporary map. A historical perspective.
        </div>
      </div>
    </main>
  );
}
