# Running `pipeline_using_agcloud_models.py`

This is the **real-model** batch pipeline. It reads images from a folder, gates them
through the IQA quality check, runs **YOLOv8 fruit detection**, then for each detected
fruit it saves a crop, uploads it to **MinIO**, calls the **AgCloud defect service**, and
runs the **conditional ripeness** PyTorch model. The result is assembled into the AgCloud
JSON payload and printed to stdout.

> Contrast with [`mock_pipeline_flow.py`](mock_pipeline_flow.py), which uses a stub detector and
> no external services. Use that one if you just want to exercise the IQA gate and payload shape.

---

## What the script actually does

```
images/ (FolderSource)
  └─ for each image:
       IQA gate (frame_quality/iqa_gate.py)
         │  status OK / Borderline → continue;  FAILED → skip detection
         ▼
       YOLOv8 detection (yolov8-fruits.pt), conf ≥ 0.3, fruit labels only
         │  for each crop:
         │    1. save  → pipeline/storage/runs/<run_id>/crops/crop_<i>.jpg
         │    2. upload → MinIO  imagery/pipeline/<run_id>/crops/crop_<i>.jpg
         │    3. defect → POST http://localhost:8011/infer_json  {bucket, key}
         │    4. ripeness → best_conditional.pt  (apple/banana/orange/pineapple)
         ▼
       build JSON payload  →  print(json.dumps(...))
```

