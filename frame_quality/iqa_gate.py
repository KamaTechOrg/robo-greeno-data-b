import json
import os
import cv2
import pyiqa
import torch


class IQAGate:
    def __init__(self, config_path="IQA_thresholds.json"):
        """
        Initializes the comprehensive IQA checker, loads thresholds, 
        and loads AI models (BRISQUE, NIQE) into memory.
        """
        self.config = self._load_config(config_path)
        
        # Setup device for AI models (Use GPU if available)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Loading AI models on: {self.device}")
        
        # Load AI models once
        self.brisque_metric = pyiqa.create_metric('brisque', device=self.device)
        self.niqe_metric = pyiqa.create_metric('niqe', device=self.device)
        
    def _load_config(self, path):
        """Loads configuration from JSON. Uses fallback defaults if missing."""
        if not os.path.exists(path):
            print(f"Warning: Config file {path} not found. Using defaults.")
            return {
                "min_luminance": 30.0,
                "max_luminance": 180.0,
                "min_laplacian_variance": 4.0,
                "max_brisque": 65.0,
                "max_niqe": 8.5
            }
        with open(path, 'r') as file:
            return json.load(file)

    def evaluate(self, image):
        """
        Evaluates image quality with a 'Fail Fast' approach.
        Returns: (is_good, reason, metrics_dict)
        """
        if image is None:
            return False, "Failed to load image", {}

        if len(image.shape) == 2:
            gray_image = image
            img_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        else: 
            gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        mean_lum = cv2.mean(gray_image)[0]
        lap_var = cv2.Laplacian(gray_image, cv2.CV_64F).var()

        # Initialize metrics dictionary (AI scores are None initially)
        metrics = {
            "luminance": round(mean_lum, 2),
            "laplacian": round(lap_var, 2),
            "brisque": None,
            "niqe": None
        }
        
        
        if mean_lum < self.config.get("min_luminance", 30.0):
            return False, "Underexposed (Too Dark)", metrics
        if mean_lum > self.config.get("max_luminance", 180.0):
            return False, "Overexposed (Too Bright)", metrics
        if lap_var < self.config.get("min_laplacian_variance", 4.0):
            return False, "Blurry", metrics
        
        
        try:
            img_tensor = torch.from_numpy(img_rgb).permute(2,0,1).unsqueeze(0).float() / 255.0
            img_tensor = img_tensor.to(self.device)
            
            with torch.no_grad():
                brisque_score = self.brisque_metric(img_tensor).item()
                niqe_score = self.niqe_metric(img_tensor).item()
            
                metrics["brisque"] = round(brisque_score, 2)
                metrics["niqe"] = round(niqe_score, 2)
            
        except Exception as e:
            print(f"Error calculating AI metrics: {e}")
            return False, "AI Metric Calculation Failed", metrics
         
        if brisque_score > self.config.get("max_brisque", 65.0):
            return False, "Poor BRISQUE Quality", metrics
        if niqe_score > self.config.get("max_niqe", 8.5):
            return False, "Poor NIQE Quality", metrics

        return True, "OK", metrics
