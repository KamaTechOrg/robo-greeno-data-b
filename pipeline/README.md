# Running `pipeline_using_agcloud_models.py`

This is the **real-model** batch pipeline. It reads images from a folder, gates them
through the IQA quality check, runs **YOLOv8 fruit detection**, then for each detected
fruit it saves a crop, uploads it to **MinIO**, calls the **AgCloud defect service**, and
runs the **conditional ripeness** PyTorch model. The result is assembled into the AgCloud
JSON payload, **published to MQTT**, and printed to stdout.

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
       build JSON payload
         ├─ publish → MQTT  topic MQTT/vision/detections  (best-effort)
         └─ print(json.dumps(...))
```

> The payload is published to the AgCloud MQTT broker (`mosquitto`, topic
> `MQTT/vision/detections`) **and** printed to the console. Publishing is **best-effort**: if no
> broker is reachable the script logs a warning and keeps running, so you can still use it
> standalone. See [MQTT publishing](#mqtt-publishing).

---

## Prerequisites

### 1. Python environment + dependencies

Python 3.10+ (the repo's bytecode caches were built with 3.12). The full pipeline needs
more than the edge requirements file lists, so install this set:

```bash
pip install opencv-python torch torchvision pyiqa ultralytics minio requests pillow numpy paho-mqtt
```

| Package        | Used for                                         |
|----------------|--------------------------------------------------|
| `opencv-python`| frame reading, crop saving (`cv2`)               |
| `torch`, `torchvision` | ripeness model + IQA backbone            |
| `pyiqa`        | BRISQUE / NIQE metrics in the IQA gate           |
| `ultralytics`  | YOLOv8 fruit detector                            |
| `minio`        | uploading crops to object storage                |
| `requests`     | calling the defect service                       |
| `paho-mqtt`    | publishing the result payload to MQTT            |
| `pillow`, `numpy` | image conversion / array handling             |

> First run downloads the MobileNetV3 ImageNet weights (for the ripeness backbone) and any
> `pyiqa` metric weights, so you need internet access on first launch.

> **Python version note.** Verified working on Python 3.12 **and** 3.14. On Python 3.14, `pip install
> pyiqa` may error while building the transitive `filterpy` dependency (`metadata-generation-failed`).
> That's harmless here — `filterpy` is **not** used by the BRISQUE/NIQE metrics this pipeline needs,
> and `import pyiqa` still works. If the error aborts the whole install, install the rest first and
> add pyiqa separately: `pip install pyiqa` (ignore the filterpy failure), or use a Python 3.11/3.12
> environment to avoid it entirely.

### 2. Model weights (gitignored — obtain separately)

Both `.pt` files are excluded by `.gitignore` and are **expected at the repository root**
(the script loads them by relative path, so it must be launched from the repo root — see
[How to run](#how-to-run)). Both ship inside the **AgCloud repo** — copy them over from there:

| File                 | What it is                                                        | Source (in the AgCloud repo) |
|----------------------|-------------------------------------------------------------------|--------|
| `yolov8-fruits.pt`   | YOLOv8 fruit detector weights                                      | `services/inference_http/weights/yolov8-fruits.pt` |
| `best_conditional.pt`| Conditional ripeness model (MobileNetV3 backbone + fruit embedding + ripeness head) | `services/ripeness-ml/checkpoints/mobilenet_v3_large/best_conditional.pt` (produced by AgCloud's `train_conditional.py`) |

Copy them to the repo root (adjust the AgCloud path to wherever you cloned it):

```bash
# AGCLOUD = path to your AgCloud-main checkout
AGCLOUD="/c/Users/user1/Downloads/AgCloud-main (1)/AgCloud-main"
cp "$AGCLOUD/services/inference_http/weights/yolov8-fruits.pt" .
cp "$AGCLOUD/services/ripeness-ml/checkpoints/mobilenet_v3_large/best_conditional.pt" .
```

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

This script talks to **three** AgCloud services. You do **not** need the full stack
(Kafka/Flink/Postgres). Start just these from the AgCloud repo's root `docker-compose.yml`:

| Service                 | Compose name           | Port (host) | Used by the script as              | Required? |
|-------------------------|------------------------|-------------|------------------------------------|-----------|
| Hot object storage      | `minio-hot`            | `9000`      | `localhost:9000` (S3 API)          | **Yes** — connected on startup |
| Fruit defect inference  | `fruit-inference-http` | `8011`      | `http://localhost:8011/infer_json` | Optional  |
| MQTT broker             | `mosquitto`            | `1883`      | `localhost:1883` (publish target)  | Optional  |

```bash
# from the AgCloud-main repo root
docker compose up -d minio-hot fruit-inference-http mosquitto
```

- **MinIO is mandatory.** The script calls `mc.bucket_exists()` at import time, so if MinIO is
  not up on `localhost:9000` it **crashes on startup** before processing anything.
- **The defect service is optional.** If `localhost:8011` is down, `call_defect_model()` catches
  the error and the crop's `defect_result` becomes `{"error": "..."}` — detection + ripeness still run.