> **Known gap — MQTT is not wired in yet.** The script prints `"Building MQTT payload..."`
> and builds the dict via `build_json()`, but it **never publishes to an MQTT broker**. The
> payload is only printed to the console. Wiring an actual MQTT publish (topic
> `MQTT/vision/detections`) is a TODO. See [Known limitations](#known-limitations--gotchas).

---

## Prerequisites

### 1. Python environment + dependencies

Python 3.10+ (the repo's bytecode caches were built with 3.12). The full pipeline needs
more than the edge requirements file lists, so install this set:

```bash
pip install opencv-python torch torchvision pyiqa ultralytics minio requests pillow numpy
```

| Package        | Used for                                         |
|----------------|--------------------------------------------------|
| `opencv-python`| frame reading, crop saving (`cv2`)               |
| `torch`, `torchvision` | ripeness model + IQA backbone            |
| `pyiqa`        | BRISQUE / NIQE metrics in the IQA gate           |
| `ultralytics`  | YOLOv8 fruit detector                            |
| `minio`        | uploading crops to object storage                |
| `requests`     | calling the defect service                       |
| `pillow`, `numpy` | image conversion / array handling             |

> First run downloads the MobileNetV3 ImageNet weights (for the ripeness backbone) and any
> `pyiqa` metric weights, so you need internet access on first launch.

### 2. Model weights (gitignored — obtain separately)

Both `.pt` files are excluded by `.gitignore` and are **expected at the repository root**
(the script loads them by relative path, so it must be launched from the repo root — see
[How to run](#how-to-run)):

| File                 | What it is                                                        | Source |
|----------------------|-------------------------------------------------------------------|--------|
| `yolov8-fruits.pt`   | YOLOv8 fruit detector weights                                      | _**<FILL IN: shared drive / release link>**_ |
| `best_conditional.pt`| Conditional ripeness model (MobileNetV3 backbone + fruit embedding + ripeness head) | Produced by AgCloud's ripeness training: `services/fruit-orchestration/services/ripeness/model/training/train_conditional.py`. Get the trained checkpoint from _**<FILL IN: shared drive / release link>**_ |

> If `best_conditional.pt` is missing the script prints a warning and continues with
> **randomly-initialised** ripeness weights (predictions will be meaningless). If
> `yolov8-fruits.pt` is missing the script **fails at startup**.

### 3. An `images/` folder

`FolderSource("images")` reads from an `images/` directory **relative to the current working
directory** (i.e. `./images` when run from the repo root). It is not committed — create it
and drop in test images:

```bash
mkdir images
# copy some .jpg/.jpeg/.png/.bmp/.webp files into ./images
```

Supported extensions: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.webp`. The script processes every
image once, in sorted filename order, then exits.

### 4. AgCloud services (minimal set)

This script only talks to **two** AgCloud services. You do **not** need the full stack
(Kafka/Flink/Postgres/MQTT). Start just these from the AgCloud repo's root
`docker-compose.yml`:

| Service                 | Compose name           | Port (host) | Used by the script as              |
|-------------------------|------------------------|-------------|------------------------------------|
| Hot object storage      | `minio-hot`            | `9000`      | `localhost:9000` (S3 API)          |
| Fruit defect inference  | `fruit-inference-http` | `8011`      | `http://localhost:8011/infer_json` |

```bash
# from the AgCloud-main repo root
docker compose up -d minio-hot fruit-inference-http
```

Credentials are hard-coded in the script and match AgCloud defaults:

- MinIO endpoint `localhost:9000`, access key `minioadmin`, secret key `minioadmin123`, `secure=False`
- The `imagery` bucket is **created automatically** by the script if it doesn't exist.
- `fruit-inference-http` runs with `TEAM=fruit` and is published on `8011:8004`. It reads the
  uploaded crop back out of MinIO by `{bucket, key}`, so MinIO must be reachable from that
  container (it is, on the `ag_cloud` docker network).

> **The defect service is effectively optional.** If `localhost:8011` is down, `call_defect_model()`
> catches the error and the crop's `defect_result` becomes `{"error": "..."}` — the rest of the
> pipeline (detection + ripeness) still runs and still prints a payload.

---

## How to run

Run **from the repository root** (not from inside `pipeline/`). This matters for three reasons:

1. The imports are package-relative (`frame_quality.iqa_gate`, `frame_source.folder_source`,
   `models.frame`) and resolve against the repo root.
2. The weights `yolov8-fruits.pt` / `best_conditional.pt` are loaded by relative path.
3. `FolderSource("images")` resolves `./images` from the current directory.

```bash
# repo root: .../robo-greeno-data-b
python -m pipeline.pipeline_using_agcloud_models
```

(or `python pipeline/pipeline_using_agcloud_models.py` — both work as long as you're in the
repo root and it's on `PYTHONPATH`; if you hit a `ModuleNotFoundError`, set
`PYTHONPATH=.` first: `set PYTHONPATH=.` on Windows / `export PYTHONPATH=.` on bash).

You should see, per image:

```
Loading Models...
Running IQA...
Running detection...
Building MQTT payload...

Pipeline Output:
{
    "frame_id": 0,
    "timestamp": 1718370000.123,
    "source": "images/strawberry_01.jpg",
    "image_quality": { "status": "OK", "reason": "OK", "metrics": { ... } },
    "detection": {
        "run_id": "....",
        "total_fruits": 1,
        "results": [ { "label": "apple", "ripeness_result": { ... }, "defect_result": { ... } } ]
    },
    "detection_error": null
}
```

Crops are written under [`pipeline/storage/runs/<run_id>/crops/`](storage/runs/) and uploaded to
MinIO under `imagery/pipeline/<run_id>/crops/`.

---

## Verifying it worked

- **Console**: each image prints a JSON block with `image_quality`, and (if quality passed) a
  `detection` object listing fruits with `ripeness_result` and `defect_result`.
- **MinIO console**: browse http://localhost:9001 (login `minioadmin` / `minioadmin123`) →
  bucket `imagery` → `pipeline/<run_id>/crops/` should contain the uploaded crops.
- **Local disk**: `pipeline/storage/runs/<run_id>/crops/` mirrors the uploaded crops.

---

## Known limitations & gotchas

1. **MQTT publishing is not implemented.** The payload is only printed. To actually deliver to
   AgCloud you'd add a publish to topic `MQTT/vision/detections` after `build_json()` in
   `run_pipeline()`. (The AgCloud `mqtt_gateway` then forwards MQTT → Kafka.)

2. **IQA thresholds fall back to defaults.** `IQAGate` looks for `IQA_thresholds.json` in the
   *current working directory*, but the only copy lives in `frame_quality/IQA_thresholds.json`.
   Run from the repo root and the gate silently uses built-in default thresholds (it prints
   `Warning: Config file IQA_thresholds.json not found. Using defaults.`). To use the tuned
   thresholds, copy that file to the directory you launch from, or pass an explicit path.

3. **IQA never returns "Borderline" as a status.** `run_iqa()` collapses the gate result to
   `"OK"` (pass) or `"FAILED"` (fail). The `run_pipeline()` check for `"Borderline"` is dead
   code — borderline images are already reported as `OK` by `iqa_gate.evaluate()`.

4. **Ripeness supports only 4 fruits.** `apple`, `banana`, `orange`, `pineapple`. Any other
   detected fruit gets `ripeness_label: "unknown"`. Note `pineapple` is in the ripeness list but
   **not** in `YOLO_FRUIT_LABELS`, so YOLO won't actually surface pineapples to the ripeness model.

5. **CPU only.** `DEVICE = "cpu"` is hard-coded for the ripeness model (the IQA gate will use CUDA
   if available). Fine for laptop testing; revisit for throughput.

6. **Hard-coded localhost endpoints.** MinIO (`localhost:9000`) and the defect service
   (`localhost:8011`) are constants in the file. Change them there if your services run elsewhere.

---

## Quick troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| `ModuleNotFoundError: frame_quality` | Not running from the repo root. `cd` to repo root and use `python -m pipeline.pipeline_using_agcloud_models`, or set `PYTHONPATH=.`. |
| Startup crash loading YOLO | `yolov8-fruits.pt` missing from repo root. |
| `Warning: best_conditional.pt not found` | Ripeness checkpoint missing → predictions are random. Obtain the weight file. |
| `MaxRetryError` / connection refused on startup | MinIO not running on `localhost:9000`. `docker compose up -d minio-hot`. |
| Every `defect_result` is `{"error": ...}` | `fruit-inference-http` not up on `localhost:8011`, or it can't reach MinIO. `docker compose up -d fruit-inference-http`. |
| No `detection` in output, `detection_error: "Skipped due to IQA failure"` | Image failed the quality gate (too dark/bright/blurry). Use clearer images or tune thresholds. |
| `total_fruits: 0` | YOLO found nothing above conf 0.3, or labels weren't in `YOLO_FRUIT_LABELS`. |
