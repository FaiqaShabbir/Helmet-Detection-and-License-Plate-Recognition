import re
import cv2
import easyocr
import os

reader = easyocr.Reader(['en'], gpu=True, model_storage_directory='./model', download_enabled=True)

HELMET_CLASS_ID = 0
NO_HELMET_CLASS_ID = 1
LICENSE_PLATE_CLASS_ID = 2
RIDER_CLASS_ID = 3

def perform_ocr(img_path, label_path):
    img = cv2.imread(img_path)

    with open(label_path, 'r') as f:
        label = f.read().splitlines()

    detected_classes = set()
    plate_img_path = None
    extracted_text = ""
    upper_line = ""
    lower_line = ""

    for line in label:
        class_id, x, y, w, h = map(float, line.split()[0:])

        if class_id == LICENSE_PLATE_CLASS_ID:
            detected_classes.add('number_plate')
            x1 = int((x - w/2) * img.shape[1])
            y1 = int((y - h/2) * img.shape[0])
            x2 = int((x + w/2) * img.shape[1])
            y2 = int((y + h/2) * img.shape[0])
            plate_img = img[y1:y2, x1:x2]
            alpha = 1.5
            beta = 0
            plate_img = cv2.convertScaleAbs(plate_img, alpha=alpha, beta=beta)
            static_folder = os.path.join(os.getcwd(), 'static')
            plate_img_path = os.path.join(static_folder, 'cropped_plate.jpg')
            cv2.imwrite(plate_img_path, plate_img)

        elif class_id == HELMET_CLASS_ID:
            detected_classes.add('helmet')
        elif class_id == NO_HELMET_CLASS_ID:
            detected_classes.add('no_helmet')
        elif class_id == RIDER_CLASS_ID:
            detected_classes.add('rider')

    result = reader.readtext(plate_img) if plate_img_path else []
    
    # Initialize a variable to store the combined line
    combined_line = ""

    # Extract the detected text
    for res in result:
        text = res[1].replace(" ", "").upper()
        
        # Check if the text matches the pattern for 3 uppercase letters followed by 2 or 4 digits
        if re.match(r'^[A-Z]{3}(\d{2}|\d{4})$', text):
            combined_line = text
            break  # Stop processing after finding a valid combined line

    # Check if a combined line was found
    if combined_line:
        extracted_text = combined_line
    else:
        # If no combined line was found, check separately for upper and lower lines
        for res in result:
            text = res[1].replace(" ", "").upper()
            if re.match(r'^[A-Z]{3}$', text) and not upper_line:
                upper_line = text
            elif re.match(r'^\d{4}$', text) and not lower_line:
                lower_line = text

        # Check if both upper and lower lines are detected
        if upper_line and lower_line:
            extracted_text = upper_line
            if re.match(r'^\d{2,4}$', lower_line):
                extracted_text += lower_line
            
    if plate_img_path is not None:
        plate_img_path = plate_img_path.replace(os.getcwd(), '')
    else:
        # Handle the case where plate_img_path is None
        plate_img_path = "Plate image not available."

    if 'number_plate' in detected_classes and 'no_helmet' in detected_classes and 'rider' in detected_classes:
        return extracted_text, plate_img_path.replace(os.getcwd(), '')
    elif 'number_plate' in detected_classes and 'helmet' in detected_classes and 'rider' in detected_classes:
        return 'Rider is with helmet.', plate_img_path.replace(os.getcwd(), '')
    elif 'number_plate' in detected_classes and 'rider' in detected_classes:
        return "Helmet recognition unavailable.", plate_img_path.replace(os.getcwd(), '')
    elif 'number_plate' in detected_classes:
        return 'Bike is rider less.', plate_img_path.replace(os.getcwd(), '')

    return "No relevant information detected.", plate_img_path
