import { FUEL_OPTIONS, GDANSK_DISTRICTS, LOYALTY_APPS } from "../constants/gdanskDistricts";
import type { FuelType, UserProfile } from "../types/api";

interface CalculatorPanelProps {
  profile: UserProfile;
  availableAppNames: string[];
  customPointCoords: { lat: number; lon: number } | null;
  onSelectDistrict: (districtId: string) => void;
  onUpdateProfile: (patch: Partial<UserProfile>) => void;
  onToggleApp: (appName: string) => void;
}

export function CalculatorPanel({
  profile,
  availableAppNames,
  customPointCoords,
  onSelectDistrict,
  onUpdateProfile,
  onToggleApp,
}: CalculatorPanelProps) {
  const appOptions =
    availableAppNames.length > 0 ? availableAppNames : LOYALTY_APPS.map((app) => app.name);
  return (
    <section className="card calculator-panel" aria-label="Parametry przejazdu i tankowania">
      <h2>Parametry tankowania i punkt startu</h2>
      <div className="form-grid">
        <label className="form-field">
          <span>
            Punkt startu (Gdańsk)
            {customPointCoords
              ? ` · mapa (${customPointCoords.lat.toFixed(3)}, ${customPointCoords.lon.toFixed(3)})`
              : ""}
          </span>
          <select
            value={profile.districtId}
            onChange={(e) => onSelectDistrict(e.target.value)}
          >
            {GDANSK_DISTRICTS.map((district) => (
              <option key={district.id} value={district.id}>
                {district.name}
              </option>
            ))}
          </select>
        </label>

        <label className="form-field">
          <span>Paliwo</span>
          <select
            value={profile.fuelType}
            onChange={(e) => onUpdateProfile({ fuelType: e.target.value as FuelType })}
          >
            {FUEL_OPTIONS.map((fuel) => (
              <option key={fuel.value} value={fuel.value}>
                {fuel.label}
              </option>
            ))}
          </select>
        </label>

        <label className="form-field">
          <span>Ilość do zatankowania (litry)</span>
          <input
            type="number"
            min="1"
            max="300"
            step="1"
            value={profile.liters}
            onChange={(e) => {
              const val = Number.parseFloat(e.target.value);
              if (!Number.isNaN(val) && val > 0) {
                onUpdateProfile({ liters: val });
              }
            }}
          />
        </label>

        <label className="form-field">
          <span>Spalanie auta (l / 100 km)</span>
          <input
            type="number"
            min="1"
            max="40"
            step="0.1"
            value={profile.consumptionPer100km}
            onChange={(e) => {
              const val = Number.parseFloat(e.target.value);
              if (!Number.isNaN(val) && val > 0) {
                onUpdateProfile({ consumptionPer100km: val });
              }
            }}
          />
        </label>
      </div>

      <div className="apps-selector">
        <span className="apps-label">Twoje aplikacje lojalnościowe:</span>
        <div className="apps-chips">
          {appOptions.map((appName) => {
            const active = profile.apps.includes(appName);
            return (
              <label key={appName} className={`app-chip ${active ? "app-chip-active" : ""}`}>
                <input
                  type="checkbox"
                  checked={active}
                  onChange={() => onToggleApp(appName)}
                />
                <span>{appName}</span>
              </label>
            );
          })}
        </div>
      </div>
    </section>
  );
}
