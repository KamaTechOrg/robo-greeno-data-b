#!/usr/bin/env bash
# Validates that the model weight files are present in the build context before they get
# baked into the image (Dockerfile COPYs model_weights/ then runs this at build time).
#
# TODO (backlog P1-4): once a versioned HTTPS artifact endpoint exists, replace this
# existence check with an actual `curl`/`wget` pull of $MODEL_VERSION from
# $ARTIFACT_BASE_URL plus a SHA-256 checksum verification, so weights no longer need to
# be placed locally before building.
set -euo pipefail

MODEL_WEIGHTS_DIR="${MODEL_WEIGHTS_DIR:-model_weights}"
REQUIRED_FILES=("yolov8-fruits.pt" "best_conditional.pt" "brisque_svm_weights.pth" "niqe_modelparameters.mat")

missing=0
for f in "${REQUIRED_FILES[@]}"; do
    path="${MODEL_WEIGHTS_DIR}/${f}"
    if [ ! -f "${path}" ]; then
        echo "[fetch_models] ERROR: missing required model file: ${path}" >&2
        missing=1
    else
        echo "[fetch_models] found ${path}"
    fi
done

if [ "${missing}" -ne 0 ]; then
    echo "[fetch_models] Place the AgCloud model weight files in '${MODEL_WEIGHTS_DIR}/' before building." >&2
    exit 1
fi

echo "[fetch_models] all required model weights present in ${MODEL_WEIGHTS_DIR}/"
