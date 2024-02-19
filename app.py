import shutil
from flask import Flask, render_template, request, redirect, url_for, flash, session 
import mysql.connector.pooling
from mysql.connector import OperationalError
from werkzeug.utils import secure_filename
import os
from detection import detect_image, detect_video
from ocr import perform_ocr
import configparser

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication

from PIL import Image, ImageDraw, ImageFont
import glob
from io import BytesIO

# Load the MySQL database credentials from the config file
config = configparser.ConfigParser()
config.read('config.ini')

app = Flask(__name__)
# Set the secret key from the config file
app.secret_key = config.get('flask', 'secret_key')

app.config['STATIC_FOLDER'] = 'static'
# Set the upload folder and allowed file extensions
app.config['PICTURE_FOLDER'] = 'D:/Yolov5+OCR+MySQL/picture_uploads'
app.config['VIDEO_FOLDER'] = 'D:/Yolov5+OCR+MySQL/video_uploads'
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'mp4', 'mov'}
app.config['ALLOWED_EXTENSIONS'] = ALLOWED_EXTENSIONS


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


db_user = config.get('mysql', 'user')
db_password = config.get('mysql', 'password')
db_host = config.get('mysql', 'host')
db_database = config.get('mysql', 'database')

# Database connection pool setup
cnx_pool = mysql.connector.pooling.MySQLConnectionPool(
    pool_name="mypool",
    pool_size=5,
    user=db_user,
    password=db_password,
    host=db_host,
    database=db_database
)


@app.route('/')
def index():
    return redirect(url_for('traffic_controller'))


