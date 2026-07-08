# Deployment Issues Backlog — Robo-Greeno Data-B Vision Pipeline

**Source:** Derived from `documents/deployment_proposal.md` §10 (Implementation Roadmap) and §11 (Remaining Unknowns).
**Purpose:** Concrete, ready-to-file GitHub issues that complete the deployment plan. Each issue includes a description, rationale, and definition of done.
**Audience:** Data-B team leads + cross-team reviewers.

---

## Terminology clarification

- **AgCloud** — the *last cohort's* entire platform (MQTT → Kafka → Flink → Postgres + MinIO + Grafana). We reuse their downstream backbone; we do not own or modify it.
- **Cloud team** — *this cohort's* backend team (Kayvan's team). Responsible for the Kafka/Flink/Postgres side, the MQTT broker, and the schema contract. **Infrastructure and backend only — no modeling involvement or responsibility.**
- **Data-A** — our sibling data team (Ingyu's team). Owns pose/navigation data and the pose-pull API.
- **Embedded** — hardware team (Pavan). Owns the Raspberry Pi 3B, camera, and the pull-on-demand frame interface.

---

## Priority levels

| Level | Meaning |
|---|---|
| **P0 — First-Integration Blocker** | Required before we can submit even a basic pipeline build to the other teams. Absolute minimal path. |
| **P0-ASK — Cross-team questions (initiate concurrently with P0)** | Not implementation work — these are questions we must send to other teams NOW. The answers drive what P1 work looks like. Asking late means P1 gets blocked or built wrong. |
| **P1 — Infrastructure & Packaging** | Packaging, deployment wrapper, watchdog, and on-Pi build. Provides the first basic working build that can be handed to Embedded for integration. Start after P0; does not require optimization to be complete. |
| **P2 — Edge Optimization** | Model format migration, quantization, and IQA footprint reduction. Improves a system that is already running and working in integration. Run a non-optimized model first; optimize after. |
| **P3 — Genuinely Deferred / Optional** | Truly optional or depends on hardware arriving or external decisions outside our control. Can start after P2. |

> **Why P0-ASK comes before P1 in the ordering:**
> The current "deferred" bucket originally mixed two different things: questions that must be *asked* now (because their answers determine how P1 is built) and work that is truly optional later. If we treat U-1 and U-2 as "do last," we risk building the wrong Dockerfile, sizing memory for the wrong device, or discovering mid-P1 that Embedded wants a native venv instead of a container. Asking concurrently with P0 costs nothing but prevents P1 from being blocked or wasted.

---

## P0 — First-Integration Blockers

These must be resolved before a single pipeline frame can be published to Cloud team's MQTT broker in any environment.

---

### P0-1 · Config refactor: env-var-ize defect-API URL + disable MinIO upload in production

**What it is:**
`pipeline/pipeline_using_agcloud_models.py` hardcodes the defect API as `localhost:8011` with no override. On the bot the service runs off-device, so this URL must come from an environment variable. The same file also contains a MinIO upload call that must be disabled (guarded or removed) for the production bot path.

**Why we need it:**
Without this the pipeline crashes or connects to the wrong host the moment it runs outside a developer laptop. The bot does not connect to MinIO in production (deployment proposal C-8). Until this is done, no off-laptop run of the production pipeline is possible.

**Files touched:**
- `pipeline/pipeline_using_agcloud_models.py` — replace `localhost:8011` constant with `os.environ.get("DEFECT_SERVICE_URL", ...)`, add `MINIO_UPLOAD_ENABLED` guard (default `0`) or remove the upload call entirely from the production entry point.
- `.env.example` — add `DEFECT_SERVICE_URL`, confirm no `MINIO_*` keys (the bot is not a MinIO writer).

**Definition of done:**
- `DEFECT_SERVICE_URL` is read from env; no hardcoded host:port for the defect API remains.
- MinIO upload call in the production entry point is either removed or behind `MINIO_UPLOAD_ENABLED=0` that defaults off.
- Pipeline runs end-to-end with `MQTT_ENABLED=0` and `DEFECT_SERVICE_URL` pointed at an offline stub without crashing.
- `.env.example` documents all new vars; no `MINIO_*` vars appear in it.

---

### P0-2 · Timestamp migration: `float seconds` → `stamp_ms` (epoch ms, int)

**What it is:**
All published payloads currently carry `"timestamp": <float seconds>`. Cross-team contract C-5 (Data-A) mandates switching to `stamp_ms` (epoch milliseconds, integer), which also aligns with AgCloud's `captured_ts` column in Postgres. The field must be renamed and reformatted in the payload builder.

**Why we need it:**
Cloud team's Flink job does 1:1 JSON-to-Postgres column mapping (C-7). A float-seconds `timestamp` field will either fail ingestion or silently write the wrong value. Data-A's `|Δstamp_ms| ≤ 50 ms` gate (C-6) also requires integer milliseconds to compute correctly. This is a hard contract, not an optimization.

**Files touched:**
- `pipeline/pipeline_using_agcloud_models.py` → `build_json()` function: rename `timestamp` to `stamp_ms`, convert `time.time()` to `int(time.time() * 1000)`.
- Any other payload-builder or subscriber that reads `"timestamp"`.

**Note:** There is an open conflict between Data-A's `stamp_ms` (epoch ms) and the AgCloud memo's example showing ISO-8601. This must be reconciled with Kayvan (Cloud team) before going live — see U-3 and P0-3 below. Implement `stamp_ms` for now since that is the Data-A contract; note it as pending Cloud team sign-off.

**Definition of done:**
- `build_json()` emits `stamp_ms` as integer epoch-ms; `"timestamp"` (float-seconds) is gone from the payload.
- A subscriber test confirms the published JSON contains `"stamp_ms": <int>`.
- U-3 is documented as a pending cross-team confirmation (not a blocker to the code change, but must be flagged before first production publish).

---

### P0-3 · Cross-team sign-off: resolve timestamp format conflict (U-3)

**What it is:**
An explicit open question: Data-A's contract says `stamp_ms` (integer epoch ms); the AgCloud memo's example shows `"timestamp": "ISO-8601"`. These cannot both be right for the same field. Cloud team (Kayvan) must specify which format Flink expects in Postgres.

**Why we need it:**
Flink ingestion fails outright on a schema mismatch (C-7). This is a synchronous blocker to any real production publish, even if P0-2 is done with the `stamp_ms` choice.

**Action:**
File an issue to track the answer; link it from P0-2. The issue closes when Cloud team (Kayvan) confirms the expected field name and type in the Postgres `missions_db` schema.

**Definition of done:**
- Cloud team has confirmed: either `stamp_ms` (integer epoch ms) or a specific ISO-8601 format + field name.
- `build_json()` updated to match if the answer differs from P0-2's implementation.
- The AgCloud memo (or `cross_team.md`) updated with the confirmed answer.

---

### P0-4 · Interface alignment: add `robot_id`, `pose`, `pose_stamp_ms` fields + build pose-pull client

**What it is:**
Three additive payload fields are required by contract (C-6): `robot_id` (string), `pose` (position + quaternion + IMU block from Data-A), and `pose_stamp_ms` (epoch ms of the pose reading). A pose-pull client must call `request_latest_pose(host, port, topic, timeout_ms=100)` once per processed frame and reject frame/pose pairs where `|Δstamp_ms| > 50 ms`.

**Why we need it:**
These fields are part of the cross-team interface contract (C-6). Without them the Cloud team's Flink job will reject or mismatch our messages. The `robot_id` field also keys the data to a specific bot in Postgres. Data-A is gating its replay→live test on our first publish, so this is a blocker to their work too.

**Files touched / new:**
- New module: `pipeline/pose_client.py` — wraps `request_latest_pose()`, computes `|Δstamp_ms|`, returns `(pose_dict, pose_stamp_ms)` or raises `StalePoseError`.
- `pipeline/pipeline_using_agcloud_models.py` → `build_json()`: add `robot_id` (from `ROBOT_ID` env var), `pose`, `pose_stamp_ms`.
- `.env.example`: add `ROBOT_ID`, `POSE_HOST`, `POSE_PORT`, `POSE_TOPIC`, `POSE_TIMEOUT_MS`, `POSE_MAX_SKEW_MS`.

**Note:** 3D back-projection is explicitly deferred; detections stay in pixel coords (deployment proposal §6).

**Definition of done:**
- `pose_client.py` implements `request_latest_pose()` contract; raises a clear error when pose is stale.
- Pipeline calls the pose client once per frame; frames with `|Δstamp_ms| > 50 ms` are skipped (not published) with a logged warning.
- `robot_id`, `pose`, `pose_stamp_ms` appear in the published JSON.
- Unit tests for `pose_client.py` run against Data-A's `sample_pose_stream.jsonl` fixture (no robot required).
- `ROBOT_ID`, `POSE_*` vars documented in `.env.example`.

---

### P0-5 · JSON schema validation against Postgres schema (Cloud team sign-off)

**What it is:**
Before any real publish, the JSON payload emitted by `build_json()` must be validated to match the Postgres `missions_db` column schema owned by Cloud team. This is not a unit test of our code — it is a cross-team schema review gate.

**Why we need it:**
Cloud team's Flink ingestion does 1:1 JSON-to-column mapping (C-7). Any field name mismatch, extra field, or wrong type silently corrupts or drops rows. This must be caught before the first real publish, not discovered in production.

**Action:**
- Obtain the Postgres schema (table definition or JSON schema spec) from Cloud team (Kayvan).
- Write a schema-validation test that asserts the output of `build_json()` matches it.
- Run this test as part of CI once P0-2 and P0-4 are merged.

**Definition of done:**
- Cloud team has provided the Postgres schema or JSON schema spec for the `missions_db` ingest table.
- A test (pytest + `jsonschema` or equivalent) validates a sample `build_json()` output against the schema.
- All field names, types, and required/optional flags match.
- Test is wired into CI.

---

### P0-6 · Dependency split: separate edge from dev requirements

**What it is:**
Create `requirements-edge.txt` (what runs on the bot) and `requirements-dev.txt` (everything else: Ultralytics training framework, MinIO client, eval tools, pycocotools). Today everything is in one implicit list. For first integration this does not need to be fully optimized — just clearly separated so we know what the bot actually needs.

**Why we need it:**
Without a split, `pip install` on the Pi pulls in Ultralytics (training framework, ~1 GB with deps), the MinIO client (not used on the bot), and eval tools. Even if models are still FP32 at first integration, the bot must not install training-framework dependencies. This is the minimal step; INT8 and torch-free optimization come later (P2).

**Files touched / new:**
- New: `requirements-edge.txt` — `opencv-python-headless`, `onnxruntime` (or `torch` if still FP32 at first integration), `paho-mqtt`, `aiomqtt`, `requests`, `pillow`, `numpy`.
- New: `requirements-dev.txt` — everything currently in the pipeline's install command, including `ultralytics`, `minio`, `pycocotools`, `pyiqa`.
- `frame_quality/requirements_edge.txt` — review against new split.

**Definition of done:**
- `requirements-edge.txt` installs cleanly on a Pi-class ARM environment without pulling in Ultralytics or MinIO.
- `requirements-dev.txt` covers full dev + eval workflow.
- README / `pipeline/README.md` updated to reference the split.

---

## P0-ASK — Cross-team questions: initiate concurrently with P0

These are not implementation tasks. They are questions that must be sent to other teams at the same time we start P0 work. The answers will arrive on the other teams' schedule, but **if we don't ask now, the answers won't arrive in time to scope P1 correctly** — and we risk building the wrong container format, sizing memory for the wrong device, or discovering a blocker mid-P1.

---

### P0-ASK-1 · Confirm hardware target: Pi 3B or Pi 5, OS bitness, cooling (U-1) → owner: Embedded (Pavan)

**What it is:**
Ask Embedded to confirm: (a) is the target Pi 3B or Pi 5? (b) what OS image is flashed — 32-bit or 64-bit Raspberry Pi OS? (c) is passive or active cooling in place?

**Why we need it now:**
The entire deployment proposal is sized for Pi 3B / 1 GB RAM. If the hardware is actually Pi 5 (4–8 GB), many P2 optimizations become nice-to-have instead of critical, and the P1 RAM budget and memory-limit sizing (P1-3, P1-6) change completely. 64-bit OS also affects which ONNX/NCNN ARM wheels are available. Asking after P1 work starts risks building P1 for the wrong target.

**Drives:** P1-2 (Dockerfile base image), P1-3 (on-Pi benchmark RSS budget), P1-6 (memory limits), P3-2 (IQA recalibration).

**Definition of done:**
- Embedded has confirmed: hardware model, RAM, OS image (32 vs. 64-bit), and cooling status.
- Deployment proposal §2 (C-1) updated with confirmed values.
- U-1 closed in `cross_team.md`.
- If Pi 5: re-evaluate which P2 items remain critical vs. nice-to-have.

---

### P0-ASK-2 · Confirm deployment wrapper: Docker container vs. native venv + systemd (U-2) → owner: Pavan + Data-B

**What it is:**
Ask Embedded (Pavan, who owns the Pi) whether Docker daemon overhead is acceptable on the target device, or whether we should ship the `robo_greeno_vision` package into a native venv + systemd service instead. The package boundary (P1-1) is identical either way; only the outer wrapper changes.

**Why we need it now:**
P1-2 is either a Dockerfile or a systemd unit file — two entirely different artifacts. If we build the Dockerfile first and Embedded then confirms Docker is too heavy for 1 GB RAM, the Dockerfile work is wasted. The package (P1-1) is safe to build in any case, but we cannot start P1-2 until U-2 is answered.

**Drives:** P1-2 (Dockerfile vs. systemd unit).

**Definition of done:**
- Pavan and Data-B have agreed: container wrapper or native venv + systemd.
- P1-2 is scoped accordingly.
- U-2 closed in `cross_team.md`.

---

## P1 — Infrastructure & Packaging

Packaging, deployment wrapper, watchdog, and on-Pi build. Provides the first basic working build that can be submitted to Embedded and other teams for integration. Does not require model optimization to be complete — run whatever format works first, optimize in P2.

---

### P1-1 · Package pipeline as importable Python module (`robo_greeno_vision`)

**What it is:**
Refactor the pipeline into a proper pip-installable Python package named `robo_greeno_vision` with a `pyproject.toml` (or `setup.cfg`). The package exposes the pipeline's entry point and speaks MQTT as its external interface.

**Why we need it:**
This is Data-A's stated preference (deployment proposal C-10) and the deployment architecture recommendation (§9). An importable module is testable in isolation, has clean version management, and lets Embedded (or Data-A) drop it into whatever outer wrapper they need. It also enables `pip install robo_greeno_vision` as the install step.

**Files touched / new:**
- New: `pyproject.toml` (or `setup.cfg`) defining `robo_greeno_vision` package.
- Existing pipeline files reorganized under `src/robo_greeno_vision/` (or flat package if simpler).
- Entry point: `python -m robo_greeno_vision` replaces current script invocation.

**Definition of done:**
- `pip install -e .` succeeds; `python -m robo_greeno_vision` launches the pipeline.
- Package imports cleanly with no relative-path assumptions about repo root.
- Model paths come from `MODEL_DIR` env var, not hardcoded relative paths.

---

### P1-2 · ARM Dockerfile + `docker-compose.edge.yml`

**What it is:**
Write an ARM64 (or ARMv7) Dockerfile that builds the `robo_greeno_vision` package into a slim runtime image, fetches model weights at build time from the versioned HTTPS artifact endpoint (see P1-4), and exposes the pipeline entry point. Provide `docker-compose.edge.yml` with `mem_limit`, `memswap_limit`, and `/dev/video0` device pass-through.

**Why we need it:**
Containerized deployment gives reproducibility (the same image runs on every Pi), isolation (the vision process cannot take down the OS), and easy updates (pull and restart). This is the outer wrapper in the deployment architecture (§9). Depends on U-2 (container vs. native venv) being confirmed by Embedded.

**Note:** If Embedded (Pavan) confirms in U-2 that container overhead is too large for 1 GB RAM, this issue becomes a native venv + systemd unit file instead. The package (P1-1) is identical either way.

**Files touched / new:**
- New: `Dockerfile` (ARM64 base, multi-stage model fetch).
- New: `docker-compose.edge.yml` (vision service with limits and device).
- New: `.dockerignore`.

**Definition of done:**
- `docker build` succeeds targeting `linux/arm64`.
- Container starts, connects to camera via `/dev/video0`, and publishes a test frame to MQTT.
- `mem_limit` and `memswap_limit` are set from the P1-3 measured RSS budget.
- No Ultralytics, MinIO client, or `pyiqa` installed in the runtime image.

---

### P1-3 · On-Pi benchmark: end-to-end latency and RSS measurement

**What it is:**
Run the full pipeline on the actual Pi 3B and measure: per-frame wall-clock latency (capture → IQA → detect → classify → pose-pull → publish) and peak RSS at each stage. Share results with Data-A (their `|Δstamp_ms| ≤ 50 ms` gate depends on it) and use them to set `mem_limit` / swap sizing.

**Why we need it:**
All RAM and latency numbers in the deployment proposal (§5.1) are indicative estimates. The actual Pi measurement determines whether the plan holds or needs adjustment. Data-A is explicitly waiting for our latency number to validate their replay→live test (U-6).

**Action:** Run `pipeline_using_agcloud_models.py` (post P0 changes) on the Pi; log per-stage times and `psutil.Process().memory_info().rss` at each stage; report to cross-team. If P2 optimizations are done, re-run with INT8 models for final numbers.

**Definition of done:**
- Per-frame latency measured on Pi 3B (with FP32 models initially; re-run with INT8 when P2-2 is done).
- Peak RSS documented per component (IQA, YOLO, ripeness, pose-pull, MQTT).
- Results shared with Data-A (latency) and Cloud team (throughput).
- `mem_limit` in `docker-compose.edge.yml` / systemd `MemoryMax=` set from measured values.
- Numbers recorded in `pipeline/README.md` as the Pi 3B benchmark table.

---

### P1-4 · Model artifact fetch system: versioned HTTPS pull + checksum verify

**What it is:**
Build a small helper (`scripts/fetch_models.sh` or `scripts/fetch_models.py`) that pulls versioned model weights from a HTTPS artifact endpoint using `MODEL_VERSION` + a manifest file, and verifies SHA-256 checksums before loading. Integrate into the Dockerfile build stage (Appendix E of deployment proposal).

**Why we need it:**
Model weights are gitignored and cannot be baked into the repo or pip package. Without a versioned fetch mechanism, every deployment requires manual file placement. The HTTPS endpoint is required because the bot does not connect to MinIO (C-8); weights must be served via plain HTTPS.

**Files touched / new:**
- New: `scripts/fetch_models.sh` (or `.py`) — curl/wget with checksum verification.
- New: `models/manifest.json` — `{version: [{task, file, sha256, size}]}`.
- `Dockerfile` — `FROM ... AS models` stage calls `fetch_models.sh`.

**Definition of done:**
- `fetch_models.sh <version>` downloads the correct model files and verifies checksums.
- On checksum mismatch: script exits non-zero with a clear error message.
- On artifact server unreachable: script either fails fast with a clear message or falls back to a local cache if present.
- Dockerfile successfully fetches models at build time.
- `MODEL_VERSION` pin documented in `.env.example`.

---

### P1-5 · Restart policy + in-process watchdog

**What it is:**
Wire the outer restart policy (`Restart=always` for systemd; `restart: unless-stopped` for Docker compose) and add a lightweight in-process watchdog: a timer thread that tracks time since the last successfully published frame; if the pipeline stalls past a threshold, it exits cleanly so the restart policy fires. Optionally integrate with `systemd WatchdogSec=`.

**Why we need it:**
Edge robotics sees transient failures: camera disconnects, network drops, pose-pull timeouts, inference hangs. Without a watchdog a stalled pipeline just sits consuming RAM without publishing. The two-layer approach (outer restart policy + inner stall detector) ensures the bot recovers automatically without human intervention.

**Files touched / new:**
- New: `pipeline/watchdog.py` — `WatchdogTimer` class (see Appendix D of deployment proposal for conceptual sketch).
- `pipeline/pipeline_using_agcloud_models.py` — call `on_frame_processed()` after each successful publish; start watchdog thread at startup.
- `systemd/robo-greeno-vision.service` (or `docker-compose.edge.yml`) — `Restart=always` / `restart: unless-stopped`.

**Definition of done:**
- If the pipeline stalls for > `FRAME_STALL_LIMIT_MS` (configurable, default 30 000 ms), the process exits with a non-zero code.
- Restart policy restarts the process within 5 seconds of exit.
- Unit test: watchdog fires correctly when `on_frame_processed()` is not called within the timeout.
- Stall events are logged with the last-good-frame timestamp for post-mortem.

---

### P1-6 · Memory safety: `mem_limit` / `MemoryMax=` + SD swap provisioning

**What it is:**
Set a hard memory cap on the vision process using Docker `mem_limit` + `memswap_limit` (or systemd `MemoryMax=` for native) sized from the P1-3 RSS measurements. Document how to provision a 1–2 GB swap file on the Pi's SD card as a crash-prevention floor.

**Why we need it:**
Without a cap the vision process can OOM-kill the entire bot OS (not just itself). The SD swap is a safety net: a frame that has to swap is a dropped frame (SD I/O is slow), but it prevents a hard crash. A bounded process that gets killed-and-restarted (P1-5) is far better than one that takes down the OS.

**Files touched / new:**
- `docker-compose.edge.yml`: `mem_limit`, `memswap_limit` (depends on P1-3 numbers).
- New: `scripts/setup_pi.sh` — documents `dphys-swapfile` reconfiguration to 1–2 GB (for native venv path).
- `systemd/robo-greeno-vision.service`: `MemoryMax=` line.

**Definition of done:**
- `mem_limit` (Docker) or `MemoryMax=` (systemd) is set from P1-3 measured values.
- Vision process is killed-and-restarted (not OS-crashed) if it exceeds the cap.
- `setup_pi.sh` documents swap provisioning; includes the `dphys-swapfile` size change and the warning that SD swap is a floor, not a performance tier.

---

### P1-7 · Deployment recipe: reproducible doc + systemd unit / compose file

**What it is:**
A deployment runbook (`documents/deployment_runbook.md` or `README-deploy.md`) that documents every step: OS image, software install, `.env` configuration, model fetch, service start, and verification. Includes the systemd unit file or compose file as the deploy artifact.

**Why we need it:**
The Sprint-3 plan commit explicitly includes *"reproducible doc + systemd unit / compose file"*. Without a runbook, every bot setup requires someone with deep repo knowledge. With one, Embedded (Pavan) or any team member can deploy the pipeline to a fresh Pi from scratch.

**Files touched / new:**
- New: `documents/deployment_runbook.md`.
- New: `systemd/robo-greeno-vision.service` (if native venv path confirmed in U-2).

**Definition of done:**
- Someone without prior context can follow the runbook and get the pipeline publishing frames to MQTT.
- Runbook covers: OS requirements (U-1 confirmed), install, `.env` setup, `MODEL_VERSION` pin, model fetch, service start, log verification.
- Service file (or compose file) is in the repo and tested on an actual Pi (or Pi-class ARM).

---

## P2 — Edge Optimization

Model format migration, quantization, and IQA footprint reduction. These improve performance substantially but are **not blockers to the first integration** — a non-optimized model in its original format can run in the pipeline in the first stage. Start P2 only after the pipeline is running and publishing to the Cloud team's MQTT broker. Optimize what we give them later.

---

### P2-1 · Export YOLO model to ONNX/NCNN (start FP32, optimize to INT8 in P2-2)

**What it is:**
Export `yolov8-fruits.pt` from Ultralytics PyTorch format to ONNX (and optionally NCNN) using `ultralytics`'s built-in export. Swap the inference call in the pipeline from `ultralytics.YOLO` to `onnxruntime.InferenceSession` (or `ncnn`). At this stage FP32 export is sufficient; INT8 quantization is P2-2.

**Why we need it:**
The Ultralytics runtime is the largest single dependency on the edge — it brings in the training framework. Exporting to ONNX removes this runtime dependency from the bot. Even FP32 ONNX Runtime is smaller and faster on ARM CPU than the full Ultralytics PyTorch stack. This is the network-optimization KPI (primary project success metric).

**Note:** This task does not block the initial integration. We can submit a first pipeline build using the original PyTorch model format and swap to ONNX as an optimization step once integration is established.

**Files touched / new:**
- New: `scripts/export_yolo.py` — calls `model.export(format="onnx")` and documents the output path.
- `pipeline/pipeline_using_agcloud_models.py` → `detect_and_crop()`: replace `ultralytics.YOLO` with `onnxruntime.InferenceSession`.
- `requirements-edge.txt`: replace `ultralytics` with `onnxruntime`.

**Definition of done:**
- Export script produces a valid `yolov8-fruits.onnx` from `yolov8-fruits.pt`.
- Pipeline runs inference via ONNX Runtime and produces the same detection results (within floating-point tolerance) as the PyTorch version on the same test images.
- Ultralytics is no longer in `requirements-edge.txt`.
- mAP difference (FP32 ONNX vs. FP32 PyTorch) is measured and documented; acceptable if < 1% mAP@0.5 delta.

---

### P2-2 · INT8 quantization of YOLO and ripeness models

**What it is:**
Post-training INT8 quantization of the exported ONNX models using ONNX Runtime's static quantization (`onnxruntime.quantization`). Requires a small calibration dataset (a subset of test images).

**Why we need it:**
INT8 halves the model size and significantly reduces CPU latency vs. FP32. On a Pi 3B (1 GB RAM, no GPU) this is the primary lever to fit within the RAM budget and hit the latency KPI. Must be gated on an acceptable mAP delta (see Definition of done).

**Files touched / new:**
- New: `scripts/quantize_models.py` — runs ONNX static quantization with calibration data.
- Export scripts updated to output INT8 variants alongside FP32.
- Pipeline updated to load INT8 models by default.

**Definition of done:**
- INT8 ONNX models produced and verified: YOLO mAP@0.5 delta vs. FP32 ≤ 3%; ripeness accuracy delta ≤ 5%.
- If delta exceeds threshold: fall back to FP16 or FP32 and document the decision.
- Latency improvement on CPU measured and documented (target: meaningful reduction from ~283 ms/img baseline).
- INT8 models are the default on edge; FP32 remains available for comparison.

---

### P2-3 · Export ripeness model (MobileNetV3 conditional) to ONNX

**What it is:**
Export `best_conditional.pt` (the `RipenessModelConditional` — MobileNetV3 backbone + fruit embedding + ripeness head) to ONNX using `torch.onnx.export()`. Replace the `torch`-based inference call in the pipeline with `onnxruntime.InferenceSession`.

**Why we need it:**
Same rationale as P2-1: removes a PyTorch inference dependency from the bot. The ripeness model is a standard PyTorch module; ONNX export is straightforward. This also enables INT8 quantization (P2-2).

**Files touched / new:**
- New: `scripts/export_ripeness.py` — `torch.onnx.export()` with dummy inputs covering all 4 fruit types.
- `pipeline/pipeline_using_agcloud_models.py` → `predict_ripeness()`: replace PyTorch inference with ONNX Runtime.

**Definition of done:**
- Export script produces a valid `ripeness_conditional.onnx`.
- ONNX inference output matches PyTorch inference output on all 4 fruit types (numerical tolerance check).
- Zero-shot accuracy on the surrogate test set unchanged vs. PyTorch baseline (63.0% ± noise).
- `torch` and `torchvision` removed from `requirements-edge.txt` (if IQA is also fixed in P2-4).

---

### P2-4 · IQA footprint fix: torch-free BRISQUE/NIQE or degrade to luminance + Laplacian at edge

**What it is:**
`pyiqa` is the only reason `torch` is in `requirements-edge.txt` for IQA. Two options (choose after evaluation):
- **Option A**: Find or implement a torch-free BRISQUE/NIQE (pure NumPy/SciPy); keep both AI metrics at the edge.
- **Option B**: Degrade the edge IQA gate to luminance + Laplacian-variance only (pure OpenCV/NumPy, already implemented). Keep `pyiqa` in `requirements-dev.txt` for offline calibration (`frame_quality_cli.py`) only.

The IQA gate is a camera-flaw detector, not an aesthetic ranker. The cheap metrics (luminance, Laplacian) carry most of the signal for hardware defects (blur, bad exposure).

**Why we need it:**
`pyiqa` pulls the entire `torch` runtime for two metrics. If P2-1 and P2-3 successfully migrate detection and classification off PyTorch, `pyiqa` becomes the sole reason `torch` remains on the edge — which defeats the purpose of the migration. Fixing this completes the PyTorch removal from `requirements-edge.txt`.

**Files touched:**
- `frame_quality/iqa_gate.py` — modify metric calculation block depending on chosen option.
- `frame_quality/requirements_edge.txt` — remove `pyiqa` (and `torch` if Option B or a torch-free implementation is used).
- `frame_quality/requirements_cli.txt` — `pyiqa` stays here for offline use.

**Definition of done:**
- `iqa_gate.py` runs on edge without importing `torch` or `pyiqa`.
- IQA gate still correctly rejects blur and exposure failures on the test image set used for calibration.
- If Option B (degraded): degradation is documented in `frame_quality/README.md` and `IQA_thresholds.json` is recalibrated for the two-metric gate.
- `torch` and `pyiqa` absent from `frame_quality/requirements_edge.txt`.

---

### P2-5 · Lazy model loading: load each model on first use, not at import

**What it is:**
Currently all models load at module import time. Change `pipeline_using_agcloud_models.py` to load each model object the first time it is actually needed (lazy initialization pattern), and release between frames if memory is tight.

**Why we need it:**
On a 1 GB Pi 3B, loading all models at startup risks OOM before the first frame is processed. Lazy loading limits peak resident memory to one model at a time during sequential processing (as recommended by the deployment proposal §5.1).

**Files touched:**
- `pipeline/pipeline_using_agcloud_models.py` — convert global model objects to module-level `None` initialized lazily on first call.

**Definition of done:**
- No model weights are loaded at import time.
- First-call latency is acceptable (documented in on-Pi benchmark, see P1-3).
- Subsequent calls do not reload weights (models remain cached after first load unless explicitly released).

---

## P3 — Genuinely Deferred / Optional

These are started only after P2, and depend on hardware arriving or external decisions (U-4) outside our control. They are not questions we can ask and resolve in parallel — they require conditions that don't exist yet.

---

### P3-1 · Store-and-forward: offline queue for intermittent connectivity (depends on U-4)

**What it is:**
A lightweight local buffer that queues published MQTT messages when the broker is unreachable and replays them when connectivity returns. Triggered by connection failures in `MQTTPublisher`.

**Why we need it:**
A moving robot will have intermittent network. Without a buffer, every network drop means lost detection records. However, this is an open joint decision with Cloud team (Kayvan) and Embedded (U-4): the teams must agree on buffer size, replay ordering, and acceptable staleness before we implement.

**Blocking dependency:** Resolution of U-4 (Cloud team + Embedded confirm connectivity model and whether buffering is required).

**Definition of done (when unblocked):**
- Messages are queued to a local file/SQLite DB when broker is unreachable.
- On reconnect, queued messages are replayed in order with original `stamp_ms` preserved.
- Buffer is bounded (configurable max size); oldest messages dropped first when full.
- Buffer behavior is configurable via env var (`OFFLINE_QUEUE_ENABLED`, `OFFLINE_QUEUE_MAX_MESSAGES`).

---

### P3-2 · IQA threshold recalibration on actual Pi 3B + Pi Camera v2 hardware

**What it is:**
Collect 20–30 raw frames from the actual Pi 3B + Pi Camera v2 (including deliberate bad frames: blocked lens, blur, low light). Run `frame_quality_cli.py` on them. Update `frame_quality/IQA_thresholds.json` with calibrated values.

**Why we need it:**
`IQA_thresholds.json` explicitly states its values are mock. The IQA gate is a *camera-flaw detector*: thresholds calibrated on a developer webcam will misclassify frames from the actual Pi Camera v2 sensor (different exposure curve, noise floor, and gamma). This must be done on actual hardware before production.

**Blocking dependency:** Actual Pi 3B + Pi Camera v2 hardware available (U-1).

**Definition of done:**
- Calibration frames collected on actual hardware (at least 20: mix of good, blurry, underexposed, overexposed).
- `frame_quality_cli.py` CSV reviewed and threshold boundaries identified.
- `frame_quality/IQA_thresholds.json` updated with calibrated values.
- IQA gate tested on hold-out frames: no good frames rejected, no bad frames passed.
- `frame_quality/README.md` documents the calibration run (hardware, date, sample count).

---

## Summary table

Ordered by the sequence in which work should be initiated — not just by importance.

| Issue | Priority | Drives / Blocks |
|---|---|---|
| P0-1 Config refactor (defect URL + MinIO disable) | P0 | All off-laptop runs |
| P0-2 Timestamp migration `stamp_ms` | P0 | Cloud team ingest |
| P0-3 U-3 timestamp format sign-off (Cloud team) | P0 | Production publish |
| P0-4 Add `robot_id`/`pose`/`pose_stamp_ms` + pose-pull client | P0 | Data-A integration |
| P0-5 JSON schema validation (Cloud team sign-off) | P0 | Production publish |
| P0-6 Dependency split: edge vs. dev requirements | P0 | Bot install |
| **P0-ASK-1 Ask Embedded: Pi 3B vs Pi 5, OS bitness, cooling (U-1)** | P0-ASK | P1-2 base image, P1-3 RSS budget, P1-6 mem limits, P3-2 IQA |
| **P0-ASK-2 Ask Embedded+Data-B: container vs. native venv (U-2)** | P0-ASK | P1-2 artifact type |
| P1-1 Package as `robo_greeno_vision` | P1 | Clean deploy (no P0-ASK dep) |
| P1-2 ARM Dockerfile or systemd unit (scoped by P0-ASK-2) | P1 | Reproducible deploy |
| P1-3 On-Pi benchmark (latency + RSS) (needs P0-ASK-1 answer) | P1 | mem_limit sizing; Data-A |
| P1-4 Model artifact fetch (versioned HTTPS + checksum) | P1 | Reproducible model deploy |
| P1-5 Restart policy + in-process watchdog | P1 | Edge reliability |
| P1-6 Memory safety: `mem_limit` + SD swap (sized from P1-3) | P1 | OOM-killer protection |
| P1-7 Deployment runbook + service file | P1 | Sprint-3 deliverable |
| P2-1 Export YOLO → ONNX (FP32 first; does not block integration) | P2 | Latency/RAM KPI |
| P2-2 INT8 quantization (YOLO + ripeness) | P2 | Final latency/RAM target |
| P2-3 Export ripeness model → ONNX | P2 | PyTorch removal from edge |
| P2-4 IQA footprint fix (torch-free or degrade) | P2 | PyTorch removal from edge |
| P2-5 Lazy model loading | P2 | OOM prevention |
| P3-1 Store-and-forward offline queue (depends on U-4 decision) | P3 | Connectivity resilience |
| P3-2 IQA threshold recalibration (needs actual hardware) | P3 | Production IQA accuracy |
