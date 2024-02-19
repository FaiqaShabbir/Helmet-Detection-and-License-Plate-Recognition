import time
import torch
import cv2 as cv
import os
from PIL import Image
from ocr import perform_ocr
import numpy as np



model = torch.hub.load('D:/Yolov5+OCR+MySQL/yolov5', 'custom',
                       path="D:/Yolov5+OCR+MySQL/best.pt", source='local', verbose=False)


def detect_image(image_path, save_folder, detection_folder=None):
    model.conf = 0.4

    # Load the image
    img = Image.open(image_path)

    # Make the detection
    results = model(img)

    # Save the detected image with bounding boxes and labels
    save_detection_results(results, img, image_path,
                           save_folder, detection_folder)

    # Perform OCR on the detected image
    image_name = os.path.splitext(os.path.basename(image_path))[0]
    image_save_path = os.path.join(save_folder, f'{image_name}.jpg')
    label_save_path = os.path.join(save_folder, f'{image_name}.txt')
    detected_text = perform_ocr(image_save_path, label_save_path)
    print("OCR Result:", detected_text)
    return image_path

def detect_video(video_path, save_folder, detection_folder=None, target_frame_rate=2):
    # Create folder for video frames and labels
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    video_folder = os.path.join(save_folder, video_name)
    os.makedirs(video_folder, exist_ok=True)

    # Open video capture
    cap = cv.VideoCapture(video_path)

    # Get video frame dimensions
    width = int(cap.get(cv.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))

    # Create video writer to save the detection video
    output_video_path = os.path.join(save_folder, f'{video_name}_detections.mp4')
    fourcc = cv.VideoWriter_fourcc(*'mp4v')
    output_video = cv.VideoWriter(output_video_path, fourcc, 25.0, (width, height))

    frame_count = 0
    frame_interval = int(25.0 / target_frame_rate)  # Calculate the frame interval

    while cap.isOpened():
        ret, frame = cap.read()

        if not ret:
            break

        # Save the frame if it's within the desired frame interval
        if frame_count % frame_interval == 0:
            frame_path = os.path.join(video_folder, f"frame{frame_count}.jpg")
            cv.imwrite(frame_path, frame)

            # Perform object detection on the frame
            frame_image = Image.open(frame_path)
            results = model(frame_image)

            # Save the frame with bounding boxes
            detection_save_path = os.path.join(video_folder, f"frame{frame_count}_detection.jpg")
            save_detection_results(results, frame_image, frame_path, video_folder, detection_folder, detection_save_path)

            # Draw bounding boxes on the frame
            frame = draw_bounding_boxes(frame, results.xyxy[0], class_names=model.names)

            # Convert frame from BGR to RGB
            frame_rgb = cv.cvtColor(frame, cv.COLOR_BGR2RGB)

            # Write the converted frame to the output video
            output_video.write(frame_rgb)

        frame_count += 1

    print("Detection video saved:", output_video_path)


def draw_bounding_boxes(frame, detections, class_names):
    colors = [
        (255, 59, 61),    # Red
        (255, 156, 149),  # Light Red
        (250, 116, 29),   # Orange
        (255, 173, 34)    # Yellow
    ]  # Define individual colors for each class

    for x1, y1, x2, y2, cls_conf, cls_pred in detections:
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        label = f'{class_names[int(cls_pred)]} {cls_conf:.2f}'
        color = colors[int(cls_pred)]
        thickness = 8
        font = cv.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5

        # Draw bounding box rectangle
        cv.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

        # Draw label background
        text_size = cv.getTextSize(label, font, font_scale, thickness)[0]
        cv.rectangle(frame, (x1, y1 - text_size[1] - 5), (x1 + text_size[0], y1 - 5), color, -1)

        # Draw label text
        cv.putText(frame, label, (x1, y1 - 5), font, font_scale, (0, 0, 0), thickness, cv.LINE_AA)

    return frame


def save_detection_results(results, img, image_path, save_folder, detection_folder=None, detection_save_path=None):
    if detection_save_path is not None:
        results.save(detection_save_path)
    # Create the folder to save the detected images and labels if it doesn't exist
    if not os.path.exists(save_folder):
        os.makedirs(save_folder)

    # Save the detected image with bounding boxes
    image_name = os.path.splitext(os.path.basename(image_path))[0]
    image_save_path = os.path.join(save_folder, f'{image_name}.jpg')
    results.save(image_save_path)

    # Save the detected labels
    label_save_path = os.path.join(save_folder, f'{image_name}.txt')
    with open(label_save_path, 'w') as f:
        for result in results.xyxy[0]:
            label = int(result[-1])
            x_center = (result[0] + result[2]) / 2 / img.width
            y_center = (result[1] + result[3]) / 2 / img.height
            width = (result[2] - result[0]) / img.width
            height = (result[3] - result[1]) / img.height
            f.write(f'{label} {x_center} {y_center} {width} {height}\n')

    # Save the detected image with bounding boxes to the specified detection folder if it exists
    if detection_folder is not None:
        if not os.path.exists(detection_folder):
            os.makedirs(detection_folder)
        detection_save_path = os.path.join(detection_folder, f'{image_name}.jpg')
        results.save(detection_save_path)