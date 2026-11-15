import { useRef, useState } from "react";
import { apiClient } from "../api/client";
import { FUEL_OPTIONS } from "../constants/gdanskDistricts";
import type { FuelType, InitialPriceEntry, ReportSource } from "../types/api";
import { readImageFileAsBase64 } from "../utils/imageUpload";

interface NewPriceReportFormProps {
  stationId: number;
  defaultFuel?: FuelType;
  onSubmitted: (stationId: number, entries: InitialPriceEntry[]) => Promise<void>;
}

type DraftPrices = Record<FuelType, string>;

const EMPTY_DRAFT: DraftPrices = {
  PB95: "",
  PB98: "",
  ON: "",
  LPG: "",
};

export function NewPriceReportForm({
  stationId,
  defaultFuel = "PB95",
  onSubmitted,
}: NewPriceReportFormProps) {
  const [fuelType, setFuelType] = useState<FuelType>(defaultFuel);
  const [priceInput, setPriceInput] = useState<string>("");
  const [photoDraft, setPhotoDraft] = useState<DraftPrices | null>(null);
  const [photoSource, setPhotoSource] = useState<ReportSource>("manual");
  const [aiNote, setAiNote] = useState<string | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handlePhotoUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setError(null);
    setAiNote(null);
    setIsExtracting(true);
    try {
      const encoded = await readImageFileAsBase64(file);
      const res = await apiClient.extractPricesFromImage(
        encoded.base64,
        encoded.mimeType,
        encoded.filename,
      );
      setPhotoDraft({
        PB95: res.prices.PB95 !== null ? res.prices.PB95.toFixed(2) : "",
        PB98: res.prices.PB98 !== null ? res.prices.PB98.toFixed(2) : "",
        ON: res.prices.ON !== null ? res.prices.ON.toFixed(2) : "",
        LPG: res.prices.LPG !== null ? res.prices.LPG.toFixed(2) : "",
      });
      setPhotoSource(res.mode === "gemini" ? "photo" : "manual");
      setAiNote(res.confidence_note);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się odczytać zdjęcia.");
    } finally {
      setIsExtracting(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleManualSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const parsed = Number.parseFloat(priceInput.replace(",", "."));
    if (Number.isNaN(parsed) || parsed < 3.0 || parsed > 15.0) {
      setError("Cena musi mieścić się w zakresie od 3,00 do 15,00 zł.");
      return;
    }

    setError(null);
    setIsSubmitting(true);
    try {
      await onSubmitted(stationId, [
        {
          fuelType,
          price: Math.round(parsed * 100) / 100,
          source: "manual",
        },
      ]);
      setPriceInput("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się zapisać zgłoszenia.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSavePhotoBatch = async () => {
    if (!photoDraft) return;

    const entries: InitialPriceEntry[] = [];
    for (const opt of FUEL_OPTIONS) {
      const raw = photoDraft[opt.value].trim();
      if (!raw) continue;
      const parsed = Number.parseFloat(raw.replace(",", "."));
      if (Number.isNaN(parsed) || parsed < 3.0 || parsed > 15.0) {
        setError(`Cena ${opt.value} musi mieścić się w zakresie od 3,00 do 15,00 zł.`);
        return;
      }
      entries.push({
        fuelType: opt.value,
        price: Math.round(parsed * 100) / 100,
        source: photoSource,
      });
    }

    if (entries.length === 0) {
      setError("Wpisz lub pozostaw co najmniej jedną cenę ze zdjęcia.");
      return;
    }

    setError(null);
    setIsSubmitting(true);
    try {
      await onSubmitted(stationId, entries);
      setPhotoDraft(null);
      setAiNote(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się zapisać cen ze zdjęcia.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div>
      <form className="new-report-form" onSubmit={handleManualSubmit}>
        <select
          aria-label="Rodzaj paliwa"
          value={fuelType}
          onChange={(e) => setFuelType(e.target.value as FuelType)}
          disabled={isSubmitting || isExtracting}
        >
          {FUEL_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.value}
            </option>
          ))}
        </select>
        <input
          type="number"
          step="0.01"
          min="3.00"
          max="15.00"
          placeholder="np. 6,39"
          aria-label="Nowa cena paliwa"
          value={priceInput}
          onChange={(e) => setPriceInput(e.target.value)}
          disabled={isSubmitting || isExtracting}
          required
        />
        <button
          type="submit"
          className="btn btn-primary btn-sm"
          disabled={isSubmitting || isExtracting}
        >
          {isSubmitting ? "Dodawanie..." : "Zgłoś cenę"}
        </button>
        <label className="btn btn-secondary btn-sm file-upload-btn">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handlePhotoUpload}
            disabled={isSubmitting || isExtracting}
            hidden
          />
          {isExtracting ? "Analizuję..." : "📷 Ze zdjęcia (AI)"}
        </label>
      </form>

      {aiNote && <p className="ai-note-banner">{aiNote}</p>}

      {photoDraft && (
        <div className="ai-review-panel">
          <p className="ai-review-hint">
            {photoSource === "photo"
              ? "Zaufany odczyt Gemini AI: zapisane ceny od razu zaktualizują stację jako potwierdzone."
              : "Tryb demo AI: zapisane ceny zostaną dodane jako niepotwierdzone."}
          </p>
          <div className="prices-mini-grid">
            {FUEL_OPTIONS.map((opt) => (
              <label key={opt.value} className="form-field">
                <span>{opt.value} (zł/l)</span>
                <input
                  type="number"
                  step="0.01"
                  min="3.00"
                  max="15.00"
                  placeholder="brak na zdjęciu"
                  value={photoDraft[opt.value]}
                  onChange={(e) =>
                    setPhotoDraft((prev) => ({
                      ...(prev ?? EMPTY_DRAFT),
                      [opt.value]: e.target.value,
                    }))
                  }
                  disabled={isSubmitting}
                />
              </label>
            ))}
          </div>
          <div className="ai-review-actions">
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={handleSavePhotoBatch}
              disabled={isSubmitting}
            >
              {isSubmitting ? "Zapisywanie..." : "Zapisz wszystkie ze zdjęcia"}
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => {
                setPhotoDraft(null);
                setAiNote(null);
              }}
              disabled={isSubmitting}
            >
              Anuluj
            </button>
          </div>
        </div>
      )}

      {error && <p className="field-error">{error}</p>}
    </div>
  );
}
