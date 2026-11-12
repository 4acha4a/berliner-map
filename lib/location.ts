import { isWithinBerlin } from "./berlin";

export type Coordinates = { lat: number; lng: number };
export type SelectionSource = "address" | "map" | "follow";
export type SectorCode = "soviet" | "american" | "british" | "french";
export type Identification = {
  dataset_status: "ready" | "missing";
  sector: { code: SectorCode; name: string } | null;
};
export type LocationState = {
  revision: number;
  source?: SelectionSource;
  coordinates?: Coordinates;
  accuracy?: number;
  label?: string;
  status: "idle" | "loading" | "ready" | "error";
  result?: Identification;
  error?: string;
  following: boolean;
  locationError?: string;
  user?: Coordinates & { accuracy?: number };
};
const outsideBerlinError = "You are outside Berlin. Find me is available only within Berlin.";

export const initialLocation: LocationState = { revision: 0, status: "idle", following: false };

export function validCoordinates(point: Coordinates) {
  return Number.isFinite(point.lat) && Number.isFinite(point.lng) &&
    Math.abs(point.lat) <= 90 && Math.abs(point.lng) <= 180;
}
export function distanceMeters(a: Coordinates, b: Coordinates) {
  const radians = Math.PI / 180;
  const dlat = (b.lat - a.lat) * radians;
  const dlng = (b.lng - a.lng) * radians;
  const h = Math.sin(dlat / 2) ** 2 + Math.cos(a.lat * radians) *
    Math.cos(b.lat * radians) * Math.sin(dlng / 2) ** 2;
  return 6371000 * 2 * Math.asin(Math.sqrt(Math.min(1, h)));
}
export async function identifyLocation(point: Coordinates, signal: AbortSignal, request = fetch): Promise<Identification> {
  if (!validCoordinates(point)) throw new Error("This location has invalid coordinates.");
  const response = await request(`/api/v1/sectors/identify?${new URLSearchParams({ lat: String(point.lat), lng: String(point.lng) })}`, {
    signal, cache: "no-store",
  });
  if (!response.ok) throw new Error("Historical identification is unavailable. Please try again.");
  const value = await response.json();
  if (!value || !["ready", "missing"].includes(value.dataset_status) ||
    !(value.sector === null || (value.sector &&
      ["soviet", "american", "british", "french"].includes(value.sector.code) && typeof value.sector.name === "string")) ||
    (value.dataset_status === "missing" && value.sector !== null)) {
    throw new Error("The historical API returned an invalid result.");
  }
  return value;
}
export function geolocationError(error: Pick<GeolocationPositionError, "code">) {
  if (error.code === 1) return "Location permission was denied. Allow location access in your browser to try again.";
  if (error.code === 3) return "Finding your location timed out. Please try again.";
  return "Your location is unavailable. Check your device location settings and try again.";
}

