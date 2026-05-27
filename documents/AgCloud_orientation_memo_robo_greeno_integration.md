# **AgCloud Orientation Memo**

**Owner:** DATA 2 Team  
**Project:** Robo-Greeno Spider Robots  
**Target Audience:** Cloud Team (Kayvan), Data Team B

## **1\. Existing CV Analysis & Strategy**

The original AgCloud CV infrastructure follows a **Cloud-Inference** model, heavily relying on continuous data streaming for central processing.

* **Decision:** We will shift to an **Edge-AI** architecture for the Spider Robots. We will bypass continuous cloud inference and heavy MQTT image streaming, but strictly reuse AgCloud's downstream data backbone, Flink ingestion logic, and final storage layers.

## **2\. Integrated Components & Service Details**

### **2.1 Monitoring & Observability Infrastructure**

| Service | Function | Access/Port |
| :---- | :---- | :---- |
| **Prometheus** | Core metrics collection and time-series database for system health. | Port: 9090 |
| **Grafana** | Visualization dashboard for metrics, system performance, and alerts. | Port: 3000 |
| **Alertmanager** | Handles alerts sent by client applications such as Prometheus or Flink. | Port: 9093 |
| **Pushgateway** | Allows ephemeral and batch jobs to expose their metrics to Prometheus. | Port: 9091 |

### **2.2 Data Backbone & Streaming**

| Service | Function | Details |
| :---- | :---- | :---- |
| **Kafka** | Distributed event streaming platform used as the primary data backbone. | Ports: 9092 (Int), 29092 (Ext) |
| **Vector Service** | High-performance service for handling vector data and embeddings. | Port: 8006 |
| **Flink (Cluster)** | Stream processing engine for real-time data transformations and model dispatching. | UI Port: 8081 |

### **2.3 AgCloud Services Mapping: Utilization vs. Bypass**

To integrate effectively, we must categorize which existing AgCloud services fit our Edge-AI flow and which will be bypassed:

**Services We Will Utilize:**

* **mosquitto:** Standard MQTT broker. Receives lightweight JSON metadata and telemetry from the Edge (Port 1883 | Topic: MQTT/vision/detections).  
* **mqtt\_gateway:** Bridge service. Automatically forwards metadata messages from MQTT to Kafka (Target: rover.images.meta.v1).  
* **flink\_writer\_db:** Stream processor. Consumes from Kafka and writes structured data to Postgres. **Crucial constraint:** This service maps JSON fields directly to database columns based on the Kafka topic name. The JSON contract must perfectly match the Postgres schema, or data ingestion will fail.  
* **PostgreSQL:** Relational DB. Stores long-term mission logs and detection history (Port 5432 | DB: missions\_db).  
* **MinIO:** S3-Compatible Object Storage. Holds the physical image files for GUI display (Port 9001).

**Services We Will Bypass:**

* **large-mosquitto & mqtt\_ingest:** Optimized for live, raw binary image uploads via MQTT. We bypass this to conserve bandwidth, opting instead for direct batch HTTP uploads to the MinIO imagery bucket.

## **3\. Machine Learning Models & Inference Engines**

The AgCloud platform utilizes a variety of specialized models. Documenting these ensures we know what capabilities exist for potential reuse:

### **3.1 Computer Vision (CV) Models**

* **Fruit Detection & Ripeness:** \* *Architecture:* YOLOv8 (specifically yolov8-fruits.pt).  
  * *Task:* Real-time object detection for fruits in the field.  
* **Fruit Ripeness & Defect Analysis:** \* *Ripeness API:* Utilizes a conditional model (best\_conditional) to classify ripeness stages of Apples, Bananas, and Oranges.  
  * *Fruit Classification:* A PyTorch Script model (fruit\_cls\_best.ts) runs on a dedicated HTTP service to classify fruits and detect defects, routing data to a fruit-defect-sink.  
* **Weed Detection:** \* *Architecture:* MobileNetV3 combined with heuristic analysis (Excess Green \- ExG).  
  * *Pipeline:* Uses Otsu thresholding for initial segmentation followed by ML refinement.  
