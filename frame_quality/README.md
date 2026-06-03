# Camera Frame Quality Evaluator (CLI)

This tool provides an automated way to assess the quality of camera frames to detect hardware flaws and environmental issues. It calculates four key metrics: **Mean Luminance**, **Laplacian Variance**, **BRISQUE**, and **NIQE**.

The primary goal of this script is to identify hardware-related failures such as a dirty lens, out-of-focus optics, or sensor malfunctions.

## Features
- **Mean Luminance:** Detects exposure issues (too dark or too bright).
- **Laplacian Variance:** Measures image sharpness to detect blur or focus loss.
- **BRISQUE & NIQE:** Non-reference quality scores that detect "unnatural" artifacts, digital noise, and sensor flaws.
- **CLI Interface:** Process an entire directory of images and export results to CSV.

---

## Prerequisites

Ensure you have Python 3.8+ installed. Install the required dependencies using pip:

```bash
pip install opencv-python pandas pyiqa torch torchvision
```

---

## Usage

Run the script from the command line by specifying the input directory containing your images:
```bash
python frame_quality_cli.py --input_dir path/to/your/images --output_csv quality_report.csv
```

### Arguments:
* ```input_dir```: (Required) Path to the folder containing image files (JPG, PNG, etc.)
* ```output_csv```: (Optional) The name of the resulting CSV file. Defaults to ```quality_report.csv```.

---

## Quality Thresholds & Calibration

**⚠️ CRITICAL: HARDWARE CALIBRATION REQUIRED ⚠️**
The thresholds listed below are **mock values**. They were tested and calibrated using a standard local webcam in a development environment. 
**They have NOT yet been tuned for the actual edge device or production environment.**

Using these default values in production may result in falsely rejecting good frames or accepting bad ones. You MUST recalculate and update these values (in `IQA_thresholds.json`) once you gather real data from the target hardware.

**Current Mock Thresholds (Pending Edge Calibration)**

| **Metric** | **Threshold** | **Indication of Flaw** |
| :---: | :---: | :---:|
| **Mean Luminance** | < 40 or > 220 | Underexposed (dark) or Overexposed (bright/blinded) |
| **Laplacian Variance** | < 100 | Image is blurred, lens is dirty, or out of focus |
| **BRISQUE Score** | > 65 | High level of digital noise or compression artifacts |
| **NIQE Score** | > 8.0 | Unnatural image distribution, likely hardware sensor error |

---

**How to Calibrate for the Edge Device:**
1. **Collect Real Samples:** Capture 20-30 raw images from the *actual production camera* (the specific edge device) in its final deployment environment.
2. **Include Faults:** Deliberately create "bad" frames using that specific camera (e.g., block the lens, alter the focus, lower the lighting).
3. **Run Analysis:** Execute this CLI script on those specific edge-device images and review the `quality_report.csv`.
4. **Update System Config:** Determine the new specific ranges that accurately distinguish "Good" vs "Bad" frames for your hardware, and update `IQA_thresholds.json` accordingly.

---

## Output Description
The script generates a CSV file with the following columns:
* **Filename:** The name of the processed image.
* **Mean_Luminance:** Average brightness level (0-255).
* **Laplacian_Variance:** Sharpness score (Higher is sharper).
* **BRISQUE_Score:** Quality score (Lower is better, typically 0-100).
* **NIQE_Score:** Naturalness score (Lower is better).

---

## License 
Internal Use Only.