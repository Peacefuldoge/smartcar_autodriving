#!/usr/bin/env python3
"""Click an image to inspect OpenCV HSV values; replacement for the old hsv.py scratch script."""

import argparse
import cv2


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    args = parser.parse_args()

    image = cv2.imread(args.image)
    if image is None:
        raise SystemExit(f"Unable to read image: {args.image}")
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    def on_click(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            print(f"x={x}, y={y}, HSV={hsv[y, x].tolist()}")

    cv2.imshow("image", image)
    cv2.setMouseCallback("image", on_click)
    cv2.waitKey(0)


if __name__ == "__main__":
    main()
