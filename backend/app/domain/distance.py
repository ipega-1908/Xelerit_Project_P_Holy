import math

EARTH_RADIUS_KM = 6371.0
DEFAULT_ROAD_FACTOR = 1.3


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in kilometers between two WGS84 coordinates."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_KM * c


def estimated_road_distance_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    road_factor: float = DEFAULT_ROAD_FACTOR,
) -> float:
    """Estimate driving distance by scaling haversine distance by a road factor."""
    if road_factor <= 0:
        raise ValueError("road_factor must be positive")
    return haversine_km(lat1, lon1, lat2, lon2) * road_factor


def calculate_extra_km(
    distance_to_station_km: float,
    distance_to_reference_km: float,
) -> float:
    """Compute round-trip extra distance relative to the nearest reference station."""
    if distance_to_station_km < 0 or distance_to_reference_km < 0:
        raise ValueError("Distances cannot be negative")
    return max(0.0, 2.0 * (distance_to_station_km - distance_to_reference_km))
