import cv2
import os
import time
from camera_utils import get_camera

# --- Configuration ---
haar_file = 'haarcascade_frontalface_default.xml'
datasets = 'known_face'
(width, height) = (130, 100)

# 1. Ask for the Person's Name in the Terminal
sub_data = input("Enter the name? (Eg:vinoth): ").strip()
if not sub_data:
    print("Error: Name cannot be empty. Task cancelled.")
    exit()

# 2. Setup the directory structure
path = os.path.join(datasets, sub_data)
if not os.path.isdir(path):
    os.makedirs(path)

# 3. Ready the camera
face_cascade = cv2.CascadeClassifier(haar_file)
webcam = get_camera()
if webcam is None:
    exit()

print(f"\nEnrollment starting for '{sub_data}'...")
print("Please look at the camera. We will capture 100 photos.")
time.sleep(2) # Give the user time to get ready

count = 1
while count <= 100:
    (_, im) = webcam.read()
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    
    # Detect faces
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    
    for (x, y, w, h) in faces:
        # Draw a rectangle around the face
        cv2.rectangle(im, (x, y), (x + w, y + h), (255, 0, 0), 2)
        
        # Crop and resize the face
        face = gray[y:y + h, x:x + w]
        face_resize = cv2.resize(face, (width, height))
        
        # Save the captured photo inside the person's folder
        file_path = os.path.join(path, f"{count}.png")
        cv2.imwrite(file_path, face_resize)
        
        # Overlay count in terminal and on screen
        print(f"Captured: {count}/100")
        cv2.putText(im, f"Progress: {count}%", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        count += 1
        
    cv2.imshow('Enrollment - Press ESC to cancel', im)
    key = cv2.waitKey(10)
    if key == 27 or key == ord('q'): # ESC or 'q' key
        print("\nEnrollment interrupted by user.")
        break

print(f"\nSuccess! 100 photos captured and saved in: {path}")

webcam.release()
cv2.destroyAllWindows()
