import type { FeatureCollection, MultiPolygon, Polygon } from "geojson";

export const sectors = {
  soviet: { name: "Soviet", colorToken: "--color-soviet" },
  american: { name: "American", colorToken: "--color-american" },
  british: { name: "British", colorToken: "--color-british" },
  french: { name: "French", colorToken: "--color-french" },
} as const;
export type SectorId = keyof typeof sectors;
export type SectorData = FeatureCollection<
  Polygon | MultiPolygon,
  { sector: SectorId }
>;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
function validRing(value: unknown): boolean {
  if (!Array.isArray(value) || value.length < 4) return false;
  if (
    !value.every(
      (p) =>
        Array.isArray(p) &&
        p.length >= 2 &&
        typeof p[0] === "number" &&
        Number.isFinite(p[0]) &&
        Math.abs(p[0]) <= 180 &&
        typeof p[1] === "number" &&
        Number.isFinite(p[1]) &&
        Math.abs(p[1]) <= 90,
    )
  )
    return false;
  return (
    value[0][0] === value[value.length - 1][0] &&
    value[0][1] === value[value.length - 1][1]
  );
}
function validPolygon(value: unknown): boolean {
  return Array.isArray(value) && value.length > 0 && value.every(validRing);
}
export function parseSectors(value: unknown): SectorData {
  if (
    !isRecord(value) ||
    value.type !== "FeatureCollection" ||
    !Array.isArray(value.features)
  ) {
    throw new Error("Expected a GeoJSON FeatureCollection.");
  }
  for (const feature of value.features) {
    if (
      !isRecord(feature) ||
      feature.type !== "Feature" ||
      !isRecord(feature.properties) ||
      typeof feature.properties.sector !== "string" ||
      !Object.hasOwn(sectors, feature.properties.sector) ||
      !isRecord(feature.geometry)
    )
      throw new Error("Invalid sector feature.");
    const { type, coordinates } = feature.geometry;
    if (
      !(type === "Polygon"
        ? validPolygon(coordinates)
        : type === "MultiPolygon" &&
          Array.isArray(coordinates) &&
          coordinates.length > 0 &&
          coordinates.every(validPolygon))
    ) {
      throw new Error("Invalid sector polygon coordinates.");
    }
  }
  if (
    value.features.length > 0 &&
    new Set(value.features.map((f) => f.properties.sector)).size !== 4
  ) {
    throw new Error("The dataset must contain all four sectors.");
  }
  return value as unknown as SectorData;
}
export async function loadSectors(signal: AbortSignal): Promise<SectorData> {
  const response = await fetch("/api/v1/sectors", {
    signal,
    cache: "no-store",
  });
  if (!response.ok) throw new Error("Historical dataset could not be loaded.");
  return parseSectors(await response.json());
}
