# CascadeClassifier face verification

The delivery system no longer depends on `cv2.face` or FisherFaces.  It uses
OpenCV's standard `cv2.CascadeClassifier`, so a normal OpenCV installation is
enough.

## Important limitation

The bundled `haarcascade_frontalface_default.xml` is a **face detector**, not an
identity recognizer.  In the default `presence` mode the vehicle verifies only
that a face remains visible for several consecutive camera frames before the
delivery can complete.  It must not be described as biometric identity
verification.

This is useful for a student/demo delivery robot because it avoids accidental
completion when nobody is standing at the vehicle, but it does not prove that
the person is the intended recipient.

## Modes

### `presence` (default)

Uses OpenCV's frontal-face Haar cascade.  Any detected face counts toward the
configured consecutive-frame gate.

```yaml
face_recognition:
  mode: presence
  cascade_path: ""       # empty -> cv2.data.haarcascades default XML
  required_matches: 3
  scale_factor: 1.1
  min_neighbors: 5
  min_face_size: [60, 60]
```

### `recipient_cascade`

If you independently train a target-specific cascade XML for each recipient,
map the task `recipient_id` to that XML:

```yaml
face_recognition:
  mode: recipient_cascade
  required_matches: 3
  recipient_cascades:
    alice: models/recipient_cascades/alice.xml
    bob: models/recipient_cascades/bob.xml
```

A missing recipient model fails closed: the node will not confirm the delivery.
Target-specific Haar/LBP cascades are classical classifiers and can be fragile
under pose, lighting, hairstyle, camera and background changes; do not treat
them as a high-security authentication mechanism.

## Check the installed cascade

```bash
python3 scripts/check_face_cascade.py
```

Optionally test an image:

```bash
python3 scripts/check_face_cascade.py --image test.jpg
```
