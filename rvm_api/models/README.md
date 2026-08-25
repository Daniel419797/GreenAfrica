# RVM AI model artifacts

Production uses two ONNX models:

1. `pet_detector.onnx` — YOLO object detector. It locates bottle-like objects and explicitly learns hard negatives such as hands, cans, and unrelated objects.
2. `pet_material_classifier.onnx` — secondary crop classifier. It separates accepted PET (`pet_clear`, `pet_colored`) from glass, HDPE, aluminum, and other material.

The service reads `manifest.json` at startup and verifies the SHA-256 digest of both artifacts before ONNX Runtime loads them. A hash mismatch, missing model, invalid class list, or inference failure is fail-closed and cannot create a recycling reward.

Do not commit ad-hoc model binaries directly to normal Git history. Store release models using Git LFS or an immutable model artifact store, then deploy the matching `manifest.json` next to the files. The manifest must be generated only after evaluation and release approval.

`manifest.example.json` documents the expected format. `training/build_manifest.py` produces the real manifest and hashes from released ONNX files.

## Production release gate

A candidate model should not be promoted until it passes field data from the actual RVM camera and enclosure. At minimum record:

- detector precision/recall and mAP on the held-out test set;
- PET classifier precision, recall, confusion matrix, and calibration quality;
- false-accept rate for glass, cans, hands, paper/cardboard, random objects, printed bottle images, partial bottles, crushed bottles, transparent bottles, and low-light/glare cases;
- duplicate-count rate for one bottle moving slowly or pausing in the gate;
- end-to-end inference latency on the target edge hardware;
- performance by camera, machine, lighting condition, bottle orientation, colour, dirt/label coverage, and bottle deformation.

The production decision thresholds belong in `manifest.json`, so a model release and its calibrated operating point are versioned together.
