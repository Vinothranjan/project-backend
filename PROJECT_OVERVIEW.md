# Aegis Smart Surveillance System

A professional, AI-powered security solution integrating real-time computer vision, remote management, and a modern web interface.

---

## 🛡️ Core Security Features (Non-Web)

### 🧠 1. Facial Intelligence
- **Face Detection**: Uses Haar Cascade classifiers to locate faces in milliseconds.
- **Face Recognition**: Implements LBPH (Local Binary Patterns Histograms) to identify authorized personnel compared to unknown intruders.
- **Database**: Automatically manages a database of `known_face` (authorized) and `unknown_face` (intruders).

### 🚨 2. Behavior-Based Threat Detection
The system analyzes movement patterns to identify suspicious behavior:
- **Lingering Alerts**: Triggered if an unidentified person stays in view for >3 seconds.
- **Hit-and-Run Alerts**: Triggered if someone quickly moves out of the frame after being spotted but before being identified.

### 📲 3. Remote Override (Telegram)
- **Instant Alerts**: Sends photo evidence of every detection directly to a Telegram bot.
- **Two-Way Control**: Includes interactive buttons (✅ Allow / ❌ Block) allowing the owner to grant access from anywhere.

### 🔓 4. QR-Code Guest Access
- **Instant Entry**: Authorized guests can show a digital QR code to receive a 60-second "Security Bypass" for entry.

---

## 💻 Web Dashboard & Interface

### 🌐 1. Aegis Dashboard
A premium, dark-themed web interface (`http://localhost:5000`) designed for ease of use:
- **Live Monitoring**: View high-quality video feed with AI identity labels.
- **Activity Logs**: Real-time scrolling feed of all detections and system actions.
- **Personnel Gallery**: Manage and view all registered users in the system.

### ⚙️ 2. Dynamic Configuration
- **Hardware Agnostic**: Switch between Labtop cameras and Mobile cameras (IP Webcam) without touching the code.
- **No-Console Control**: All inputs (IP URLs, Guest toggles, and Model Re-training) are handled via web buttons.

---

## 📂 Project Structure

- `web_app/`: Contains the Flask server, HTML templates, and CSS/JS assets.
- `telegram_manager.py`: The bridge between the AI logic and Telegram.
- `camera_utils.py`: Hardware abstraction layer for various camera types.
- `known_face/`: Folder for authorized images.
- `unknown_face/`: Folder for captured intruder photos.

---

## 🚀 Getting Started
1. Install requirements: `pip install flask flask-cors opencv-contrib-python`
2. Run the server: `python web_app/app.py`
3. Access the dashboard: Browse to `http://localhost:5000`