// Only the current location is held in memory. Maps objects belong to the view.
export class LocationController {
  private state = initialLocation;
  private listeners = new Set<() => void>();
  private request?: AbortController;
  private intent = 0;
  private gpsGeneration = 0;
  private watcher?: number;
  private followTimeout?: ReturnType<typeof setTimeout>;
  private geo?: Geolocation;
  private lastIdentification?: Coordinates & { accuracy?: number; time: number };
  constructor(private identify = identifyLocation, private now = Date.now) {}
  getSnapshot = () => this.state;
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };
  private update(patch: Partial<LocationState>) {
    this.state = { ...this.state, ...patch };
    this.listeners.forEach((listener) => listener());
  }
  begin(source: SelectionSource) {
    this.request?.abort();
    const intent = ++this.intent;
    this.update({ revision: intent, source, coordinates: undefined, accuracy: undefined,
      label: undefined, status: "loading", result: undefined, error: undefined });
    return intent;
  }
  fail(intent: number, message: string) {
    if (intent === this.intent) this.update({ status: "error", error: message });
  }
  async select(point: Coordinates, source: SelectionSource, options: { accuracy?: number; label?: string; intent?: number } = {}) {
    const intent = options.intent ?? this.begin(source);
    if (intent !== this.intent) return;
    if (!validCoordinates(point)) { this.fail(intent, "This location has invalid coordinates."); return; }
    const request = new AbortController();
    this.request = request;
    this.update({ coordinates: point, accuracy: options.accuracy, label: options.label });
    const timeout = setTimeout(() => request.abort(), 10000);
    try {
      const result = await this.identify(point, request.signal);
      if (intent === this.intent && !request.signal.aborted) this.update({ status: "ready", result });
    } catch {
      this.fail(intent, request.signal.aborted
        ? "Historical identification timed out. Please try again."
        : "Historical identification is unavailable. Please try again.");
    } finally { clearTimeout(timeout); }
  }
  manual(point: Coordinates, source: "address" | "map", label?: string) {
    this.stopFollowing();
    return this.select(point, source, { label });
  }
  async address(prediction: { mainText?: { text: string } | null; text?: { text: string }; toPlace(): { fetchFields(options: { fields: string[] }): Promise<unknown>; location?: { lat(): number; lng(): number } | null; formattedAddress?: string | null } }) {
    this.stopFollowing();
    const intent = this.begin("address");
    try {
      const place = prediction.toPlace();
      await place.fetchFields({ fields: ["location", "formattedAddress"] });
      if (!place.location) throw new Error("No location");
      const point = { lat: place.location.lat(), lng: place.location.lng() };
      // Berlin bounding box also rejects synthetic out-of-area route predictions.
      if (!isWithinBerlin(point)) {
        this.fail(intent, "Choose an address within Berlin."); return;
      }
      const address = place.formattedAddress?.trim();
      const name = prediction.mainText?.text.trim();
      const label = address
        ? name && !address.toLocaleLowerCase().includes(name.toLocaleLowerCase()) ? `${name}, ${address}` : address
        : prediction.text?.text.trim() || name || "Selected address";
      await this.select(point, "address", { intent, label });
    } catch { this.fail(intent, "This address could not be loaded. Choose another suggestion or try again."); }
  }
  stopFollowing = () => {
    clearTimeout(this.followTimeout);
    this.followTimeout = undefined;
    this.lastIdentification = undefined;
    if (this.state.following) this.update({ following: false });
    if (this.state.source === "follow" && this.state.status === "loading" && !this.state.coordinates) {
      this.update({ status: "idle" });
    }
  };
  private stopTracking() {
    ++this.gpsGeneration;
    if (this.watcher !== undefined) this.geo?.clearWatch(this.watcher);
    this.watcher = undefined;
    this.stopFollowing();
  }
  revokePermission = () => {
    const wasFollowing = this.state.following;
    this.stopTracking();
    if (this.state.source === "follow") {
      this.request?.abort();
      ++this.intent;
      if (this.state.status === "loading") this.update({ status: "idle" });
    }
    this.update({ user: undefined, locationError: wasFollowing ? geolocationError({ code: 1 }) : this.state.locationError });
  };
  findMe(geo: Geolocation | undefined, secure: boolean) {
    // Retry a failed watcher only after a fresh user action.
    if (this.state.locationError) this.stopTracking();
    this.stopFollowing();
    if (this.state.user && !isWithinBerlin(this.state.user)) {
      this.rejectOutsideLocation();
      this.startTracking(geo, secure);
      return;
    }
    this.begin("follow");
    this.update({ following: true, locationError: undefined });
    this.startTracking(geo, secure);
    if (this.state.following && this.state.user) this.identifyUserPosition();
  }
  private rejectOutsideLocation() {
    this.stopFollowing();
    if (this.state.source === "follow" && this.state.status === "loading") {
      this.request?.abort();
      ++this.intent;
      this.update({ status: "idle" });
    }
    this.update({ locationError: outsideBerlinError });
  }
  private identifyUserPosition = () => {
    if (!this.state.following || !this.state.user) return;
    if (!isWithinBerlin(this.state.user)) { this.rejectOutsideLocation(); return; }
    const { lat, lng, accuracy } = this.state.user;
    const point = { lat, lng };
    const last = this.lastIdentification;
    const improved = accuracy !== undefined && last?.accuracy !== undefined && accuracy < last.accuracy / 2;
    if (last) {
      if (!improved && distanceMeters(last, point) < Math.max(10, last.accuracy ?? 10, accuracy ?? 10)) return;
      const remaining = 10000 - (this.now() - last.time);
      if (remaining > 0) {
        // Check the final position after cooldown even if the user stops moving.
        if (this.followTimeout === undefined) this.followTimeout = setTimeout(() => {
          this.followTimeout = undefined;
          this.identifyUserPosition();
        }, remaining);
        return;
      }
    }
    clearTimeout(this.followTimeout);
    this.followTimeout = undefined;
    this.lastIdentification = { ...point, accuracy, time: this.now() };
    void this.select(point, "follow", { accuracy });
  };
  // Called automatically only after a non-prompting permission check reports granted.
  startTracking(geo: Geolocation | undefined, secure: boolean) {
    if (this.watcher !== undefined) return;
    if (!secure || !geo) {
      const requested = this.state.following;
      this.stopFollowing();
      if (requested) this.update({ locationError: !secure
        ? "Location access requires HTTPS or localhost."
        : "Your browser does not support geolocation." });
      return;
    }
    this.geo = geo;
    const generation = ++this.gpsGeneration;
    const failure = (error: Pick<GeolocationPositionError, "code">) => {
      if (generation !== this.gpsGeneration) return;
      if (error.code === 1) {
        this.revokePermission();
      } else {
        this.stopFollowing();
      }
      this.update({ locationError: geolocationError(error) });
    };
    const success = (position: GeolocationPosition) => {
      if (generation !== this.gpsGeneration) return;
      const point = { lat: position.coords.latitude, lng: position.coords.longitude };
      if (!validCoordinates(point)) { failure({ code: 2 }); return; }
      const accuracy = Number.isFinite(position.coords.accuracy) && position.coords.accuracy >= 0 ? position.coords.accuracy : undefined;
      const previous = this.state.user;
      const improved = accuracy !== undefined && previous?.accuracy !== undefined && accuracy < previous.accuracy / 2;
      const outside = !isWithinBerlin(point);
      if (outside && this.state.following) this.rejectOutsideLocation();
      this.update({ locationError: outside && this.state.locationError === outsideBerlinError ? outsideBerlinError : undefined });
      const changedRegion = previous && isWithinBerlin(previous) !== isWithinBerlin(point);
      if (previous && !changedRegion && !improved && distanceMeters(previous, point) < Math.max(10, Math.min(previous.accuracy ?? 10, accuracy ?? 10))) return;
      this.update({ user: { ...point, accuracy } });
      this.identifyUserPosition();
    };
    try {
      this.watcher = geo.watchPosition(success, failure, { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 });
    } catch { failure({ code: 2 }); }
  }
  deactivate = () => {
    this.stopTracking();
    this.request?.abort();
    ++this.intent;
    if (this.state.status === "loading") this.update({ status: "idle" });
  };
  dismiss = () => {
    this.request?.abort();
    ++this.intent;
    this.update({ status: "idle", error: undefined, result: undefined,
      coordinates: undefined, source: undefined, accuracy: undefined, label: undefined });
  };
}

// Permissions.query never prompts. Unsupported browsers wait for the Find me click.
export function observeLocationPermission(
  controller: LocationController,
  permissions: Pick<Permissions, "query"> | undefined,
  geo: Geolocation | undefined,
  secure: boolean,
  isVisible: () => boolean,
) {
  let active = true;
  let status: PermissionStatus | undefined;
  const changed = () => {
    if (!active || !isVisible()) return;
    if (status?.state === "granted") controller.startTracking(geo, secure);
    else controller.revokePermission();
  };
  void (async () => {
    try {
      status = await permissions?.query({ name: "geolocation" });
      if (!active || !status || !isVisible()) return;
      status.addEventListener("change", changed);
      // An initial prompt state must not cancel a concurrent Find me click.
      if (status.state !== "prompt") changed();
    } catch { /* A Find me click still works without the Permissions API. */ }
  })();
  return () => {
    active = false;
    status?.removeEventListener("change", changed);
  };
}
