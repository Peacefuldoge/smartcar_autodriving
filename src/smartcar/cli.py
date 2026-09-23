from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Autonomous smart-car utilities")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="run autonomous driving")
    run_parser.add_argument("--config", default="config/default.json")
    run_parser.add_argument("--dry-run", action="store_true")

    collect_parser = sub.add_parser("collect", help="collect camera / steering training data")
    collect_parser.add_argument("--output", default="data/recording")
    collect_parser.add_argument("--camera", default="/dev/video2")
    collect_parser.add_argument("--joystick", default="/dev/input/js0")
    collect_parser.add_argument("--serial", default="/dev/ttyUSB0")
    collect_parser.add_argument("--library", default="lib/libart_driver.so")
    collect_parser.add_argument("--throttle", type=int, default=1560)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "run":
        from .autonomous import run

        run(Path(args.config), dry_run=args.dry_run)
    elif args.command == "collect":
        from .data_collection import collect

        collect(
            args.output,
            camera_device=args.camera,
            joystick_device=args.joystick,
            serial_device=args.serial,
            library=args.library,
            throttle=args.throttle,
        )
