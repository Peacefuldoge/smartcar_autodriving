#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from smartcar.face_recognition import FisherFacesModel


def largest_face(image, cascade):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    if len(faces) == 0:
        return image
    x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
    return image[y:y + h, x:x + w]


def main() -> None:
    p = argparse.ArgumentParser(description='Train OpenCV FisherFaces recipient recognizer')
    p.add_argument('--dataset', required=True, help='dataset/<person_id>/*.jpg')
    p.add_argument('--model', default='models/fisherfaces.yml')
    p.add_argument('--labels', default='models/fisherfaces_labels.json')
    p.add_argument('--threshold', type=float, default=3500.0)
    p.add_argument('--width', type=int, default=160)
    p.add_argument('--height', type=int, default=160)
    args = p.parse_args()

    dataset = Path(args.dataset)
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    images = []
    labels = []
    label_names = {}
    for label, person_dir in enumerate(sorted(p for p in dataset.iterdir() if p.is_dir())):
        label_names[label] = person_dir.name
        for path in sorted(person_dir.iterdir()):
            if path.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.bmp'}:
                continue
            image = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if image is None:
                continue
            images.append(largest_face(image, cascade))
            labels.append(label)

    model = FisherFacesModel(threshold=args.threshold, face_size=(args.width, args.height))
    model.train(images, labels, label_names)
    model.save(Path(args.model), Path(args.labels))
    print(f'trained FisherFaces with {len(images)} images / {len(label_names)} people')


if __name__ == '__main__':
    main()
