import type { PriceStatus } from "../types/api";
import { formatAgeHours, getStatusLabel } from "../utils/formatters";

interface PriceStatusBadgeProps {
  status: PriceStatus;
  ageHours: number | null;
  confirmationsCount?: number;
}

export function PriceStatusBadge({
  status,
  ageHours,
  confirmationsCount,
}: PriceStatusBadgeProps) {
  const ageText = formatAgeHours(ageHours);
  const label = getStatusLabel(status);
  const confirmationsLabel =
    confirmationsCount !== undefined && confirmationsCount > 0
      ? ` · ${confirmationsCount} potw.`
      : "";

  return (
    <span className={`status-badge status-${status}`}>
      {label} · {ageText}
      {confirmationsLabel}
    </span>
  );
}
