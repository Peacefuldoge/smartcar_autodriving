from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from .behavior import TimedCommand
from .hardware import DriveCommand


class TimedManeuverExecutor:
    """Non-blocking executor for BehaviorController timed command sequences.

    The historical program used time.sleep() while overtaking/stopping.  A ROS node must
    keep spinning while a maneuver runs, so this helper exposes the command that should be
    active at any given monotonic timestamp.
    """

    def __init__(self) -> None:
        self._steps: Sequence[TimedCommand] = ()
        self._index = 0
        self._deadline = 0.0
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    def cancel(self) -> None:
        self._steps = ()
        self._index = 0
        self._deadline = 0.0
        self._active = False

    def start(self, steps: Iterable[TimedCommand], now: float) -> None:
        seq = tuple(steps)
        if not seq:
            self.cancel()
            return
        self._steps = seq
        self._index = 0
        self._deadline = now + max(0.0, float(seq[0].duration))
        self._active = True

    def command(self, now: float) -> Optional[DriveCommand]:
        if not self._active:
            return None

        while self._active and now >= self._deadline:
            self._index += 1
            if self._index >= len(self._steps):
                self.cancel()
                return None
            self._deadline += max(0.0, float(self._steps[self._index].duration))

        return self._steps[self._index].command if self._active else None


@dataclass
class _StampedCommand:
    command: Optional[DriveCommand] = None
    stamp: float = 0.0


class CommandMuxCore:
    """Pure-Python command arbiter shared by the ROS mux node and unit tests."""

    VALID_MODES = {"autonomous", "manual"}

    def __init__(self, *, neutral: int = 1500, timeout: float = 0.3, mode: str = "autonomous") -> None:
        if mode not in self.VALID_MODES:
            raise ValueError(f"Unsupported control mode: {mode}")
        self.neutral = int(neutral)
        self.timeout = float(timeout)
        self.mode = mode
        self._autonomous = _StampedCommand()
        self._manual = _StampedCommand()

    def set_mode(self, mode: str) -> None:
        if mode not in self.VALID_MODES:
            raise ValueError(f"Unsupported control mode: {mode}")
        self.mode = mode

    def update(self, source: str, command: DriveCommand, now: float) -> None:
        if source == "autonomous":
            self._autonomous = _StampedCommand(command, now)
        elif source == "manual":
            self._manual = _StampedCommand(command, now)
        else:
            raise ValueError(f"Unknown command source: {source}")

    def select(self, now: float) -> DriveCommand:
        selected = self._autonomous if self.mode == "autonomous" else self._manual
        if selected.command is None or now - selected.stamp > self.timeout:
            return DriveCommand(self.neutral, self.neutral)
        return selected.command


def steering_from_joy_axis(axis_value: float, *, center: int = 1500, span: int = 750,
                           minimum: int = 500, maximum: int = 2450) -> int:
    axis_value = max(-1.0, min(1.0, float(axis_value)))
    steering = int(round(center - axis_value * span))
    return max(minimum, min(maximum, steering))
