from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms


EXPECTED_CLASSES = ["aluminum", "glass", "hdpe", "other", "pet_clear", "pet_colored"]


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def build_loaders(root: Path, image_size: int, batch: int, workers: int):
    train_tf = transforms.Compose(
        [
            transforms.RandomResizedCrop(image_size, scale=(0.70, 1.0)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(10),
            transforms.ColorJitter(brightness=0.25, contrast=0.25, saturation=0.20, hue=0.04),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ]
    )
    eval_tf = transforms.Compose(
        [
            transforms.Resize(int(image_size * 1.14)),
            transforms.CenterCrop(image_size),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ]
    )
    train_ds = datasets.ImageFolder(root / "train", transform=train_tf)
    val_ds = datasets.ImageFolder(root / "val", transform=eval_tf)
    test_ds = datasets.ImageFolder(root / "test", transform=eval_tf)

    if train_ds.classes != EXPECTED_CLASSES:
        raise SystemExit(
            f"Classifier classes must be exactly {EXPECTED_CLASSES}; found {train_ds.classes}. "
            "Rename dataset folders before training so class IDs are stable."
        )
    if val_ds.classes != train_ds.classes or test_ds.classes != train_ds.classes:
        raise SystemExit("train/val/test class folders differ")

    counts = np.bincount(np.asarray(train_ds.targets), minlength=len(train_ds.classes)).astype(np.float32)
    if np.any(counts == 0):
        raise SystemExit(f"Every classifier class needs training samples; counts={counts.tolist()}")
    weights = counts.sum() / (len(counts) * counts)

    kwargs = dict(batch_size=batch, num_workers=workers, pin_memory=torch.cuda.is_available())
    train_loader = DataLoader(train_ds, shuffle=True, drop_last=False, **kwargs)
    val_loader = DataLoader(val_ds, shuffle=False, drop_last=False, **kwargs)
    test_loader = DataLoader(test_ds, shuffle=False, drop_last=False, **kwargs)
    return train_ds.classes, torch.tensor(weights, dtype=torch.float32), train_loader, val_loader, test_loader


def build_model(class_count: int) -> nn.Module:
    model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, class_count)
    return model


@torch.no_grad()
def evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> dict:
    model.eval()
    total = 0
    correct = 0
    class_total = np.zeros(len(EXPECTED_CLASSES), dtype=np.int64)
    class_correct = np.zeros(len(EXPECTED_CLASSES), dtype=np.int64)
    logits_all: list[torch.Tensor] = []
    targets_all: list[torch.Tensor] = []

    for images, targets in loader:
        images = images.to(device, non_blocking=True)
        targets = targets.to(device, non_blocking=True)
        logits = model(images)
        pred = logits.argmax(dim=1)
        total += targets.numel()
        correct += int((pred == targets).sum().item())
        for idx in range(len(EXPECTED_CLASSES)):
            mask = targets == idx
            class_total[idx] += int(mask.sum().item())
            class_correct[idx] += int(((pred == idx) & mask).sum().item())
        logits_all.append(logits.detach().cpu())
        targets_all.append(targets.detach().cpu())

    recalls = {
        EXPECTED_CLASSES[idx]: (
            float(class_correct[idx] / class_total[idx]) if class_total[idx] else 0.0
        )
        for idx in range(len(EXPECTED_CLASSES))
    }
    return {
        "accuracy": float(correct / total) if total else 0.0,
        "macro_recall": float(np.mean(list(recalls.values()))) if recalls else 0.0,
        "per_class_recall": recalls,
        "logits": torch.cat(logits_all) if logits_all else torch.empty((0, len(EXPECTED_CLASSES))),
        "targets": torch.cat(targets_all) if targets_all else torch.empty((0,), dtype=torch.long),
    }


def fit_temperature(logits: torch.Tensor, targets: torch.Tensor) -> float:
    if logits.numel() == 0:
        return 1.0
    temperature = nn.Parameter(torch.ones(1))
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.LBFGS([temperature], lr=0.05, max_iter=50)

    def closure():
        optimizer.zero_grad()
        safe_temp = temperature.clamp(0.25, 10.0)
        loss = criterion(logits / safe_temp, targets)
        loss.backward()
        return loss

    optimizer.step(closure)
    return float(temperature.detach().clamp(0.25, 10.0).item())


class TemperatureScaledModel(nn.Module):
    def __init__(self, model: nn.Module, temperature: float):
        super().__init__()
        self.model = model
        self.register_buffer("temperature", torch.tensor(float(temperature), dtype=torch.float32))

    def forward(self, x):
        return self.model(x) / self.temperature


def main() -> None:
    parser = argparse.ArgumentParser(description="Train GreenAfrica PET material classifier")
    parser.add_argument("--data", required=True, help="Root containing train/val/test class directories")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--patience", type=int, default=12)
    parser.add_argument("--seed", type=int, default=419797)
    parser.add_argument("--output", default="artifacts/classifier")
    parser.add_argument("--version", required=True)
    args = parser.parse_args()

    seed_everything(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    classes, class_weights, train_loader, val_loader, test_loader = build_loaders(
        Path(args.data).resolve(), args.image_size, args.batch, args.workers
    )
    model = build_model(len(classes)).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights.to(device), label_smoothing=0.05)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(1, args.epochs))

    best_score = -math.inf
    best_path = output_dir / "best_classifier.pt"
    stale = 0
    history: list[dict] = []

    for epoch in range(1, args.epochs + 1):
        model.train()
        running_loss = 0.0
        samples = 0
        for images, targets in train_loader:
            images = images.to(device, non_blocking=True)
            targets = targets.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            logits = model(images)
            loss = criterion(logits, targets)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            optimizer.step()
            running_loss += float(loss.item()) * targets.numel()
            samples += targets.numel()
        scheduler.step()

        val = evaluate(model, val_loader, device)
        score = val["macro_recall"]
        row = {
            "epoch": epoch,
            "train_loss": running_loss / max(1, samples),
            "val_accuracy": val["accuracy"],
            "val_macro_recall": val["macro_recall"],
            "lr": optimizer.param_groups[0]["lr"],
        }
        history.append(row)
        print(json.dumps(row))

        if score > best_score + 1e-5:
            best_score = score
            stale = 0
            torch.save({"state_dict": model.state_dict(), "classes": classes, "version": args.version}, best_path)
        else:
            stale += 1
            if stale >= args.patience:
                break

    checkpoint = torch.load(best_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["state_dict"])
    val = evaluate(model, val_loader, device)
    temperature = fit_temperature(val["logits"], val["targets"])
    calibrated = TemperatureScaledModel(model, temperature).to(device).eval()
    test = evaluate(calibrated, test_loader, device)

    onnx_path = output_dir / "pet_material_classifier.onnx"
    dummy = torch.randn(1, 3, args.image_size, args.image_size, device=device)
    torch.onnx.export(
        calibrated,
        dummy,
        str(onnx_path),
        input_names=["images"],
        output_names=["logits"],
        opset_version=17,
        do_constant_folding=True,
        dynamic_axes=None,
    )

    metadata = {
        "version": args.version,
        "classes": classes,
        "seed": args.seed,
        "image_size": args.image_size,
        "temperature": temperature,
        "best_val_macro_recall": best_score,
        "test_accuracy": test["accuracy"],
        "test_macro_recall": test["macro_recall"],
        "test_per_class_recall": test["per_class_recall"],
        "onnx": str(onnx_path),
        "history": history,
    }
    (output_dir / "classifier_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (output_dir / "classes.json").write_text(json.dumps(classes, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in metadata.items() if k != "history"}, indent=2))


if __name__ == "__main__":
    main()
