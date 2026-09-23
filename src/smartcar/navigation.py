from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from .hardware import DriveCommand


EARTH_RADIUS_M = 6371008.8


@dataclass(frozen=True)
class GeoPoint:
    latitude: float
    longitude: float
    altitude: float = 0.0


@dataclass(frozen=True)
class NavigationResult:
    command: DriveCommand
    arrived: bool
    distance_m: float
    target_bearing_deg: float
    heading_deg: Optional[float]
    bearing_error_deg: Optional[float]


def haversine_m(a: GeoPoint, b: GeoPoint) -> float:
    lat1, lat2 = math.radians(a.latitude), math.radians(b.latitude)
    dlat = lat2 - lat1
    dlon = math.radians(b.longitude - a.longitude)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def bearing_deg(a: GeoPoint, b: GeoPoint) -> float:
    lat1, lat2 = math.radians(a.latitude), math.radians(b.latitude)
    dlon = math.radians(b.longitude - a.longitude)
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def angle_error_deg(target: float, current: float) -> float:
    return (target - current + 180.0) % 360.0 - 180.0


class GPSNavigatorCore:
    """GPS waypoint guidance layered on top of the existing lane steering command."""

    def __init__(self, *, neutral: int = 1500, speed: int = 1560,
                 steering_min: int = 500, steering_max: int = 2450,
                 arrival_radius_m: float = 3.0, bearing_gain: float = 3.0,
                 steering_direction: float = 1.0, heading_min_move_m: float = 0.8) -> None:
        self.neutral = int(neutral)
        self.speed = int(speed)
        self.steering_min = int(steering_min)
        self.steering_max = int(steering_max)
        self.arrival_radius_m = float(arrival_radius_m)
        self.bearing_gain = float(bearing_gain)
        self.steering_direction = float(steering_direction)
        self.heading_min_move_m = float(heading_min_move_m)
        self._previous: Optional[GeoPoint] = None
        self._heading: Optional[float] = None

    def reset(self) -> None:
        self._previous = None
        self._heading = None

    def _update_heading(self, position: GeoPoint) -> None:
        if self._previous is not None and haversine_m(self._previous, position) >= self.heading_min_move_m:
            self._heading = bearing_deg(self._previous, position)
            self._previous = position
        elif self._previous is None:
            self._previous = position

    def compute(self, position: GeoPoint, target: GeoPoint, lane_steering: int) -> NavigationResult:
        self._update_heading(position)
        distance = haversine_m(position, target)
        target_bearing = bearing_deg(position, target)
        if distance <= self.arrival_radius_m:
            return NavigationResult(
                command=DriveCommand(self.neutral, self.neutral),
                arrived=True,
                distance_m=distance,
                target_bearing_deg=target_bearing,
                heading_deg=self._heading,
                bearing_error_deg=0.0 if self._heading is not None else None,
            )

        error = None
        steering = int(lane_steering)
        if self._heading is not None:
            error = angle_error_deg(target_bearing, self._heading)
            steering += int(round(self.steering_direction * self.bearing_gain * error))
        steering = max(self.steering_min, min(self.steering_max, steering))
        return NavigationResult(
            command=DriveCommand(self.speed, steering),
            arrived=False,
            distance_m=distance,
            target_bearing_deg=target_bearing,
            heading_deg=self._heading,
            bearing_error_deg=error,
        )
