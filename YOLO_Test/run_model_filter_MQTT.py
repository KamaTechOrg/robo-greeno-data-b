import json
from ultralytics import YOLO

def map_to_ontology(raw_label):
    """
    Takes a raw label from the LaboroTomato model (e.g., 'l_green' or 'b_fully_ripened')
    and returns the standardized label according to the Data Ontology v1.0 document.
    """
    label = raw_label.lower()
    
    if "fully_ripened" in label:
        return "tomato_ripe"
    
    elif "half_ripened" in label:
        return "tomato_half_ripe"
    
    elif "green" in label:
        return "tomato_unripe"
    
    else:
        return "unknown_object"

def process_model_output(results, confidence_threshold=0.65):
    """
    Takes the results object from YOLO inference, filters out low-confidence detections,
    and returns a clean list ready to be sent via MQTT.
    """
    final_detections = []
    
    # If no detections were found, return an empty list
    if not results or not results[0].boxes:
        return final_detections
        
    boxes = results[0].boxes
    class_names_dict = results[0].names

    for box in boxes:
        conf = float(box.conf[0])
        
        # 1. Filter by confidence threshold (removes blurry background tomatoes)
        if conf < confidence_threshold:
            continue
            
        # 2. Extract the original class from the model
        class_id = int(box.cls[0])
        raw_label = class_names_dict[class_id]
        
        # 3. Translate to our Ontology language
        ontology_label = map_to_ontology(raw_label)
        
        # 4. Extract bounding box coordinates (for robot kinematics)
        coords = box.xyxy[0].tolist() # [x_min, y_min, x_max, y_max]
        
        # Pack the data into a clean dictionary that is easy to convert to JSON
        final_detections.append({
            "class": ontology_label,
            "confidence": round(conf, 2),
            "bbox": [round(c, 2) for c in coords]
        })
        
    return final_detections

if __name__ == "__main__":
    print("Loading model...")
    # Load your local weights file
    model = YOLO("best.pt")

    # Run the model on the image
    image_path = "test_tomato_4.jpg" # Make sure this matches your image name
    print(f"Running inference on {image_path}...")
    results = model(image_path)

    # Pop up a window showing the image, bounding boxes, and masks
    results[0].show()

    # Process the raw results using our new pipeline functions
    print("\n=== Processing Detections ===")
    clean_data = process_model_output(results, confidence_threshold=0.65)
    
    # Print the final clean JSON output
    print("\nFinal Output for MQTT:")
    print(json.dumps(clean_data, indent=2))
    print("=============================")