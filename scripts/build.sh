#!/usr/bin/env bash
# Builds the vision container image, capturing every build-step command and its full
# STDIO to a timestamped log file so the build can be reviewed after the fact.
set -euo pipefail

cd "$(dirname "$0")/.."

IMAGE_TAG="${IMAGE_TAG:-robo-greeno-vision:local}"
mkdir -p logs
LOG_FILE="logs/build_$(date -u +%Y%m%dT%H%M%SZ).log"

CREATE_TEMP_CERTS=false
if [ ! -d "certs" ]; then
    mkdir certs
    CREATE_TEMP_CERTS=true
fi

echo "[build] building ${IMAGE_TAG}, logging to ${LOG_FILE}"

cleanup() {
    if [ "$CREATE_TEMP_CERTS" = true ]; then
        rm -rf certs
    fi
}
trap cleanup EXIT

if docker build --progress=plain -t "${IMAGE_TAG}" . 2>&1 | tee "${LOG_FILE}"; then
    echo "[build] SUCCESS: ${IMAGE_TAG}"
    docker images "${IMAGE_TAG}"
else
    echo "[build] FAILED — see ${LOG_FILE}" >&2
    exit 1
fi
