# Deployment Proposal — Robo-Greeno Data-B Vision Pipeline on the Bot

**Status:** Draft for cross-team review
**Audience:** Data-B, Embedded, Data-A, Cloud/AgCloud 
**Scope:** Research & design only. This document does **not** change pipeline code; it recommends a
deployment pathway and lists the concrete work needed to execute it.
**Decision posture:** *Hybrid* — where a team has given an explicit answer (quoted from
`cross_team.md`), we make an opinionated, citation-backed recommendation. Where a technical unknown
remains, we present a comparative trade-off menu and flag it as a joint decision for the next
Embedded sync.

---

## 1. Context & Objective

Data-B owns the on-bot computer-vision pipeline: capture a frame → gate it through image-quality
assessment (IQA) → run detection/classification (fruit, ripeness, later pest/soil/disease) →
serialize to JSON → publish to AgCloud. Today this pipeline is **laptop-centric**: it assumes
services on `localhost`, loads full-precision PyTorch + Ultralytics + `pyiqa` models, has no
container/packaging/requirements/CI, and loads model weights by relative path from the repo root.

Deployment to the bot is the Sprint-3 deliverable, and **edge network optimization is the project's
primary KPI** (`documents/robo_greeno_data_team_b_plan.md`). This proposal is the design gate before
that work begins. It aligns the deployment format with the other teams' confirmed interfaces and
addresses the high-risk realities of the target hardware.

The platform stance is set by AgCloud:

> *"We will shift to an Edge-AI architecture for the Spider Robots. We will bypass continuous cloud
> inference and heavy MQTT image streaming, but strictly reuse AgCloud's downstream data backbone,
> Flink ingestion logic, and final storage layers."* — `AgCloud_orientation_memo_robo_greeno_integration.md`

So: **inference runs on the bot; the cloud backbone (MQTT → Kafka → Flink → Postgres) is reused,
not rebuilt.** MinIO remains AgCloud-internal infrastructure — the bot does not write to it in
production (see §7).

### ⚠ Open conflict surfaced up front — hardware target

Embedded's **final** answer fixes the target as **Raspberry Pi 3B, CPU-only, 1 GB RAM**:

> *"For now we are running on Raspberry Pi 3B CPU only — no hardware accelerator in this phase. Hailo
> AI HAT+ is not in our current BOM. If inference is too slow in Phase 3/4, we will revisit this. For
> now please optimize your models for RPi CPU."* — `cross_team.md`, Embedded Team

The project plan and the original issue text both say "Pi 5." **This proposal is designed for the
Pi 3B / 1 GB constraint** — the worst case — so a Pi 5 (4–8 GB RAM) becomes pure headroom. The
discrepancy is logged as cross-team item **U-1** (§11) for Embedded to confirm, because 1 GB vs
4–8 GB RAM changes the entire feasibility analysis below.

---

## 2. Constraints & Givens (firm cross-team contracts)

These are settled. Recommendations that follow are anchored to them.

