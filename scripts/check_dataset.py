#!/usr/bin/env python3
"""Check whether a numbered image dataset has gaps."""

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()

    ids = sorted(int(p.stem) for p in args.directory.glob("*.jpg") if p.stem.isdigit())
    if not ids:
        print("No numbered JPG images found")
        return
    existing = set(ids)
    missing = [i for i in range(ids[0], ids[-1] + 1) if i not in existing]
    print(f"images={len(ids)} range={ids[0]}..{ids[-1]} missing={len(missing)}")
    if missing:
        print("missing ids:", ", ".join(map(str, missing[:200])))


if __name__ == "__main__":
    main()
