import sys
import os
import cv2
import numpy as np
import time
import threading
import logging
from flask import (
    Flask,
    render_template,
    Response,
    jsonify,
    send_from_directory,
    request,
)
from flask_cors import CORS

# Load .env file (optional - don't fail if not found)
try:
    from dotenv import load_dotenv

    try:
        env_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
        )
        load_dotenv(env_path)
    except Exception:
        pass
except Exception:
    pass

# Disable Flask logging
log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

# Add parent directory to path to import local modules
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

try:
    from telegram_manager import TelegramManager
    from camera_utils import get_camera

    print("Modules imported successfully")
except Exception as e:
    print(f"Error importing modules: {e}")
    TelegramManager = None
    get_camera = None

app = Flask(
    __name__,
    static_folder=os.path.join(os.path.dirname(__file__), "static"),
    static_url_path="/static",
)
CORS(app)


class SurveillanceSystem:
    def __init__(self):
        # Create a dummy Telegram manager if import failed
        if TelegramManager is None:

            class DummyTM:
                def send_message(self, *args, **kwargs):
                    pass

                def send_photo_with_buttons(self, *args, **kwargs):
                    pass

                def register_callback(self, *args, **kwargs):
                    pass

            self.tm = DummyTM()
        else:
            self.tm = TelegramManager()

        self.qr_detector = cv2.QRCodeDetector()

        self.webcam = None
        self.camera_source = None
        self.guest_mode = False
        self.access_timer = 0
        self.last_unknown_time = 0
        self.is_unknown_lingering = False

        # Training data
        self.haar_file = os.path.join(ROOT_DIR, "haarcascade_frontalface_default.xml")
        self.datasets = os.path.join(ROOT_DIR, "known_face")
        self.unknown_folder = os.path.join(ROOT_DIR, "unknown_face")
        self.names = {}
        self.width, self.height = 130, 100
        self.model = cv2.face.LBPHFaceRecognizer_create()
        self.face_cascade = cv2.CascadeClassifier(self.haar_file)

        # Skip training if Haar cascade fails to load
        if self.face_cascade.empty():
            print("Warning: Haar cascade failed to load. Face detection disabled.")

        # Create directories if they don't exist
        if not os.path.exists(self.datasets):
            os.makedirs(self.datasets)
        if not os.path.exists(self.unknown_folder):
            os.makedirs(self.unknown_folder)

        # Train lazily (don't fail if no faces yet)
        self.train_model()

        # Flag to track if real training data exists
        # We simply check if we loaded images and trained successfully
        # The model.train() call sets internal state we can check
        self.model_is_trained = len(self.names) > 0
        self.has_real_training = self.model_is_trained and len(self.names) > 0

        # If no faces were trained, ensure names is empty
        if not self.has_real_training:
            print("No trained faces")
            self.names = {}

        # Auto-start camera if CAMERA_URL env is set (for deployment)
        camera_url = os.environ.get("CAMERA_URL")
        if camera_url:
            print(f"Auto-starting camera from CAMERA_URL: {camera_url}")
            self.start_camera("mobile", camera_url)

        # Callbacks
        self.tm.register_callback("allow_entry", self.allow_access)
        self.tm.register_callback("block_entry", self.block_access)

    def start_camera(self, source_type, url=None):
        if self.webcam is not None:
            self.webcam.release()
            self.webcam = None

        # Detect headless/cloud environments (no physical camera available)
        is_cloud = os.environ.get("RENDER") or os.environ.get("DYNO") or os.environ.get("CLOUD_ENV")

        if source_type == "internal":
            if is_cloud:
                print("Internal camera not available in cloud environment.")
                return False, "Internal camera is not available on cloud deployments. Please use a Mobile/IP Camera URL instead."
            # Try to open local camera
            try:
                cap = cv2.VideoCapture(0)
                if cap.isOpened():
                    self.webcam = cap
                    self.camera_source = 0
                    return True, "Internal camera started."
                cap.release()
                return False, "No internal camera detected on this device."
            except Exception as e:
                print(f"Error starting internal camera: {e}")
                return False, f"Failed to start internal camera: {e}"

        elif source_type == "mobile" and url:
            try:
                from camera_utils import ThreadedCamera
                self.webcam = ThreadedCamera(url)
                if self.webcam.isOpened():
                    self.camera_source = url
                    return True, "Mobile/IP camera stream started."
                return False, f"Could not connect to camera stream at: {url}"
            except Exception as e:
                print(f"Error starting mobile camera: {e}")
                return False, f"Failed to connect to mobile camera: {e}"

        return False, "Invalid camera source type."

    def train_model(self):
        print(f"Training with datasets at: {self.datasets}")
        images, labels, self.names, id = [], [], {}, 0
        if not os.path.exists(self.datasets):
            os.makedirs(self.datasets)
            print(f"Created datasets directory: {self.datasets}")
        else:
            # Check if directory is empty
            subdirs = [
                d
                for d in os.listdir(self.datasets)
                if os.path.isdir(os.path.join(self.datasets, d))
            ]
            if not subdirs:
                print("Warning: No subdirectories found in datasets folder.")

        for subdirs_path, dirs, files in os.walk(self.datasets):
            for subdir in dirs:
                self.names[id] = subdir
                subjectpath = os.path.join(self.datasets, subdir)
                files_in_dir = os.listdir(subjectpath)
                if not files_in_dir:
                    print(f"Warning: No files in {subjectpath}")
                for filename in files_in_dir:
                    path = os.path.join(subjectpath, filename)
                    try:
                        img = cv2.imread(path, 0)
                        if img is not None and img.size > 0:
                            # Ensure image is in correct format
                            if len(img.shape) == 2:
                                images.append(img)
                                labels.append(int(id))
                            else:
                                print(f"Warning: Image {path} has wrong format")
                        else:
                            print(f"Warning: Could not read image: {path}")
                    except Exception as e:
                        print(f"Error reading image {path}: {e}")
                id += 1

        if len(images) > 0:
            try:
                # Convert to numpy arrays with proper types
                images_array = np.array(images)
                labels_array = np.array(labels)
                self.model.train(images_array, labels_array)
                print(f"Model trained successfully with {len(images)} images.")
            except Exception as e:
                print(f"Error training model: {e}")
                self.names = {}
        else:
            print("Warning: No face data found for training.")

    def allow_access(self, user_name):
        self.guest_mode = True
        self.access_timer = time.time() + 60
        self.tm.send_message(f"✅ Access Granted by {user_name}.")

    def block_access(self, user_name):
        self.guest_mode = False
        self.tm.send_message(f"❌ Access Denied by {user_name}.")

    def get_frame(self):
        if self.webcam is None:
            return None

        try:
            success, im = self.webcam.read()
        except Exception as e:
            print(f"Error reading frame: {e}")
            return None

        if not success or im is None or im.size == 0:
            return None

        # Validate frame is valid
        if im.shape[0] == 0 or im.shape[1] == 0:
            return None

        current_time = time.time()

        # Guest Mode Timer
        if self.guest_mode and current_time > self.access_timer:
            self.guest_mode = False
            self.tm.send_message("⚠️ Temporary guest access has expired.")

        # QR Code Scannner
        qr_data, _, _ = self.qr_detector.detectAndDecode(im)
        if qr_data and qr_data.startswith("GUEST:"):
            guest_name = qr_data.split(":")[1]
            if not self.guest_mode:
                self.guest_mode = True
                self.access_timer = current_time + 60
                self.tm.send_message(
                    f"🔓 QR ACCESS: Guest '{guest_name}' recognized. Entry granted for 60s."
                )

        gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)

        if self.face_cascade.empty():
            cv2.putText(
                im,
                "Face detector not loaded",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2,
            )
            ret, buffer = cv2.imencode(".jpg", im)
            if ret:
                return buffer.tobytes()
            return None

        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)

        unknown_in_frame = False
        model_trained = self.has_real_training

        for x, y, w, h in faces:
            cv2.rectangle(im, (x, y), (x + w, y + h), (255, 255, 0), 2)
            face = gray[y : y + h, x : x + w]

            if face.size == 0:
                continue

            face_resize = cv2.resize(face, (self.width, self.height))

            # Validate resized face
            if face_resize is None or face_resize.size == 0:
                continue

            # Skip prediction entirely if no real training data
            if not model_trained:
                cv2.putText(
                    im,
                    "No Training Data",
                    (x - 10, y - 10),
                    cv2.FONT_HERSHEY_PLAIN,
                    1,
                    (0, 0, 255),
                )
                continue

            # Ensure face_resize is valid grayscale image
            if len(face_resize.shape) != 2:
                continue

            try:
                # Triple-check model is trained before predicting
                if (
                    not hasattr(self.model, "labels")
                    or self.model.labels is None
                    or len(getattr(self.model.labels, "labels", [])) == 0
                ):
                    cv2.putText(
                        im,
                        "Model Not Trained",
                        (x - 10, y - 10),
                        cv2.FONT_HERSHEY_PLAIN,
                        1,
                        (0, 0, 255),
                    )
                    continue

                prediction = self.model.predict(face_resize)
                if len(prediction) >= 2 and prediction[1] < 100:
                    name = self.names.get(prediction[0], "Unknown")
                    cv2.putText(
                        im,
                        f"{name} - {int(prediction[1])}",
                        (x - 10, y - 10),
                        cv2.FONT_HERSHEY_COMPLEX,
                        1,
                        (51, 255, 255),
                    )
                else:
                    unknown_in_frame = True
                    cv2.putText(
                        im,
                        "Unknown",
                        (x - 10, y - 10),
                        cv2.FONT_HERSHEY_PLAIN,
                        1,
                        (0, 255, 0),
                    )
            except Exception as e:
                print(f"Prediction error: {e}")
                unknown_in_frame = True
                cv2.putText(
                    im,
                    "Prediction Error",
                    (x - 10, y - 10),
                    cv2.FONT_HERSHEY_PLAIN,
                    1,
                    (0, 0, 255),
                )

        # Threat Intelligence
        if not os.path.isdir(self.unknown_folder):
            os.makedirs(self.unknown_folder)

        if unknown_in_frame:
            if self.last_unknown_time == 0:
                self.last_unknown_time = current_time
            elif (
                current_time - self.last_unknown_time > 3
                and not self.is_unknown_lingering
            ):
                self.is_unknown_lingering = True
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = os.path.join(
                    self.unknown_folder, f"lingering_{timestamp}.jpg"
                )
                cv2.imwrite(filename, im)
                self.tm.send_photo_with_buttons(
                    filename, "🚨 LINGERING: Unknown person detected for >3s."
                )
        else:
            if self.last_unknown_time != 0:
                duration = current_time - self.last_unknown_time
                if duration < 3 and not self.is_unknown_lingering:
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    filename = os.path.join(
                        self.unknown_folder, f"hit_run_{timestamp}.jpg"
                    )
                    cv2.imwrite(filename, im)
                    self.tm.send_photo_with_buttons(
                        filename, "🏃 HIT-AND-RUN: Unknown person left frame."
                    )
                self.last_unknown_time = 0
                self.is_unknown_lingering = False

        # Status Overlay
        status_text = "ACCESS GRANTED" if self.guest_mode else "SECURED"
        status_color = (0, 255, 0) if self.guest_mode else (0, 0, 255)
        cv2.putText(
            im,
            f"STATUS: {status_text}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            status_color,
            2,
        )

        # Encode frame
        try:
            ret, buffer = cv2.imencode(".jpg", im)
            if ret:
                return buffer.tobytes()
        except Exception as e:
            print(f"Error encoding frame: {e}")
        return None


