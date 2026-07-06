# Deployable artifact for the vision pipeline (frame pull -> IQA -> detection -> ripeness -> MQTT publish).
# Runs as a non-root user so files written to bind-mounted volumes (e.g. ./crops) stay
# owned by a regular, editable/deletable UID on the host instead of root.
FROM python:3.12-slim

ARG APP_UID=1000
ARG APP_GID=1000

# libglib2.0-0: required by opencv-python-headless on a slim base for cv2.VideoCapture (V4L2).
# v4l-utils: gives `v4l2-ctl --list-devices` as an on-bot camera diagnostic tool.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        v4l-utils \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g "${APP_GID}" appuser \
    && useradd -m -u "${APP_UID}" -g "${APP_GID}" appuser

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY requirements-edge.txt .
RUN pip install --no-cache-dir -r requirements-edge.txt

COPY . .

# Validates model_weights/*.pt are present in the build context; baked into the image here,
# not re-checked at container startup (see scripts/docker-entrypoint.sh).
RUN bash scripts/fetch_models.sh

ENV MODEL_DIR=/app/model_weights

RUN chown -R appuser:appuser /app
USER appuser

ENTRYPOINT ["bash", "scripts/docker-entrypoint.sh"]
