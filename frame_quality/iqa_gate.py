import json
import os
import traceback
import cv2
import numpy as np
import pyiqa
import torch
from PIL import Image

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
                
                "brisque_weight": 0.45,
                "niqe_qeight": 0.35,
                "sharpness_weight": 0.20,
                
                "threshold": 0.55
            }
        with open(path, 'r') as file:
            return json.load(file)


    def _normalize_brisque(self, x):
        # lower is better -> convert to 0..1 (higher is better)
        x = np.clip(x, 0, 100)
        return 1.0 - (x / 100.0)
    
    def _normalize_niqe(self, x):
        x = np.clip(x, 0, 10)
        return 1.0 - (x / 10.0)
    
    def _normalize_sharpness(self, x):
        # typical laplacian variance: higher is better but unbounded
        return np.clip(x / 1000.0, 0, 1)
        
    def evaluate(self, image):
        """
        Evaluates image quality with a 'Fail Fast' approach.
        Returns: (is_good, reason, metrics_dict)
        """
        if image is None or getattr(image, "size", 0) == 0:
            return False, "Invalid image", {}

        if len(image.shape) == 2:
            gray_image = image
            img_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        else: 
            gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        h, w = img_rgb.shape[:2]
        
        mean_lum = cv2.mean(gray_image)[0]
        lap_var = cv2.Laplacian(gray_image, cv2.CV_64F).var()

        # Initialize metrics dictionary (AI scores are None initially)
        metrics = {
            "luminance": round(mean_lum, 2),
            "laplacian": round(lap_var, 2),
            "brisque": None,
            "niqe": None,
            "final_score": None
        }
        
        if mean_lum < self.config.get("min_luminance", 30.0):
            return False, "Underexposed (Too Dark)", metrics
        if mean_lum > self.config.get("max_luminance", 180.0):
            return False, "Overexposed (Too Bright)", metrics
        if h < 20 or w < 20:
            return False, "Image too small", metrics
                
        try:
            with torch.no_grad():
                img_pil = Image.fromarray(img_rgb)
                brisque_score = self.brisque_metric(img_pil).item()
                metrics["brisque"] = round(brisque_score, 2)
                
                MIN_SIZE = 128
                TARGET_SIZE = 256
                
                if h < MIN_SIZE or w < MIN_SIZE:
                    img_niqe = cv2.resize(img_rgb, (TARGET_SIZE, TARGET_SIZE))
                else:
                    img_niqe = img_rgb
                

                niqe_score = self.niqe_metric(Image.fromarray(img_niqe)).item()               
                metrics["niqe"] = round(niqe_score, 2)
            
        except Exception as e:
            print(traceback.format_exc())
            print(f"Error calculating AI metrics: {e}")
            return False, "AI metric failure", metrics
         
        # ----------------------------
        # normalization
        # ----------------------------
        brisque_score = self._normalize_brisque(brisque_score)
        niqe_score = self._normalize_niqe(niqe_score)
        sharpness_score = self._normalize_sharpness(lap_var)

        # ----------------------------
        # weighted score
        # ----------------------------
        final_score = (
            self.config.get("brisque_weight", 0.45) * brisque_score +
            self.config.get("niqe_weight", 0.35) * niqe_score +
            self.config.get("sharpness_weight", 0.20) * sharpness_score
        )
        metrics["final_score"] = round(final_score, 3)
        
        # ----------------------------
        # decision
        # ----------------------------
        threshold = self.config.get("threshold", 0.55)

        if final_score >= threshold:
            return True, "OK", metrics
        elif final_score >= threshold - 0.1:
            return True, "Borderline", metrics
        else:
            return False, "Low quality", metrics
