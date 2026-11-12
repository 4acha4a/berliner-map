import type { Coordinates } from "./location";

// Screen-sized markers without a cloud map ID or deprecated Marker API.
export function locationMarker(map: google.maps.Map, point: Coordinates, kind: "selected" | "user") {
  const overlay = new google.maps.OverlayView();
  const element = document.createElement("div");
  element.className = `location-marker location-marker-${kind}`;
  element.setAttribute("role", "img");
  element.setAttribute("aria-label", kind === "user" ? "Your current location" : "Selected location");
  overlay.onAdd = () => { overlay.getPanes()?.overlayMouseTarget.appendChild(element); };
  overlay.draw = () => {
    const position = overlay.getProjection().fromLatLngToDivPixel(new google.maps.LatLng(point));
    if (position) { element.style.left = `${position.x}px`; element.style.top = `${position.y}px`; }
  };
  overlay.onRemove = () => element.remove();
  overlay.setMap(map);
  return () => overlay.setMap(null);
}

export function selectMapPoint(event: { latLng: { lat(): number; lng(): number } | null; stop?: () => void }, select: (point: Coordinates) => void) {
  event.stop?.(); // Data-layer clicks must not propagate to the base map.
  if (event.latLng) select({ lat: event.latLng.lat(), lng: event.latLng.lng() });
}
