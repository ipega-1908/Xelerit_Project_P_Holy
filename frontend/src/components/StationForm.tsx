import { useRef, useState } from "react";
import { apiClient } from "../api/client";
import { FUEL_OPTIONS, GDANSK_DISTRICTS } from "../constants/gdanskDistricts";
import type {
  FuelType,
  InitialPriceEntry,
  ReportSource,
  Station,
  StationPayload,
} from "../types/api";
import { readImageFileAsBase64 } from "../utils/imageUpload";
import { LocationPickerMap } from "./LocationPickerMap";

interface StationFormProps {
  initialStation?: Station;
  onSave: (payload: StationPayload, initialPrices: InitialPriceEntry[]) => Promise<void>;
  onCancel: () => void;
}

type PriceInputs = Record<FuelType, string>;

const EMPTY_PRICES: PriceInputs = {
  PB95: "",
  PB98: "",
  ON: "",
  LPG: "",
};

export function StationForm({ initialStation, onSave, onCancel }: StationFormProps) {
  const isEditMode = initialStation !== undefined;

  const [name, setName] = useState(initialStation?.name ?? "");
  const [brand, setBrand] = useState(initialStation?.brand ?? "Orlen");
  const [address, setAddress] = useState(initialStation?.address ?? "");
  const [district, setDistrict] = useState(initialStation?.district ?? "Śródmieście");
  const [latitude, setLatitude] = useState(
    initialStation ? initialStation.latitude : 54.352,
  );
  const [longitude, setLongitude] = useState(
    initialStation ? initialStation.longitude : 18.6466,
  );
  const [prices, setPrices] = useState<PriceInputs>(EMPTY_PRICES);
  const [pricesSource, setPricesSource] = useState<ReportSource>("manual");

  const [aiNote, setAiNote] = useState<string | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleDistrictPreset = (districtId: string) => {
    const found = GDANSK_DISTRICTS.find((d) => d.id === districtId);
    if (!found) return;
    setDistrict(found.name.replace(" (Centrum)", ""));
    setLatitude(found.latitude);
    setLongitude(found.longitude);
  };

  const handlePhotoUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setError(null);
    setAiNote(null);
    setIsExtracting(true);
    try {
      const encoded = await readImageFileAsBase64(file);
      const extracted = await apiClient.extractPricesFromImage(
        encoded.base64,
        encoded.mimeType,
        encoded.filename,
      );
      setPrices({
        PB95: extracted.prices.PB95 !== null ? extracted.prices.PB95.toFixed(2) : "",
        PB98: extracted.prices.PB98 !== null ? extracted.prices.PB98.toFixed(2) : "",
        ON: extracted.prices.ON !== null ? extracted.prices.ON.toFixed(2) : "",
        LPG: extracted.prices.LPG !== null ? extracted.prices.LPG.toFixed(2) : "",
      });
      setPricesSource(extracted.mode === "gemini" ? "photo" : "manual");
      setAiNote(extracted.confidence_note);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się odczytać zdjęcia.");
    } finally {
      setIsExtracting(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const parsedPrices: InitialPriceEntry[] = [];
    if (!isEditMode) {
      for (const opt of FUEL_OPTIONS) {
        const raw = prices[opt.value].trim();
        if (!raw) continue;
        const val = Number.parseFloat(raw.replace(",", "."));
        if (Number.isNaN(val) || val < 3.0 || val > 15.0) {
          setError(`Cena ${opt.value} musi mieścić się w zakresie 3,00–15,00 zł.`);
          return;
        }
        parsedPrices.push({
          fuelType: opt.value,
          price: Math.round(val * 100) / 100,
          source: pricesSource,
        });
      }
    }

    setError(null);
    setIsSubmitting(true);
    try {
      await onSave(
        {
          name: name.trim(),
          brand: brand.trim(),
          address: address.trim(),
          district: district.trim(),
          latitude,
          longitude,
        },
        parsedPrices,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się zapisać stacji.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form className="card entity-form" onSubmit={handleSubmit}>
      <div className="entity-form-header">
        <h3>{isEditMode ? `Edytuj stację: ${initialStation.name}` : "Dodaj nową stację paliw"}</h3>
        {!isEditMode && (
          <select
            aria-label="Wypełnij współrzędne z dzielnicy Gdańska"
            defaultValue=""
            onChange={(e) => {
              if (e.target.value) handleDistrictPreset(e.target.value);
            }}
          >
            <option value="">Wypełnij współrzędne z dzielnicy...</option>
            {GDANSK_DISTRICTS.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        )}
      </div>

      <div className="form-grid">
        <label className="form-field">
          <span>Nazwa stacji</span>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="np. Orlen Pruszcz Gdański"
            required
          />
        </label>

        <label className="form-field">
          <span>Sieć (marka)</span>
          <input
            type="text"
            value={brand}
            onChange={(e) => setBrand(e.target.value)}
            placeholder="np. Orlen, BP, Circle K, Shell, Moya"
            required
          />
        </label>

        <label className="form-field">
          <span>Adres</span>
          <input
            type="text"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="np. ul. Grunwaldzka 10"
            required
          />
        </label>

        <label className="form-field">
          <span>Dzielnica / miejscowość</span>
          <input
            type="text"
            value={district}
            onChange={(e) => setDistrict(e.target.value)}
            placeholder="np. Śródmieście"
            required
          />
        </label>

      </div>

      <div className="location-picker-section">
        <div className="location-picker-header">
          <span>Zaznacz lokalizację stacji na mapie</span>
          <span className="muted">
            Wybrano: {latitude.toFixed(5)}, {longitude.toFixed(5)}
          </span>
        </div>
        <LocationPickerMap
          latitude={latitude}
          longitude={longitude}
          onChange={(lat, lon) => {
            setLatitude(lat);
            setLongitude(lon);
          }}
        />
      </div>

      {!isEditMode && (
        <div className="ai-prices-section">
          <div className="ai-prices-header">
            <span>Ceny początkowe na stacji (opcjonalne):</span>
            <label className="btn btn-secondary btn-sm file-upload-btn">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handlePhotoUpload}
                disabled={isExtracting || isSubmitting}
                hidden
              />
              {isExtracting ? "Analizuję zdjęcie..." : "📷 Odczytaj ceny ze zdjęcia (AI)"}
            </label>
          </div>

          {aiNote && <p className="ai-note-banner">{aiNote}</p>}

          <div className="prices-mini-grid">
            {FUEL_OPTIONS.map((opt) => (
              <label key={opt.value} className="form-field">
                <span>{opt.value} (zł/l)</span>
                <input
                  type="number"
                  step="0.01"
                  min="3.00"
                  max="15.00"
                  placeholder="opcjonalnie"
                  value={prices[opt.value]}
                  onChange={(e) =>
                    setPrices((prev) => ({ ...prev, [opt.value]: e.target.value }))
                  }
                />
              </label>
            ))}
          </div>
        </div>
      )}

      {error && <p className="field-error">{error}</p>}

      <div className="form-actions">
        <button type="submit" className="btn btn-primary" disabled={isSubmitting || isExtracting}>
          {isSubmitting ? "Zapisywanie..." : isEditMode ? "Zapisz zmiany" : "Dodaj stację"}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={isSubmitting}>
          Anuluj
        </button>
      </div>
    </form>
  );
}
