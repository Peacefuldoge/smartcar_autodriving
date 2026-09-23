from __future__ import annotations

import ctypes
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union


@dataclass(frozen=True)
class DriveCommand:
    throttle: int
    steering: int


class RaceCarDriver:
    """ctypes wrapper for the competition-provided libart_driver.so."""

    def __init__(self, library: Union[str, Path], serial_device: str, baudrate: int = 38400):
        library = Path(library)
        if not library.exists():
            raise FileNotFoundError(
                f"Vehicle driver library not found: {library}. "
                "Copy the original libart_driver.so into lib/."
            )

        self._lib = ctypes.CDLL(str(library))
        self._lib.art_racecar_init.argtypes = [ctypes.c_int, ctypes.c_char_p]
        self._lib.art_racecar_init.restype = ctypes.c_int
        self._lib.send_cmd.argtypes = [ctypes.c_int, ctypes.c_int]
        self._lib.send_cmd.restype = None

        result = self._lib.art_racecar_init(baudrate, serial_device.encode("utf-8"))
        if result < 0:
            raise RuntimeError(f"Failed to initialize vehicle interface on {serial_device}")

    def send(self, command: DriveCommand) -> None:
        self._lib.send_cmd(int(command.throttle), int(command.steering))

    def stop(self, neutral: int = 1500) -> None:
        self.send(DriveCommand(neutral, neutral))


class DryRunDriver:
    """Driver replacement for development without hardware."""

    def __init__(self):
        self.last_command: Optional[DriveCommand] = None

    def send(self, command: DriveCommand) -> None:
        changed = command != self.last_command
        self.last_command = command
        if changed:
            print(f"[dry-run] throttle={command.throttle} steering={command.steering}")

    def stop(self, neutral: int = 1500) -> None:
        self.send(DriveCommand(neutral, neutral))
