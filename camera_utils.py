import cv2
import os
import json
import threading
import time

CONFIG_FILE = "camera_settings.json"

class ThreadedCamera:
    """
    A wrapper class for cv2.VideoCapture that runs frame reading in a background thread.
    This prevents the MJPEG buffer from filling up, which fixes 'lag' on mobile streams.
    """
    def __init__(self, source):
        self.cap = cv2.VideoCapture(source)
        self.ret = False
        self.frame = None
        self.is_running = True
        self.thread = threading.Thread(target=self._update, args=())
        self.thread.daemon = True
        self.thread.start()
        # Give the thread a moment to grab the first frame
        time.sleep(0.5)

    def _update(self):
        while self.is_running:
            if self.cap.isOpened():
                (self.ret, self.frame) = self.cap.read()
            else:
                self.is_running = False
            time.sleep(0.01) # Small sleep to avoid CPU hogging

    def read(self):
        # Similar signature to cv2.VideoCapture.read()
        return self.ret, self.frame

    def release(self):
        self.is_running = False
        self.thread.join(timeout=1)
        self.cap.release()

    def isOpened(self):
        return self.cap.isOpened()

def get_camera():
    """
    Returns a camera object based on user presence and hardware detection.
    Can be a standard cv2.VideoCapture or our ThreadedCamera for mobile.
    """
    source = 0
    config_exists = os.path.exists(CONFIG_FILE)

    # 1. Load saved config if it exists
    if config_exists:
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                source = config.get("source", 0)
                print(f"[INFO] Using saved camera source: {source}")
        except Exception:
            pass
    else:
        # 2. Check for internal camera presence
        cap_test = cv2.VideoCapture(0)
        has_internal_camera = cap_test.isOpened()
        cap_test.release()

        print("\n" + "="*40)
        print("      CAMERA SETUP & CONFIGURATION      ")
        print("="*40)
        
        if not has_internal_camera:
            print("[NOTICE] No built-in camera detected on this computer.")
            print("You can use your mobile phone as a high-quality camera.")
        else:
            print("[INFO] Internal camera detected.")
            print("TIP: Use your mobile camera for MUCH better image quality.")

        print("\nHOW TO USE MOBILE CAMERA:")
        print("1. Install 'IP Webcam' on Android.")
        print("2. PRESS 'q' or 'ESC' to stop the application at any time.")
        
        print("\nOPTIONS:")
        if has_internal_camera:
            print("1. Use Laptop/Internal Camera")
        print("2. Use Mobile Camera (IP URL)")
        
        choice = input("\nSelect choice (1 or 2): ").strip()
        
        if choice == '2':
            url = input("Enter the IP URL (e.g., http://192.168.1.5:8080): ").strip()
            
            # Smart URL Correction:
            if url and not any(url.endswith(suffix) for suffix in ["/video", "/shot.jpg", "/live"]):
                from urllib.parse import urlparse
                parsed = urlparse(url)
                if parsed.path in ["", "/"]:
                    url = url.rstrip('/') + "/video"
                    print(f"[INFO] Automatically appended '/video' for stream: {url}")
            
            if url:
                source = url
            else:
                print("[WARN] No URL provided. " + ("Defaulting to laptop." if has_internal_camera else "Exiting."))
                source = 0 if has_internal_camera else None
        else:
            source = 0 if has_internal_camera else None

        if source is not None:
            save = input("\nDo you want to save this setting for next time? (y/n): ").strip().lower()
            if save == 'y':
                with open(CONFIG_FILE, "w") as f:
                    json.dump({"source": source}, f)
                print(f"[SUCCESS] Settings saved to {CONFIG_FILE}")
                print("To reset later, delete 'camera_settings.json'.")

    if source is None:
        print("[ERROR] No camera source selected.")
        return None

    # 3. Initialize Camera
    # Use ThreadedCamera for mobile/URLs to avoid buffering lag.
    if isinstance(source, str) and (source.startswith("http") or "ip" in source):
        print("[INFO] Threaded mode enabled for mobile camera (fixes lag).")
        cap = ThreadedCamera(source)
    else:
        cap = cv2.VideoCapture(source)
        
    if not cap.isOpened():
        print(f"\n[ERROR] Failed to connect to: {source}")
        if source != 0:
            print("Trying default laptop camera...")
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return None
        else:
            return None
            
    return cap

def reset_config():
    """Removes the camera configuration file."""
    if os.path.exists(CONFIG_FILE):
        os.remove(CONFIG_FILE)
        print("[INFO] Camera settings reset.")
