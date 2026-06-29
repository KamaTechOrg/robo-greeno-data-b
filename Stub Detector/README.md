# Stub Detector

## IMPORTANT WARNING: NOT A REAL AI MODEL
**Do NOT use this module for machine learning evaluation or production deployment.** This is a explicitly simple, hardcoded **Stub Detector** created for Sprint 2. It does not process images or run any actual AI inference. It will always return predefined, fake bounding boxes labeled as "tomato". 

## Purpose
The goal of this module is to unblock the team and allow end-to-end testing of the data pipeline (from the IQA Gate to the Cloud Sink) without the overhead, latency, or setup complexity of a real deep learning model.

## Interface Contract
This stub strictly adheres to the Sprint 1 Interface Contract (`iqa_gate -> detector -> json_serializer`).
* **Input:** Receives an async dictionary containing `frame_id`, `robot_id`, and `image_bytes`.
* **Output:** Returns a structured dictionary containing an ISO 8601 `timestamp` and a list of `inference_results` (bounding boxes).
* **Error Handling:** If invalid data is provided, it catches the crash gracefully, logs the error, and returns an empty list of detections to prevent pipeline failure.

## Running the Tests
A comprehensive test suite is included to verify the happy path, missing metadata, and failure injection scenarios.
To run the tests locally, navigate to this directory and execute:
```bash
python test_stub_detector.py