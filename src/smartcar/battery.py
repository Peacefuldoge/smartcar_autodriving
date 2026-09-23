from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


_VOLTAGE_PATTERNS = (
    re.compile(r"(?:VOLTAGE|VOLT|VBAT|BATTERY)\s*[:=]\s*(-?\d+(?:\.\d+)?)", re.I),
    re.compile(r"\bV\s*[:=]\s*(-?\d+(?:\.\d+)?)", re.I),
    re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*(?:V)?\s*$", re.I),
)


def parse_voltage_line(line: str) -> Optional[float]:
    text = line.strip()
    for pattern in _VOLTAGE_PATTERNS:
        match = pattern.search(text)
        if match:
            try:
                value = float(match.group(1))
            except ValueError:
                return None
            return value if value >= 0.0 else None
    return None


@dataclass(frozen=True)
class BatteryReading:
    voltage: float
    percentage: float
    low: bool


class BatteryMonitorCore:
    """Voltage-to-state conversion with hysteresis to prevent low-battery chatter."""

    def __init__(self, *, low_voltage: float, recovery_voltage: float,
                 empty_voltage: float, full_voltage: float) -> None:
        if not empty_voltage < low_voltage <= recovery_voltage < full_voltage:
            raise ValueError("Expected empty < low <= recovery < full voltage")
        self.low_voltage = float(low_voltage)
        self.recovery_voltage = float(recovery_voltage)
        self.empty_voltage = float(empty_voltage)
        self.full_voltage = float(full_voltage)
        self.low = False

    def update(self, voltage: float) -> BatteryReading:
        voltage = float(voltage)
        if self.low:
            if voltage >= self.recovery_voltage:
                self.low = False
        elif voltage <= self.low_voltage:
            self.low = True

        percentage = (voltage - self.empty_voltage) / (self.full_voltage - self.empty_voltage)
        percentage = max(0.0, min(1.0, percentage))
        return BatteryReading(voltage=voltage, percentage=percentage, low=self.low)
