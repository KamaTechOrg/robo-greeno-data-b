# Deployment Runbook — Vision Pipeline Container

**Purpose:** get the vision pipeline (frame pull → IQA → detection → ripeness → MQTT publish)
running as a container, either for off-bot verification or on the actual Raspberry Pi bot.
This is the first deployable artifact for the pipeline — see `documents/deployment_proposal.md`
for the full design rationale and `documents/deployment_issues_backlog.md` for the broader
follow-on work (pose integration, edge-optimized model formats, versioned model artifact
fetch, watchdog/memory limits) that is intentionally **out of scope** here.

## 1. Prerequisites

- Docker Engine with Compose v2 (`docker compose version`).
- The two gitignored AgCloud model weight files, obtained separately (see `pipeline/README.md`
  for their source):
  - `yolov8-fruits.pt` (mandatory — the pipeline fails to start without it)
  - `best_conditional.pt` (optional — a missing file logs a warning and falls back to
    randomly-initialized ripeness weights, it does not block startup)
- A camera reachable at `/dev/video0` (only required for a real on-bot run; not needed for
  off-bot verification, see §4).

## 2. Place model weights

Create a `model_weights/` folder at the repo root (same level as this `Dockerfile`) and place
both files there:

```
model_weights/
├── yolov8-fruits.pt
└── best_conditional.pt
```

`scripts/fetch_models.sh` runs during `docker build` and fails the build early with a clear
error if either file is missing. Weights are baked into the image at build time — there is no
runtime fetch step (see `documents/deployment_proposal.md` §8.2 for the future versioned
HTTPS artifact-fetch plan, backlog item P1-4).

## 3. Configure

Copy `.env.example` to `.env` and adjust:

- `FRAME_SOURCE` — `webcam` on the actual bot; `synthetic` for a no-camera smoke test (§4);
  `folder` to replay a local image directory (dev/eval parity).
- `MQTT_HOST` / `MQTT_TOPIC` / `DEFECT_SERVICE_URL` — point at the off-bot broker and defect
  service; both run off the bot in production (the bot only runs the vision container).
- `MINIO_UPLOAD_ENABLED` — leave at `0`. The bot is never a MinIO writer in production.
- `APP_UID` / `APP_GID` — set to match the UID/GID of whoever needs to read/delete files under
  `./crops` on the host (defaults to `1000:1000`); the container runs as this non-root user.

## 4. Build

```bash
bash scripts/build.sh
```

Builds the image, streaming every build step's STDIO to the terminal and to a timestamped
`logs/build_<timestamp>.log` file for later review. Fails non-zero (and via `set -e`) if any
step — including the model-weight check — fails.

## 5. Verify off-bot (no camera needed)

Before handing this to Embedded, confirm the artifact actually loads and runs a cycle, without
needing real hardware:

```bash
bash scripts/verify_deployment.sh
```

This builds the image, starts a container with `FRAME_SOURCE=synthetic` (a generated test
frame, no camera), `MQTT_ENABLED=0`, `MINIO_UPLOAD_ENABLED=0`, lets it run for ~20s, and checks
the logs for: the entrypoint's startup line, at least one full pipeline cycle completing
(model loading, IQA, and the "Publishing to MQTT..." step), and the absence of any fatal
traceback.

## 6. Run

On a dev machine or the bot itself:

```bash
bash scripts/run.sh
```

Runs `docker compose up --build` in the foreground, streaming output to the terminal and to
`logs/run_<timestamp>.log`. Use `Ctrl+C` to stop, or run detached with
`docker compose up --build -d` and follow with `docker compose logs -f`.

For a real camera pull (the issue's definition of done — "the pipeline pulls an image"), set
`FRAME_SOURCE=webcam` in `.env` and make sure `docker-compose.yml`'s `/dev/video0:/dev/video0`
device line is present (it's commented out only for the no-camera synthetic verification path).

## 7. Processed images ↔ detection results

Each detection result in the published MQTT JSON includes `crop_path` and the parent `run_id`
(see `build_json()` / `mock_detection()` in `pipeline/pipeline_using_agcloud_models.py`). Crops
are written under the container's `STORAGE_DIR_OVERRIDE` path, which `docker-compose.yml` binds
to `./crops` on the host — so the exact image referenced by a given detection result is
available at `./crops/runs/<run_id>/crops/crop_<index>.jpg` on the host, owned by the
`APP_UID:APP_GID` configured in `.env` (not root).

## 8. Logs

- **Build**: `logs/build_<timestamp>.log` (from `scripts/build.sh`).
- **Run**: `logs/run_<timestamp>.log` (from `scripts/run.sh`), or `docker compose logs -f`
  / `docker logs <container>` for a live/attached view.
- **In-container**: structured log lines (timestamp, level, message) to stdout, controlled by
  the `LOG_LEVEL` env var (`INFO` by default; set `DEBUG` to also see full per-frame JSON
  payloads).

## 9. Troubleshooting

| Symptom | Likely cause |
|---|---|
| Build fails at `fetch_models.sh` | `model_weights/*.pt` not placed before building (§2) |
| Container exits immediately, no camera error | `FRAME_SOURCE=webcam` but no `/dev/video0` device mapped, or no camera attached |
| Crops on host are owned by `root`, can't be deleted | `APP_UID`/`APP_GID` in `.env` don't match the image build args — rebuild after setting them |
| MQTT publish warnings in logs | Broker unreachable at `MQTT_HOST`/`MQTT_PORT` — pipeline still runs and logs payloads, just doesn't publish (best-effort, by design) |
