import cv2
import numpy
import os
import time
from telegram_manager import TelegramManager
from camera_utils import get_camera

# --- Initialize Modules ---
tm = TelegramManager()
qr_detector = cv2.QRCodeDetector()

# Global states
guest_mode = False
access_timer = 0
last_unknown_time = 0
is_unknown_lingering = False

# Callbacks for Telegram (Receives the user_name from Telegram)
def allow_access(user_name):
    global guest_mode, access_timer
    guest_mode = True
    access_timer = time.time() + 60
    tm.send_message(f"✅ Access Granted by {user_name} .")
    print(f"Remote Override: Access Allowed by {user_name}")

def block_access(user_name):
    global guest_mode
    guest_mode = False
    tm.send_message(f"❌ Access Denied by {user_name}.")
    print(f"Remote Override: Access Blocked by {user_name}")

tm.register_callback("allow_entry", allow_access)
tm.register_callback("block_entry", block_access)

# --- Original Training Logic ---
size = 4
haar_file = 'haarcascade_frontalface_default.xml'
datasets = 'known_face'
print('Training...')
(images, labels, names, id) = ([], [], {}, 0)
for (subdirs, dirs, files) in os.walk(datasets):
    for subdir in dirs:
        names[id] = subdir
        subjectpath = os.path.join(datasets, subdir)
        for filename in os.listdir(subjectpath):
            path = subjectpath + '/' + filename 
            label = id
            images.append(cv2.imread(path, 0))
            labels.append(int(label))
        id += 1
(width, height) = (130, 100)

(images, labels) = [numpy.array(lis) for lis in [images, labels]]

# --- Safety Check: Ensure we have data to train ---
if len(images) == 0:
    print("\n[ERROR] No face data found in 'datasets/' folder!")
    print(">>> Please run 'newface.py' to capture face samples first.")
    exit()

model = cv2.face.LBPHFaceRecognizer_create()
model.train(images, labels)

face_cascade = cv2.CascadeClassifier(haar_file)
webcam = get_camera()
if webcam is None:
    exit()
print("System Active.")
tm.send_message("🚀 Face Recognition System Started.")

cnt = 0
while True:
    (_, im) = webcam.read()
    current_time = time.time()
    
    # 1. Guest Mode Timer
    if guest_mode and current_time > access_timer:
        guest_mode = False
        tm.send_message("⚠️ Temporary guest access has expired.")

    # 2. QR Code Scannner (for GUEST: format)
    qr_data, _, _ = qr_detector.detectAndDecode(im)
    if qr_data and qr_data.startswith("GUEST:"):
        guest_name = qr_data.split(":")[1]
        if not guest_mode:
            guest_mode = True
            access_timer = current_time + 60
            tm.send_message(f"🔓 QR ACCESS: Guest '{guest_name}' recognized. Entry granted for 60s.")

    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY) 
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    
    unknown_in_frame = False
    
    for (x, y, w, h) in faces:
        cv2.rectangle(im, (x, y), (x + w, y + h), (255, 255, 0), 2)
        face = gray[y:y + h, x:x + w]
        face_resize = cv2.resize(face, (width, height))

        prediction = model.predict(face_resize)
        cv2.rectangle(im, (x, y), (x + w, y + h), (0, 255, 0), 3)
        
        # LBPH threshold: Lower values mean better matches. Typical range 40-70.
        if prediction[1] < 100:
            cv2.putText(im, '%s - %.0f' % (names[prediction[0]], prediction[1]), (x - 10, y - 10), cv2.FONT_HERSHEY_COMPLEX, 1, (51, 255, 255))
            print(names[prediction[0]])
            cnt = 0
        else:
            unknown_in_frame = True
            cv2.putText(im, 'Unknown', (x - 10, y - 10), cv2.FONT_HERSHEY_PLAIN, 1, (0, 255, 0))
            
            # Legacy loop-based alert (replaced/supplemented by Telegram)
            cnt += 1
            if cnt > 100:
                print("Unknown Person Detected (Legacy Trigger)")
                cnt = 0

    # 3. Threat Intelligence (Lingering & Hit-and-Run)
    unknown_folder = "unknown_face"
    if not os.path.isdir(unknown_folder):
        os.makedirs(unknown_folder)

    if unknown_in_frame:
        if last_unknown_time == 0:
            last_unknown_time = current_time
        elif current_time - last_unknown_time > 3 and not is_unknown_lingering:
            is_unknown_lingering = True
            
            # Save to 'unknown_face' folder with timestamp
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(unknown_folder, f"lingering_{timestamp}.jpg")
            cv2.imwrite(filename, im)
            
            # Send latest captured photo to Telegram
            tm.send_photo_with_buttons(filename, "🚨 LINGERING: Unknown person detected for >3s. Action required?")
            print(f"Telegram Alert: Unknown person lingering! Saved as {filename}")
    else:
        # Check if they left the frame
        if last_unknown_time != 0:
            duration = current_time - last_unknown_time
            if duration < 3 and not is_unknown_lingering:
                # Save to 'unknown_face' folder with timestamp
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = os.path.join(unknown_folder, f"hit_run_{timestamp}.jpg")
                cv2.imwrite(filename, im)
                
                # Send latest captured photo to Telegram
                tm.send_photo_with_buttons(filename, "🏃 HIT-AND-RUN: Unknown person left frame before identification.")
                print(f"Telegram Alert: Hit-and-run! Saved as {filename}")
            
            # Reset
            last_unknown_time = 0
            is_unknown_lingering = False

    # Status Overlay
    status_text = "ACCESS GRANTED" if guest_mode else "SECURED"
    status_color = (0, 255, 0) if guest_mode else (0, 0, 255)
    cv2.putText(im, f"STATUS: {status_text}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)

    cv2.imshow('OpenCV Surveillance', im)
    key = cv2.waitKey(10)
    if key == 27 or key == ord('q'): # ESC or 'q'
        break

webcam.release()
cv2.destroyAllWindows()
tm.send_message("🛑 Surveillance System Shielding Down.")
