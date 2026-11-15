import { useCallback, useEffect, useState } from "react";
import type { FuelType, UserProfile } from "../types/api";

const PROFILE_STORAGE_KEY = "fuel_deals_user_profile";

const DEFAULT_PROFILE: UserProfile = {
  districtId: "srodmiescie",
  fuelType: "PB95",
  liters: 45,
  consumptionPer100km: 7.5,
  apps: ["Orlen Vitay"],
};

function loadInitialProfile(): UserProfile {
  try {
    const raw = window.localStorage.getItem(PROFILE_STORAGE_KEY);
    if (!raw) {
      return DEFAULT_PROFILE;
    }
    const parsed = JSON.parse(raw) as Partial<UserProfile>;
    return {
      districtId:
        typeof parsed.districtId === "string" && parsed.districtId.length > 0
          ? parsed.districtId
          : DEFAULT_PROFILE.districtId,
      fuelType: isValidFuel(parsed.fuelType) ? parsed.fuelType : DEFAULT_PROFILE.fuelType,
      liters:
        typeof parsed.liters === "number" && parsed.liters > 0
          ? parsed.liters
          : DEFAULT_PROFILE.liters,
      consumptionPer100km:
        typeof parsed.consumptionPer100km === "number" && parsed.consumptionPer100km > 0
          ? parsed.consumptionPer100km
          : DEFAULT_PROFILE.consumptionPer100km,
      apps: Array.isArray(parsed.apps)
        ? parsed.apps.filter((item): item is string => typeof item === "string")
        : DEFAULT_PROFILE.apps,
    };
  } catch {
    return DEFAULT_PROFILE;
  }
}

function isValidFuel(value: unknown): value is FuelType {
  return value === "PB95" || value === "PB98" || value === "ON" || value === "LPG";
}

export function useUserProfile() {
  const [profile, setProfile] = useState<UserProfile>(loadInitialProfile);

  useEffect(() => {
    window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(profile));
  }, [profile]);

  const updateProfile = useCallback((patch: Partial<UserProfile>) => {
    setProfile((prev) => ({ ...prev, ...patch }));
  }, []);

  const toggleApp = useCallback((appName: string) => {
    setProfile((prev) => {
      const exists = prev.apps.includes(appName);
      return {
        ...prev,
        apps: exists ? prev.apps.filter((name) => name !== appName) : [...prev.apps, appName],
      };
    });
  }, []);

  return { profile, updateProfile, toggleApp };
}
