import json
import yaml
from ultralytics import YOLO
from camera_mock import MockCamera

def load_config(config_path="config.yaml"):
    """
    Loads the YAML configuration file containing pipeline settings.
    """
    try:
        with open(config_path, "r") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print(f"[Error] Configuration file '{config_path}' not found.")
        exit(1)

def run_pipeline():
    """
    Main execution loop for the AgRobot computer vision pipeline.
    """
    print("[Pipeline] Starting AgRobot Vision Pipeline...")
    
    # 1. Load configuration parameters
    config = load_config()
    model_path = config['yolo']['model_path']
    conf_thresh = config['yolo']['confidence_threshold']
    img_size = config['yolo']['image_size']
    
    # 2. Initialize YOLO Model
    print(f"[Pipeline] Loading YOLO model from '{model_path}'...")
    model = YOLO(model_path)
    
    # 3. Initialize Camera (Using MockCamera for testing)
    # Note: The Embedded team will replace this with their RealCamera class
    camera = MockCamera(image_folder='./images')
    
    # 4. Main Processing Loop
    frame_count = 0
    while True:
        # Pull the next frame from the camera buffer
        frame = camera.get_frame()
        
        # Break the loop if the camera stream ends
        if frame is None:
            print("[Pipeline] No more frames to process. Exiting...")
            break
            
        frame_count += 1
        print(f"\n--- Processing Frame #{frame_count} ---")
        
        # TODO: Add IQA (Image Quality Assessment) check here before running inference
        
        # Run YOLO inference using config settings
        results = model.predict(
            source=frame, 
            conf=conf_thresh, 
            imgsz=img_size, 
            verbose=False  # Keep terminal output clean
        )
        
        # Extract detection results into a clean JSON format
        detections = json.loads(results[0].to_json())
        print(f"[Pipeline] Found {len(detections)} tomatoes in this frame.")
        
        # TODO: Add MQTT publishing logic here to send 'detections' to the Cloud team
        
if __name__ == "__main__":
    run_pipeline()