# Interface Contract Document

## 1. image_source → iqa_gate

### Purpose
Transfer raw camera frames from robot cameras into the image quality validation stage.

### Transport
asyncio.Queue (Python async in-memory queue)

### Producer
image_source

### Consumer
iqa_gate

### Input Payload Schema
```json
{
  "frame_id": int,
  "timestamp": str,
  "robot_id": str,
  "camera_id": str,
  "image_bytes": "bytes",
  "encoding": "jpeg"
}
```

### Expected Throughput
To be defined with embedded team (images per robot per second).

### Error Handling
- Corrupt frame → drop frame  
- Missing metadata → warning log  
- Decode failure → reject frame  

### Async Behavior
Non-blocking producer/consumer queue.

### Mock Strategy
Local scripts can inject test JPEG files into the queue.

---

## 2. iqa_gate → detector

### Purpose
Pass validated high-quality frames into the object detection pipeline.

### Transport
asyncio.Queue

### Producer
iqa_gate

### Consumer
detector

### Input Payload Schema
```json
{
  "frame_id": int,
  "timestamp": str,
  "robot_id": str,
  "camera_id": str,
  "image_bytes": "bytes",
  "encoding": "jpeg",
  "quality_score": float
}
```

### Validation Rules
- quality_score threshold: TBD  
- Image must decode successfully  
- Minimum resolution: TBD  

### Error Handling
- Low-quality image → reject frame  
- Decode failure → log + drop frame  

### Mock Strategy
Mock IQA module assigns random or fixed quality scores.

---

## 3. detector → json_serializer

### Purpose
Convert detector outputs into standardized structured detection records.

### Transport
Internal async function call

### Producer
detector

### Consumer
json_serializer

### Detection Payload Schema
```json
{
  "frame_id": int,
  "robot_id": str,
  "timestamp": str,
  "inference_results": [
    {
      "task_type": str,
      "label": str,
      "confidence": float,
      "bbox": [int, int, int, int],
      "attributes": {}
    }
  ]
}
```

### Detection Rules
- Bounding box format: [x_min, y_min, x_max, y_max]
- Confidence range: 0.0 - 1.0

### Error Handling
- Empty detections → send empty list  
- Invalid bounding box → discard detection  
- Detector crash → log error  

### Async Behavior
Stateless processing.

### Mock Strategy
Dummy detector emits fixed detections for test images.

---

## 4. json_serializer → mqtt_publisher

### Purpose
Serialize structured detections into MQTT-ready payloads.

### Transport
Internal async queue

### Producer
json_serializer

### Consumer
mqtt_publisher

### Serialized Payload Format
```json
{
  "event_type": "string",
  "robot_id": "string",
  "frame_id": int,
  "timestamp": "string",
  "detections": [
    {
      "task_type": "string",
      "label": "string",
      "confidence": float,
      "bbox": [int, int, int, int],
      "attributes": {}
    }
  ]
}
```

### Serialization Format
UTF-8 JSON

### Error Handling
- Serialization failure → log + drop payload  
- Invalid schema → reject message  

### Async Behavior
Non-blocking producer.

### Mock Strategy
Static JSON payload generator from sample detections.

---

## 5. mqtt_publisher → cloud_sink

### Purpose
Publish detection events into the cloud ingestion service.

### Transport
MQTT

### Producer
mqtt_publisher

### Consumer
cloud_sink

### MQTT Topic
greenhouse/detections/{robot_id}

### MQTT Configuration
- QoS: 1  
- Retention: Disabled  
- Payload: UTF-8 JSON  

### Retry Policy
Exponential backoff retry mechanism.

### Error Handling
- Network failure → buffer locally  
- Broker unavailable → retry queue  
- Publish failure → log error  

### Async Behavior
Event-driven asynchronous publishing.

### Mock Strategy
Local Mosquitto broker for development/testing.
