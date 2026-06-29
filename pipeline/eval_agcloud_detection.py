"""
Standalone offline evaluation of the AgCloud detection model (yolov8-fruits.pt)
against the LaboroTomato COCO-format test set.

No MinIO / Kafka / MQTT — detector only.

Scoring is class-agnostic by default: GT boxes (6 tomato ripeness classes) and
predicted boxes (80 COCO classes) are both collapsed to category_id=1. This fairly
measures localisation even though "tomato" is not in the model's label set.

Usage (run from repo root):
    python pipeline/eval_agcloud_detection.py
    python pipeline/eval_agcloud_detection.py --limit 10 --visualize 5
    python pipeline/eval_agcloud_detection.py --conf 0.25 --out my_eval_out/
"""

import argparse
import csv
import json
import os
import time
from pathlib import Path

import cv2
import numpy as np
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval
from ultralytics import YOLO


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--weights",    default="yolov8-fruits.pt",
                   help="Path to YOLO weights (relative to repo root)")
    p.add_argument("--images",     default="images/laboro_tomato/test",
                   help="Directory of test images")
    p.add_argument("--ann",        default="images/laboro_tomato/annotations/test.json",
                   help="COCO-format ground-truth JSON")
    p.add_argument("--conf",       type=float, default=0.001,
                   help="Detection confidence threshold (low = full PR curve)")
    p.add_argument("--iou",        type=float, default=0.6,
                   help="NMS IoU threshold")
    p.add_argument("--out",        default="eval_out",
                   help="Output directory for metrics and demo images")
    p.add_argument("--limit",      type=int, default=0,
                   help="Process only the first N images (0 = all)")
    p.add_argument("--visualize",  type=int, default=0,
                   help="Save annotated demo images for the first N images (0 = none)")
    return p.parse_args()


# ---------------------------------------------------------------------------
# COCO helpers
# ---------------------------------------------------------------------------

SUPPORTED_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def build_agnostic_gt(coco_gt: COCO):
    """Return a new COCO object with all categories collapsed to id=1."""
    data = {
        "info": {},
        "licenses": [],
        "images": coco_gt.dataset["images"],
        "categories": [{"id": 1, "name": "object", "supercategory": "object"}],
        "annotations": [
            {**ann, "category_id": 1}
            for ann in coco_gt.dataset["annotations"]
        ],
    }
    coco_agnostic = COCO()
    coco_agnostic.dataset = data
    coco_agnostic.createIndex()
    return coco_agnostic


