import type {
  AdminLoginResponse,
  AdminSession,
  Benefit,
  BenefitPayload,
  CorrectionResult,
  DealsResponse,
  FuelType,
  PriceExtractionResponse,
  PriceReport,
  PriceVote,
  ReportSource,
  Station,
  StationPayload,
} from "../types/api";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const USER_ID_STORAGE_KEY = "fuel_deals_user_id";
const ADMIN_TOKEN_STORAGE_KEY = "fuel_deals_admin_token";

export function getAdminToken(): string | null {
  const token = window.sessionStorage.getItem(ADMIN_TOKEN_STORAGE_KEY);
  return token && token.trim().length > 0 ? token : null;
}

export function setAdminToken(token: string | null): void {
  if (token) {
    window.sessionStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, token);
  } else {
    window.sessionStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY);
  }
}

function adminAuthHeaders(): Record<string, string> {
  const token = getAdminToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function getOrCreateUserId(): string {
  const existing = window.localStorage.getItem(USER_ID_STORAGE_KEY);
  if (existing && existing.trim().length > 0) {
    return existing;
  }
  const generated =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `driver-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  window.localStorage.setItem(USER_ID_STORAGE_KEY, generated);
  return generated;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!headers.has("Content-Type") && init?.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    let message = `Błąd serwera (${response.status})`;
    try {
      const errorBody = (await response.json()) as { detail?: unknown };
      if (typeof errorBody.detail === "string") {
        message = errorBody.detail;
      } else if (Array.isArray(errorBody.detail) && errorBody.detail.length > 0) {
        const first = errorBody.detail[0] as { msg?: string };
        if (typeof first.msg === "string") {
          message = first.msg;
        }
      }
    } catch {
      // Fallback to HTTP status text when body is not JSON.
    }
    if (response.status === 401 && headers.has("Authorization")) {
      setAdminToken(null);
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export interface DealsQuery {
  lat: number;
  lon: number;
  fuel: FuelType;
  liters: number;
  consumption: number;
  apps: string[];
}

export const apiClient = {
  async adminLogin(username: string, password: string): Promise<AdminLoginResponse> {
    const result = await request<AdminLoginResponse>("/admin/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    setAdminToken(result.access_token);
    return result;
  },

  getAdminSession(): Promise<AdminSession> {
    return request<AdminSession>("/admin/session", {
      headers: adminAuthHeaders(),
    });
  },

  adminLogout(): void {
    setAdminToken(null);
  },

  getStations(): Promise<Station[]> {
    return request<Station[]>("/stations");
  },

  createStation(payload: StationPayload): Promise<Station> {
    return request<Station>("/stations", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  updateStation(stationId: number, payload: StationPayload): Promise<Station> {
    return request<Station>(`/stations/${stationId}`, {
      method: "PUT",
      headers: adminAuthHeaders(),
      body: JSON.stringify(payload),
    });
  },

  deleteStation(stationId: number): Promise<void> {
    return request<void>(`/stations/${stationId}`, {
      method: "DELETE",
      headers: adminAuthHeaders(),
    });
  },

  getBenefits(): Promise<Benefit[]> {
    return request<Benefit[]>("/benefits");
  },

  createBenefit(payload: BenefitPayload): Promise<Benefit> {
    return request<Benefit>("/benefits", {
      method: "POST",
      headers: adminAuthHeaders(),
      body: JSON.stringify(payload),
    });
  },

  updateBenefit(benefitId: number, payload: BenefitPayload): Promise<Benefit> {
    return request<Benefit>(`/benefits/${benefitId}`, {
      method: "PUT",
      headers: adminAuthHeaders(),
      body: JSON.stringify(payload),
    });
  },

  deleteBenefit(benefitId: number): Promise<void> {
    return request<void>(`/benefits/${benefitId}`, {
      method: "DELETE",
      headers: adminAuthHeaders(),
    });
  },

  extractPricesFromImage(
    imageBase64: string,
    mimeType: string,
    filename: string,
  ): Promise<PriceExtractionResponse> {
    return request<PriceExtractionResponse>("/ai/extract-prices", {
      method: "POST",
      body: JSON.stringify({
        image_base64: imageBase64,
        mime_type: mimeType,
        filename,
      }),
    });
  },

  getStationPriceReports(stationId: number, fuelType?: FuelType): Promise<PriceReport[]> {
    const query = fuelType ? `?fuel_type=${encodeURIComponent(fuelType)}` : "";
    return request<PriceReport[]>(`/stations/${stationId}/price-reports${query}`);
  },

  createPriceReport(
    stationId: number,
    fuelType: FuelType,
    price: number,
    source: ReportSource = "manual",
  ): Promise<PriceReport> {
    return request<PriceReport>(`/stations/${stationId}/price-reports`, {
      method: "POST",
      headers: { "X-User-Id": getOrCreateUserId() },
      body: JSON.stringify({ fuel_type: fuelType, price, source }),
    });
  },

  confirmPriceReport(reportId: number): Promise<PriceVote> {
    return request<PriceVote>(`/price-reports/${reportId}/confirmations`, {
      method: "POST",
      headers: { "X-User-Id": getOrCreateUserId() },
    });
  },

  correctPriceReport(reportId: number, price: number): Promise<CorrectionResult> {
    return request<CorrectionResult>(`/price-reports/${reportId}/corrections`, {
      method: "POST",
      headers: { "X-User-Id": getOrCreateUserId() },
      body: JSON.stringify({ price }),
    });
  },

  getDeals(params: DealsQuery): Promise<DealsResponse> {
    const search = new URLSearchParams({
      lat: String(params.lat),
      lon: String(params.lon),
      fuel: params.fuel,
      liters: String(params.liters),
      consumption: String(params.consumption),
    });
    for (const app of params.apps) {
      search.append("apps", app);
    }
    return request<DealsResponse>(`/deals?${search.toString()}`);
  },
};
