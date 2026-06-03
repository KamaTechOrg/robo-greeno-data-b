import json


def run_iqa(image):
    # Mock implementation of Image Quality Assessment
    return {
        "status": "OK",
        "score": 0.95
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

    print("Running detection...")
    detection = mock_detection(image)

    print("Building MQTT payload...")
    payload = build_json(detection, quality)

    return payload


if __name__ == "__main__":
    image = "sample.jpg"

    result = run_pipeline(image)

    print("\nPipeline Output:")
    print(json.dumps(result, indent=4))