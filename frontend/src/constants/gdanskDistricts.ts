import type { FuelType, GdanskDistrict } from "../types/api";

export const GDANSK_DISTRICTS: GdanskDistrict[] = [
  { id: "srodmiescie", name: "Śródmieście (Centrum)", latitude: 54.352, longitude: 18.6466 },
  { id: "wrzeszcz", name: "Wrzeszcz", latitude: 54.3806, longitude: 18.6122 },
  { id: "oliwa", name: "Oliwa", latitude: 54.4071, longitude: 18.5675 },
  { id: "przymorze", name: "Przymorze", latitude: 54.4055, longitude: 18.5964 },
  { id: "zaspa", name: "Zaspa", latitude: 54.3935, longitude: 18.6041 },
  { id: "morena", name: "Piecki-Migowo (Morena)", latitude: 54.3556, longitude: 18.5875 },
  { id: "chelm", name: "Chełm", latitude: 54.3347, longitude: 18.6143 },
  { id: "jasien", name: "Jasień", latitude: 54.3418, longitude: 18.5542 },
  { id: "osowa", name: "Osowa", latitude: 54.4268, longitude: 18.4832 },
  { id: "orunia", name: "Orunia", latitude: 54.321, longitude: 18.6365 },
  { id: "matarnia", name: "Matarnia / Szadółki", latitude: 54.3489, longitude: 18.5321 },
  { id: "stogi", name: "Stogi", latitude: 54.3654, longitude: 18.7042 },
];

export const FUEL_OPTIONS: { value: FuelType; label: string }[] = [
  { value: "PB95", label: "Benzyna 95 (PB95)" },
  { value: "PB98", label: "Benzyna 98 (PB98)" },
  { value: "ON", label: "Olej napędowy (ON)" },
  { value: "LPG", label: "Autogaz (LPG)" },
];

export const LOYALTY_APPS: { name: string; brand: string }[] = [
  { name: "Orlen Vitay", brand: "Orlen" },
  { name: "BPme", brand: "BP" },
  { name: "Circle K EXTRA", brand: "Circle K" },
  { name: "Shell ClubSmart", brand: "Shell" },
  { name: "Super MOYA", brand: "Moya" },
];