def xywh_clip(x, y, w, h, img_w, img_h):
    """Clip COCO xywh box to image bounds (avoid COCO eval warnings)."""
    x = max(0.0, float(x))
    y = max(0.0, float(y))
    w = min(float(w), img_w - x)
    h = min(float(h), img_h - y)
    return x, y, max(w, 0.0), max(h, 0.0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    out_dir = Path(args.out)
    demo_dir = out_dir / "demo"
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.visualize > 0:
        demo_dir.mkdir(parents=True, exist_ok=True)

    # --- Load model ---
    print(f"Loading model: {args.weights}")
    model = YOLO(args.weights)
    class_names = model.names
    print(f"  Model classes ({len(class_names)}): {list(class_names.values())[:10]} ...")

    # --- Load ground truth ---
    print(f"Loading ground truth: {args.ann}")
    coco_gt_orig = COCO(args.ann)
    coco_gt = build_agnostic_gt(coco_gt_orig)

    gt_images = coco_gt_orig.dataset["images"]
    if args.limit > 0:
        gt_images = gt_images[:args.limit]

    img_dir = Path(args.images)

    # Build file_name → image record lookup
    fname_to_img = {img["file_name"]: img for img in coco_gt_orig.dataset["images"]}

    print(f"\nRunning inference on {len(gt_images)} images (conf={args.conf}) ...\n")

    dt_list = []          # COCO detection results
    per_image_rows = []   # for per_image.csv
    latencies_ms = []
    total_preds = 0
    images_with_detections = 0

    for idx, img_info in enumerate(gt_images):
        fname = img_info["file_name"]
        image_id = img_info["id"]
        img_path = img_dir / fname
        if not img_path.exists():
            print(f"  [SKIP] not found: {img_path}")
            continue

        img_bgr = cv2.imread(str(img_path))
        if img_bgr is None:
            print(f"  [SKIP] could not read: {img_path}")
            continue

        img_h, img_w = img_bgr.shape[:2]

        t0 = time.perf_counter()
        results = model.predict(img_bgr, conf=args.conf, iou=args.iou, verbose=False)
        latency_ms = (time.perf_counter() - t0) * 1000
        latencies_ms.append(latency_ms)

        result = results[0]
        boxes = result.boxes

        n_pred = len(boxes)
        max_conf = float(boxes.conf.max()) if n_pred > 0 else 0.0
        total_preds += n_pred
        if n_pred > 0:
            images_with_detections += 1

        # GT count for this image
        ann_ids = coco_gt_orig.getAnnIds(imgIds=[image_id])
        n_gt = len(ann_ids)

        per_image_rows.append({
            "file_name": fname,
            "image_id": image_id,
            "n_gt": n_gt,
            "n_pred": n_pred,
            "max_conf": round(max_conf, 4),
            "latency_ms": round(latency_ms, 1),
        })

        # Accumulate COCO detection results (class-agnostic: category_id=1)
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            bw, bh = x2 - x1, y2 - y1
            bx, by, bw, bh = xywh_clip(x1, y1, bw, bh, img_w, img_h)
            dt_list.append({
                "image_id": image_id,
                "category_id": 1,
                "bbox": [bx, by, bw, bh],
                "score": float(box.conf[0]),
            })

        # Visualise demo images
        if args.visualize > 0 and idx < args.visualize:
            annotated = result.plot()  # model predictions (ultralytics built-in)

            # Overlay GT boxes in green
            for ann in coco_gt_orig.loadAnns(ann_ids):
                gx, gy, gw, gh = [int(v) for v in ann["bbox"]]
                cat_name = coco_gt_orig.cats[ann["category_id"]]["name"]
                cv2.rectangle(annotated, (gx, gy), (gx + gw, gy + gh), (0, 255, 0), 2)
                cv2.putText(annotated, f"GT:{cat_name}", (gx, max(gy - 6, 0)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)

            demo_path = demo_dir / (Path(fname).stem + "_eval.jpg")
            cv2.imwrite(str(demo_path), annotated)

        if (idx + 1) % 20 == 0 or (idx + 1) == len(gt_images):
            print(f"  {idx+1}/{len(gt_images)} — last latency {latency_ms:.0f} ms")

    # ---------------------------------------------------------------------------
    # COCO eval (class-agnostic)
    # ---------------------------------------------------------------------------
    print("\nRunning COCOeval ...")

    if dt_list:
        coco_dt = coco_gt.loadRes(dt_list)
        evaluator = COCOeval(coco_gt, coco_dt, "bbox")
        evaluator.evaluate()
        evaluator.accumulate()
        evaluator.summarize()
        stats = evaluator.stats  # 12-element array
    else:
        print("  No predictions — all COCO metrics are 0.")
        stats = [0.0] * 12

    map50        = float(stats[1])
    map50_95     = float(stats[0])
    ar_max1      = float(stats[6])
    ar_max10     = float(stats[7])

    mean_lat = float(np.mean(latencies_ms)) if latencies_ms else 0.0
    success_rate = images_with_detections / len(gt_images) if gt_images else 0.0

    # Simple precision / recall at conf=0.25 as a demo-friendly summary
    # (re-run a quick count at a practical threshold)
    tp_count = 0
    fp_count = 0
    iou_thresh = 0.5
    practical_conf = 0.25
    matched_ann = set()

    for img_info in gt_images:
        image_id = img_info["id"]
        ann_ids = coco_gt_orig.getAnnIds(imgIds=[image_id])
        anns = coco_gt_orig.loadAnns(ann_ids)
        gt_boxes = [a["bbox"] for a in anns]  # xywh

        img_preds = [d for d in dt_list if d["image_id"] == image_id and d["score"] >= practical_conf]
        img_preds_sorted = sorted(img_preds, key=lambda x: -x["score"])

        matched_gt = set()
        for pred in img_preds_sorted:
            px, py, pw, ph = pred["bbox"]
            px2, py2 = px + pw, py + ph
            best_iou, best_j = 0.0, -1
            for j, gt_b in enumerate(gt_boxes):
                if j in matched_gt:
                    continue
                gx, gy, gw, gh = gt_b
                gx2, gy2 = gx + gw, gy + gh
                ix = max(0, min(px2, gx2) - max(px, gx))
                iy = max(0, min(py2, gy2) - max(py, gy))
                inter = ix * iy
                union = pw * ph + gw * gh - inter
                iou = inter / union if union > 0 else 0.0
                if iou > best_iou:
                    best_iou, best_j = iou, j
            if best_iou >= iou_thresh and best_j >= 0:
                tp_count += 1
                matched_gt.add(best_j)
            else:
                fp_count += 1

    total_gt = sum(len(coco_gt_orig.getAnnIds(imgIds=[i["id"]])) for i in gt_images)
    fn_count = total_gt - tp_count
    precision = tp_count / (tp_count + fp_count) if (tp_count + fp_count) > 0 else 0.0
    recall    = tp_count / (tp_count + fn_count) if (tp_count + fn_count) > 0 else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # ---------------------------------------------------------------------------
    # Print summary (the "batch efficacy numbers" for the demo)
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("  AGCLOUD DETECTION MODEL — LaboroTomato Eval Summary")
    print("=" * 60)
    print(f"  Model              : {args.weights}")
    print(f"  Dataset            : {args.images} ({len(gt_images)} images)")
    print(f"  Scoring            : class-agnostic (all GT → object, all preds → object)")
    print(f"  Note               : model has no 'tomato' class (COCO 80); measures localisation")
    print()
    print(f"  mAP@0.5            : {map50:.4f}")
    print(f"  mAP@0.5:0.95       : {map50_95:.4f}")
    print(f"  AR@1               : {ar_max1:.4f}")
    print(f"  AR@10              : {ar_max10:.4f}")
    print()
    print(f"  Precision @conf≥0.25, IoU≥0.5 : {precision:.4f}")
    print(f"  Recall    @conf≥0.25, IoU≥0.5 : {recall:.4f}")
    print(f"  F1                             : {f1:.4f}")
    print()
    print(f"  Total images       : {len(gt_images)}")
    print(f"  Images w/ ≥1 det.  : {images_with_detections}  ({success_rate*100:.1f}% success rate)")
    print(f"  Total predictions  : {total_preds}")
    print(f"  Total GT boxes     : {total_gt}")
    print(f"  Mean latency       : {mean_lat:.1f} ms/image")
    print("=" * 60)

    # ---------------------------------------------------------------------------
    # Write outputs
    # ---------------------------------------------------------------------------
    metrics = {
        "model": args.weights,
        "dataset": args.images,
        "n_images": len(gt_images),
        "model_classes": list(class_names.values()),
        "scoring": "class-agnostic",
        "conf_threshold_mAP": args.conf,
        "conf_threshold_prf": practical_conf,
        "iou_threshold_prf": iou_thresh,
        "mAP_0_5": round(map50, 4),
        "mAP_0_5_0_95": round(map50_95, 4),
        "AR_max1": round(ar_max1, 4),
        "AR_max10": round(ar_max10, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "success_rate": round(success_rate, 4),
        "total_predictions": total_preds,
        "total_gt_boxes": total_gt,
        "mean_latency_ms_per_image": round(mean_lat, 1),
    }

    metrics_path = out_dir / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\n  Metrics written  : {metrics_path}")

    matrix_path = out_dir / "matrix_row.csv"
    with open(matrix_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "model", "dataset", "n_images", "scoring",
            "mAP@0.5", "mAP@0.5:0.95", "precision", "recall", "f1",
            "success_rate", "latency_ms_per_img",
        ])
        writer.writeheader()
        writer.writerow({
            "model": args.weights,
            "dataset": "LaboroTomato/test",
            "n_images": len(gt_images),
            "scoring": "class-agnostic",
            "mAP@0.5": round(map50, 4),
            "mAP@0.5:0.95": round(map50_95, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "success_rate": round(success_rate, 4),
            "latency_ms_per_img": round(mean_lat, 1),
        })
    print(f"  Matrix row       : {matrix_path}")

    per_img_path = out_dir / "per_image.csv"
    with open(per_img_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["file_name", "image_id", "n_gt", "n_pred", "max_conf", "latency_ms"])
        writer.writeheader()
        writer.writerows(per_image_rows)
    print(f"  Per-image CSV    : {per_img_path}")

    if args.visualize > 0:
        print(f"  Demo images      : {demo_dir}/  ({min(args.visualize, len(gt_images))} saved)")

    print()


if __name__ == "__main__":
    main()
