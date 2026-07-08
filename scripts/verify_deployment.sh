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
VERIFY_SECONDS="${VERIFY_SECONDS:-90}"

echo "[verify] building ${IMAGE_TAG}"

CREATE_TEMP_CERTS=false
if [ ! -d "certs" ]; then
    mkdir certs
    CREATE_TEMP_CERTS=true
fi

docker build -t "${IMAGE_TAG}" .

if [ "$CREATE_TEMP_CERTS" = true ]; then
    rm -rf certs
fi

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

CONTAINER_STATUS=$(docker inspect -f '{{.State.Running}}' vision-pipeline-test 2>/dev/null)

CONTAINER_LOGS=$(docker logs vision-pipeline-test)

docker stop vision-pipeline-test > /dev/null
docker rm vision-pipeline-test > /dev/null

if [ "$CONTAINER_STATUS" = "true" ] && ! echo "$CONTAINER_LOGS" | grep -qiE "traceback|exception|error"; then
    echo "=================================================="
    echo " SUCCESS: Vision pipeline container is stable!"
    echo "=================================================="
    exit 0
else
    echo "=================================================="
    echo " FAILURE: Container crashed or reported errors."
    echo "=================================================="
    echo "Last logs:"
    echo "$CONTAINER_LOGS" | tail -n 20
    exit 1
fi