@app.route('/traffic_controller')
def traffic_controller():
    return render_template('traffic_controller.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    error_msg = None
    if request.method == 'POST':
        # Get the email and password from the login form
        email = request.form['email']
        password = request.form['password']

        try:
            # Use the connection pool to get a connection
            cnx = cnx_pool.get_connection()

            # Fetch the user information from the database
            cursor = cnx.cursor()
            query = "SELECT id, password FROM users WHERE email = %s"
            cursor.execute(query, (email,))
            result = cursor.fetchone()

            if result is not None and password == result[1]:
                # User exists and password is correct
                session['authenticated'] = True  # Set the authenticated session variable
                return redirect(url_for('upload'))
            else:
                # User does not exist or password is incorrect
                error_msg = 'Incorrect email or password'

            # Close the cursor and the connection
            cursor.close()
            cnx.close()

        except mysql.connector.Error as err:
            # Handle any MySQL errors
            error_msg = f"MySQL Error: {err}"

    return render_template('login.html', error_msg=error_msg)



@app.route('/upload')
def upload():
    if 'authenticated' in session and session['authenticated']:
        # User is authenticated, show the "Login Successfully" message
        session['authenticated'] = False  # Reset the authenticated session variable
        login_success_message = "Login Successful"  # Set the message you want to display
        return render_template('upload.html', login_success_message=login_success_message)
    else:
        return render_template('upload.html')  # Redirect to the login page if not authenticated


def clean_detection_folder():
    # Define the path to the detection folder
    detection_folder = 'runs/detect/'

    # Use glob to find all subfolders in the detection folder matching the pattern exp*
    exp_folders = glob.glob(os.path.join(detection_folder, 'exp*'))

    # Iterate over the exp* folders and delete their contents
    for exp_folder in exp_folders:
        try:
            shutil.rmtree(exp_folder)
        except Exception as e:
            print(f"Error deleting folder {exp_folder}: {e}")

@app.route('/picture_upload', methods=['POST'])
def picture_upload():

    # Clean the detection folder before processing a new picture upload
    clean_detection_folder()

    # Check if the file is present in the request
    if 'picture' not in request.files:
        return 'No file selected'
    picture = request.files['picture']
    # If the file is not allowed, return an error message
    if not allowed_file(picture.filename):
        return 'Invalid file type'
    # Save the file with a secure filename
    filename = secure_filename(picture.filename)

    # create a folder with the same name as the image file to store the image and label file together
    folder_path = os.path.join(
        app.config['PICTURE_FOLDER'], 'detection', os.path.splitext(filename)[0])
    os.makedirs(folder_path, exist_ok=True)

    # Save the image file in the folder created above
    image_path = os.path.join(folder_path, filename)
    picture.save(image_path)

    # Call the detect_image() function to perform the detection and save the results
    detect_image(image_path, folder_path)

    # Call the perform_ocr() function to perform OCR on the license plate and get the resulting text
    label_path = os.path.splitext(image_path)[0] + '.txt'
    try:
        text, cropped_image_path = perform_ocr(image_path, label_path)

        # Get the relative path of the cropped image
        cropped_image_path = cropped_image_path.replace(os.getcwd(), '')

        # Get the license plate number from the OCR text
        license_plate_no = text.strip()

        # Save the detected image in the static folder with the license plate number as its filename
        static_folder_path = os.path.join(app.static_folder, 'detection')
        os.makedirs(static_folder_path, exist_ok=True)
        static_image_path = os.path.join(
            static_folder_path, license_plate_no + '.jpg')
        shutil.copyfile(image_path, static_image_path)

        # Copy the detected image from runs/detect/exp* folder to static/detect_bounding_box folder
        # Use glob to find the detected images in the exp* folders
        exp_folders = glob.glob('runs/detect/exp*/')
        for exp_folder in exp_folders:
            detected_image_path = os.path.join(exp_folder, os.path.basename(image_path))
            if os.path.exists(detected_image_path):
                detect_bounding_box_folder = os.path.join(app.static_folder, 'detect_bounding_box')
                os.makedirs(detect_bounding_box_folder, exist_ok=True)
                detected_image_name = os.path.join(detect_bounding_box_folder, license_plate_no + '.jpg')
                shutil.copyfile(detected_image_path, detected_image_name)
                break  # Copy from the first available exp* folder

        # Render the upload.html template with the cropped image and extracted text
        return render_template('upload.html', 
                               extracted_text=text, 
                               cropped_image_path=cropped_image_path, 
                               detected_image_path=url_for('static', filename='detect_bounding_box/' + license_plate_no + '.jpg'))
    except TypeError:
        pic_error_message = "License plate not recognized"
        return render_template('upload.html', pic_error_message=pic_error_message)
    except AttributeError:
        pic_error_message = "License plate not recognized"
        return render_template('upload.html', pic_error_message=pic_error_message)


@app.route('/video_upload', methods=['POST'])
def video_upload():

     # Clean the detection folder before processing a new picture upload
    clean_detection_folder()

    # Check if the file is present in the request
    if 'video' not in request.files:
        return 'No file selected'

    video = request.files['video']

    # If the file is not allowed, return an error message
    if not allowed_file(video.filename):
        return 'Invalid file type'

    # Save the file with a secure filename
    filename = secure_filename(video.filename)

    # Create a folder with the same name as the video file to store the frames and label files
    folder_path = os.path.join(
        app.config['VIDEO_FOLDER'], 'detection', os.path.splitext(filename)[0])
    os.makedirs(folder_path, exist_ok=True)

    # Save the video file in the folder created above
    video_path = os.path.join(folder_path, filename)
    video.save(video_path)

    # Call the detect_video() function to perform object detection and save the frames
    detect_video(video_path, folder_path, target_frame_rate=2)

    # Get the folder name without the path
    video_name = os.path.basename(folder_path)

    # Get the static folder path
    static_folder_path = app.static_folder

    # Create a folder in the static folder to save the video frames
    video_frames_folder = os.path.join(
        static_folder_path, 'frames', video_name)
    os.makedirs(video_frames_folder, exist_ok=True)

    # Initialize a list to store frame paths with valid number_plate detections
    valid_frames = []

    # Copy the frames from the detection folder to the static folder and filter by valid detections
    frames_folder_path = os.path.join(folder_path, video_name)
    for frame_file in os.listdir(frames_folder_path):
        frame_file_path = os.path.join(frames_folder_path, frame_file)
        label_file_path = os.path.splitext(frame_file_path)[0] + '.txt'

        # Check if the label file exists and contains a "number_plate" class (class index 2)
        if os.path.exists(label_file_path):
            with open(label_file_path, 'r') as label_file:
                lines = label_file.readlines()
                for line in lines:
                    parts = line.strip().split(' ')
                    class_index = int(parts[0])
                    if class_index == 2:  # Check if the class index is 2 (number_plate)
                        valid_frames.append(frame_file)
                        break  # No need to check other lines if we found "number_plate"

        # Copy valid frames to the static folder
        if frame_file in valid_frames:
            shutil.copyfile(frame_file_path, os.path.join(
                video_frames_folder, frame_file))

    # Render the popup.html template with the extracted frames
    frames = sorted(os.listdir(video_frames_folder))
    return render_template('popup.html', video_name=video_name, frames=frames)


@app.route('/perform_ocr_on_video', methods=['POST'])
def perform_ocr_on_video():
    # Get the selected frame and video name from the form
    frame = request.form['frame']
    video_name = request.form['video_name']

    # Get the static folder path
    static_folder_path = app.static_folder

    # Get the path of the selected frame image and label file
    frame_path = os.path.join(
        static_folder_path, 'frames', video_name, frame)  # type: ignore
    label_path = os.path.splitext(frame_path)[0] + '.txt'
    try:
        # Call the perform_ocr() function to perform OCR on the selected frame
        text, cropped_image_path = perform_ocr(
            frame_path, label_path)  # type: ignore

        # Get the relative path of the cropped image
        cropped_image_path = cropped_image_path.replace(os.getcwd(), '')

        # Get the license plate number from the OCR text
        license_plate_no = text.strip()

        # Save the detected image in the static folder with the license plate number as its filename
        static_folder_path = os.path.join(app.static_folder, 'detection')
        os.makedirs(static_folder_path, exist_ok=True)
        static_image_path = os.path.join(
            static_folder_path, license_plate_no + '.jpg')
        shutil.copyfile(frame_path, static_image_path)

        # Copy the detected image from runs/detect/exp* folder to static/detect_bounding_box folder
        # Use glob to find the detected images in the exp* folders
        exp_folders = glob.glob('runs/detect/exp*/')
        for exp_folder in exp_folders:
            detected_image_path = os.path.join(exp_folder, os.path.basename(frame_path))
            if os.path.exists(detected_image_path):
                detect_bounding_box_folder = os.path.join(app.static_folder, 'detect_bounding_box')
                os.makedirs(detect_bounding_box_folder, exist_ok=True)
                detected_image_name = os.path.join(detect_bounding_box_folder, license_plate_no + '.jpg')
                shutil.copyfile(detected_image_path, detected_image_name)
                break  # Copy from the first available exp* folder
        # Render the upload.html template with the cropped image and extracted text
        return render_template('upload.html', extracted_text=text, cropped_image_path=cropped_image_path,
                                detected_image_path=url_for('static', filename='detect_bounding_box/' + license_plate_no + '.jpg'),
                                    show_card=True)
    except TypeError:
        pic_error_message = "License plate not recognized"
        return render_template('upload.html', pic_error_message=pic_error_message)


def send_email(to_email, subject, content, attachment_path=None):
    # Email configuration
    email_host = 'smtp.gmail.com'
    email_port = 587
    email_sender = config.get('email', 'email_address')
    email_password = config.get('email', 'email_password')

    # Create a multipart message
    message = MIMEMultipart()
    message['From'] = email_sender
    message['To'] = to_email
    message['Subject'] = subject

    # Attach the content to the email body
    message.attach(MIMEText(content, 'plain'))

    # Attach the challan image or PDF to the email if available
    if attachment_path:
        with open(attachment_path, 'rb') as attachment:
            if attachment_path.lower().endswith('.pdf'):
                attachment_mime = MIMEApplication(attachment.read())
            else:
                attachment_mime = MIMEImage(attachment.read())
            attachment_mime.add_header(
                'Content-Disposition', 'attachment', filename=os.path.basename(attachment_path))
            message.attach(attachment_mime)

    # Create a secure connection to the email server
    server = smtplib.SMTP(email_host, email_port)
    server.starttls()

    # Log in to the email server
    server.login(email_sender, email_password)

    # Send the email
    server.sendmail(email_sender, to_email, message.as_string())

    # Quit the server
    server.quit()

# logo_path = os.path.join(app.static_folder, 'logo.png')

def generate_challan_image(person_name, father_name, person_cnic, person_contact_number, license_plate_no,
                           email_id, violation_datetime, violation_location, violation_type, fine_amount,
                           payment_deadline, picture_evidence):
    # Create a blank image with a white background
    image = Image.new('RGB', (900, 700), color='white')
    draw = ImageDraw.Draw(image)

    # Load fonts
    font_title = ImageFont.truetype("arial.ttf", 36)
    font_header = ImageFont.truetype("arial.ttf", 24)
    font_attribute = ImageFont.truetype("arial.ttf", 18)

    # 1. Load and paste the logo on the top left corner with a transparent background
    logo_path = os.path.join(app.static_folder, 'logo.png')  # Replace with the actual path to the logo image
    try:
        logo_img = Image.open(logo_path)
        logo_img = logo_img.convert("RGBA")  # Convert to RGBA mode to handle transparency
        logo_img = logo_img.resize((70, 70))  # Resize the logo image
        image.paste(logo_img, (20, 20), mask=logo_img)  # Place the logo at (20, 20) with transparency
    except Exception as e:
        print("Failed to load and paste the logo:", e)

    # 2. Write "HDLPR" in the top right corner
    hdlpr_text = "HDLPR"
    _, _, hdlpr_text_width, hdlpr_text_height = draw.textbbox((20, 20), text=hdlpr_text, font=font_header, align='center')
    draw.text((image.width - hdlpr_text_width - 20, 20), hdlpr_text, fill="black", font=font_header)
    
    # Convert the picture evidence from bytes to Image object
    try:
        img = Image.open(BytesIO(picture_evidence))
        img = img.resize((400, 300))  # Resize the picture evidence
        image.paste(img, ((image.width - img.width) // 2, 130))  # Center the picture evidence
        
    except Exception as e:
        print("Failed to load and paste picture evidence:", e)

    # 4. Organize attributes in a grid format with borders, background, headings, and section titles
    attribute_box_width = 380
    attribute_box_height = 30
    attribute_box_x = (image.width - attribute_box_width) // 8
    attribute_box_y = 480  # Start below the image and "Evidence" label

    def draw_attribute_box(title, value, x, y):
        # Draw an attribute box with a title and value
        draw.rectangle([(x + 10, y), (x + attribute_box_width, y + attribute_box_height)], outline="black", width=2)
        _, _, title_width, title_height = draw.textbbox((0, 0), text=title, font=font_attribute)
        _, _, value_width, value_height = draw.textbbox((0, 0), text=value, font=font_attribute)
        draw.text((x + 10 + (attribute_box_width - title_width - value_width - 10) // 2, y + 5), title, fill="black", font=font_attribute)
        draw.text((x + 10 + (attribute_box_width + title_width - value_width + 10) // 2, y + 5), value, fill="black", font=font_attribute)

    # Draw section titles
    section_heading_y = 440
    draw.text((20, section_heading_y), "Personal Details", fill="black", font=font_header)
    draw.text((image.width // 2 + 20, section_heading_y), "Violation Details", fill="black", font=font_header)

    # Draw personal details
    draw_attribute_box("Name:", person_name, 20, attribute_box_y)
    draw_attribute_box("Father's Name:", father_name, 20, attribute_box_y + attribute_box_height)
    draw_attribute_box("CNIC:", person_cnic, 20, attribute_box_y + 2 * attribute_box_height)
    draw_attribute_box("Contact Number:", person_contact_number, 20, attribute_box_y + 3 * attribute_box_height)

    # Draw violation details
    draw_attribute_box("Violation Date & Time:", violation_datetime, image.width // 2 + 20, attribute_box_y)
    draw_attribute_box("Violation Location:", violation_location, image.width // 2 + 20, attribute_box_y + attribute_box_height)
    draw_attribute_box("Violation Type:", violation_type, image.width // 2 + 20, attribute_box_y + 2 * attribute_box_height)
    draw_attribute_box("Fine Amount:", fine_amount, image.width // 2 + 20, attribute_box_y + 3 * attribute_box_height)
    draw_attribute_box("Payment Deadline:", payment_deadline, image.width // 2 + 20, attribute_box_y + 4 * attribute_box_height)

    # Add borders to the image
    border_width = 10
    draw.rectangle([(border_width, border_width), (image.width - border_width, image.height - border_width)],
                   outline="black", width=border_width)

    # Save the generated image in the static folder
    image_path = os.path.join(app.static_folder, 'challan', f"{license_plate_no}_challan.png")  # Replace with the actual path to save the image
    image.save(image_path)

    return image_path



# os.path.join(app.static_folder, 'challan', f"{license_plate_no}_challan.png")
@app.route('/generate_challan', methods=['POST'])
def generate_challan():
    try:
        # Get the form data
        person_name = request.form['person_name']
        father_name = request.form['father_name']
        person_cnic = request.form['person_cnic']
        person_contact_number = request.form['person_contact_number']
        license_plate_no = request.form['license_plate_no']
        email_id = request.form['email_id']
        violation_datetime = request.form['violation_datetime']
        violation_location = request.form['violation_location']
        violation_type = request.form['violation_type']
        fine_amount = request.form['fine_amount']
        payment_deadline = request.form['payment_deadline']

         # Use the connection pool to get a connection
        cnx = cnx_pool.get_connection()

        # Fetch the person data from the database
        cursor = cnx.cursor()
        query = "SELECT person_name, father_name, person_contact_number, email_id FROM persons WHERE person_cnic = %s AND license_plate_no = %s"
        values = (person_cnic, license_plate_no)
        cursor.execute(query, values)
        result = cursor.fetchone()

        # Close the cursor
        cursor.close()

        # Check if the person exists in the database
        if result is None:
            cnx.close()  # Close the connection before returning
            return "Person not found in the database."

        # Unpack the person data
        person_name, father_name, person_contact_number, email_id = result

        # Insert the data into the traffic_violation table
        cursor = cnx.cursor()
        query = "INSERT INTO traffic_violations (person_name, father_name, person_cnic, person_contact_number, license_plate_no, email_id, violation_datetime, violation_location, violation_type, fine_amount, payment_deadline, picture_path) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        # Save the detected image in the traffic_violation table
        with open(os.path.join(app.static_folder, 'detection', license_plate_no + '.jpg'), 'rb') as f:
            picture_path = f.read()
        values = (person_name, father_name, person_cnic, person_contact_number, license_plate_no, email_id,
                  violation_datetime, violation_location, violation_type, fine_amount, payment_deadline, picture_path)
        cursor.execute(query, values)
        cnx.commit()

        # Close the database connection
        cursor.close()
        cnx.close()

        # Send the challan to the mentioned email
        email_subject = f'You have been challaned for {violation_type}'
        email_content = f'Dear {person_name},\n\nYou have been issued a challan for {violation_type} on {violation_datetime}. The fine amount is {fine_amount}. Please make the payment before {payment_deadline} to avoid any penalties.\n\nSincerely,\nHelmet Detection and License Plate Recognition Team'
        # Generate the challan image and pass the picture evidence
        picture_evidence = picture_path  # Assuming picture_path is binary data of the picture evidence
        attachment_path = generate_challan_image(person_name, father_name, person_cnic, person_contact_number,
                                                license_plate_no, email_id, violation_datetime, violation_location,
                                                violation_type, fine_amount, payment_deadline, picture_evidence)

        send_email(email_id, email_subject, email_content, attachment_path)

        # Render the challan.html template with the form data and the path of the detected picture
        flash('Email sent successfully!', 'success')  # This will display the success message on the template
        return render_template('challan.html', person_name=person_name, father_name=father_name, person_cnic=person_cnic, person_contact_number=person_contact_number, license_plate_no=license_plate_no, email_id=email_id, violation_datetime=violation_datetime, violation_location=violation_location, violation_type=violation_type, fine_amount=fine_amount, payment_deadline=payment_deadline)
    except OperationalError as e:
        error_message = "Error: Failed to connect to the database."
        # Pass the error message to the challan.html template
        return render_template('challan.html', error_message=error_message)


@app.route('/challan_form/<license_plate_no>')
def challan_form(license_plate_no):

    # Use the connection pool to get a connection
    cnx = cnx_pool.get_connection()
    # Fetch the user information from the database
    cursor = cnx.cursor()
    query = "SELECT person_name, father_name, person_cnic, person_contact_number, email_id FROM persons WHERE license_plate_no = %s"
    cursor.execute(query, (license_plate_no,))
    result = cursor.fetchone()

    # Check if the license plate number exists in the database
    if result is None:
        return render_template('upload.html', error_message="Bike with this license number is not registered.")

    # Get the path of the detected image
    image_path = os.path.join(
        app.static_folder, 'detection', license_plate_no, license_plate_no + '.jpg')

    # Render the generate_challan.html template with the form data and the path of the detected picture
    return render_template('challan.html', person_name=result[0], father_name=result[1], person_cnic=result[2], person_contact_number=result[3], license_plate_no=license_plate_no, email_id=result[4], image_path=image_path)


if __name__ == '__main__':
    app.run(debug=True)
