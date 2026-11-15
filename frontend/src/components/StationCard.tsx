import { useState } from "react";
import { FUEL_OPTIONS } from "../constants/gdanskDistricts";
import type { FuelType, InitialPriceEntry, Station, StationPayload } from "../types/api";
import { formatBenefitConditions, formatPln } from "../utils/formatters";
import { NewPriceReportForm } from "./NewPriceReportForm";
import { PriceCorrectionForm } from "./PriceCorrectionForm";
import { PriceStatusBadge } from "./PriceStatusBadge";
import { StationForm } from "./StationForm";

interface StationCardProps {
  station: Station;
  userApps: string[];
  isAdmin: boolean;
  onConfirmReport: (reportId: number) => Promise<void>;
  onCorrectReport: (reportId: number, newPrice: number) => Promise<void>;
  onCreateReports: (stationId: number, entries: InitialPriceEntry[]) => Promise<void>;
  onUpdateStation: (stationId: number, payload: StationPayload) => Promise<void>;
  onDeleteStation: (stationId: number) => Promise<void>;
}

export function StationCard({
  station,
  userApps,
  isAdmin,
  onConfirmReport,
  onCorrectReport,
  onCreateReports,
  onUpdateStation,
  onDeleteStation,
}: StationCardProps) {
  const [correctingFuel, setCorrectingFuel] = useState<FuelType | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [isBusy, setIsBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  if (isAdmin && isEditing) {
    return (
      <StationForm
        initialStation={station}
        onSave={async (payload) => {
          await onUpdateStation(station.id, payload);
          setIsEditing(false);
        }}
        onCancel={() => setIsEditing(false)}
      />
    );
  }

  const handleConfirm = async (reportId: number) => {
    setActionError(null);
    setIsBusy(true);
    try {
      await onConfirmReport(reportId);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Nie udało się potwierdzić ceny.");
    } finally {
      setIsBusy(false);
    }
  };

  const handleCorrect = async (reportId: number, newPrice: number) => {
    setActionError(null);
    setIsBusy(true);
    try {
      await onCorrectReport(reportId, newPrice);
      setCorrectingFuel(null);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Nie udało się zapisać korekty.");
    } finally {
      setIsBusy(false);
    }
  };

  const handleDelete = async () => {
    setActionError(null);
    setIsBusy(true);
    try {
      await onDeleteStation(station.id);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Nie udało się usunąć stacji.");
      setIsBusy(false);
    }
  };

  return (
    <article className="card station-card">
      <div className="station-card-header">
        <div>
          <h3>{station.name}</h3>
          <p className="station-meta">
            Sieć: <strong>{station.brand}</strong> · {station.district} · {station.address}
          </p>
        </div>

        {isAdmin && (
          <div className="entity-actions">
            <button
              type="button"
              className="btn btn-secondary btn-xs"
              onClick={() => setIsEditing(true)}
              disabled={isBusy}
            >
              Edytuj
            </button>
            {!confirmDelete ? (
              <button
                type="button"
                className="btn-vote btn-reject btn-xs"
                onClick={() => setConfirmDelete(true)}
                disabled={isBusy}
              >
                Usuń
              </button>
            ) : (
              <div className="confirm-delete-row">
                <button
                  type="button"
                  className="btn-vote btn-reject btn-xs"
                  onClick={handleDelete}
                  disabled={isBusy}
                >
                  Potwierdź
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-xs"
                  onClick={() => setConfirmDelete(false)}
                  disabled={isBusy}
                >
                  Anuluj
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {station.active_benefits.length > 0 && (
        <div className="station-benefits">
          {station.active_benefits.map((benefit) => {
            const hasApp = userApps.includes(benefit.app_name);
            return (
              <span
                key={benefit.id}
                className={`benefit-tag ${hasApp ? "benefit-tag-owned" : ""}`}
              >
                {benefit.app_name}: {formatBenefitConditions(benefit)}
                {hasApp ? " (masz)" : ""}
              </span>
            );
          })}
        </div>
      )}

      <div className="fuel-rows">
        {FUEL_OPTIONS.map((opt) => {
          const summary = station.prices[opt.value];
          const applicableBenefit = station.active_benefits.find(
            (b) =>
              userApps.includes(b.app_name) && (b.fuel_type === null || b.fuel_type === opt.value),
          );
          const discountedPrice =
            summary.price !== null && applicableBenefit
              ? Math.max(0, summary.price - applicableBenefit.discount_per_liter)
              : null;

          return (
            <div key={opt.value} className="fuel-row">
              <div className="fuel-row-main">
                <span className="fuel-code">{opt.value}</span>
                <div className="fuel-prices">
                  <strong>
                    {summary.price !== null ? `${formatPln(summary.price)}/l` : "Brak ceny"}
                  </strong>
                  {discountedPrice !== null && (
                    <span className="app-price-inline">
                      z apką: {formatPln(discountedPrice)}/l
                    </span>
                  )}
                </div>
                <PriceStatusBadge
                  status={summary.status}
                  ageHours={summary.age_hours}
                  confirmationsCount={summary.confirmations_count}
                />
                {summary.winning_report_id !== null && (
                  <div className="vote-actions">
                    <button
                      type="button"
                      className="btn-vote btn-confirm"
                      onClick={() => handleConfirm(summary.winning_report_id as number)}
                      disabled={isBusy}
                    >
                      ✓
                    </button>
                    <button
                      type="button"
                      className="btn-vote btn-reject"
                      onClick={() =>
                        setCorrectingFuel((prev) => (prev === opt.value ? null : opt.value))
                      }
                      disabled={isBusy}
                    >
                      ✕
                    </button>
                  </div>
                )}
              </div>

              {correctingFuel === opt.value &&
                summary.price !== null &&
                summary.winning_report_id !== null && (
                  <PriceCorrectionForm
                    currentPrice={summary.price}
                    isSubmitting={isBusy}
                    onSubmit={(newPrice) =>
                      handleCorrect(summary.winning_report_id as number, newPrice)
                    }
                    onCancel={() => setCorrectingFuel(null)}
                  />
                )}
            </div>
          );
        })}
      </div>

      {actionError && <p className="field-error">{actionError}</p>}

      <div className="station-add-price">
        <span className="add-price-title">Dodaj nowe zgłoszenie ceny:</span>
        <NewPriceReportForm stationId={station.id} onSubmitted={onCreateReports} />
      </div>
    </article>
  );
}
