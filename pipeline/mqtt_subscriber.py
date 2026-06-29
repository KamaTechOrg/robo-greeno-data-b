"""
Tiny MQTT subscriber to watch what the pipeline publishes.

Run this in one terminal, then run the pipeline in another:

    python pipeline/mqtt_subscriber.py
    python -m pipeline.pipeline_using_agcloud_models

Every payload published to the detections topic is printed here as it arrives.
Override the broker/topic with the same env vars the pipeline uses:
    MQTT_HOST (default localhost), MQTT_PORT (default 1883),
    MQTT_TOPIC (default MQTT/vision/detections)
"""
import json
import os

import paho.mqtt.client as mqtt

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "MQTT/vision/detections")


def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"Connected to {MQTT_HOST}:{MQTT_PORT}, subscribing to '{MQTT_TOPIC}'")
    client.subscribe(MQTT_TOPIC, qos=1)


def on_message(client, userdata, msg):
    print(f"\n=== message on {msg.topic} ===")
    try:
        print(json.dumps(json.loads(msg.payload.decode()), indent=2))
    except Exception:
        print(msg.payload.decode(errors="replace"))


try:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
except (AttributeError, TypeError):
    client = mqtt.Client()

client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
print("Waiting for messages... (Ctrl+C to stop)")
client.loop_forever()
