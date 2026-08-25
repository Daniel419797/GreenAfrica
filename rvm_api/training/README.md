# GreenAfrica RVM AI training

This directory contains the reproducible training and release path for the production RVM models. Runtime code does not download or silently replace models. Deployment uses ONNX artifacts with SHA-256 hashes recorded in `models/manifest.json`.

## 1. Collect and label detector data

Use frames from the actual RVM cameras/enclosures. Split by capture session/machine, not random adjacent video frames, to avoid train/test leakage.

YOLO detector classes must be stable:

```text
0 bottle
1 can
2 hand
3 other_object
```

The detector dataset YAML should have independent `train`, `val`, and `test` splits. Include difficult negatives: hands entering the gate, phones, paper/cardboard, cans, glass, bottle caps, printed bottle images, background motion, partial objects, glare, dark scenes, crushed bottles, labels, transparent bottles, and multiple objects.

## 2. Collect material-classifier crops

The classifier dataset uses `ImageFolder` layout:

```text
material_dataset/
  train/
    aluminum/
    glass/
    hdpe/
    other/
    pet_clear/
    pet_colored/
  val/
    ...same classes...
  test/
    ...same classes...
```

The six class names are intentionally fixed because they become stable model IDs in production. Use real crops from the detector path, including hard negatives and difficult PET examples. Do not create validation/test sets by taking neighboring frames from the same bottle video as training data.

## 3. Train

```bash
cd rvm_api
python -m venv .venv-training
source .venv-training/bin/activate
pip install -r training/requirements-training.txt

python training/train_detector.py \
  --data /data/rvm_detector/data.yaml \
  --version 2026.08.1 \
  --output training/artifacts/detector

python training/train_classifier.py \
  --data /data/rvm_material \
  --version 2026.08.1 \
  --output training/artifacts/classifier
```

The detector starts from a trained YOLO11 checkpoint and fine-tunes on RVM data. The classifier starts from ImageNet-pretrained MobileNetV3, handles class imbalance, uses augmentation and label smoothing, selects by validation macro recall, temperature-calibrates confidence, evaluates the held-out test set, and exports calibrated logits to ONNX.

## 4. Field validation and threshold selection

Before release, run the candidate models on recorded and live data from the physical RVM. Thresholds must be selected from measured false-accept/false-reject tradeoffs, not guessed.

For a reward-paying machine, prioritize false-accept control. Report at least:

- bottle detector precision/recall and mAP;
- PET precision and recall for both accepted PET classes;
- false acceptance rate per non-PET class;
- confusion matrix;
- duplicate-count rate;
- calibration/reliability curve;
- inference p50/p95/p99 latency on target hardware;
- results by lighting, machine/camera, bottle colour, deformation, orientation and label coverage.

## 5. Build immutable release artifacts

```bash
python training/build_manifest.py \
  --detector training/artifacts/detector/pet_detector.onnx \
  --classifier training/artifacts/classifier/pet_material_classifier.onnx \
  --classifier-classes-json training/artifacts/classifier/classes.json \
  --detector-classes bottle,can,hand,other_object \
  --version 2026.08.1 \
  --detector-confidence 0.62 \
  --classifier-confidence 0.78 \
  --output-dir models
```

That command copies the ONNX files and writes their SHA-256 digests into `models/manifest.json`. Production startup verifies those hashes before accepting any bottle.

## 6. Production environment

Recommended production settings:

```text
RVM_AI_ENABLED=true
RVM_AI_FAIL_STARTUP_IF_UNAVAILABLE=true
RVM_AI_REQUIRE_MODEL_HASHES=true
RVM_AI_MODEL_MANIFEST=models/manifest.json
RVM_AI_EXECUTION_PROVIDER=auto
RVM_AI_ALLOWED_OBJECT_LABELS=bottle
RVM_AI_ALLOWED_PET_LABELS=pet_clear,pet_colored
RVM_ALLOW_MANUAL_EVENTS=false
RVM_ADMIN_TOKEN=<strong random secret>
```

`auto` selects TensorRT, then CUDA, then CPU when available. Benchmark the actual machine and pin a provider explicitly after hardware validation if deterministic latency is required.

## Production rule

A training script, pretrained checkpoint, or unvalidated public dataset is not itself a production PET model. Only promote a model after the release gate above has passed on representative RVM field data. The runtime deliberately fails closed when the verified release artifacts are missing or invalid.
