import { useState } from "react";
import type { DealItem } from "../types/api";
import { formatBenefitConditions, formatPln } from "../utils/formatters";
import { PriceCorrectionForm } from "./PriceCorrectionForm";
import { PriceStatusBadge } from "./PriceStatusBadge";

interface DealCardProps {
  rank: number;
  deal: DealItem;
  onConfirmReport: (reportId: number) => Promise<void>;
  onCorrectReport: (reportId: number, newPrice: number) => Promise<void>;
}

export function DealCard({ rank, deal, onConfirmReport, onCorrectReport }: DealCardProps) {
  const [showCorrection, setShowCorrection] = useState(false);
  const [isVoting, setIsVoting] = useState(false);
  const [voteError, setVoteError] = useState<string | null>(null);

  const fuelSummary = deal.station.prices[deal.fuel_type];
  const reportId = fuelSummary.winning_report_id;

  const handleConfirm = async () => {
    if (reportId === null) return;
    setVoteError(null);
    setIsVoting(true);
    try {
      await onConfirmReport(reportId);
    } catch (err) {
      setVoteError(err instanceof Error ? err.message : "Nie udało się potwierdzić ceny.");
    } finally {
      setIsVoting(false);
    }
  };

  const handleCorrect = async (newPrice: number) => {
    if (reportId === null) return;
    setVoteError(null);
    setIsVoting(true);
    try {
      await onCorrectReport(reportId, newPrice);
      setShowCorrection(false);
    } catch (err) {
      setVoteError(err instanceof Error ? err.message : "Nie udało się zapisać korekty.");
    } finally {
      setIsVoting(false);
    }
  };

  return (
    <article className={`card deal-card ${deal.is_profitable ? "deal-profitable" : ""}`}>
      <div className="deal-header">
        <div>
          <span className="rank-pill">#{rank}</span>
          {deal.is_reference_station && <span className="ref-pill">Najbliższa stacja</span>}
          <h3>{deal.station.name}</h3>
          <p className="station-meta">
            {deal.station.district} · {deal.station.address} · ok. {deal.distance_km.toFixed(1)} km
            {deal.extra_km > 0 ? ` (+${deal.extra_km.toFixed(1)} km objazdu)` : " (brak objazdu)"}
          </p>
        </div>

        <div className="net-gain-box">
          <span className="net-gain-label">
            {deal.is_reference_station
              ? "Punkt odniesienia"
              : deal.net_gain >= 0
                ? "Zysk netto"
                : "Bilans objazdu"}
          </span>
          <strong className={deal.net_gain > 0 ? "gain-positive" : "gain-neutral"}>
            {deal.net_gain > 0 ? `+${formatPln(deal.net_gain)}` : formatPln(deal.net_gain)}
          </strong>
        </div>
      </div>

      <div className="deal-prices-row">
        <div className="price-column">
          <span className="price-label">Cena ze słupka</span>
          <strong className="price-value">{formatPln(deal.pump_price)}/l</strong>
        </div>

        <div className="price-column">
          <span className="price-label">
            {deal.applied_benefit ? `Z aplikacją ${deal.applied_benefit.app_name}` : "Twoja cena efektywna"}
          </span>
          <strong className="price-value price-effective">
            {formatPln(deal.effective_price_per_liter)}/l
          </strong>
        </div>

        <div className="price-column">
          <span className="price-label">Opłacalność</span>
          <span className="calc-breakdown">
            Oszczędność: {formatPln(deal.savings)} · Koszt objazdu: {formatPln(deal.detour_cost)}
          </span>
          <span className="calc-breakdown">
            {deal.is_reference_station
              ? "Najbliższa stacja — brak dodatkowego objazdu"
              : deal.min_liters === null
                ? "Drożej niż na najbliższej stacji — objazd nieopłacalny"
                : deal.min_liters === 0
                  ? "Opłaca się od pierwszego litra"
                  : deal.is_profitable
                    ? `Opłaca się od ${deal.min_liters.toFixed(1)} l`
                    : `Opłaca się dopiero od ${deal.min_liters.toFixed(1)} l`}
          </span>
        </div>
      </div>

      {deal.applied_benefit && (
        <p className="benefit-line">
          Rabat aktywny: <strong>{deal.applied_benefit.app_name}</strong> (
          {formatBenefitConditions(deal.applied_benefit)}) — oszczędzasz dodatkowo{" "}
          {formatPln(deal.total_discount)}
        </p>
      )}

      {!deal.applied_benefit && deal.station.active_benefits.length > 0 && (
        <p className="benefit-hint">
          Dostępny rabat z aplikacją sieci: {deal.station.active_benefits[0].app_name} (
          {formatBenefitConditions(deal.station.active_benefits[0])})
        </p>
      )}

      <div className="deal-footer">
        <PriceStatusBadge
          status={deal.price_status}
          ageHours={deal.price_age_hours}
          confirmationsCount={fuelSummary.confirmations_count}
        />

        {reportId !== null && (
          <div className="vote-actions">
            <button
              type="button"
              className="btn-vote btn-confirm"
              title="Potwierdź cenę"
              onClick={handleConfirm}
              disabled={isVoting}
            >
              ✓ Potwierdź
            </button>
            <button
              type="button"
              className="btn-vote btn-reject"
              title="Odrzuć i podaj poprawną cenę"
              onClick={() => setShowCorrection((prev) => !prev)}
              disabled={isVoting}
            >
              ✕ Zła cena
            </button>
          </div>
        )}
      </div>

      {deal.needs_warning && deal.warning_message && (
        <p className="warning-banner">⚠ {deal.warning_message}</p>
      )}

      {voteError && <p className="field-error">{voteError}</p>}

      {showCorrection && (
        <PriceCorrectionForm
          currentPrice={deal.pump_price}
          isSubmitting={isVoting}
          onSubmit={handleCorrect}
          onCancel={() => setShowCorrection(false)}
        />
      )}
    </article>
  );
}