* **Leaf Disease Detection:** \* *Task:* Analyzes images of crop leaves to detect early signs of diseases and botanical stress.  
  * *Pipeline Integration:* Triggered automatically via the image.new.leaves Kafka topic when new images are uploaded. It operates as a secondary step after weed/crop segmentation.  
* **Security & Anomaly Detection:** \* *MegaDetector (MDV5A):* Wildlife detection and camera trap analysis (Confidence threshold: 0.2).  
  * *CLIP (RN50):* Uses OpenAI's CLIP architecture for zero-shot anomaly detection.  
  * *Mask Classifier:* ONNX-based YOLOv8 model for detecting protective gear/masks.  
* **Aerial & Drone Imagery Analytics:** \* *Models Used:* Employs PyTorch models including an Object Detection API, Anomaly Detection, and a Spatial Segmentation model to map out top-down field conditions.

### **3.2 Acoustic & Audio Analysis**

* **Sound Classifier:** \* *Architecture:* PANNs (Pretrained Audio Neural Networks) \- Cnn14.  
  * *Performance:* The model Cnn14\_mAP=0.431.pth indicates a Mean Average Precision (mAP) of 0.431 on the AudioSet dataset.  
  * *Tasks:* Environmental sound classification and acoustic plant stress detection.

### **3.3 Environmental Models**

* **Soil Moisture Prediction:** ONNX-based model (soil\_moisture\_best.onnx) used for irrigation control logic.

## **4\. Kafka Messaging Infrastructure (Topics)**

To integrate with the AgCloud data stream, services must produce or consume from the following primary topics:

| Topic Category | Topic Name | Description |
| :---- | :---- | :---- |
| **Vision/Images** | image.new.fruits, image.new.ground, image.new.aerial, image.new.leaves | Triggers for CV inference pipelines. |
| **Acoustics** | sound.new.sounds, sound.new.plants | Ingested audio files ready for classification. |
| **Inference Results** | rover.images.meta.v1 | Metadata and detection results for the rover team. |
| **Alerts** | alerts | Central topic for all system-generated warnings. |
| **Sensors** | sensors, sensor\_anomalies | Raw telemetry and detected sensor faults. |

## **5\. Input/Output Contract (JSON)**

To ensure the flink\_writer\_db maps data correctly to PostgreSQL, our Edge devices will strictly adhere to the following JSON structure:

JSON  
{  
  "mission\_id": "m\_1002",  
  "device\_id": "spider\_01",  
  "timestamp": "ISO-8601",  
  "location": {  
    "lat": 31.04,  
    "lon": 34.85  
  },  
  "inference\_results": {  
    "detections": \[...\]  
  },  
  "image\_filename": "unique\_id.jpg"  
}

## **6\. Data Storage & Access**

Our data will be persisted using AgCloud's existing storage layer:

* **Object Storage (MinIO):** Physical images will be stored in the imagery bucket, accessible via port 9001\.  
* **Relational DB (PostgreSQL):** Structured metadata will be stored in missions\_db. We will rely entirely on the existing flink\_writer\_db to automate this transfer without writing manual SQL.

## **7\. Hardware & Known Concerns**

* **Hardware Interfacing:** AgCloud uses a central Docker server for backend processing, while our inference runs entirely on the Edge (Raspberry Pi).  
* **Concerns:** Handling network latency and ensuring strict synchronization between the JSON metadata pushed to Kafka and the actual image files uploaded to MinIO.

## **8\. Planned Next Steps (Definition of Done)**

1. **Protocol Validation:** Finalize the MQTT metadata payload and ensure flink\_writer\_db parses the location and filename fields flawlessly.  
2. **Integration Test:** Execute a manual end-to-end test (Robot Edge Simulator \-\> MQTT \-\> Kafka \-\> Postgres & MinIO).  
3. **Pipeline Confirmation:** Review the exact entry points for the existing leaf\_pipelines to ensure our weed/leaf detections trigger it correctly.  
4. **Sign-off:** Final document review and approval by the Cloud Team regarding the utilized vs. bypassed components.

