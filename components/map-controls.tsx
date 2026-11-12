import { sectors } from "@/lib/sectors";
type Props = {
  visible: boolean;
  opacity: number;
  available: boolean;
  onVisible: (value: boolean) => void;
  onOpacity: (value: number) => void;
};
export function MapControls({
  visible,
  opacity,
  available,
  onVisible,
  onOpacity,
}: Props) {
  return (
    <section className="controls card" aria-labelledby="overlay-heading">
      <div className="eyebrow">HISTORICAL LAYERS</div>
      <h2 id="overlay-heading">Allied occupation sectors</h2>
      <p className="muted">Berlin · 1945 reference period</p>
      <label className="toggle-row">
        <span>Show historical overlay</span>
        <input
          type="checkbox"
          checked={visible}
          disabled={!available}
          onChange={(e) => onVisible(e.target.checked)}
        />
      </label>
      <label className="opacity-label" htmlFor="opacity">
        <span>Overlay opacity</span>
        <output>{Math.round(opacity * 100)}%</output>
      </label>
      <input
        id="opacity"
        type="range"
        min="0"
        max="80"
        step="0.5"
        value={Math.round(opacity * 100)}
        disabled={!available || !visible}
        onChange={(e) => onOpacity(Number(e.target.value) / 100)}
      />
      <ul className="map-legend" aria-label="Sector color legend">
        {Object.entries(sectors).map(([id, sector]) => (
          <li className="legend-item" key={id}>
            <span className={`legend-marker zone-${id}`} />
            {sector.name}
          </li>
        ))}
      </ul>
      <p className="hint">
        {available
          ? "Click a sector on the map to explore it."
          : "Legend preview · boundaries not yet available"}
      </p>
    </section>
  );
}