# Create system object with error handling
try:
    system = SurveillanceSystem()
    print("SurveillanceSystem initialized successfully")
except Exception as e:
    print(f"Error initializing SurveillanceSystem: {e}")

    # Create a minimal fallback system
    class FallbackSystem:
        webcam = None
        guest_mode = False

        def get_frame(self):
            return None

    system = FallbackSystem()


@app.route("/")
def index():
    return render_template("index.html")


def gen_frames():
    # Create a placeholder frame for when camera isn't available
    placeholder_frame = None

    while True:
        frame = system.get_frame()
        if frame is not None:
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
        elif placeholder_frame is not None:
            yield (
                b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                + placeholder_frame
                + b"\r\n"
            )
        else:
            # Return static placeholder
            placeholder_frame = _create_placeholder_frame()
            if placeholder_frame:
                yield (
                    b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                    + placeholder_frame
                    + b"\r\n"
                )
        time.sleep(0.1)


def _create_placeholder_frame():
    """Create a placeholder image when camera is not available."""
    import numpy as np
    import cv2

    # Create a dark background image
    img = np.zeros((480, 640, 3), dtype=np.uint8)

    # Add "No Camera" text
    cv2.putText(
        img,
        "No Camera Available",
        (130, 220),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (255, 255, 255),
        2,
    )
    cv2.putText(
        img,
        "Click 'Change Camera' to select a source",
        (140, 270),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (200, 200, 200),
        1,
    )

    ret, buffer = cv2.imencode(".jpg", img)
    if ret:
        return buffer.tobytes()
    return None


