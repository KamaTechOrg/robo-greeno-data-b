"""
Zero-shot transfer test: does best_conditional.pt generalise to tomatoes?

The ripeness model was trained on apple/banana/orange/pineapple.
This script evaluates it on LaboroTomato using GT bounding boxes to crop
tomatoes directly (bypassing YOLO), then compares predicted ripeness to
the mapped ground-truth ripeness label.

GT → ripeness mapping:
  b_green / l_green          → unripe
  b_half_ripened / l_half_ripened → ripe
  b_fully_ripened / l_fully_ripened → ripe   (fully ripe, not overripe)

NOTE: "overripe" has zero GT samples in LaboroTomato; per-class metrics
handle this safely without division errors.

Usage (run from repo root):
    python pipeline/eval_ripeness_model.py
    python pipeline/eval_ripeness_model.py --limit 20 --fruit apple
    python pipeline/eval_ripeness_model.py --all-fruits
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from pycocotools.coco import COCO
from torchvision import transforms
from torchvision.models import MobileNet_V3_Large_Weights, mobilenet_v3_large

# ---------------------------------------------------------------------------
# Model definition (copied from pipeline_using_agcloud_models.py:118-141
# to avoid that file's import-time MinIO / YOLO side-effects)
# ---------------------------------------------------------------------------

RIPENESS_FRUITS = ["apple", "banana", "orange", "pineapple"]
RIPENESS_LABELS = ["unripe", "ripe", "overripe"]

DEVICE = "cpu"

ROTTEN_TRANSFORM = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225],
    ),
])

# LaboroTomato 6-class → ripeness label mapping
GT_CLASS_TO_RIPENESS = {
    "b_green":          "unripe",
    "l_green":          "unripe",
    "b_half_ripened":   "ripe",
    "l_half_ripened":   "ripe",
    "b_fully_ripened":  "ripe",
    "l_fully_ripened":  "ripe",
}


class RipenessModelConditional(nn.Module):
    def __init__(self, num_ripeness: int, num_fruits: int, embed_dim: int = 16):
        super().__init__()
        weights = MobileNet_V3_Large_Weights.IMAGENET1K_V2
        self.backbone = mobilenet_v3_large(weights=weights)
        in_feats = self.backbone.classifier[-1].in_features
        self.backbone.classifier[-1] = nn.Identity()
        self.fruit_embed = nn.Embedding(num_fruits, embed_dim)
        self.head = nn.Linear(in_feats + embed_dim, num_ripeness)

    def forward(self, x, fruit_idx):
        feats = self.backbone(x)
        fvec = self.fruit_embed(fruit_idx)
        return self.head(torch.cat([feats, fvec], dim=1))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_model(weights_path: str) -> RipenessModelConditional:
    model = RipenessModelConditional(
        num_ripeness=len(RIPENESS_LABELS),
        num_fruits=len(RIPENESS_FRUITS),
    )
    state_dict = torch.load(weights_path, map_location=DEVICE)
    model.load_state_dict(state_dict)
    model.eval()
    return model


def crop_from_gt(img_bgr: np.ndarray, bbox_xywh: list) -> np.ndarray | None:
    """Crop a bounding box (COCO xywh) from a BGR image. Returns None if degenerate."""
    x, y, w, h = [int(v) for v in bbox_xywh]
    x = max(0, x)
    y = max(0, y)
    x2 = min(x + w, img_bgr.shape[1])
    y2 = min(y + h, img_bgr.shape[0])
    if x2 <= x or y2 <= y:
        return None
    return img_bgr[y:y2, x:x2]


def predict_ripeness(model: RipenessModelConditional, crop_bgr: np.ndarray, fruit_label: str):
    """Run ripeness inference on a BGR crop array. Returns (label, confidence)."""
    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(crop_rgb)           # PIL for torchvision transforms
    tensor = ROTTEN_TRANSFORM(pil_img).unsqueeze(0).to(DEVICE)
    fruit_idx = torch.tensor([RIPENESS_FRUITS.index(fruit_label)]).to(DEVICE)

    with torch.no_grad():
        logits = model(tensor, fruit_idx)
        probs = F.softmax(logits, dim=1)
        pred_idx = int(torch.argmax(probs, dim=1).item())
        confidence = float(probs[0][pred_idx].item())

    return RIPENESS_LABELS[pred_idx], confidence


def print_results(fruit_label: str, records: list):
    """
    records: list of {"gt_class", "gt_ripeness", "pred_ripeness", "confidence"}
    Handles zero-sample classes safely.
    """
    print(f"\n{'='*60}")
    print(f"  Fruit surrogate used: {fruit_label}")
    print(f"  Total crops evaluated: {len(records)}")
    print(f"{'='*60}")

    # Overall accuracy
    correct = sum(1 for r in records if r["pred_ripeness"] == r["gt_ripeness"])
    total = len(records)
    acc = correct / total if total > 0 else 0.0
    print(f"\n  Overall accuracy: {correct}/{total} = {acc:.1%}")

    # Per GT class breakdown
    print("\n  Per GT-class breakdown:")
    by_class = defaultdict(list)
    for r in records:
        by_class[r["gt_class"]].append(r)

    print(f"  {'GT class':<22} {'GT ripeness':<12} {'n':>5}  {'correct':>8}  {'acc':>7}")
    print(f"  {'-'*22} {'-'*12} {'-'*5}  {'-'*8}  {'-'*7}")
    for cls in sorted(by_class):
        rows = by_class[cls]
        gt_rip = GT_CLASS_TO_RIPENESS[cls]
        n = len(rows)
        c = sum(1 for r in rows if r["pred_ripeness"] == gt_rip)
        a = c / n if n > 0 else 0.0
        print(f"  {cls:<22} {gt_rip:<12} {n:>5}  {c:>8}  {a:>7.1%}")

    # Confusion matrix (pred × gt, only for classes with ≥1 sample)
    used_labels = [l for l in RIPENESS_LABELS
                   if any(r["gt_ripeness"] == l for r in records)]
    print("\n  Confusion matrix (rows=predicted, cols=GT):")
    header = f"  {'pred \\ gt':<12}" + "".join(f"{l:>12}" for l in used_labels)
    print(header)
    for pred_l in RIPENESS_LABELS:
        row_vals = []
        for gt_l in used_labels:
            count = sum(1 for r in records
                        if r["pred_ripeness"] == pred_l and r["gt_ripeness"] == gt_l)
            row_vals.append(count)
        if any(v > 0 for v in row_vals) or pred_l in used_labels:
            print(f"  {pred_l:<12}" + "".join(f"{v:>12}" for v in row_vals))

    # Mean confidence
    mean_conf = float(np.mean([r["confidence"] for r in records])) if records else 0.0
    print(f"\n  Mean confidence: {mean_conf:.3f}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_eval(model, coco_gt, img_dir, fruit_label, limit=0):
    images = coco_gt.dataset["images"]
    if limit > 0:
        images = images[:limit]

    id_to_catname = {c["id"]: c["name"] for c in coco_gt.dataset["categories"]}
    records = []
    skipped = 0

    for img_info in images:
        img_path = img_dir / img_info["file_name"]
        if not img_path.exists():
            skipped += 1
            continue

        img_bgr = cv2.imread(str(img_path))
        if img_bgr is None:
            skipped += 1
            continue

        ann_ids = coco_gt.getAnnIds(imgIds=[img_info["id"]])
        anns = coco_gt.loadAnns(ann_ids)

        for ann in anns:
            cat_name = id_to_catname[ann["category_id"]]
            gt_ripeness = GT_CLASS_TO_RIPENESS.get(cat_name)
            if gt_ripeness is None:
                continue  # unknown GT class, skip

            crop = crop_from_gt(img_bgr, ann["bbox"])
            if crop is None:
                continue

            pred_label, confidence = predict_ripeness(model, crop, fruit_label)
            records.append({
                "gt_class": cat_name,
                "gt_ripeness": gt_ripeness,
                "pred_ripeness": pred_label,
                "confidence": confidence,
            })

    if skipped > 0:
        print(f"  [info] skipped {skipped} images (file not found / unreadable)")

    return records


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--weights",    default="best_conditional.pt")
    p.add_argument("--images",     default="images/laboro_tomato/test")
    p.add_argument("--ann",        default="images/laboro_tomato/annotations/test.json")
    p.add_argument("--fruit",      default="apple",
                   choices=RIPENESS_FRUITS,
                   help="Fruit label to pass as surrogate for tomato")
    p.add_argument("--all-fruits", action="store_true",
                   help="Run once per supported fruit label and compare all")
    p.add_argument("--limit",      type=int, default=0,
                   help="Process only the first N images (0 = all)")
    p.add_argument("--out",        default="eval_out")
    args = p.parse_args()

    # Check weights exist
    if not Path(args.weights).exists():
        print(f"ERROR: {args.weights} not found. Must run from repo root.")
        sys.exit(1)

    print(f"Loading model: {args.weights}")
    model = load_model(args.weights)

    print(f"Loading ground truth: {args.ann}")
    coco_gt = COCO(args.ann)

    img_dir = Path(args.images)
    fruits_to_test = RIPENESS_FRUITS if args.all_fruits else [args.fruit]

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_results = {}
    for fruit_label in fruits_to_test:
        print(f"\nRunning with fruit surrogate: {fruit_label} ...")
        records = run_eval(model, coco_gt, img_dir, fruit_label, args.limit)
        print_results(fruit_label, records)
        correct = sum(1 for r in records if r["pred_ripeness"] == r["gt_ripeness"])
        all_results[fruit_label] = {
            "total_crops": len(records),
            "correct": correct,
            "accuracy": round(correct / len(records), 4) if records else 0.0,
            "mean_confidence": round(float(np.mean([r["confidence"] for r in records])), 4) if records else 0.0,
        }

    # Summary across fruits if --all-fruits
    if args.all_fruits:
        print(f"\n{'='*60}")
        print("  Summary: accuracy by fruit surrogate")
        print(f"{'='*60}")
        for fl, res in sorted(all_results.items(), key=lambda x: -x[1]["accuracy"]):
            print(f"  {fl:<12}  acc={res['accuracy']:.1%}  mean_conf={res['mean_confidence']:.3f}  n={res['total_crops']}")
        best = max(all_results, key=lambda k: all_results[k]["accuracy"])
        print(f"\n  Best surrogate: {best} (acc={all_results[best]['accuracy']:.1%})")

    # Write JSON output
    out = {
        "model": args.weights,
        "dataset": args.images,
        "scoring": "zero-shot transfer, GT crops, class-mapped ripeness",
        "gt_class_to_ripeness": GT_CLASS_TO_RIPENESS,
        "limit": args.limit,
        "results_by_fruit": all_results,
    }
    out_path = out_dir / "ripeness_metrics.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n  Metrics written: {out_path}\n")


if __name__ == "__main__":
    main()
