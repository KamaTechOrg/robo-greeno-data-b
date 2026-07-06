#!/usr/bin/env bash
# Off-bot verification: (1) confirm the image builds and the artifact is generated, and
# (2) confirm the artifact can be loaded and run at least one pipeline cycle without a
# real camera, broker, or MinIO — using FRAME_SOURCE=synthetic instead of a real bot.
#
# Not wired into CI (not required for this issue's scope); run by hand, or drop into a
# CI job later as a fast-follow.
set -euo pipefail

cd "$(dirname "$0")/.."

IMAGE_TAG="${IMAGE_TAG:-robo-greeno-vision:verify}"
CONTAINER_NAME="robo-greeno-vision-verify-$$"
VERIFY_SECONDS="${VERIFY_SECONDS:-20}"

echo "[verify] building ${IMAGE_TAG}"
docker build -t "${IMAGE_TAG}" .
echo "[verify] build succeeded — artifact generated:"
docker images "${IMAGE_TAG}"

echo "[verify] starting container '${CONTAINER_NAME}' with FRAME_SOURCE=synthetic (no camera/broker/MinIO required)"
docker run -d --name "${CONTAINER_NAME}" \
    -e FRAME_SOURCE=synthetic \
    -e MQTT_ENABLED=0 \
    -e MINIO_UPLOAD_ENABLED=0 \
    -e LOG_LEVEL=INFO \
    "${IMAGE_TAG}" >/dev/null

cleanup() {
    docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[verify] letting it run for ${VERIFY_SECONDS}s..."
sleep "${VERIFY_SECONDS}"

LOGS="$(docker logs "${CONTAINER_NAME}" 2>&1)"
echo "----- container logs -----"
echo "${LOGS}"
echo "---------------------------"

if ! echo "${LOGS}" | grep -q "starting pipeline"; then
    echo "[verify] FAILED: entrypoint start line not found in logs" >&2
    exit 1
fi

if ! echo "${LOGS}" | grep -q "Publishing to MQTT"; then
    echo "[verify] FAILED: no pipeline cycle completed (no 'Publishing to MQTT' log line)" >&2
    exit 1
fi

if echo "${LOGS}" | grep -qiE "Traceback \(most recent call last\)"; then
    echo "[verify] FAILED: a fatal traceback was logged" >&2
    exit 1
fi

echo "[verify] SUCCESS: image builds, and the artifact loads models and completes at least one pipeline cycle without a real bot"
