// Shared rectangular Berlin search area, not an exact administrative boundary.
export const BERLIN_BOUNDS = {
  north: 52.68,
  south: 52.33,
  west: 13.08,
  east: 13.77,
} as const;

export function isWithinBerlin(point: { lat: number; lng: number }) {
  return point.lat >= BERLIN_BOUNDS.south && point.lat <= BERLIN_BOUNDS.north &&
    point.lng >= BERLIN_BOUNDS.west && point.lng <= BERLIN_BOUNDS.east;
}