| # | Constraint | Source (quoted) |
|---|---|---|
| C-1 | **Pi 3B, CPU-only, 1 GB RAM**, no accelerator | *"Raspberry Pi 3B CPU only — no hardware accelerator… optimize your models for RPi CPU."* — Embedded |
| C-2 | **Frames are pulled on demand** by our code via OpenCV; no push/stream/callback | *"Frames will be pulled on demand by your code using OpenCV: `cap = cv2.VideoCapture(0)`… We are not pushing frames via callback or stream at this stage."* — Embedded |
| C-3 | **Camera = Pi Camera v2** | Embedded |
| C-4 | **Pose is pulled synchronously from Data-A** per processed frame (no 50 Hz subscription) | *"Data B pulls pose from Data A directly at capture time… `request_latest_pose(host, port, topic, timeout_ms=100)`."* — Data-A |
| C-5 | **Timestamp switches `float seconds → stamp_ms` (epoch ms, int)** | *"timestamp float-seconds → stamp_ms int (epoch ms) — which also matches AgCloud captured_ts."* — Data-A |
| C-6 | **Add 3 additive fields** to each detection message: `robot_id`, `pose`, `pose_stamp_ms`; reject pairs with **\|Δstamp\| > 50 ms** | Data-A |
| C-7 | **Detections → MQTT `MQTT/vision/detections` → Kafka `rover.images.meta.v1` → Flink → Postgres `missions_db`**; JSON must map **1:1 to Postgres columns** | AgCloud memo (*"The JSON contract must perfectly match the Postgres schema, or data ingestion will fail."*) |
| C-8 | **Bot publishes detections via MQTT only.** The bot does not upload crops to MinIO in production. The MinIO upload in the current dev pipeline (`pipeline_using_agcloud_models.py`) exists for comparison and testing only and must not be enabled in the production bot deployment. | Production architecture decision (cf. CLAUDE.md §Active Constraints #10; originally from AgCloud memo — superseded for bot deployment) |
| C-9 | **Final packaging is a joint call with Embedded** (Pavan owns the Pi) | Data-A |
| C-10 | Data-A's stated **deployment preference** | *"tentative preference: an importable Python package that speaks MQTT (drops straight into the on-bot pull interface), with a container as the deploy wrapper."* — Data-A |

---

## 3. Decision 1 — Packaging & Environment Strategy

**Why it matters.** This choice determines how every other team consumes our work: how Embedded
launches it on the Pi they own, how Data-A's pose client drops in, how we ship updates, and how much
of the Pi's scarce RAM/storage the wrapper itself consumes.

**Options.**

| Option | What it is | Pros | Cons (on Pi 3B / 1 GB) |
|---|---|---|---|
| **A. Native venv + systemd** | `pip install` into a venv on the Pi, run under systemd | Lowest RAM/storage overhead; simplest on-device debugging | No build-time reproducibility; "works on my Pi" drift; manual dependency pinning |
| **B. Docker container on the Pi** | Build an ARM image, run with `docker run`/compose | Reproducible, isolated, easy restart/limits policy | Image can be ~1–2 GB (ARM PyTorch wheels are large); daemon + container RAM overhead eats into 1 GB; slower cold start |
| **C. Importable Python package + thin container wrapper** | Ship `robo_greeno_vision` as a pip-installable module that speaks MQTT and exposes the pull interface; container is the deploy unit | Matches Data-A's stated preference (C-10); drops into Embedded's pull interface (C-2); module is reusable/testable off-bot; container gives reproducible deploy | Inherits Docker's overhead on 1 GB (see B) |

**Recommendation — *opinionated where the teams spoke; comparative where they didn't*.**

- **Adopt Option C as the architecture.** It is Data-A's literal stated preference (C-10), it slots
  directly into Embedded's pull-on-demand frame interface (C-2), and a clean importable module is far
  easier to unit-test and reuse than a script. **Primary rationale: direct cross-team agreement.**
- **Leave one sub-question open for the Embedded sync (item U-2):** *is the container wrapper worth
  its RAM/storage overhead on a 1 GB Pi 3B, or do we ship the same package into a native venv +
  systemd and use the container only for CI / dev parity?* Because **Pavan owns the Pi (C-9)** and
  the answer depends on how much RAM the rest of the bot's software stack already consumes, this is a
  joint call. The package boundary (Option C) is identical either way, so this choice can be deferred
  without rework — only the outer wrapper changes.

---

## 4. Decision 2 — Edge Runtime & Model Format (the core technical fork)

**Why it matters.** This is the single highest-impact technical decision and the one most tied to the
project's network-optimization KPI. The current runtime stack — **PyTorch + `torchvision` +
Ultralytics + `pyiqa`** — is heavy: Ultralytics pulls the full training framework, and `pyiqa` (used
for the BRISQUE/NIQE AI metrics) drags in full `torch`. Three FP32 models load at import. On a 1 GB
Pi 3B this is the difference between "runs" and "OOM."

**Options.**

| Dimension | Current (laptop) | Edge target |
|---|---|---|
| Detector runtime | Ultralytics PyTorch (`yolov8-fruits.pt`) | **NCNN or ONNX Runtime**, INT8 |
| Ripeness runtime | PyTorch MobileNetV3 (`best_conditional.pt`) | **ONNX Runtime / TFLite**, INT8 |
| IQA AI metrics | `pyiqa` BRISQUE + NIQE (full torch) | torch-free BRISQUE/NIQE, **or** edge-degrade to luminance + Laplacian only |
| Precision | FP32 | INT8 (fallback FP16/FP32 if accuracy drops too far) |

**Recommendation — *opinionated, KPI-backed*.**

1. **Migrate off the FP32 PyTorch/Ultralytics runtime to exported, quantized runtimes.** This is
   exactly the Sprint-3 plan commit (*"Multi-format export… NCNN, ONNX Runtime, TFLite… Post-training
   INT8 quantization… mAP delta documented vs. FP32 reference"*) and the direct way to hit the
   network-optimization KPI. Exported INT8 models cut both resident memory and CPU latency versus
   FP32 PyTorch, which is what makes the 1 GB budget (§5) and the latency budget (§5) feasible.
2. **Resolve the `pyiqa` footprint.** `pyiqa` exists only for the two AI metrics (BRISQUE, NIQE).
   Pulling full `torch` for those alone is the largest avoidable dependency on the edge. Recommend
   evaluating a **torch-free BRISQUE/NIQE** implementation; if none is accurate enough, **degrade the
   edge IQA gate to luminance + Laplacian-variance only** (both are pure OpenCV/NumPy and already
   implemented) and keep the AI metrics for the offline `frame_quality_cli.py` calibration path. The
   IQA gate is a *camera-flaw detector*, not an aesthetic ranker, so the cheap metrics carry most of
   the signal. **Trade-off to document:** lower fidelity on borderline frames vs. removing the
   single heaviest edge dependency.
3. **Default to INT8, with a documented accuracy gate.** Ship INT8 only if the Sprint-3 mAP delta vs.
   FP32 is acceptable; otherwise fall back to FP16/FP32. The threshold is a Sprint-3 benchmark output,
   not decided here.

> **Licensing note (see §8.3):** Ultralytics is AGPL. Exported NCNN/ONNX artifacts may still derive
> from an AGPL toolchain. **Internal deployment on the company's own robot is not distribution to end
> users**, which significantly limits AGPL exposure for this use case. Alternatives (RF-DETR / YOLOX,
> Apache-2.0) are mapped in §8.3 if permissive-license distribution to external parties becomes a
> requirement.

---

## 5. Decision 3 — Hardware Compatibility, Resource Budget & Reliability

**Why it matters.** The Pi 3B is the binding constraint: **quad-core Cortex-A53 @ 1.2 GHz, 1 GB
LPDDR2, no GPU/accelerator.** Everything must fit in ~1 GB shared with the OS, and the process must
survive a hostile physical environment.

### 5.1 Baseline budget

- **Sequential, not parallel, detector execution.** The architecture-extension doc offers parallel
  execution "given sufficient CPU and memory" and a **sequential fallback "for resource-constrained
  edge devices."** The Pi 3B is squarely the latter — run models one at a time.
- **Lazy model loading**, not load-at-import. Today all three models load at module import; on the Pi
  we load each runtime only when first needed (and ideally release between tasks), to keep the
  resident set small.
- **OS bitness & ARM wheels** (item U-1 follow-on): 64-bit Raspberry Pi OS unlocks better ONNX/NCNN
  wheels; confirm with Embedded which image is flashed.
- **Thermal**: sustained CPU inference on a bare Pi 3B throttles — note passive/active cooling as an
  Embedded hardware ask.
- **Shared per-frame latency budget with Data-A.** Our YOLO CPU latency alone is **~283 ms/img**
  (Sprint-2 baseline). The synchronous pose pull (C-4, `timeout_ms=100`) adds to that. The end-to-end
  per-frame budget (capture → IQA → detect → crop → upload → classify → pose-pull → publish) must be
  measured on the Pi and shared, since Data-A's stability/Δt ≤ 50 ms gate (C-6) depends on it.

**Indicative per-component RAM table** (to be replaced with measured RSS during Sprint-3 — these are
the numbers that justify the `mem_limit` and swap sizing below):

| Component | Indicative resident RAM | Notes |
|---|---|---|
| Raspberry Pi OS (lite) | ~120–200 MB | headless |
| OpenCV + frame buffer | ~80–150 MB | |
| MQTT client + JSON | small | broker runs off-bot (§7) |
| Detector runtime (INT8 NCNN/ONNX) | ~100–250 MB | vs. much larger for FP32 PyTorch+Ultralytics |
| Ripeness runtime (INT8) | ~50–120 MB | loaded lazily |
| **Headroom target** | keep ≥ 150 MB free | OOM-killer safety |

### 5.2 Hard memory limits & OOM prevention

With ~1 GB shared, loading PyTorch/YOLO/OpenCV at once risks tripping the Linux **OOM killer**, which
would silently kill our process mid-frame. Defenses, in order:

1. **Bound the process with strict resource caps.** Use Docker `mem_limit` / `--memory` (with
   `--memory-swap`) — or, for a native install, systemd `MemoryMax=` (cgroups v2) — sized from the
   measured RSS budget above, so the vision process can never starve the OS. A bounded process that
   gets killed-and-restarted (§5.3) is far better than an unbounded one that takes the whole bot down.
2. **Mandate a 1–2 GB swap file on the SD card** as a safety net (raise the Raspberry Pi default
   ~100 MB `dphys-swapfile`). **I/O trade-off, documented honestly:** SD swap is slow and wears the
   card, so it is a **crash-prevention floor, not a performance tier** — a frame that has to swap is
   effectively a *dropped* frame, and that event should be surfaced by the watchdog (§5.3), not relied
   upon as normal operation.
3. **Reduce demand at the source.** The INT8 exported runtimes (§4) plus lazy/sequential loading
   (§5.1) are the primary lever — they cut resident memory enough that the caps and swap are a safety
   net rather than a constant crutch.

### 5.3 Reliability & crash recovery

Edge robotics sees transient failures: **camera disconnects, network drops, frame-pull deadlocks.**
Two layers:

1. **System-level restart policy (outer net).** systemd `Restart=always` (native) or Docker
   `restart: unless-stopped` (container) guarantees the process comes back after a crash or OOM kill.
2. **In-process watchdog / health-check (inner net).** A lightweight routine tracks frame-pull and
   inference latency; if a stage hangs past a threshold (e.g., camera read or pose pull blocks), it
   trips — either restarting the offending thread or exiting cleanly so the restart policy fires.
   systemd `WatchdogSec=` is the clean integration point (the process pings the watchdog; a missed
   ping triggers a managed restart). A conceptual sketch is in Appendix D.

---

## 6. Decision 4 — Cross-Team Interface Alignment

**Why it matters.** Deployment format must honor the interfaces the other teams have already pinned.

- **Inbound frames (Embedded).** Pull-on-demand via `cv2.VideoCapture` (C-2). Our existing
  `WebcamSource` already matches this; the Pi Camera v2 (C-3) is reachable through the same OpenCV
  path (or `picamera2` if needed — confirm with Embedded).
- **Inbound pose (Data-A).** Call `request_latest_pose(host, port, topic, timeout_ms=100)` once per
  processed frame (C-4). Bind the pose to the frame's capture instant; **reject the pair if
  \|Δstamp\| > 50 ms** (C-6). Build the client against Data-A's reference code and the 200-message
  replay fixture (`sample_pose_stream.jsonl`) — no robot required.
- **Timestamp switch (C-5).** Convert our `float seconds` to **`stamp_ms` (epoch ms, int)** in the
  payload builder. This aligns with AgCloud `captured_ts`, so Postgres ingest lines up.
- **Additive payload fields (C-6).** Add `robot_id`, `pose` (position + quaternion in odom, plus IMU
  and stability blocks Data-A now ships), and `pose_stamp_ms`. Detections stay in **pixel coords**;
  3D back-projection is deferred (Data-B owns intrinsics, Data-A owns the camera→body extrinsic, which
  *"stays parked until the mount is fixed."*).
- **Outbound to Cloud (C-7, C-8).** Publish detection JSON to MQTT `MQTT/vision/detections` (→ Kafka
  `rover.images.meta.v1` → Flink → Postgres). The bot does **not** upload crops to MinIO; crop
  storage is an AgCloud-internal concern. Because Flink does **1:1 JSON→column mapping**, the payload
  schema must be validated against the Postgres schema before we go live.

> ⚠ **Timestamp-format conflict (item U-3).** `cross_team.md` mandates `stamp_ms` (epoch ms), but the
> AgCloud memo's JSON example shows `"timestamp": "ISO-8601"`. These must be reconciled with Kayvan
> before publishing, since a schema mismatch fails Flink ingestion outright.

---

## 7. Decision 5 — Service Topology (on-bot vs off-bot)

**Why it matters.** In production the pipeline talks to **two services** — the **MQTT broker** and
the (optional) **defect inference API**. In dev, a MinIO service also runs on the laptop's
`localhost` via the AgCloud docker-compose for comparison purposes, but MinIO is AgCloud-internal and
the bot does not write to it in production. Running any of these services on the Pi 3B is infeasible
(they would consume the RAM needed for inference).

**Recommendation — *opinionated, aligns with AgCloud's Edge-AI memo*.**

- **The bot runs *only* the vision package.** The MQTT broker and the (optional) defect API run
  **off-bot** (cloud / gateway host) and are reached over the network. MinIO is AgCloud-internal and
  the bot is **not** a writer to it. This matches AgCloud's stance (*"bypass continuous cloud
  inference… reuse AgCloud's downstream backbone"*) and frees Pi CPU/RAM.
- **This requires env-var-izing the currently hardcoded defect-API endpoint** (§8 / §10). Today the
  defect API (`localhost:8011`) is hardcoded with no override (MQTT is already env-configurable).
  **MinIO credentials and endpoint are not part of the bot's production configuration.**
- **Open question — connectivity & store-and-forward (item U-4).** A moving bot will have
  intermittent network. If the broker is briefly unreachable, do we drop frames, or buffer them
  locally and forward when the link returns? A lightweight **store-and-forward / offline queue** is
  likely needed. This is a joint decision with Cloud (Kayvan) and Embedded (network design).

---

## 8. Decision 6 — Configuration, Secrets, Model Artifacts & Licensing

**Why it matters.** Deployment-readiness requires removing laptop assumptions, shipping light
artifacts, and respecting licensing.

### 8.1 Configuration & secrets

- Replace hardcoded `localhost` endpoints with **environment variables / a `.env` file** (Appendix B).
  The defect-API URL must become configurable; today only the `MQTT_*` vars are. **MinIO credentials
  and endpoint are not part of the bot's production configuration** — the bot does not connect to
  MinIO.

### 8.2 Model artifact delivery & versioning

**Problem.** Weights are currently fetched by relative path and gitignored. We must **not** bake heavy
binaries (`.pt` / `.onnx` / `.ncnn`) into source control, the pip package, or the container image —
that bloats every clone, install, and image pull.

**Recommendation — *opinionated*.** **Pull versioned model artifacts on demand from a versioned
HTTPS artifact endpoint** (e.g., a release server, CI/CD release assets, or a shared HTTPS object
store). Because the bot does not connect to MinIO, model weights must be served over plain HTTPS
rather than the MinIO S3 API. Options:

- at **container-build time** — fetched by `curl`/`wget` into a dedicated deploy layer, producing an
  immutable image that contains the exact pinned weights; **or**
- during a **first-run setup/verification step** — for the native-venv path.

Specify:
- a **versioned URL convention**, e.g. `https://artifacts.internal/models/<task>/<version>/model.onnx`;
- a **`MODEL_VERSION` / manifest** env pin so a deploy is reproducible;
- a **checksum + size verification** gate before the model is loaded;
- a **documented fallback** when the artifact server is unreachable (fail fast with a clear error, or
  use a last-known-good cached copy).

This decouples model iteration from code releases and keeps both the repo and the package light. A
conceptual fetch helper is in Appendix E.

### 8.3 Licensing

- **Ultralytics YOLO is AGPL.** Exported NCNN/ONNX artifacts may still derive from the AGPL
  toolchain. **Internal deployment on the company's own robot is not distribution to end users**,
  which significantly limits AGPL exposure — internal use is not "conveying" under AGPL. If
  permissive-license *distribution* (shipping the container/package to external parties) becomes a
  requirement, the plan's tracked alternatives (RF-DETR / YOLOX, Apache-2.0) are the fallback.
- **Pin MIT `albumentations`**, not AGPL `AlbumentationsX`, anywhere augmentation ships.

---

## 9. Recommended Strategy (summary)

Ship the pipeline as an **importable Python package that speaks MQTT, wrapped in a container as the
deploy unit** (Data-A's stated preference, Embedded's pull interface). Run **only** that package on
the **Pi 3B**; keep the MQTT broker and defect API **off-bot** — the bot does not connect to MinIO.
Replace the FP32 PyTorch/Ultralytics/`pyiqa` runtime with **exported, INT8-quantized NCNN/ONNX/TFLite**
models and a **torch-free (or degraded) IQA gate** to fit 1 GB RAM and hit the network-optimization
KPI. Make the deployment survivable with **hard memory limits + SD swap**, a **restart policy +
in-process watchdog**, and **pull-on-demand versioned model artifacts** from a versioned HTTPS
artifact endpoint.

| Decision | Recommendation | Basis |
|---|---|---|
| Packaging | Importable package + container wrapper | Opinionated (C-10, C-2); wrapper-vs-venv left open (U-2) |
| Runtime/format | Exported INT8 NCNN/ONNX/TFLite; fix `pyiqa` footprint | Opinionated (KPI + Sprint-3 plan) |
| Resource budget | Sequential + lazy load; `mem_limit`/`MemoryMax`; 1–2 GB SD swap | Opinionated (1 GB constraint) |
| Reliability | Restart policy + in-process watchdog | Opinionated (edge risk) |
| Interfaces | Frame pull, pose pull, `stamp_ms`, +3 fields, MQTT publish | Firm (C-2…C-8) |
| Service topology | Bot publishes via MQTT only; MinIO is AgCloud-internal (bot is not a writer) | Opinionated (AgCloud memo); connectivity open (U-4) |
| Artifacts | Pull-on-demand versioned weights from HTTPS artifact endpoint (no MinIO on bot) | Opinionated |

---

## 10. Implementation Roadmap — what we must do to complete deployment

Sequenced and actionable. Each item names the primary file(s) it touches. (This is the work that
*follows* sign-off; it is not done in this document.)

1. **Config refactor** — env-var-ize the defect-API URL; disable the MinIO upload path in
   production (guard with `MINIO_UPLOAD_ENABLED=0` defaulting off, or remove the call entirely from
   the production entry point).
   → `pipeline/pipeline_using_agcloud_models.py` (the hardcoded `localhost:8011` constant and the
   MinIO upload calls).
2. **Dependency split + lazy load** — edge vs. dev `requirements`; load each model on first use.
   → new `requirements-edge.txt` / `requirements-dev.txt`; `pipeline/pipeline_using_agcloud_models.py`.
3. **Export + INT8 quantize** YOLO and ripeness models; swap the inference calls to the NCNN/ONNX/TFLite
   runtime. → new export/quant scripts; the detector/ripeness wrappers.
4. **IQA footprint fix** — torch-free BRISQUE/NIQE, or edge-degrade to luminance + Laplacian.
   → `frame_quality/iqa_gate.py`, `frame_quality/requirements_edge.txt`.
5. **Interface alignment** — `timestamp → stamp_ms`; add `robot_id`/`pose`/`pose_stamp_ms`; build the
   Data-A pose-pull client (`request_latest_pose`) + Δt ≤ 50 ms gate; validate JSON against the
   Postgres schema. → payload builder (`build_json`), a new `pose_client` module.
6. **Package + container** — turn the pipeline into `robo_greeno_vision` (pyproject) + an ARM
   Dockerfile wrapper. → new `pyproject.toml`, `Dockerfile`.
7. **Off-bot service config + connectivity** — point at remote broker and defect API (MinIO is not
   a bot endpoint); add store-and-forward if U-4 confirms intermittent links. → config + a small
   buffering layer.
8. **On-Pi benchmark** — measure end-to-end per-frame latency and RSS against the §5 budget; feed
   numbers back to Data-A (latency) and into `mem_limit`/swap sizing.
9. **Deployment recipe** — reproducible doc + systemd unit / compose file (per the Sprint-3 commit).
10. **Model-artifact fetch** — build-time or first-run pull-on-demand from versioned HTTPS artifact
    endpoint with `MODEL_VERSION` pin + checksum verify (Decision 6). → model-fetch helper
    (`curl`/`wget` + manifest), Dockerfile build stage.
11. **Memory-safety config** — set Docker `mem_limit` / systemd `MemoryMax=` from the measured RAM
    table; provision the 1–2 GB SD swap file (Decision 3). → compose/systemd, Pi setup script.
12. **Resilience layer** — wire the restart policy (`Restart=always` / `restart: unless-stopped`) and
    add the in-process watchdog/health-check (frame-pull + inference latency → self-restart on hang,
    optionally via systemd `WatchdogSec=`). → systemd/compose, a small `watchdog` module.

---

## 11. Remaining Unknowns & Cross-Team Asks

Mapped to owners from `cross_team.md` issue #6.

| # | Open item | Owner | Why it matters |
|---|---|---|---|
| **U-1** | Confirm target is **Pi 3B / 1 GB** (not Pi 5); confirm OS bitness (32 vs 64-bit) and cooling | Pavan (Embedded) | Sets the entire RAM/runtime feasibility; bitness gates ONNX/NCNN wheels |
| **U-2** | Container wrapper vs. native venv + systemd on the 1 GB Pi | Pavan + Data-B | Wrapper overhead may not fit; package boundary is identical either way |
| **U-3** | Reconcile timestamp format — `stamp_ms` vs. AgCloud memo's ISO-8601 example | Kayvan (Cloud) | Flink does 1:1 column mapping; a mismatch fails ingestion |
| **U-4** | Connectivity model + store-and-forward when broker or defect API unreachable | Kayvan + Pavan | Determines whether frames are dropped or buffered on a moving bot |
| **U-5** | Whether Cloud wants **real-time IQA skip stats** aggregated on-bot and included in the MQTT payload (MinIO bucket/retention is no longer a bot concern — the bot does not write to MinIO) | Kayvan | Determines whether we add a skip-stat counter field to the published JSON |
| **U-6** | Earliest "very basic pipeline" date; confirm Data-B switches to `stamp_ms` | Scot (Data-B) | Data-A is gating its replay→live test on our date |
| **U-7** | IMU ownership / which MCU; camera→body extrinsic | Ingyu (Data-A) | Extrinsic parked until mount fixed; affects later 3D back-projection |
| **U-8** | Interface-contract `TBD`s: IQA quality threshold, min resolution, target images/sec | Data-B + Embedded | Needed to finalize the gate and the latency budget |

---

## Appendix A — Example `Dockerfile` (illustrative, ARM, build-time model fetch)

> Conceptual. Final base image, pins, and whether we containerize at all depend on U-1/U-2.

```dockerfile
# Multi-stage: fetch pinned model weights from HTTPS artifact endpoint, then a slim runtime image.
FROM arm64v8/python:3.12-slim AS models
ARG MODEL_VERSION
ARG ARTIFACT_BASE_URL
COPY scripts/fetch_models.sh .
# Pulls models from $ARTIFACT_BASE_URL/<task>/<MODEL_VERSION>/... and verifies checksums (see Appendix E)
RUN bash fetch_models.sh "$MODEL_VERSION" "$ARTIFACT_BASE_URL" /models

FROM arm64v8/python:3.12-slim AS runtime
WORKDIR /app
COPY requirements-edge.txt .
RUN pip install --no-cache-dir -r requirements-edge.txt        # onnxruntime / ncnn, opencv, paho-mqtt
COPY . .                                                        # the robo_greeno_vision package (NO weights)
COPY --from=models /models /models                             # weights live here, not in source control
ENV MODEL_DIR=/models
ENTRYPOINT ["python", "-m", "robo_greeno_vision"]
```

## Appendix B — Example `.env.example`

```ini
# --- Robot identity ---
ROBOT_ID=spider-01

# --- MQTT (off-bot broker) ---
MQTT_ENABLED=1
MQTT_HOST=broker.internal
MQTT_PORT=1883
MQTT_TOPIC=MQTT/vision/detections

# --- Defect inference API (off-bot, optional) ---
DEFECT_SERVICE_URL=http://infer.internal:8011/infer_json

# --- Data-A pose pull ---
POSE_HOST=broker.internal
POSE_PORT=1883
POSE_TOPIC=robogreeno/data-a/spider-01/pose
POSE_TIMEOUT_MS=100
POSE_MAX_SKEW_MS=50          # reject frame/pose pairs where |Δstamp_ms| > this value

# --- Model artifacts ---
MODEL_VERSION=2026.06.0
MODEL_DIR=/models
ARTIFACT_BASE_URL=https://artifacts.internal/models

# --- Memory safety ---
MEM_LIMIT_MB=700
```

> **Note:** No `MINIO_*` vars. The bot does not connect to MinIO in production.

## Appendix C — Example `docker-compose.edge.yml` (illustrative)

```yaml
services:
  vision:
    image: robo-greeno-vision:${MODEL_VERSION}
    env_file: .env
    restart: unless-stopped          # outer-net crash recovery (§5.3)
    mem_limit: 700m                  # hard cap so we can't OOM the OS (§5.2)
    memswap_limit: 2700m             # total memory+swap (700 MB RAM cap + 2 GB swap = 2700 MB)
    devices:
      - "/dev/video0:/dev/video0"    # Pi Camera v2 via OpenCV (C-2/C-3)
```

## Appendix D — Watchdog / health-check (conceptual pseudocode)

> Structural example of the logic and integration points only — **not** a production implementation.

```python
# Lightweight liveness guard for the frame loop. Intent, not final code.
last_progress_ts = now_ms()

def on_frame_processed():
    global last_progress_ts
    last_progress_ts = now_ms()          # called after each successful publish

def watchdog_tick():                     # runs on a timer thread
    stalled = now_ms() - last_progress_ts
    if stalled > FRAME_STALL_LIMIT_MS:   # camera/pose-pull/inference hung
        log.error("pipeline stalled %d ms — exiting for restart policy", stalled)
        # Option A: notify systemd (sd_notify "WATCHDOG=1" on healthy ticks; miss -> managed restart)
        # Option B: exit non-zero so Restart=always / restart: unless-stopped fires
        raise SystemExit(1)
```

## Appendix E — Model-fetch helper (conceptual pseudocode)

> Structural example only — conveys the versioned-pull + checksum-verify integration point.

```python
# Pull pinned weights from versioned HTTPS artifact endpoint at build-time or first run (§8.2).
# Intent, not final code.
def fetch_models(version, dest, manifest, base_url):
    for entry in manifest[version]:                 # manifest: {version: [{task,name,sha256,size}]}
        url = f"{base_url}/{entry.task}/{version}/{entry.file}"
        local = download_via_https(url, dest)       # requests / curl / wget — no MinIO client needed
        if sha256(local) != entry.sha256 or size(local) != entry.size:
            raise RuntimeError(f"artifact verify failed: {url}")
    # If artifact server unreachable: fail fast with a clear message, or fall back to last-known-good cache.
```

---

*This is a design proposal for cross-team review. Items U-1…U-8 are the explicit asks; everything
opinionated above is anchored to a quoted contract in `cross_team.md` / the AgCloud memo / the
project plan and will be revised as those answers land.*
