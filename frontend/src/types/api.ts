export type FuelType = "PB95" | "PB98" | "ON" | "LPG";
export type ReportSource = "manual" | "photo";

export interface InitialPriceEntry {
  fuelType: FuelType;
  price: number;
  source: ReportSource;
}

export type PriceStatus =
  | "verified"
  | "unconfirmed"
  | "suspicious"
  | "expired"
  | "unknown";

export interface Benefit {
  id: number;
  owner_id?: number | null;
  is_own?: boolean;
  brand: string;
  app_name: string;
  fuel_type: FuelType | null;
  discount_per_liter: number;
  max_liters: number | null;
  active_weekdays: number[] | null;
  start_hour: number | null;
  end_hour: number | null;
  valid_from: string;
  valid_to: string;
  checked_at: string;
  description: string;
}

export interface FuelPriceSummary {
  fuel_type: FuelType;
  price: number | null;
  status: PriceStatus;
  support: number;
  confirmations_count: number;
  rejections_count: number;
  reported_at: string | null;
  age_hours: number | null;
  winning_report_id: number | null;
  needs_warning: boolean;
}

export interface Station {
  id: number;
  name: string;
  brand: string;
  address: string;
  district: string;
  latitude: number;
  longitude: number;
  created_at: string;
  prices: Record<FuelType, FuelPriceSummary>;
  active_benefits: Benefit[];
}

export interface StationPayload {
  name: string;
  brand: string;
  address: string;
  district: string;
  latitude: number;
  longitude: number;
}

export interface BenefitPayload {
  brand: string;
  app_name: string;
  fuel_type: FuelType | null;
  discount_per_liter: number;
  max_liters: number | null;
  active_weekdays: number[] | null;
  start_hour: number | null;
  end_hour: number | null;
  valid_from: string;
  valid_to: string;
  description: string;
}

export interface PriceExtractionResponse {
  mode: string;
  prices: Record<FuelType, number | null>;
  confidence_note: string;
}

export interface PriceReport {
  id: number;
  station_id: number;
  fuel_type: FuelType;
  price: number;
  user_id: string;
  source: ReportSource;
  reported_at: string;
  confirmations_count: number;
  rejections_count: number;
}

export interface PriceVote {
  id: number;
  report_id: number;
  user_id: string;
  vote_type: "confirm" | "reject";
  created_at: string;
}

export interface CorrectionResult {
  rejected_report_id: number;
  vote: PriceVote;
  new_report: PriceReport;
}

export interface DealItem {
  station: Station;
  fuel_type: FuelType;
  pump_price: number;
  effective_price_per_liter: number;
  applied_benefit: Benefit | null;
  total_discount: number;
  distance_km: number;
  extra_km: number;
  detour_cost: number;
  savings: number;
  net_gain: number;
  min_liters: number | null;
  is_profitable: boolean;
  is_reference_station: boolean;
  price_status: PriceStatus;
  price_age_hours: number | null;
  needs_warning: boolean;
  warning_message: string | null;
}

export interface DealsResponse {
  fuel_type: FuelType;
  liters: number;
  consumption_per_100km: number;
  reference_station_id: number | null;
  reference_station_name: string | null;
  reference_price: number | null;
  deals: DealItem[];
}

export interface GdanskDistrict {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
}

export interface UserProfile {
  districtId: string;
  fuelType: FuelType;
  liters: number;
  consumptionPer100km: number;
  apps: string[];
}

export interface AdminLoginResponse {
  access_token: string;
  token_type: "bearer";
  username: string;
  expires_at: string;
}

export interface AdminSession {
  username: string;
  is_admin: boolean;
}

export type AuthRole = "user" | "admin";

export interface AuthSession {
  username: string;
  role: AuthRole;
  user_id: number | null;
}

export interface AuthTokenResponse extends AuthSession {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
}
