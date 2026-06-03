import json

import cv2

from frame_quality.iqa_gate import IQAGate


iqa_gate = IQAGate()

def run_iqa(image):
    is_good, reason, metrics = iqa_gate.evaluate(image)

    return {
        "status": "OK" if is_good else "FAILED",
        "reason": reason,
        "metrics": metrics
    }


def mock_detection(image):
    # Mock implementation of object detection
    return {
        "label": "strawberry",
        "confidence": 0.9,
        "bbox": [10, 20, 50, 50]
    }


def build_json(detection, quality):
    # Mock implementation of MQTT payload
    return {
        "image_quality": quality,
        "detection": detection
    }


def run_pipeline(image):
    print("Running IQA...")
    quality = run_iqa(image)

    if quality["status"] != "OK":
        return {
            "image_quality": quality,
            "detection": None
        }
        
    print("Running detection...")
    detection = mock_detection(image)

    print("Building MQTT payload...")
    payload = build_json(detection, quality)

    return payload


if __name__ == "__main__":
    image_path = "apple.jpg"
    image = cv2.imread(image_path)
    result = run_pipeline(image)

    print("\nPipeline Output:")
    print(json.dumps(result, indent=4))