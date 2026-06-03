import json

import cv2

from frame_quality.iqa_gate import IQAGate
from frame_source.file_source import FileSource
from frame_source.folder_source import FolderSource
from frame_source.synthetic_source import SyntheticSource


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
        "bbox": [10, 20, 50, 50],
        "success": True,
        "reason": ""
    }


def build_json(frame, detection, quality, detection_error = None):
    # Mock implementation of MQTT payload
    return {
        "frame_id": frame.frame_id,
        "timestamp": frame.timestamp,
        "source": frame.source,
        "image_quality": quality,
        "detection": detection,
        "detection_error": detection_error
    }


def run_pipeline(frame):
    print("Running IQA...")
    quality = run_iqa(frame.image)

    detection = None
    detection_error = None
    
    if quality["status"] == "OK":
        try:
            print("Running detection...")
            detection = mock_detection(frame.image)
        except Exception as e:
            detection_error = str(e)
    else:
        detection_error = "Skipped due to IQA failure"

    print("Building MQTT payload...")
    payload = build_json(frame, detection, quality, detection_error)

    return payload


if __name__ == "__main__":
    source = SyntheticSource()
    print(f"the source is {source}")
    while True:
        frame = source.read()
        
        if frame is None:
            break
        result = run_pipeline(frame)

        print("\nPipeline Output:")
        print(json.dumps(result, indent=4))