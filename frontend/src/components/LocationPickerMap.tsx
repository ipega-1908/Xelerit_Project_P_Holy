import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

interface LocationPickerMapProps {
  latitude: number;
  longitude: number;
  onChange: (latitude: number, longitude: number) => void;
}

const DEFAULT_ZOOM = 13;

function roundCoordinate(value: number): number {
  return Math.round(value * 100000) / 100000;
}

export function LocationPickerMap({
  latitude,
  longitude,
  onChange,
}: LocationPickerMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markerRef = useRef<L.CircleMarker | null>(null);
  const onChangeRef = useRef(onChange);

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || mapRef.current) return;

    const map = L.map(container, {
      center: [latitude, longitude],
      zoom: DEFAULT_ZOOM,
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 19,
    }).addTo(map);

    const marker = L.circleMarker([latitude, longitude], {
      radius: 9,
      color: "#ffffff",
      weight: 2,
      fillColor: "#dc2626",
      fillOpacity: 0.95,
    })
      .bindTooltip("Lokalizacja stacji", { direction: "top" })
      .addTo(map);

    map.on("click", (event: L.LeafletMouseEvent) => {
      const nextLat = roundCoordinate(event.latlng.lat);
      const nextLon = roundCoordinate(event.latlng.lng);
      onChangeRef.current(nextLat, nextLon);
    });

    mapRef.current = map;
    markerRef.current = marker;

    return () => {
      map.remove();
      mapRef.current = null;
      markerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const marker = markerRef.current;
    if (!map || !marker) return;

    const current = marker.getLatLng();
    if (current.lat === latitude && current.lng === longitude) return;

    marker.setLatLng([latitude, longitude]);
    map.panTo([latitude, longitude], { animate: true });
  }, [latitude, longitude]);

  return <div ref={containerRef} className="location-picker-box" />;
}
