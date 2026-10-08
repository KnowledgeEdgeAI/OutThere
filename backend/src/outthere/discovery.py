"""Internal candidate math only. No public matching API until privacy gates are implemented."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Availability:
    user_id: str
    latitude: float  # Coarse area centre, never a live GPS stream.
    longitude: float
    radius_m: float
    starts_at: int
    ends_at: int
    vibes: frozenset[str]

    def __post_init__(self):
        values = (self.latitude, self.longitude, self.radius_m)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Coordinates and radius must be finite")
        if not -90 <= self.latitude <= 90 or not -180 <= self.longitude <= 180:
            raise ValueError("Invalid coordinates")
        if self.radius_m <= 0 or self.ends_at <= self.starts_at:
            raise ValueError("Radius and time interval must be positive")


def distance_m(a: Availability, b: Availability) -> float:
    lat_a, lat_b = math.radians(a.latitude), math.radians(b.latitude)
    dlat, dlon = lat_b - lat_a, math.radians(b.longitude - a.longitude)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat_a) * math.cos(lat_b) * math.sin(dlon / 2) ** 2
    return 2 * 6_371_008.8 * math.asin(math.sqrt(min(1.0, max(0.0, h))))


def compatible(a: Availability, b: Availability, *, blocked: bool = False) -> bool:
    return (
        not blocked
        and a.user_id != b.user_id
        and max(a.starts_at, b.starts_at) < min(a.ends_at, b.ends_at)
        and bool(a.vibes & b.vibes)
        and distance_m(a, b) <= min(a.radius_m, b.radius_m)
    )
