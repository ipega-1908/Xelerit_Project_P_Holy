import { useState } from "react";
import { FUEL_OPTIONS } from "../constants/gdanskDistricts";
import type { Benefit, BenefitPayload, FuelType } from "../types/api";

interface BenefitFormProps {
  initialBenefit?: Benefit;
  onSave: (payload: BenefitPayload) => Promise<void>;
  onCancel: () => void;
}

const WEEKDAYS: { day: number; label: string }[] = [
  { day: 0, label: "pn" },
  { day: 1, label: "wt" },
  { day: 2, label: "śr" },
  { day: 3, label: "czw" },
  { day: 4, label: "pt" },
  { day: 5, label: "sb" },
  { day: 6, label: "nd" },
];

function toDateInputValue(iso: string | undefined, fallbackDaysOffset: number): string {
  if (iso) {
    return iso.slice(0, 10);
  }
  const d = new Date(Date.now() + fallbackDaysOffset * 86400_000);
  return d.toISOString().slice(0, 10);
}

export function BenefitForm({ initialBenefit, onSave, onCancel }: BenefitFormProps) {
  const isEditMode = initialBenefit !== undefined;

  const [brand, setBrand] = useState(initialBenefit?.brand ?? "Orlen");
  const [appName, setAppName] = useState(initialBenefit?.app_name ?? "Orlen Vitay");
  const [fuelType, setFuelType] = useState<string>(initialBenefit?.fuel_type ?? "ALL");
  const [discount, setDiscount] = useState(
    initialBenefit ? initialBenefit.discount_per_liter.toFixed(2) : "0.30",
  );
  const [maxLiters, setMaxLiters] = useState(
    initialBenefit && initialBenefit.max_liters !== null ? String(initialBenefit.max_liters) : "50",
  );
  const [weekdays, setWeekdays] = useState<number[]>(initialBenefit?.active_weekdays ?? []);
  const [startHour, setStartHour] = useState(
    initialBenefit && initialBenefit.start_hour !== null ? String(initialBenefit.start_hour) : "",
  );
  const [endHour, setEndHour] = useState(
    initialBenefit && initialBenefit.end_hour !== null ? String(initialBenefit.end_hour) : "",
  );
  const [validFrom, setValidFrom] = useState(toDateInputValue(initialBenefit?.valid_from, -1));
  const [validTo, setValidTo] = useState(toDateInputValue(initialBenefit?.valid_to, 90));
  const [description, setDescription] = useState(initialBenefit?.description ?? "");

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleDay = (day: number) => {
    setWeekdays((prev) => (prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day]));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const parsedDiscount = Number.parseFloat(discount.replace(",", "."));
    if (Number.isNaN(parsedDiscount) || parsedDiscount <= 0 || parsedDiscount > 5.0) {
      setError("Rabat musi być większy od 0 i nie przekraczać 5,00 zł/l.");
      return;
    }

    const parsedMaxLiters = maxLiters.trim()
      ? Number.parseFloat(maxLiters.replace(",", "."))
      : null;
    if (parsedMaxLiters !== null && (Number.isNaN(parsedMaxLiters) || parsedMaxLiters <= 0)) {
      setError("Limit litrów musi być liczbą dodatnią lub pozostać pusty.");
      return;
    }

    const parsedStart = startHour.trim() ? Number.parseInt(startHour, 10) : null;
    const parsedEnd = endHour.trim() ? Number.parseInt(endHour, 10) : null;
    if (validTo < validFrom) {
      setError("Data końca ważności musi być późniejsza lub równa dacie początku.");
      return;
    }

    setError(null);
    setIsSubmitting(true);
    try {
      await onSave({
        brand: brand.trim(),
        app_name: appName.trim(),
        fuel_type: fuelType === "ALL" ? null : (fuelType as FuelType),
        discount_per_liter: Math.round(parsedDiscount * 100) / 100,
        max_liters: parsedMaxLiters,
        active_weekdays: weekdays.length > 0 ? [...weekdays].sort((a, b) => a - b) : null,
        start_hour: parsedStart,
        end_hour: parsedEnd,
        valid_from: `${validFrom}T00:00:00Z`,
        valid_to: `${validTo}T23:59:59Z`,
        description: description.trim(),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się zapisać rabatu.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form className="card entity-form" onSubmit={handleSubmit}>
      <h3>{isEditMode ? `Edytuj rabat: ${initialBenefit.app_name}` : "Dodaj nowy rabat sieci"}</h3>
      <div className="form-grid">
        <label className="form-field">
          <span>Sieć stacji</span>
          <input
            type="text"
            value={brand}
            onChange={(e) => setBrand(e.target.value)}
            placeholder="np. Orlen"
            required
          />
        </label>

        <label className="form-field">
          <span>Nazwa aplikacji</span>
          <input
            type="text"
            value={appName}
            onChange={(e) => setAppName(e.target.value)}
            placeholder="np. Orlen Vitay"
            required
          />
        </label>

        <label className="form-field">
          <span>Paliwo</span>
          <select value={fuelType} onChange={(e) => setFuelType(e.target.value)}>
            <option value="ALL">Wszystkie paliwa</option>
            {FUEL_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.value}
              </option>
            ))}
          </select>
        </label>

        <label className="form-field">
          <span>Rabat (zł/l)</span>
          <input
            type="number"
            step="0.01"
            min="0.01"
            max="5.00"
            value={discount}
            onChange={(e) => setDiscount(e.target.value)}
            required
          />
        </label>

        <label className="form-field">
          <span>Limit litrów (puste = bez limitu)</span>
          <input
            type="number"
            step="1"
            min="1"
            max="500"
            value={maxLiters}
            onChange={(e) => setMaxLiters(e.target.value)}
          />
        </label>

        <label className="form-field">
          <span>Opis warunków</span>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="np. Rabat weekendowy z aplikacją"
          />
        </label>

        <label className="form-field">
          <span>Godzina od (0–23, opcjonalnie)</span>
          <input
            type="number"
            min="0"
            max="23"
            value={startHour}
            onChange={(e) => setStartHour(e.target.value)}
          />
        </label>

        <label className="form-field">
          <span>Godzina do (0–24, opcjonalnie)</span>
          <input
            type="number"
            min="0"
            max="24"
            value={endHour}
            onChange={(e) => setEndHour(e.target.value)}
          />
        </label>

        <label className="form-field">
          <span>Ważny od</span>
          <input
            type="date"
            value={validFrom}
            onChange={(e) => setValidFrom(e.target.value)}
            required
          />
        </label>

        <label className="form-field">
          <span>Ważny do</span>
          <input
            type="date"
            value={validTo}
            onChange={(e) => setValidTo(e.target.value)}
            required
          />
        </label>
      </div>

      <div className="apps-selector">
        <span className="apps-label">
          Dni obowiązywania w strefie Europe/Warsaw (brak zaznaczeń = codziennie):
        </span>
        <div className="apps-chips">
          {WEEKDAYS.map((w) => {
            const active = weekdays.includes(w.day);
            return (
              <label key={w.day} className={`app-chip ${active ? "app-chip-active" : ""}`}>
                <input type="checkbox" checked={active} onChange={() => toggleDay(w.day)} />
                <span>{w.label}</span>
              </label>
            );
          })}
        </div>
      </div>

      {error && <p className="field-error">{error}</p>}

      <div className="form-actions">
        <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
          {isSubmitting ? "Zapisywanie..." : isEditMode ? "Zapisz zmiany" : "Dodaj rabat"}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={isSubmitting}>
          Anuluj
        </button>
      </div>
    </form>
  );
}
