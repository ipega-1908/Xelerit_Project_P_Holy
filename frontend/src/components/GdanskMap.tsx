import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";
import type { DealItem } from "../types/api";
import { formatPln, getStatusLabel } from "../utils/formatters";

interface GdanskMapProps {
  startLat: number;
  startLon: number;
  isCustomPoint: boolean;
  deals: DealItem[];
  onSelectStartPoint: (lat: number, lon: number) => void;
  onResetToDistrict: () => void;
}

function buildStationPopupElement(deal: DealItem): HTMLElement {
  const container = document.createElement("div");
  container.className = "map-popup";

  const title = document.createElement("strong");
  title.textContent = deal.station.name;
  container.appendChild(title);

  const address = document.createElement("div");
  address.textContent = `${deal.station.district} · ${deal.station.address}`;
  container.appendChild(address);

  const prices = document.createElement("div");
  prices.textContent = `Słupek: ${formatPln(deal.pump_price)}/l · Z apką: ${formatPln(deal.effective_price_per_liter)}/l`;
  container.appendChild(prices);

  const gain = document.createElement("div");
  const gainText =
    deal.net_gain > 0 ? `+${formatPln(deal.net_gain)}` : formatPln(deal.net_gain);
  gain.textContent = `Zysk netto: ${gainText} (${getStatusLabel(deal.price_status)})`;
  container.appendChild(gain);

  return container;
}

function getStationMarkerColors(deal: DealItem): { color: string; fillColor: string } {
  if (deal.is_profitable) {
    return { color: "#0e5e32", fillColor: "#147d44" };
  }
  if (deal.is_reference_station) {
    return { color: "#1546a8", fillColor: "#1d5bd6" };
  }
  return { color: "#475569", fillColor: "#64748b" };
}

export function GdanskMap({
  startLat,
  startLon,
  isCustomPoint,
  deals,
  onSelectStartPoint,
  onResetToDistrict,
}: GdanskMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerGroupRef = useRef<L.LayerGroup | null>(null);
  const onSelectRef = useRef(onSelectStartPoint);

  onSelectRef.current = onSelectStartPoint;

  useEffect(() => {
    if (!containerRef.current || mapRef.current !== null) {
      return;
    }

    const map = L.map(containerRef.current).setView([startLat, startLon], 12);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap",
      maxZoom: 18,
    }).addTo(map);

    const layerGroup = L.layerGroup().addTo(map);
    map.on("click", (event: L.LeafletMouseEvent) => {
      onSelectRef.current(
        Math.round(event.latlng.lat * 100000) / 100000,
        Math.round(event.latlng.lng * 100000) / 100000,
      );
    });

    mapRef.current = map;
    layerGroupRef.current = layerGroup;

    return () => {
      map.remove();
      mapRef.current = null;
      layerGroupRef.current = null;
    };
  }, []);

  useEffect(() => {
    const layerGroup = layerGroupRef.current;
    const map = mapRef.current;
    if (!layerGroup || !map) {
      return;
    }

    layerGroup.clearLayers();

    for (const deal of deals) {
      const colors = getStationMarkerColors(deal);
      const marker = L.circleMarker([deal.station.latitude, deal.station.longitude], {
        radius: deal.is_profitable ? 9 : 7,
        color: colors.color,
        fillColor: colors.fillColor,
        fillOpacity: 0.9,
        weight: 2,
      });
      marker.bindPopup(buildStationPopupElement(deal));
      marker.addTo(layerGroup);
    }

    const startMarker = L.circleMarker([startLat, startLon], {
      radius: 10,
      color: "#991b1b",
      fillColor: "#ef4444",
      fillOpacity: 0.95,
      weight: 3,
    });
    startMarker.bindPopup(
      isCustomPoint ? "Twój wybrany punkt startu na mapie" : "Wybrana dzielnica startowa",
    );
    startMarker.addTo(layerGroup);

    if (!isCustomPoint) {
      map.panTo([startLat, startLon]);
    }
  }, [deals, startLat, startLon, isCustomPoint]);

  return (
    <section className="card map-card" aria-label="Mapa stacji paliw w Gdańsku">
      <div className="map-header">
        <div>
          <h3>Mapa Gdańska – kliknij, aby ustawić punkt startu</h3>
          <p className="station-meta">
            Czerwony znacznik: Twój start · Zielone: opłacalny objazd · Niebieski: najbliższa stacja
          </p>
        </div>
        {isCustomPoint && (
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={onResetToDistrict}
          >
            Wróć do wybranej dzielnicy
          </button>
        )}
      </div>
      <div ref={containerRef} className="leaflet-container-box" />
    </section>
  );
}
