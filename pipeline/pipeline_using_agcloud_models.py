import json
from pathlib import Path
import uuid

import cv2
import requests

from frame_quality.iqa_gate import IQAGate
from frame_source.file_source import FileSource
from frame_source.webcam_source import WebcamSource
from frame_source.folder_source import FolderSource
from ultralytics import YOLO
from minio import Minio

import torch
import torch.nn as nn
from torchvision.models import mobilenet_v3_large, MobileNet_V3_Large_Weights
from torchvision import transforms
from PIL import Image
import torch.nn.functional as F

# ============================================================
# Configuration & Directories
# ============================================================

DEFECT_SERVICE_URL = "http://localhost:8011/infer_json"
BUCKET_NAME = "imagery"

BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
RUNS_DIR = STORAGE_DIR / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# Labels & Constants
# ============================================================

YOLO_FRUIT_LABELS = {
    "apple", "banana", "orange", "pear", "peach",
    "plum", "mango", "grape", "cherry", "pomegranate"
}

RIPENESS_FRUITS = ["apple", "banana", "orange", "pineapple"]
RIPENESS_LABELS = ["unripe", "ripe", "overripe"]

DEVICE = "cpu"

# ============================================================
# MinIO Client
# ============================================================

mc = Minio(
    "localhost:9000",
    access_key="minioadmin",
    secret_key="minioadmin123",
    secure=False
)

if not mc.bucket_exists(BUCKET_NAME):
    mc.make_bucket(BUCKET_NAME)


# ============================================================
# Ripeness Model Architecture
# ============================================================
class RipenessModelConditional(nn.Module):
    """
    Image -> MobileNetV3 backbone
    Fruit type (idx) -> Embedding
    Concatenate -> Linear -> ripeness logits
    """
    def __init__(self, num_ripeness: int, num_fruits: int, embed_dim: int = 16):
        super().__init__()
        weights = MobileNet_V3_Large_Weights.IMAGENET1K_V2
        self.backbone = mobilenet_v3_large(weights=weights)
        in_feats = self.backbone.classifier[-1].in_features
        self.backbone.classifier[-1] = nn.Identity()
        self.fruit_embed = nn.Embedding(num_fruits, embed_dim)
        self.head = nn.Linear(in_feats + embed_dim, num_ripeness)

    def forward(self, x, fruit_idx):
        feats = self.backbone(x)                  # [B, in_feats]
        fvec  = self.fruit_embed(fruit_idx)       # [B, embed_dim]
        out   = torch.cat([feats, fvec], dim=1)   # [B, in_feats+embed_dim]
        return self.head(out)                     # [B, num_ripeness]


def build_conditional(num_ripeness: int, num_fruits: int, embed_dim: int = 16) -> nn.Module:
    return RipenessModelConditional(num_ripeness, num_fruits, embed_dim)


# ============================================================
# Initialize Models
# ============================================================

print("Loading Models...")

YOLO_MODEL = YOLO("yolov8-fruits.pt")
iqa_gate = IQAGate()

# Load Ripeness Model
ROTTEN_MODEL = build_conditional(
    num_ripeness=len(RIPENESS_LABELS),
    num_fruits=len(RIPENESS_FRUITS)
)

try:
    state_dict = torch.load("best_conditional.pt", map_location=DEVICE)
    ROTTEN_MODEL.load_state_dict(state_dict)
except FileNotFoundError:
    print("Warning: best_conditional.pt not found. Make sure the file exists.")

ROTTEN_MODEL.eval()

ROTTEN_TRANSFORM = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    ),
])

# ============================================================
# Pipeline Functions
# ============================================================

def run_iqa(image):
    is_good, reason, metrics = iqa_gate.evaluate(image)

    return {
        "status": "OK" if is_good else "FAILED",
        "reason": reason,
        "metrics": metrics
    }

