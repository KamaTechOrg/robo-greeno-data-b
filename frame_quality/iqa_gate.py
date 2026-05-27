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
                "min_luminance": 50.0,
                "max_luminance": 190.0,
                "min_laplacian_variance": 15.0,
                "max_brisque": 45.0,
                "max_niqe": 8.0
            }
        with open(path, 'r') as file:
            return json.load(file)

    def evaluate(self, image_path):
        """
        Evaluates image quality using all 4 metrics.
        Returns: (is_good, reason, metrics_dict)
        """
        image_array = cv2.imread(image_path)
        if image_array is None:
            return False, "Failed to load image", {}

        gray_image = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)

        mean_lum = cv2.mean(gray_image)[0]
        lap_var = cv2.Laplacian(gray_image, cv2.CV_64F).var()

        try:
            brisque_score = self.brisque_metric(image_path).item()
            niqe_score = self.niqe_metric(image_path).item()
        except Exception as e:
            print(f"Error calculating AI metrics: {e}")
            # Assign intentionally bad scores on failure
            brisque_score, niqe_score = 999.0, 999.0 

        metrics = {
            "luminance": round(mean_lum, 2),
            "laplacian": round(lap_var, 2),
            "brisque": round(brisque_score, 2),
            "niqe": round(niqe_score, 2)
        }

        if mean_lum < self.config.get("min_luminance"):
            return False, "Underexposed (Too Dark)", metrics
        if mean_lum > self.config.get("max_luminance"):
            return False, "Overexposed (Too Bright)", metrics
        if lap_var < self.config.get("min_laplacian_variance"):
            return False, "Blurry", metrics
            
        if brisque_score > self.config.get("max_brisque"):
            return False, "Poor BRISQUE Quality", metrics
        if niqe_score > self.config.get("max_niqe"):
            return False, "Poor NIQE Quality", metrics

        return True, "OK", metrics
