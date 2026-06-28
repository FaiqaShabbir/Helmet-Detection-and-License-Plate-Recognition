# Helmet Detection and License Plate Recognition

An end-to-end computer vision system to detect whether a two-wheeler rider is wearing a helmet and — when a helmet is not detected — locate and read the vehicle's license plate so an electronic challan can be issued.

This repository contains code and configuration to run inference (and optionally training) using one-stage object detectors (YOLO-family) for helmet and license-plate detection and an OCR engine for reading license plate characters.

---

## Features

- Detect helmets on riders in images and video streams
- Detect and crop license plates when helmet is not detected
- Read license plate text using OCR (Tesseract or EasyOCR)
- Support for running on live camera feed, video file, or image folder
- Hooks and notes for training or fine-tuning object detection models on custom datasets

---

## Stack & Dependencies

- Language: Python 3.8+
- Typical libraries: PyTorch, OpenCV, NumPy
- Common tools you may need:
  - ultralytics / YOLOv5 or YOLOv8 (for detection)
  - pytesseract or easyocr (for OCR)
  - opencv-python (for image I/O and drawing)

Note: This repository does not bundle pre-trained weights. See the "Model weights" section below.

---

## Repository layout

Top-level files you'll typically care about:

- README.md — this file
- requirements.txt — (optional) Python dependencies for quick install
- models/ — place to keep model weights (create this directory and add .pt/.onnx files)
- scripts/ or src/ — put detection and OCR scripts here (your repo may already have these; adjust names accordingly)
- data/ — optional directory for sample images, videos, or annotation files

If your repository has different paths or filenames, update the commands below accordingly.

---

## Quick start (inference)

1. Create and activate a virtual environment (recommended):

```bash
python -m venv venv
# macOS / Linux
source venv/bin/activate
# Windows (PowerShell)
venv\Scripts\Activate.ps1

pip install -U pip
pip install -r requirements.txt
```

2. Put or download model weights into models/ (example names):

- models/helmet_yolo.pt  — detection model for helmets
- models/lp_yolo.pt      — detection model for license plates

3. Run detection on an image or video.

Replace <DETECTION_SCRIPT> and arguments with your repository's script name. Example generic command:

```bash
python <DETECTION_SCRIPT>.py --source path/to/video_or_image --weights models/helmet_yolo.pt --output results/
```

If your pipeline separates detection and OCR, first run detection to crop the plate, then run OCR on the cropped plate images:

```bash
python <LP_DETECT_SCRIPT>.py --source path/to/video.mp4 --weights models/lp_yolo.pt --save-crops plates/
python <OCR_SCRIPT>.py --input plates/ --engine easyocr  # or pytesseract
```

---

## Model weights

- This repository expects you to provide or download trained weights. You can start with publicly available YOLO weights (e.g., yolov5s.pt) and fine-tune on a helmet/plate dataset.
- Place weights under `models/` and reference them with the `--weights` flag in your scripts.

---

## Training (notes)

If you plan to train/fine-tune detection models:

- Prepare dataset in YOLO format (images + .txt label files) or COCO format and update the training config accordingly.
- Typical training command (ultralytics / yolov5 example):

```bash
# adapt dataset.yaml and hyperparameters as needed
python train.py --img 640 --batch 16 --epochs 50 --data dataset.yaml --weights yolov5s.pt --project runs/train
```

- Monitor mAP, precision, and recall. Iterate on augmentation, label quality, and class balance.

---

## OCR

- Two common choices:
  - pytesseract: lightweight, uses the Tesseract engine (requires Tesseract installed on system).
  - easyocr: Python-only (installable via pip), often better for challenging plates but slower.

- Preprocess cropped plate images for best OCR results: grayscale, contrast stretching, denoising, and perspective correction.

---

## Configuration

Document config variables in a central place (config.yaml or config.py). Typical settings:

- CAMERA_SOURCE (0 for webcam, or path to RTSP/MP4)
- DETECTION_WEIGHTS
- LP_WEIGHTS
- OCR_ENGINE
- OUTPUT_DIR

---

## Example workflow

1. Run helmet detector on incoming frames.
2. If rider without helmet is detected, run license plate detector on the same frame.
3. Crop the license plate region and pass it to OCR.
4. Save evidence (frame snapshot, cropped plate, recognized text) to disk or database.
5. Optionally, create an automated challan generation step (outside scope of this repo).

---

## Contributing

Contributions are welcome. Suggested steps:

1. Fork the repository
2. Create a feature branch
3. Run tests (if provided) and linting
4. Open a pull request describing the change

If you add scripts or change file layout, please update this README with the correct run commands.

---

## License

Specify your project license here (e.g., MIT, Apache-2.0). If you don't want to pick one yet, add a LICENSE file later.

---

## Acknowledgements

- YOLO (Joseph Redmon, Ultralytics) for object detection
- Tesseract / EasyOCR for OCR functionality

---

If you'd like, I can add this README directly to the repository (I see an existing short README). Tell me whether you want me to replace the current README.md or add a new file like README_FULL.md. I can also adapt commands to the exact script names once you tell me which detection scripts exist in the repo.
