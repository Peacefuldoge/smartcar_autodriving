from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class GPSFix:
    latitude: float
    longitude: float
    altitude: float = 0.0
    valid: bool = True
    satellites: int = 0
    hdop: float = 0.0
    course_deg: Optional[float] = None
    speed_knots: Optional[float] = None


def _checksum_ok(sentence: str) -> bool:
    sentence = sentence.strip()
    if not sentence.startswith("$") or "*" not in sentence:
        return False
    body, checksum = sentence[1:].split("*", 1)
    value = 0
    for ch in body:
        value ^= ord(ch)
    try:
        return value == int(checksum[:2], 16)
    except ValueError:
        return False


def _coord_to_decimal(raw: str, hemisphere: str) -> float:
    if not raw:
        raise ValueError("empty NMEA coordinate")
    value = float(raw)
    degrees = int(value // 100)
    minutes = value - degrees * 100
    decimal = degrees + minutes / 60.0
    if hemisphere.upper() in {"S", "W"}:
        decimal = -decimal
    return decimal


def parse_nmea(sentence: str, *, verify_checksum: bool = True) -> Optional[GPSFix]:
    """Parse GGA/RMC NMEA sentences into a small, dependency-free GPSFix.

    Returns None for unsupported sentence types or invalid fixes.
    """
    sentence = sentence.strip()
    if not sentence:
        return None
    if verify_checksum and not _checksum_ok(sentence):
        return None
    payload = sentence[1: sentence.index("*")] if "*" in sentence else sentence.lstrip("$")
    fields = payload.split(",")
    kind = fields[0][-3:] if fields else ""

    try:
        if kind == "GGA":
            # $GxGGA,time,lat,N,lon,E,quality,sats,hdop,alt,M,...
            if len(fields) < 10 or int(fields[6] or 0) <= 0:
                return None
            return GPSFix(
                latitude=_coord_to_decimal(fields[2], fields[3]),
                longitude=_coord_to_decimal(fields[4], fields[5]),
                altitude=float(fields[9] or 0.0),
                valid=True,
                satellites=int(fields[7] or 0),
                hdop=float(fields[8] or 0.0),
            )
        if kind == "RMC":
            # $GxRMC,time,status,lat,N,lon,E,speed,course,date,...
            if len(fields) < 9 or fields[2].upper() != "A":
                return None
            return GPSFix(
                latitude=_coord_to_decimal(fields[3], fields[4]),
                longitude=_coord_to_decimal(fields[5], fields[6]),
                valid=True,
                course_deg=float(fields[8]) if fields[8] else None,
                speed_knots=float(fields[7]) if fields[7] else None,
            )
    except (ValueError, IndexError):
        return None
    return None