def detect_and_crop(image):
    """
    Detect fruits in the image and return cropped fruit images.
    """

    result = YOLO_MODEL.predict(
        image,
        conf=0.3,
        verbose=False
    )[0]

    crops = []

    for box in result.boxes:

        label = result.names[int(box.cls[0])]

        if label not in YOLO_FRUIT_LABELS:
            continue

        x1, y1, x2, y2 = map(int, box.xyxy[0])
        crop = image[y1:y2, x1:x2]

        if crop.size == 0:
            continue

        crops.append({
            "label": label,
            "image": crop
        })

    return crops

def save_crop(crop_image, crop_path):
    cv2.imwrite(str(crop_path), crop_image)

def upload_crop_to_minio(bucket_name, crop_path, object_name):
    mc.fput_object(bucket_name, object_name, str(crop_path))
  
def call_defect_model(bucket_name, object_name):
    try:
        response = requests.post(
            DEFECT_SERVICE_URL,
            json={"bucket": bucket_name, "key": object_name},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}
      
def predict_ripeness(crop_path: str, fruit_label: str):
    """
    Predict if fruit is unripe / ripe / overripe
    """
    # Check if fruit is supported by our PyTorch model
    if fruit_label not in RIPENESS_FRUITS:
        return {
            "ripeness_label": "unknown",
            "confidence": 0.0,
            "reason": f"Fruit '{fruit_label}' not supported by ripeness model"
        }

    image = Image.open(crop_path).convert("RGB")
    tensor = ROTTEN_TRANSFORM(image).unsqueeze(0).to(DEVICE)
    
    fruit_idx = torch.tensor([RIPENESS_FRUITS.index(fruit_label)]).to(DEVICE)

    with torch.no_grad():
        logits = ROTTEN_MODEL(tensor, fruit_idx)
        probs = F.softmax(logits, dim=1)
        pred_idx = torch.argmax(probs, dim=1).item()
        confidence = probs[0][pred_idx].item()

    return {
        "ripeness_label": RIPENESS_LABELS[pred_idx],
        "confidence": float(confidence)
    }

def process_single_fruit(crop, label, fruit_index, run_id, crops_dir, bucket_name):
    """
    Process a single fruit crop: save, upload, defect check, ripeness check.
    """
    crop_path = crops_dir / f"crop_{fruit_index}.jpg"
    
    # 1. Save Crop
    save_crop(crop, crop_path)

    # 2. Upload to MinIO
    object_name = f"pipeline/{run_id}/crops/crop_{fruit_index}.jpg"
    upload_crop_to_minio(bucket_name, crop_path, object_name)

    # 3. Defect Detection (API Call)
    defect_result = call_defect_model(bucket_name, object_name)

    # 4. Ripeness Prediction (PyTorch Model)
    ripeness_result = predict_ripeness(str(crop_path), label)

    return {
        "fruit_index": fruit_index,
        "label": label,
        "crop_path": str(crop_path),
        "minio_key": object_name,
        "defect_result": defect_result,
        "ripeness_result": ripeness_result
    }
    
def mock_detection(image):
    run_id = str(uuid.uuid4())
    crops_dir = (RUNS_DIR / run_id / "crops")
    crops_dir.mkdir(parents=True, exist_ok=True)
    
    detected_fruits = detect_and_crop(image)
    results = []
    
    for fruit_index, fruit_data in enumerate(detected_fruits):
        result = process_single_fruit(
            crop=fruit_data["image"],
            label=fruit_data["label"],
            fruit_index=fruit_index,
            run_id=run_id,
            crops_dir=crops_dir,
            bucket_name=BUCKET_NAME
        )
        results.append(result)

    return {
        "run_id": run_id,
        "total_fruits": len(results),
        "results": results,
        "success": True,
        "reason": ""
    }
    
def build_json(frame, detection, quality, detection_error=None):
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
    
    if quality["status"] in ["OK", "Borderline"]:
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
    source = FolderSource("images")
    while True:
        frame = source.read()
        
        if frame is None:
            break
        result = run_pipeline(frame)

        print("\nPipeline Output:")
        print(json.dumps(result, indent=4))