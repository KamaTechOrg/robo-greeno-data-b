import os
import cv2  # OpenCV library for image processing

class MockCamera:
    def __init__(self, image_folder):
        """
        Initializes the mock camera with a local directory path.
        """
        self.image_folder = image_folder
        
        # Fetch and sort all valid image files from the local directory
        self.image_files = sorted([
            f for f in os.listdir(image_folder) 
            if f.lower().endswith(('.jpg', '.jpeg', '.png'))
        ])
        self.current_index = 0
        
        print(f"[MockCamera] Initialized. Found {len(self.image_files)} images in '{image_folder}'")

    def get_frame(self):
        """
        Pulls the next image from the folder, simulating a hardware camera feed.
        Returns:
            numpy.ndarray: The image frame, or None if the stream is finished.
        """
        if self.current_index >= len(self.image_files):
            print("[MockCamera] End of image stream.")
            return None  
        
        img_path = os.path.join(self.image_folder, self.image_files[self.current_index])
        
        # Read the image as a standard BGR pixel array (just like a real camera sensor)
        frame = cv2.imread(img_path)
        
        if frame is None:
            print(f"[MockCamera] Warning: Could not read image {img_path}")
        
        self.current_index += 1
        return frame