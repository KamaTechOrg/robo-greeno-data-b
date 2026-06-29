# Detection Pipeline Architecture Extension

## Purpose

This document defines the internal architecture of the Detection Stage, focusing on:

* Multi-model execution
* Detector orchestration
* Early-exit optimization
* Aggregation of detection results

This document extends the existing Interface Contract and focuses on runtime behavior inside the detection subsystem.

---

# High-Level Architecture

```text
Frame Source
      |
      v
   IQA Gate
      |
      v
Detector Orchestrator
      |
      +------------------+
      |                  |
      v                  v
 AgCloud Model      Additional Models
      |                  |
      +--------+---------+
               |
               v
      Result Aggregator
               |
               v
        Output Publisher
```

---

# Detector Orchestrator

## Responsibility

The Detector Orchestrator manages all detection models and determines:

* Which models should run
* Execution order
* Parallel vs sequential execution
* Early-exit decisions
* Error isolation

The orchestrator receives validated frames from the IQA stage and forwards them to one or more detectors.

---

## Input

```json
{
  "frame_id": 123,
  "timestamp": "2026-06-04T14:30:00Z",
  "robot_id": "robot_01",
  "camera_id": "front_camera",
  "image_bytes": "<binary>"
}
```

---

## Output

```json
{
  "frame_id": 123,
  "detections": [
    {
      "class_name": "ripe_tomato",
      "confidence": 0.94,
      "source_model": "agcloud"
    }
  ]
}
```

---

# Multi-Model Execution Strategy

## Motivation

Different detection tasks may require different specialized models.

### Examples

| Task                | Model          |
| ------------------- | -------------- |
| Fruit detection     | AgCloud        |
| Disease detection   | Disease Model  |
| Ripeness estimation | Ripeness Model |
| Obstacle detection  | YOLO           |

A single model may not cover all required use cases.

---

## Parallel Execution

Preferred mode:

```text
Frame
  |
  +--> AgCloud
  |
  +--> Disease Detector
  |
  +--> Ripeness Detector
```

### Advantages

* Lower end-to-end latency
* Independent model execution
* Easier scaling

### Requirements

* Sufficient CPU and memory resources
* Thread-safe inference execution

---

## Sequential Execution

Fallback mode for resource-constrained edge devices.

```text
Frame
  |
  v
AgCloud
  |
  v
Disease Detector
  |
  v
Ripeness Detector
```

### Advantages

* Lower memory usage
* Simpler scheduling

### Disadvantages

* Higher latency

---

# Early Exit Mechanism

## Purpose

Reduce unnecessary computation on edge hardware.

---

## Example Scenario

If AgCloud determines with high confidence that no target object exists:

```json
{
  "class_name": "background",
  "confidence": 0.98
}
```

then additional detectors may be skipped.

---

## Decision Rule

```text
IF confidence >= threshold
AND no further analysis required

THEN stop pipeline
```

### Example

```text
Frame
  |
  v
AgCloud
  |
  +--> No tomato found
          |
          v
      Early Exit
```

instead of:

```text
AgCloud
  |
  v
Disease Detector
  |
  v
Ripeness Detector
```

---

## Configurable Threshold

```python
EARLY_EXIT_THRESHOLD = 0.95
```

The threshold should remain configurable and may be tuned during testing.

---

# Result Aggregation

## Purpose

Combine outputs from multiple detectors into a unified response.

---

## Aggregation Process

1. Collect results from all completed detectors.
2. Normalize class names according to ontology conventions.
3. Attach source model information.
4. Merge into a single detection payload.

---

## Example Aggregated Output

```json
{
  "frame_id": 123,
  "detections": [
    {
      "class_name": "tomato",
      "confidence": 0.94,
      "source_model": "agcloud"
    },
    {
      "class_name": "leaf_disease",
      "confidence": 0.87,
      "source_model": "disease_detector"
    }
  ]
}
```

---

# Error Handling

Detector failures must not stop the pipeline.

### Example

```text
AgCloud -> SUCCESS
Disease Detector -> FAILURE
Ripeness Detector -> SUCCESS
```

### Pipeline Behavior

* Log detector failure
* Continue processing remaining detectors
* Return partial results

### Example Response

```json
{
  "frame_id": 123,
  "detections": [...],
  "errors": [
    {
      "detector": "disease_detector",
      "message": "Inference timeout"
    }
  ]
}
```
