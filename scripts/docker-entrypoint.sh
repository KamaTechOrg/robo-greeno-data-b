#!/usr/bin/env bash
# Container entrypoint. Model weights are already verified and baked into the image at
# build time (see scripts/fetch_models.sh run during `docker build`), so they are not
# re-checked here on every container start.
set -euo pipefail

echo "[entrypoint] $(date -u +%FT%TZ) starting pipeline (FRAME_SOURCE=${FRAME_SOURCE:-webcam})"
exec python -m pipeline.pipeline_using_agcloud_models
