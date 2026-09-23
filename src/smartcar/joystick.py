from __future__ import annotations

import array
import fcntl
import os
import struct
from dataclasses import dataclass
from typing import List, Union


AXIS_NAMES = {
    0x00: "x", 0x01: "y", 0x02: "z", 0x03: "rx", 0x04: "ry", 0x05: "rz",
    0x06: "throttle", 0x07: "rudder", 0x08: "wheel", 0x09: "gas", 0x0A: "brake",
    0x10: "hat0x", 0x11: "hat0y",
}
BUTTON_NAMES = {
    0x130: "a", 0x131: "b", 0x133: "x", 0x134: "y",
    0x136: "tl", 0x137: "tr", 0x138: "tl2", 0x139: "tr2",
    0x13A: "select", 0x13B: "start",
}


@dataclass(frozen=True)
class JoystickEvent:
    kind: str
    name: str
    value: Union[float, int]


class LinuxJoystick:
    def __init__(self, device: str = "/dev/input/js0"):
        self._file = open(device, "rb", buffering=0)
        os.set_blocking(self._file.fileno(), False)

        axis_count_buf = array.array("B", [0])
        fcntl.ioctl(self._file, 0x80016A11, axis_count_buf)
        button_count_buf = array.array("B", [0])
        fcntl.ioctl(self._file, 0x80016A12, button_count_buf)

        axis_buf = array.array("B", [0] * 0x40)
        fcntl.ioctl(self._file, 0x80406A32, axis_buf)
        self.axis_map = [AXIS_NAMES.get(code, f"axis_{code:02x}") for code in axis_buf[: axis_count_buf[0]]]

        button_buf = array.array("H", [0] * 200)
        fcntl.ioctl(self._file, 0x80406A34, button_buf)
        self.button_map = [BUTTON_NAMES.get(code, f"button_{code:03x}") for code in button_buf[: button_count_buf[0]]]

    def read_events(self) -> List[JoystickEvent]:
        events: List[JoystickEvent] = []
        while True:
            try:
                data = self._file.read(8)
            except BlockingIOError:
                break
            if not data or len(data) != 8:
                break
            _, value, event_type, number = struct.unpack("IhBB", data)
            event_type &= ~0x80  # ignore JS_EVENT_INIT bit
            if event_type & 0x01 and number < len(self.button_map):
                events.append(JoystickEvent("button", self.button_map[number], int(value)))
            if event_type & 0x02 and number < len(self.axis_map):
                events.append(JoystickEvent("axis", self.axis_map[number], value / 32767.0))
        return events

    def close(self) -> None:
        self._file.close()
