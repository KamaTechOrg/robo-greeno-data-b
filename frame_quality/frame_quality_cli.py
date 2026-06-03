import argparse
import os
import cv2
from pathlib import Path
import pandas as pd
import pyiqa
import torch

def parse_arguments():
    """
    Parses command line arguments for the CLI.
    """
    parser = argparse.ArgumentParser(description="Evaluate camera frame quality for hardware flaws.")
    parser.add_argument("--input_dir", type=str, required=True,
                        help="Path to the directory containng test images.")
    parser.add_argument("--output_csv", type=str, default="quality_report.csv",
                        help="Path to save the output CSV file.")
    return parser.parse_args()


def calculate_luminance(gray_image):
    """
    Calculates the mean luminance of an image.
    Low value = underexposed (dark), High value = overexposed (washed out).
    """
    return cv2.mean(gray_image)[0]


def calculate_laplacian_variance(gray_image):
    """
    Calculate the variance of the Laplacian.
    Low value indicates lack of edges, meaning the image is likely blurred.
    """
    return cv2.Laplacian(gray_image, cv2.CV_64F).var()


def main():
    args = parse_arguments()
    
    if not os.path.isdir(args.input_dir):
        print(f"Error: Directory '{args.input_dir}' does not exist.")
        return
    
    print("Initializing quality models (BRISQUE, NIQE)...")
    #Initialize pyiqa metrics. Device defaults to CPU if GPU is unavailable.
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    brisque_metric = pyiqa.create_metric('brisque', device=device)
    niqe_metric = pyiqa.create_metric('niqe', device=device)

    #Supported image extensions
    search_pattern = os.path.join(args.input_dir, "*.[jpJP][npNP][gG0]*")
    image_paths = [p for p in Path(args.input_dir).iterdir() if p.suffix.lower() in ['.jpg', '.jpeg', '.png']]
    image_paths = [str(p) for p in image_paths]

    if not image_paths:
        print(f"No images found in '{args.input_dir}'.")
        return
    
    results = []
    print(f"Found {len(image_paths)} images. Starting processing...")

    for img_path in image_paths:
        filename = os.path.basename(img_path)

        # Read image using OpenCV
        img_bgr = cv2.imread(img_path)
        if img_bgr is None:
            print(f"Warning: could not read {filename}. Skipping.")
            continue

        # Convert to Grayscale for OpenCV metrics
        img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        # Calculate standerd CV metrics
        mean_lum = calculate_luminance(img_gray)
        lap_var = calculate_laplacian_variance(img_gray)

        # Calculate Deep/Statistical metics using pyiqa
        # pyiqa expects image path or tensor, using path for simplicity
        try:
            brisque_score = brisque_metric(img_path).item()
            niqe_score = niqe_metric(img_path).item()
        except Exception as e:
            print(f"Error calculating BRISQUE/NIQE for {filename}: {e}")
            brisque_score, niqe_score = None, None

        results.append({
            "Filename": filename,
            "Mean_Luminance": round(mean_lum, 2),
            "Laplacian_Variance": round(lap_var, 2),
            "BRISQUE_Score": round(brisque_score, 2) if brisque_score else None,
            "NIQE_Score": round(niqe_score, 2) if niqe_score else None
        })

        print(f"Processed: {filename}")

    # Save to CSV using pandas
    df = pd.DataFrame(results)
    df.to_csv(args.output_csv, index=False)
    print(f"\nProcessing complete! Results saved to '{args.output_csv}'.")

if __name__ == "__main__":
    main()