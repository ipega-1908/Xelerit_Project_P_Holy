import type { DealsResponse } from "../types/api";
import { formatPln } from "../utils/formatters";
import { DealCard } from "./DealCard";

interface DealsRankingListProps {
  data: DealsResponse | null;
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
  onConfirmReport: (reportId: number) => Promise<void>;
  onCorrectReport: (reportId: number, newPrice: number) => Promise<void>;
}

export function DealsRankingList({
  data,
  isLoading,
  error,
  onRetry,
  onConfirmReport,
  onCorrectReport,
}: DealsRankingListProps) {
  if (isLoading && !data) {
    return <div className="state-box">Obliczam opłacalność objazdów dla Gdańska...</div>;
  }

  if (error) {
    return (
      <div className="state-box state-error">
        <p>Nie udało się pobrać rankingu: {error}</p>
        <button type="button" className="btn btn-secondary btn-sm" onClick={onRetry}>
          Spróbuj ponownie
        </button>
      </div>
    );
  }

  if (!data || data.deals.length === 0) {
    return (
      <div className="state-box">
        Brak stacji z ceną wybranego paliwa. Dodaj pierwszą cenę w zakładce „Lista stacji”.
      </div>
    );
  }

  const refDeal = data.deals.find((deal) => deal.is_reference_station);
  const bestProfitable = data.deals.find((deal) => deal.is_profitable);
  const nearestBreakEven = data.deals.find(
    (deal) => !deal.is_reference_station && deal.min_liters !== null,
  );
  const isOutsideCoverage = refDeal !== undefined && refDeal.distance_km > 5.0;

  return (
    <section className="deals-section">
      {data.reference_station_name && data.reference_price !== null && (
        <div className="reference-banner">
          <div>
            Porównujemy z najbliższą stacją:{" "}
            <strong>{data.reference_station_name}</strong>
            {refDeal ? ` (ok. ${refDeal.distance_km.toFixed(1)} km stąd)` : ""}, cena bazowa:{" "}
            <strong>{formatPln(data.reference_price)}/l</strong>.
            {isLoading && <span className="updating-pill">Przeliczam...</span>}
          </div>

          {bestProfitable ? (
            <div className="verdict-line verdict-positive">
              Najlepszy objazd: <strong>{bestProfitable.station.name}</strong> — zysk netto{" "}
              <strong>+{formatPln(bestProfitable.net_gain)}</strong>.
            </div>
          ) : (
            <div className="verdict-line verdict-neutral">
              Przy {data.liters} l żaden objazd nie daje zysku netto — najkorzystniej zatankować na
              najbliższej stacji ({data.reference_station_name}).
              {nearestBreakEven && nearestBreakEven.min_liters !== null
                ? ` Najbliżej opłacalności: ${nearestBreakEven.station.name} (od ${nearestBreakEven.min_liters.toFixed(1)} l).`
                : ""}
            </div>
          )}

          {isOutsideCoverage && refDeal && (
            <div className="verdict-hint">
              Punkt startu jest oddalony o ok. {refDeal.distance_km.toFixed(1)} km od najbliższej
              stacji z bazy (w bazie są tylko stacje z Gdańska).
            </div>
          )}
        </div>
      )}

      <div className="deals-list">
        {data.deals.map((deal, index) => (
          <DealCard
            key={deal.station.id}
            rank={index + 1}
            deal={deal}
            onConfirmReport={onConfirmReport}
            onCorrectReport={onCorrectReport}
          />
        ))}
      </div>
    </section>
  );
}