- **The MQTT broker is optional.** Without it, publishing is skipped (warning logged) and the
  pipeline still runs and prints payloads. See [MQTT publishing](#mqtt-publishing).

Credentials are hard-coded in the script and match AgCloud defaults:

- MinIO endpoint `localhost:9000`, access key `minioadmin`, secret key `minioadmin123`, `secure=False`
- The `imagery` bucket is **created automatically** by the script if it doesn't exist.
- `fruit-inference-http` runs with `TEAM=fruit` and is published on `8011:8004`. It reads the
  uploaded crop back out of MinIO by `{bucket, key}`, so MinIO must be reachable from that
  container (it is, on the `ag_cloud` docker network).

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

You should see startup logs followed by one JSON block per image:

```
Loading Models...
Connected to MQTT broker at localhost:1883 (topic 'MQTT/vision/detections')
Running IQA...
Running detection...
Building MQTT payload...
Publishing to MQTT...
```

A frame that **passes** the gate (real output for `images/orange.jpg`, trimmed):

```json
{
    "frame_id": 1,
    "timestamp": 1781472652.85,
    "source": "images\\orange.jpg",
    "image_quality": {
        "status": "Borderline",
        "reason": "Borderline",
        "metrics": { "luminance": 68.42, "laplacian": 3293.07,
                     "brisque": 24.03, "niqe": 11.96, "final_score": 0.542 }
    },
    "detection": {
        "run_id": "c8279798-...",
        "total_fruits": 1,
        "results": [
            {
                "fruit_index": 0,
                "label": "orange",
                "minio_key": "pipeline/c8279798-.../crops/crop_0.jpg",
                "defect_result": { "ok": true, "label": "ok", "score": 0.013, "team": "fruit" },
                "ripeness_result": { "ripeness_label": "unripe", "confidence": 0.9999 }
            }
        ]
    },
    "detection_error": null
}
```

A frame that **fails** the gate (real output for `images/apple.jpg`) — detection is skipped:

```json
{
    "frame_id": 0,
    "source": "images\\apple.jpg",
    "image_quality": { "status": "FAILED", "reason": "...", "metrics": { ... } },
    "detection": null,
    "detection_error": "Skipped due to IQA failure"
}
```

Crops are written under [`pipeline/storage/runs/<run_id>/crops/`](storage/runs/) and uploaded to
MinIO under `imagery/pipeline/<run_id>/crops/`.

---

## MQTT publishing

After building each payload, the script publishes it (JSON, QoS 1) to the AgCloud broker. From
there AgCloud's `mqtt_gateway` forwards it to Kafka (`rover.images.meta.v1`) → Flink → Postgres.

Configuration is via environment variables (defaults match the AgCloud integration contract):

| Env var        | Default                  | Meaning                                  |
|----------------|--------------------------|------------------------------------------|
| `MQTT_ENABLED` | `1`                      | Set to `0` to skip publishing entirely.  |
| `MQTT_HOST`    | `localhost`              | Broker host.                             |
| `MQTT_PORT`    | `1883`                   | Broker port.                             |
| `MQTT_TOPIC`   | `MQTT/vision/detections` | Topic to publish to.                     |

Publishing is **best-effort**: if the broker can't be reached at startup, the script logs a
warning and continues (payloads are still printed). To watch messages arrive, open a **second
terminal first** (so it's listening), then run the pipeline:

```bash
# Terminal 1 — subscriber (included helper, uses the same MQTT_* env vars)
python pipeline/mqtt_subscriber.py

# Terminal 2 — run the pipeline from the repo root
python -m pipeline.pipeline_using_agcloud_models
```

Each published payload prints in Terminal 1 as it arrives. If you have the Mosquitto CLI tools
installed, this one-liner does the same thing:

```bash
mosquitto_sub -h localhost -p 1883 -t "MQTT/vision/detections" -v
```

To run fully offline with no broker, set `MQTT_ENABLED=0` (`set MQTT_ENABLED=0` on Windows).

---

## Verifying it worked

- **Console**: each image prints a JSON block with `image_quality`, and (if quality passed) a
  `detection` object listing fruits with `ripeness_result` and `defect_result`.
- **MinIO console**: browse http://localhost:9001 (login `minioadmin` / `minioadmin123`) →
  bucket `imagery` → `pipeline/<run_id>/crops/` should contain the uploaded crops.
- **Local disk**: `pipeline/storage/runs/<run_id>/crops/` mirrors the uploaded crops.
- **MQTT**: run `python pipeline/mqtt_subscriber.py` in a second terminal before the pipeline;
  one message prints per processed frame. See [MQTT publishing](#mqtt-publishing).

---

## Known limitations & gotchas

1. **Ripeness supports only 4 fruits.** `apple`, `banana`, `orange`, `pineapple` (the fruit set the
   `best_conditional.pt` embedding was trained on). Any other detected fruit gets
   `ripeness_label: "unknown"`.

2. **CPU only.** `DEVICE = "cpu"` is hard-coded for the ripeness model (the IQA gate will use CUDA
   if available). Fine for laptop testing; revisit for throughput.

3. **Hard-coded service endpoints.** MinIO (`localhost:9000`) and the defect service
   (`localhost:8011`) are constants in the file (MQTT is env-configurable — see above). Change the
   MinIO/defect constants in the script if those services run elsewhere.

### Recently fixed

- IQA thresholds now load from `frame_quality/IQA_thresholds.json` regardless of working directory
  (previously fell back to built-in defaults unless launched from that folder).
- The IQA gate now reports a real `"Borderline"` status for marginal frames instead of collapsing
  everything to `OK`/`FAILED`.
- `pineapple` is now in `YOLO_FRUIT_LABELS`, so pineapple detections actually reach the ripeness model.
- The result payload is now published to MQTT (best-effort), not just printed.

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
| `Warning: could not connect to MQTT broker` | `mosquitto` not running on `localhost:1883`. Start it, point `MQTT_HOST`/`MQTT_PORT` elsewhere, or set `MQTT_ENABLED=0` to silence. Pipeline still runs regardless. |
