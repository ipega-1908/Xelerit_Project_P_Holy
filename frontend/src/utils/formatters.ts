import type { Benefit, PriceStatus } from "../types/api";

const WEEKDAY_NAMES_SHORT = ["pn", "wt", "śr", "czw", "pt", "sb", "nd"];

export function formatPln(amount: number): string {
  return `${amount.toFixed(2).replace(".", ",")} zł`;
}

export function formatAgeHours(ageHours: number | null): string {
  if (ageHours === null) {
    return "brak danych";
  }
  if (ageHours < 1) {
    const mins = Math.max(1, Math.round(ageHours * 60));
    return `${mins} min temu`;
  }
  if (ageHours < 24) {
    return `${Math.round(ageHours)} godz. temu`;
  }
  const days = Math.round(ageHours / 24);
  return days === 1 ? "1 dzień temu" : `${days} dni temu`;
}

export function getStatusLabel(status: PriceStatus): string {
  switch (status) {
    case "verified":
      return "Zweryfikowana";
    case "unconfirmed":
      return "Niepotwierdzona";
    case "suspicious":
      return "Podejrzana";
    case "expired":
      return "Przestarzała (>3 dni)";
    case "unknown":
      return "Brak ceny";
  }
}

export function formatBenefitConditions(benefit: Benefit): string {
  const parts: string[] = [`-${formatPln(benefit.discount_per_liter)}/l`];

  if (benefit.max_liters !== null) {
    parts.push(`limit ${benefit.max_liters} l`);
  }
  if (benefit.active_weekdays && benefit.active_weekdays.length > 0) {
    const days = benefit.active_weekdays.map((d) => WEEKDAY_NAMES_SHORT[d] ?? String(d)).join(", ");
    parts.push(`dni: ${days}`);
  }
  if (benefit.start_hour !== null && benefit.end_hour !== null) {
    parts.push(`godz. ${benefit.start_hour}:00–${benefit.end_hour}:00`);
  }

  return parts.join(" · ");
}
