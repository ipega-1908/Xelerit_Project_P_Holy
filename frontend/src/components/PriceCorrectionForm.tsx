import { useState } from "react";
import { formatPln } from "../utils/formatters";

interface PriceCorrectionFormProps {
  currentPrice: number;
  isSubmitting: boolean;
  onSubmit: (newPrice: number) => Promise<void>;
  onCancel: () => void;
}

export function PriceCorrectionForm({
  currentPrice,
  isSubmitting,
  onSubmit,
  onCancel,
}: PriceCorrectionFormProps) {
  const [priceInput, setPriceInput] = useState<string>(currentPrice.toFixed(2));
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const parsed = Number.parseFloat(priceInput.replace(",", "."));
    if (Number.isNaN(parsed) || parsed < 3.0 || parsed > 15.0) {
      setValidationError("Podaj poprawną cenę od 3,00 do 15,00 zł.");
      return;
    }
    if (Math.round(parsed * 100) === Math.round(currentPrice * 100)) {
      setValidationError("Nowa cena musi różnić się od obecnej (użyj ✓, aby potwierdzić).");
      return;
    }
    setValidationError(null);
    await onSubmit(Math.round(parsed * 100) / 100);
  };

  return (
    <form className="inline-correction-form" onSubmit={handleSubmit}>
      <label className="inline-label">
        Poprawna cena (obecnie {formatPln(currentPrice)}):
        <div className="inline-controls">
          <input
            type="number"
            step="0.01"
            min="3.00"
            max="15.00"
            value={priceInput}
            onChange={(e) => setPriceInput(e.target.value)}
            disabled={isSubmitting}
            required
          />
          <button type="submit" className="btn btn-primary btn-sm" disabled={isSubmitting}>
            {isSubmitting ? "Zapisywanie..." : "Wyślij korektę"}
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={onCancel}
            disabled={isSubmitting}
          >
            Anuluj
          </button>
        </div>
      </label>
      {validationError && <p className="field-error">{validationError}</p>}
    </form>
  );
}
