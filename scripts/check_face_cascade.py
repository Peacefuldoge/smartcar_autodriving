#!/usr/bin/env python3
"""Validate an OpenCV cascade XML and optionally run it on one image."""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from smartcar.face_recognition import CascadeFaceDetector, default_frontal_face_cascade


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--cascade', default='', help='Cascade XML; defaults to OpenCV frontal-face cascade')
    p.add_argument('--image', default='', help='Optional image to inspect')
    args = p.parse_args()

    cascade = args.cascade or default_frontal_face_cascade()
    detector = CascadeFaceDetector(cascade)
    print(f'cascade: {cascade}')
    print('CascadeClassifier: OK')

    if args.image:
        image = cv2.imread(str(Path(args.image)))
        if image is None:
            raise SystemExit(f'Unable to read image: {args.image}')
        faces = detector.detect(image)
        print(f'faces: {len(faces)}')
        for i, face in enumerate(faces):
            print(f'  {i}: x={face.x} y={face.y} w={face.width} h={face.height}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
