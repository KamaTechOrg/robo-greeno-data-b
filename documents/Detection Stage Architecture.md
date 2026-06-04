# Edge AI Detection Pipeline Architecture

## Overview
This document defines the architecture for the edge AI pipeline responsible for image quality assessment, object detection, serialization, and cloud publishing.

The system is designed as an asynchronous, queue-based pipeline to ensure non-blocking execution and scalability per robot stream.

---

# 1. image_source → iqa_gate

## Purpose
Transfer raw camera frames from robot cameras into the image quality validation stage.

## Transport
asyncio.Queue (in-memory async queue)

## Input Payload Schema
```json
{
  "frame_id": "int",
  "timestamp": "str",
  "robot_id": "str",
  "camera_id": "str",
  "image_bytes": "bytes",
  "encoding": "jpeg"
}
```

## Output
Validated frame with quality score.

## Error Handling
- Corrupt frame → drop frame
- Missing metadata → warning log
- Decode failure → reject frame

## Async Behavior
Non-blocking producer/consumer model per robot stream.

## Mock Strategy
Local scripts inject JPEG files into queue.

---

# 2. iqa_gate → detector

## Purpose
Pass validated high-quality frames into object detection pipeline.

## Transport
asyncio.Queue

## Input Payload Schema
```json
{
  "frame_id": "int",
  "timestamp": "str",
  "robot_id": "str",
  "camera_id": "str",
  "image_bytes": "bytes",
  "encoding": "jpeg",
  "quality_score": "float"
}
```

## Validation Rules
- quality_score >= 0.6 (configurable threshold)
- Image must decode successfully
- Minimum resolution required (configurable)

## Error Handling
- Low-quality image → reject
- Decode failure → log + drop frame

## Mock Strategy
Random or fixed quality scores assigned by mock IQA module.

---

# 3. Detector Stage Architecture

## Purpose
Run inference on validated frames and produce structured detection results.

## Transport
asyncio.Queue

## Input Schema
Same as iqa_gate output.

## Output Schema
```json
{
  "frame_id": "int",
  "robot_id": "str",
  "timestamp": "str",
  "inference_results": [
    {
      "task_type": "str",
      "label": "str",
      "confidence": "float",
      "bbox": [0, 0, 0, 0],
      "attributes": {}
    }
  ]
}
```

## Detection Rules
- bbox format: [x_min, y_min, x_max, y_max]
- confidence: 0.0 - 1.0
- empty detections allowed []

## Error Handling
- Empty image → reject
- Decode failure → drop + log
- Detector crash → log error, continue pipeline

## Async Behavior
Stateless inference workers, scalable via worker pool.

## Mock Strategy
Fixed detections (e.g., strawberry) or randomized outputs.

---

# 4. detector → json_serializer

## Purpose
Convert detector outputs into standardized structured detection records.

## Transport
Internal async function call / queue

## Output Schema
```json
{
  "event_type": "str",
  "robot_id": "str",
  "frame_id": "int",
  "timestamp": "str",
  "detections": []
}
```

## Error Handling
- Serialization failure → log + drop
- Invalid schema → reject message

## Async Behavior
Non-blocking transformation layer.

## Mock Strategy
Static JSON generation from sample detections.

---

# 5. mqtt_publisher → cloud_sink

## Purpose
Publish detection events to cloud ingestion service.

## Transport
MQTT

## Topic
greenhouse/detections/{robot_id}

## Configuration
- QoS: 1
- Retention: disabled

## Error Handling
- Network failure → local buffer
- Broker unavailable → retry queue
- Publish failure → exponential backoff retry

## Async Behavior
Event-driven asynchronous publishing.

## Mock Strategy
Local Mosquitto broker for testing.

---

# 6. Async System Design

## Core Pattern
- asyncio.Queue per pipeline stage
- Producer/consumer architecture
- Backpressure handled via queue limits

## Pipeline Flow
image_source → iqa_gate → detector → serializer → mqtt_publisher → cloud_sink

---

# 7. Global Error Handling Strategy

- Frame corruption → drop early
- Validation failures → reject stage-wise
- Inference failures → log + continue
- Serialization failures → drop payload
- MQTT failures → retry with backoff

---

# 8. Scalability Considerations

- Detector stage can be horizontally scaled (worker pool)
- Queue isolation per robot improves throughput
- Stateless inference enables GPU distribution
- Backpressure prevents overload on downstream services

---

# 9. Mocking Strategy (Development Mode)

- Webcam/file source for image injection
- Fake IQA scores for testing thresholds
- Dummy detector outputs for repeatability
- Local MQTT broker simulation

---

# End of Document
