from ultralytics import YOLO

print("Loading model...")
# 1. Load your local weights file
model = YOLO("best.pt")

# 2. Run the model on the image
image_path = "test_tomato_4.jpg" # Make sure this matches your image name
print(f"Running inference on {image_path}...")
results = model(image_path)

# 3. Pop up a window with the image, bounding boxes, and masks (since it's a segmentation model)
results[0].show()

# 4. Extract text results to prove to Scot that the ontology works
print("\n=== Detection Results ===")
boxes = results[0].boxes
class_names_dict = model.names # The dictionary that stores which classes the model knows

print(f"Total tomatoes detected: {len(boxes)}\n")

# Iterate over each tomato the model found and print its status
for i, box in enumerate(boxes):
    class_id = int(box.cls[0])           # The class ID
    class_name = class_names_dict[class_id] # The name (e.g., ripe / green)
    confidence = float(box.conf[0])      # The model's confidence level
    
    print(f"Tomato {i+1}: {class_name} (Confidence: {confidence:.2f})")
    
print("=========================")