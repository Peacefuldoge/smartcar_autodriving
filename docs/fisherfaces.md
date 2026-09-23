# FisherFaces recipient recognition

Dataset layout:

```text
data/faces/
├── alice/
│   ├── 001.jpg
│   └── 002.jpg
├── bob/
│   ├── 001.jpg
│   └── 002.jpg
└── ...
```

Train:

```bash
python3 scripts/train_fisherfaces.py \
  --dataset data/faces \
  --model models/fisherfaces.yml \
  --labels models/fisherfaces_labels.json
```

The training script detects/crops the largest frontal face when possible, converts it to grayscale, resizes all samples to the same size and applies histogram equalization. The ROS node uses the same preprocessing before prediction.

Enable the node only after a model has been trained:

```bash
roslaunch smartcar_autonomous_driving delivery_vehicle.launch enable_face:=true
```

`face_recognition.threshold` is a distance threshold, not a probability. Calibrate it with held-out images from your actual camera/lighting instead of treating the example value as universal.