@app.route("/video_feed")
def video_feed():
    return Response(gen_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/status")
def get_status():
    return jsonify(
        {
            "guest_mode": system.guest_mode,
            "camera_active": system.webcam is not None and system.webcam.isOpened(),
            "camera_source": str(system.camera_source),
            "system_active": True,
            "access_timer": max(0, int(system.access_timer - time.time()))
            if system.guest_mode
            else 0,
        }
    )


@app.route("/api/start_camera", methods=["POST"])
def api_start_camera():
    data = request.get_json()
    source_type = data.get("type")
    url = data.get("url")
    result = system.start_camera(source_type, url)
    # start_camera returns (success: bool, message: str)
    if isinstance(result, tuple):
        success, message = result
    else:
        success, message = result, "OK" if result else "Failed to start camera."
    return jsonify({"success": success, "message": message})


@app.route("/api/train", methods=["POST"])
def api_train():
    system.train_model()
    return jsonify({"success": True})


@app.route("/api/toggle_guest", methods=["POST"])
def toggle_guest():
    system.guest_mode = not system.guest_mode
    if system.guest_mode:
        system.access_timer = time.time() + 300  # 5 minutes from web toggle
    return jsonify({"success": True, "guest_mode": system.guest_mode})


@app.route("/api/known_faces")
def get_known_faces():
    # Return list of names and one sample image path for each
    faces = []
    if os.path.exists(system.datasets):
        for name in os.listdir(system.datasets):
            if os.path.isdir(os.path.join(system.datasets, name)):
                faces.append(name)
    return jsonify(faces)


@app.route("/known_face/<path:filename>")
def serve_known_face(filename):
    return send_from_directory(system.datasets, filename)


@app.route("/unknown_face/<path:filename>")
def serve_unknown_face(filename):
    return send_from_directory(system.unknown_folder, filename)


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("AEGIS SURVEILLANCE DASHBOARD IS READY!")
    print("Open your browser and go to: http://localhost:5000")
    print("=" * 50 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
