# Deployable artifact for the vision pipeline (frame pull -> IQA -> detection -> ripeness -> MQTT publish).
# Runs as a non-root user so files written to bind-mounted volumes (e.g. ./crops) stay
# owned by a regular, editable/deletable UID on the host instead of root.
FROM python:3.12-slim

ARG APP_UID=1000
ARG APP_GID=1000


COPY certs/* /usr/local/share/ca-certificates/

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    update-ca-certificates && \
    apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        v4l-utils \
        libxcb1 \
        libx11-xcb1 \
        libxrender1 \
        libxext6 \
        libgl1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g "${APP_GID}" appuser \
    && useradd -m -u "${APP_UID}" -g "${APP_GID}" appuser

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY requirements-edge.txt .
RUN pip install --no-cache-dir -r requirements-edge.txt

COPY . .

RUN mkdir -p /home/appuser/.cache/torch/hub/pyiqa /home/appuser/.config
COPY model_weights/brisque_svm_weights.pth /home/appuser/.cache/torch/hub/pyiqa/brisque_svm_weights.pth
RUN chown -R appuser:appuser /home/appuser
# Validates model_weights/*.pt are present in the build context; baked into the image here,
# not re-checked at container startup (see scripts/docker-entrypoint.sh).
RUN bash scripts/fetch_models.sh

ENV MODEL_DIR=/app/model_weights

RUN chown -R appuser:appuser /app
USER appuser

ENTRYPOINT ["bash", "scripts/docker-entrypoint.sh"]
