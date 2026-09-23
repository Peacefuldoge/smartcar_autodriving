from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import time
from typing import Dict, Iterable, List, Optional

from .hardware import DriveCommand
from .object_detection import Detection


LABELS = {
    0: "overtake",
    1: "stop_line",
    2: "speed_limit",
    3: "speed_limit_end",
    4: "left_turn",
    5: "cone_right",
    6: "cone_left",
    7: "cone_right_mid",
    8: "cone_left_mid",
    9: "zebra_crossing",
    10: "parking_stop",
}

DEFAULT_THRESHOLDS = {
    "overtake": 0.35,
    "stop_line": 0.70,
    "speed_limit": 0.60,
    "speed_limit_end": 0.60,
    "left_turn": 0.70,
    "cone_right": 0.70,
    "cone_left": 0.70,
    "cone_right_mid": 0.70,
    "cone_left_mid": 0.70,
    "zebra_crossing": 0.70,
    "parking_stop": 0.70,
}


@dataclass(frozen=True)
class TimedCommand:
    duration: float
    command: DriveCommand


@dataclass
class BehaviorDecision:
    command: DriveCommand
    maneuver: List[TimedCommand] = field(default_factory=list)
    events: List[str] = field(default_factory=list)


class BehaviorController:
    """High-level rule controller reconstructed from the final user4.py competition logic.

    Compared with the original script, confirmation counters are tracked per label and one
    final command is produced per frame. This removes accidental interactions caused by one
    global counter and repeated send_cmd calls.
    """

    def __init__(
        self,
        *,
        cruise_speed: int = 1600,
        limited_speed: int = 1530,
        slow_speed: int = 1560,
        turn_speed: int = 1538,
        neutral: int = 1500,
        left_bias: int = 12,
        left_bias_seconds: float = 2.0,
        cooldown_seconds: float = 5.0,
        confirmation_frames: Optional[Dict[str, int]] = None,
    ):
        self.cruise_speed = cruise_speed
        self.limited_speed = limited_speed
        self.slow_speed = slow_speed
        self.turn_speed = turn_speed
        self.neutral = neutral
        self.left_bias = left_bias
        self.left_bias_seconds = left_bias_seconds
        self.cooldown_seconds = cooldown_seconds
        self.confirmation_frames = confirmation_frames or {}

        self.speed_limited = False
        self.left_bias_until = 0.0
        self.stop_line_used = False
        self.detection_cooldown_until = 0.0
        self._counts: Dict[int, int] = defaultdict(int)

    def _required(self, label_id: int) -> int:
        name = LABELS.get(label_id, str(label_id))
        return max(1, int(self.confirmation_frames.get(name, 1)))

    def _confirmed(self, detection: Detection) -> bool:
        name = LABELS.get(detection.label_id)
        if name is None:
            return False
        if detection.score < DEFAULT_THRESHOLDS.get(name, 1.0):
            self._counts[detection.label_id] = 0
            return False
        self._counts[detection.label_id] += 1
        if self._counts[detection.label_id] >= self._required(detection.label_id):
            self._counts[detection.label_id] = 0
            return True
        return False

    def base_command(self, steering: int, now: Optional[float] = None) -> DriveCommand:
        """Return the continuous lane-following command for the current behavior state.

        This is intentionally public so event-driven front-ends such as ROS can publish
        steering updates continuously without artificially re-counting stale detections.
        """
        now = time.monotonic() if now is None else now
        speed = self.limited_speed if self.speed_limited else self.cruise_speed
        if now < self.left_bias_until:
            steering += self.left_bias
            speed = min(speed, self.turn_speed)
        return DriveCommand(speed, steering)

    def update(
        self,
        steering: int,
        detections: Iterable[Detection],
        now: Optional[float] = None,
    ) -> BehaviorDecision:
        now = time.monotonic() if now is None else now
        decision = BehaviorDecision(command=self.base_command(steering, now))
        if now < self.detection_cooldown_until:
            return decision

        for detection in sorted(detections, key=lambda d: d.score, reverse=True):
            if not self._confirmed(detection):
                continue

            label = detection.label_id
            name = LABELS.get(label, f"class_{label}")
            decision.events.append(name)

            if label == 0:  # overtaking sequence from user4.py
                decision.maneuver = [
                    TimedCommand(0.23, DriveCommand(self.slow_speed, 1968)),
                    TimedCommand(0.15, DriveCommand(self.slow_speed, 943)),
                    TimedCommand(0.08, DriveCommand(self.slow_speed, 943)),
                    TimedCommand(0.13, DriveCommand(self.slow_speed, 1500)),
                    TimedCommand(0.05, DriveCommand(self.slow_speed, 950)),
                    TimedCommand(0.05, DriveCommand(self.slow_speed, 950)),
                    TimedCommand(0.20, DriveCommand(self.slow_speed, 1968)),
                    TimedCommand(0.02, DriveCommand(self.slow_speed, 1968)),
                ]
                self.detection_cooldown_until = now + self.cooldown_seconds
                break

            if label == 1 and not self.stop_line_used:
                decision.maneuver = [
                    TimedCommand(0.05, DriveCommand(1490, self.neutral)),
                    TimedCommand(2.0, DriveCommand(1530, self.neutral)),
                ]
                self.stop_line_used = True
                break

            if label == 2:
                self.speed_limited = True
                decision.command = DriveCommand(self.limited_speed, steering)
                break

            if label == 3:
                self.speed_limited = False
                decision.command = DriveCommand(self.cruise_speed, steering)
                break

            if label == 4:
                self.left_bias_until = now + self.left_bias_seconds
                decision.command = DriveCommand(self.turn_speed, steering + self.left_bias)
                break

            if label == 9:
                decision.maneuver = [
                    TimedCommand(0.05, DriveCommand(1490, self.neutral)),
                    TimedCommand(2.0, DriveCommand(self.neutral, self.neutral)),
                ]
                break

            if label == 10:
                decision.maneuver = [
                    TimedCommand(0.05, DriveCommand(1490, steering)),
                    TimedCommand(2.0, DriveCommand(self.neutral, self.neutral)),
                ]
                self.detection_cooldown_until = now + self.cooldown_seconds
                break

            # Cone labels 5-8 were counted in the historical script but did not contain
            # an actual steering maneuver. They are surfaced as events without inventing behavior.

        return decision
