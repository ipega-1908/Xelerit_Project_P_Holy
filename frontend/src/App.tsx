import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, apiClient, getAdminToken } from "./api/client";
import { AdminAuthBar } from "./components/AdminAuthBar";
import { BenefitsView } from "./components/BenefitsView";
import { CalculatorPanel } from "./components/CalculatorPanel";
import { DealsRankingList } from "./components/DealsRankingList";
import { GdanskMap } from "./components/GdanskMap";
import { StationCard } from "./components/StationCard";
import { StationForm } from "./components/StationForm";
import { GDANSK_DISTRICTS, LOYALTY_APPS } from "./constants/gdanskDistricts";
import { useUserProfile } from "./hooks/useUserProfile";
import type {
  Benefit,
  BenefitPayload,
  DealsResponse,
  InitialPriceEntry,
  Station,
  StationPayload,
} from "./types/api";

type ActiveTab = "calculator" | "stations" | "benefits";

export function App() {
  const { profile, updateProfile, toggleApp } = useUserProfile();
  const [activeTab, setActiveTab] = useState<ActiveTab>("calculator");

  const [dealsData, setDealsData] = useState<DealsResponse | null>(null);
  const [dealsLoading, setDealsLoading] = useState<boolean>(true);
  const [dealsError, setDealsError] = useState<string | null>(null);

  const [stations, setStations] = useState<Station[]>([]);
  const [stationsLoading, setStationsLoading] = useState<boolean>(true);
  const [stationsError, setStationsError] = useState<string | null>(null);
  const [districtFilter, setDistrictFilter] = useState<string>("ALL");
  const [showAddStation, setShowAddStation] = useState<boolean>(false);

  const [benefits, setBenefits] = useState<Benefit[]>([]);
  const [benefitsLoading, setBenefitsLoading] = useState<boolean>(true);
  const [benefitsError, setBenefitsError] = useState<string | null>(null);
  const [adminUsername, setAdminUsername] = useState<string | null>(null);

  useEffect(() => {
    if (!getAdminToken()) return;
    apiClient
      .getAdminSession()
      .then((session) => setAdminUsername(session.username))
      .catch(() => {
        apiClient.adminLogout();
        setAdminUsername(null);
      });
  }, []);

  const [customStartCoords, setCustomStartCoords] = useState<{ lat: number; lon: number } | null>(
    null,
  );

  const selectedDistrict = useMemo(
    () =>
      GDANSK_DISTRICTS.find((d) => d.id === profile.districtId) ?? GDANSK_DISTRICTS[0],
    [profile.districtId],
  );

  const activeLat = customStartCoords ? customStartCoords.lat : selectedDistrict.latitude;
  const activeLon = customStartCoords ? customStartCoords.lon : selectedDistrict.longitude;

  const fetchDeals = useCallback(async () => {
    setDealsLoading(true);
    setDealsError(null);
    try {
      const response = await apiClient.getDeals({
        lat: activeLat,
        lon: activeLon,
        fuel: profile.fuelType,
        liters: profile.liters,
        consumption: profile.consumptionPer100km,
        apps: profile.apps,
      });
      setDealsData(response);
    } catch (err) {
      setDealsError(err instanceof Error ? err.message : "Błąd pobierania rankingu.");
    } finally {
      setDealsLoading(false);
    }
  }, [
    activeLat,
    activeLon,
    profile.fuelType,
    profile.liters,
    profile.consumptionPer100km,
    profile.apps,
  ]);

  const fetchStations = useCallback(async () => {
    setStationsLoading(true);
    setStationsError(null);
    try {
      const data = await apiClient.getStations();
      setStations(data);
    } catch (err) {
      setStationsError(err instanceof Error ? err.message : "Błąd pobierania stacji.");
    } finally {
      setStationsLoading(false);
    }
  }, []);

  const fetchBenefits = useCallback(async () => {
    setBenefitsLoading(true);
    setBenefitsError(null);
    try {
      const data = await apiClient.getBenefits();
      setBenefits(data);
    } catch (err) {
      setBenefitsError(err instanceof Error ? err.message : "Błąd pobierania rabatów.");
    } finally {
      setBenefitsLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchDeals();
  }, [fetchDeals]);

  useEffect(() => {
    void fetchStations();
    void fetchBenefits();
  }, [fetchStations, fetchBenefits]);

  const refreshAll = useCallback(async () => {
    await Promise.all([fetchDeals(), fetchStations(), fetchBenefits()]);
  }, [fetchDeals, fetchStations, fetchBenefits]);

  const handleConfirmReport = useCallback(
    async (reportId: number) => {
      await apiClient.confirmPriceReport(reportId);
      await refreshAll();
    },
    [refreshAll],
  );

  const handleCorrectReport = useCallback(
    async (reportId: number, newPrice: number) => {
      await apiClient.correctPriceReport(reportId, newPrice);
      await refreshAll();
    },
    [refreshAll],
  );

  const handleCreateReports = useCallback(
    async (stationId: number, entries: InitialPriceEntry[]) => {
      for (const entry of entries) {
        await apiClient.createPriceReport(stationId, entry.fuelType, entry.price, entry.source);
      }
      await refreshAll();
    },
    [refreshAll],
  );

  const handleCreateStation = useCallback(
    async (payload: StationPayload, initialPrices: InitialPriceEntry[]) => {
      const created = await apiClient.createStation(payload);
      for (const entry of initialPrices) {
        await apiClient.createPriceReport(created.id, entry.fuelType, entry.price, entry.source);
      }
      setShowAddStation(false);
      await refreshAll();
    },
    [refreshAll],
  );

  const runAdminAction = useCallback(
    async (action: () => Promise<void>) => {
      try {
        await action();
        await refreshAll();
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          setAdminUsername(null);
        }
        throw err;
      }
    },
    [refreshAll],
  );

  const handleAdminLogin = useCallback(async (username: string, password: string) => {
    const res = await apiClient.adminLogin(username, password);
    setAdminUsername(res.username);
  }, []);

  const handleAdminLogout = useCallback(() => {
    apiClient.adminLogout();
    setAdminUsername(null);
  }, []);

  const handleUpdateStation = useCallback(
    async (stationId: number, payload: StationPayload) => {
      await runAdminAction(() => apiClient.updateStation(stationId, payload).then(() => undefined));
    },
    [runAdminAction],
  );

  const handleDeleteStation = useCallback(
    async (stationId: number) => {
      await runAdminAction(() => apiClient.deleteStation(stationId));
    },
    [runAdminAction],
  );

  const handleCreateBenefit = useCallback(
    async (payload: BenefitPayload) => {
      await runAdminAction(() => apiClient.createBenefit(payload).then(() => undefined));
    },
    [runAdminAction],
  );

  const handleUpdateBenefit = useCallback(
    async (benefitId: number, payload: BenefitPayload) => {
      await runAdminAction(() => apiClient.updateBenefit(benefitId, payload).then(() => undefined));
    },
    [runAdminAction],
  );

  const handleDeleteBenefit = useCallback(
    async (benefitId: number) => {
      await runAdminAction(() => apiClient.deleteBenefit(benefitId));
    },
    [runAdminAction],
  );

  const availableAppNames = useMemo(() => {
    const names = new Set<string>(LOYALTY_APPS.map((a) => a.name));
    for (const benefit of benefits) {
      names.add(benefit.app_name);
    }
    return Array.from(names);
  }, [benefits]);

  const availableDistricts = useMemo(
    () => Array.from(new Set(stations.map((s) => s.district))).sort(),
    [stations],
  );

  const filteredStations = useMemo(
    () =>
      districtFilter === "ALL"
        ? stations
        : stations.filter((s) => s.district === districtFilter),
    [stations, districtFilter],
  );

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>Gdzie Taniej? – Paliwo w Gdańsku</h1>
          <p className="subtitle">
            Ceny ze słupka i z aplikacji sieci oraz kalkulator opłacalności objazdu
          </p>
        </div>

        <div className="header-controls">
          <nav className="tabs" aria-label="Widoki aplikacji">
            <button
              type="button"
              className={`tab-btn ${activeTab === "calculator" ? "tab-active" : ""}`}
              onClick={() => setActiveTab("calculator")}
            >
              Kalkulator objazdu
            </button>
            <button
              type="button"
              className={`tab-btn ${activeTab === "stations" ? "tab-active" : ""}`}
              onClick={() => setActiveTab("stations")}
            >
              Lista stacji ({stations.length})
            </button>
            <button
              type="button"
              className={`tab-btn ${activeTab === "benefits" ? "tab-active" : ""}`}
              onClick={() => setActiveTab("benefits")}
            >
              Rabaty ({benefits.length})
            </button>
          </nav>

          <AdminAuthBar
            adminUsername={adminUsername}
            onLogin={handleAdminLogin}
            onLogout={handleAdminLogout}
          />
        </div>
      </header>

      <main className="app-main">
        {activeTab === "calculator" && (
          <>
            <CalculatorPanel
              profile={profile}
              availableAppNames={availableAppNames}
              customPointCoords={customStartCoords}
              onSelectDistrict={(districtId) => {
                setCustomStartCoords(null);
                updateProfile({ districtId });
              }}
              onUpdateProfile={updateProfile}
              onToggleApp={toggleApp}
            />
            <GdanskMap
              startLat={activeLat}
              startLon={activeLon}
              isCustomPoint={customStartCoords !== null}
              deals={dealsData?.deals ?? []}
              onSelectStartPoint={(lat, lon) => setCustomStartCoords({ lat, lon })}
              onResetToDistrict={() => setCustomStartCoords(null)}
            />
            <DealsRankingList
              data={dealsData}
              isLoading={dealsLoading}
              error={dealsError}
              onRetry={() => void fetchDeals()}
              onConfirmReport={handleConfirmReport}
              onCorrectReport={handleCorrectReport}
            />
          </>
        )}

        {activeTab === "stations" && (
          <section className="stations-view">
            <div className="stations-toolbar">
              <label className="filter-label">
                Filtruj dzielnicę:
                <select
                  value={districtFilter}
                  onChange={(e) => setDistrictFilter(e.target.value)}
                >
                  <option value="ALL">Wszystkie dzielnice</option>
                  {availableDistricts.map((district) => (
                    <option key={district} value={district}>
                      {district}
                    </option>
                  ))}
                </select>
              </label>

              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setShowAddStation((prev) => !prev)}
              >
                {showAddStation ? "Zamknij formularz" : "+ Dodaj stację"}
              </button>
            </div>

            {showAddStation && (
              <div className="form-wrapper">
                <StationForm
                  onSave={handleCreateStation}
                  onCancel={() => setShowAddStation(false)}
                />
              </div>
            )}

            {stationsLoading && stations.length === 0 ? (
              <div className="state-box">Ładuję listę stacji w Gdańsku...</div>
            ) : stationsError ? (
              <div className="state-box state-error">
                <p>Nie udało się załadować stacji: {stationsError}</p>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => void fetchStations()}
                >
                  Spróbuj ponownie
                </button>
              </div>
            ) : filteredStations.length === 0 ? (
              <div className="state-box">Brak stacji spełniających wybrane kryteria.</div>
            ) : (
              <div className="stations-grid">
                {filteredStations.map((station) => (
                  <StationCard
                    key={station.id}
                    station={station}
                    userApps={profile.apps}
                    isAdmin={adminUsername !== null}
                    onConfirmReport={handleConfirmReport}
                    onCorrectReport={handleCorrectReport}
                    onCreateReports={handleCreateReports}
                    onUpdateStation={handleUpdateStation}
                    onDeleteStation={handleDeleteStation}
                  />
                ))}
              </div>
            )}
          </section>
        )}

        {activeTab === "benefits" && (
          <BenefitsView
            benefits={benefits}
            isLoading={benefitsLoading}
            error={benefitsError}
            isAdmin={adminUsername !== null}
            onRetry={() => void fetchBenefits()}
            onCreateBenefit={handleCreateBenefit}
            onUpdateBenefit={handleUpdateBenefit}
            onDeleteBenefit={handleDeleteBenefit}
          />
        )}
      </main>
    </div>
  );
}

export default App;
