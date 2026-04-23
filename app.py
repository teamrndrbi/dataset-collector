"""
Dataset Collector — Flask Backend
OAuth 2.0 Google Drive integration (not Service Account, due to storage quota limits).
"""

import os
import sys
import json
import base64
import threading
from datetime import datetime

from flask import Flask, render_template, request, jsonify, redirect, url_for, session

DRIVE_AVAILABLE = False
try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    DRIVE_AVAILABLE = True
except ImportError:
    pass

# ─── PyInstaller Support ─────────────────────────────────────────────────────
# When frozen by PyInstaller, files are in a temp dir. But user data (counter,
# config, token) must be in a writable location next to the executable.
if getattr(sys, 'frozen', False):
    # Running as PyInstaller bundle
    BUNDLE_DIR = sys._MEIPASS  # Where templates/static are bundled
    APP_DIR = os.path.dirname(sys.executable)  # Where .exe/.app lives (writable)
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_DIR = BUNDLE_DIR

app = Flask(__name__,
            template_folder=os.path.join(BUNDLE_DIR, "templates"),
            static_folder=os.path.join(BUNDLE_DIR, "static"))
app.secret_key = os.urandom(24)

# User data files go next to executable (writable)
COUNTER_FILE = os.path.join(APP_DIR, "counter.txt")
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
TEMP_DIR = os.path.join(APP_DIR, "temp_uploads")
TOKEN_FILE = os.path.join(APP_DIR, "token.json")
# client_secret.json: check APP_DIR first, then BUNDLE_DIR
CLIENT_SECRET_FILE = os.path.join(APP_DIR, "client_secret.json")
if not os.path.exists(CLIENT_SECRET_FILE):
    CLIENT_SECRET_FILE = os.path.join(BUNDLE_DIR, "client_secret.json")

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

counter_lock = threading.Lock()
os.makedirs(TEMP_DIR, exist_ok=True)

# Allow HTTP for local dev (OAuth requires HTTPS normally)
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"


def load_config():
    default = {"dataset_name": "Dataset", "parent_folder_id": "", "drive_enabled": False}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
            for k, v in default.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
        except Exception:
            return default
    return default


def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)


def get_next_id():
    with counter_lock:
        current = 0
        if os.path.exists(COUNTER_FILE):
            try:
                with open(COUNTER_FILE, "r") as f:
                    c = f.read().strip()
                    if c:
                        current = int(c)
            except Exception:
                current = 0
        nid = current + 1
        with open(COUNTER_FILE, "w") as f:
            f.write(str(nid))
        return nid


def get_drive_service():
    """Build Drive service from saved OAuth token."""
    if not os.path.exists(TOKEN_FILE):
        return None
    try:
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        if creds and creds.valid:
            return build("drive", "v3", credentials=creds)
        return None
    except Exception as e:
        print(f"[ERROR] Drive auth: {e}")
        return None


def find_or_create_folder(service, name, parent_id):
    """Find or create folder inside parent_id."""
    q = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false and '{parent_id}' in parents"
    results = service.files().list(q=q, spaces="drive", fields="files(id, name)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
    return service.files().create(body=meta, fields="id").execute().get("id")


def upload_to_drive(file_path, file_name, label):
    config = load_config()
    service = get_drive_service()
    if not service:
        return {"success": False, "reason": "Google Drive not authorized. Click 'Login Google Drive' in Settings."}
    pid = config.get("parent_folder_id", "")
    if not pid:
        return {"success": False, "reason": "Parent Folder ID not set. Go to Settings."}
    try:
        ds = config.get("dataset_name", "Dataset")
        ds_id = find_or_create_folder(service, ds, pid)
        lbl_id = find_or_create_folder(service, label, ds_id)
        media = MediaFileUpload(file_path, mimetype="image/jpeg", resumable=True)
        up = service.files().create(
            body={"name": file_name, "parents": [lbl_id]},
            media_body=media, fields="id, name").execute()
        return {"success": True, "drive_file_id": up.get("id"), "drive_file_name": up.get("name")}
    except Exception as e:
        print(f"[ERROR] Drive upload: {e}")
        return {"success": False, "reason": str(e)}


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    try:
        data = request.get_json()
        if not data or "image" not in data or "label" not in data:
            return jsonify({"success": False, "error": "Missing image or label"}), 400
        image_data = data["image"]
        label = data["label"].strip()
        if not label:
            return jsonify({"success": False, "error": "Label cannot be empty"}), 400
        if "," in image_data:
            image_data = image_data.split(",")[1]
        image_bytes = base64.b64decode(image_data)
        image_id = get_next_id()
        id_str = f"{image_id:06d}"
        file_name = f"{id_str}_{label}.jpg"
        label_dir = os.path.join(TEMP_DIR, label)
        os.makedirs(label_dir, exist_ok=True)
        file_path = os.path.join(label_dir, file_name)
        with open(file_path, "wb") as f:
            f.write(image_bytes)
        drive_result = {"success": False, "reason": "Drive not configured"}
        config = load_config()
        if config.get("drive_enabled") and DRIVE_AVAILABLE:
            drive_result = upload_to_drive(file_path, file_name, label)
            if drive_result.get("success"):
                try:
                    os.remove(file_path)
                    if not os.listdir(label_dir):
                        os.rmdir(label_dir)
                except OSError:
                    pass
        return jsonify({
            "success": True, "id": id_str, "file_name": file_name, "label": label,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "drive_upload": drive_result,
            "saved_locally": not drive_result.get("success", False),
        })
    except Exception as e:
        print(f"[ERROR] Upload: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/config", methods=["GET"])
def get_config():
    config = load_config()
    has_token = os.path.exists(TOKEN_FILE)
    has_client_secret = os.path.exists(CLIENT_SECRET_FILE)
    return jsonify({
        "dataset_name": config.get("dataset_name", "Dataset"),
        "parent_folder_id": config.get("parent_folder_id", ""),
        "drive_enabled": config.get("drive_enabled", False),
        "drive_available": DRIVE_AVAILABLE,
        "drive_authorized": has_token,
        "has_client_secret": has_client_secret,
    })


@app.route("/config", methods=["POST"])
def update_config():
    try:
        data = request.get_json()
        config = load_config()
        if "dataset_name" in data:
            config["dataset_name"] = data["dataset_name"].strip() or "Dataset"
        if "parent_folder_id" in data:
            config["parent_folder_id"] = data["parent_folder_id"].strip()
        if "drive_enabled" in data:
            config["drive_enabled"] = bool(data["drive_enabled"])
        # Handle client_secret JSON
        if "client_secret" in data:
            cs = data["client_secret"]
            if isinstance(cs, str):
                try:
                    cs = json.loads(cs)
                except json.JSONDecodeError:
                    return jsonify({"success": False, "error": "Invalid JSON for client secret"}), 400
            with open(CLIENT_SECRET_FILE, "w") as f:
                json.dump(cs, f, indent=2)
        save_config(config)
        return jsonify({"success": True, "message": "Configuration saved."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/auth/google")
def auth_google():
    """Start OAuth 2.0 flow."""
    if not os.path.exists(CLIENT_SECRET_FILE):
        return "Client secret not configured. Go to Settings first.", 400
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES,
        redirect_uri=url_for("auth_callback", _external=True)
    )
    auth_url, state_val = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )
    session["oauth_state"] = state_val
    # Store code_verifier for PKCE
    session["code_verifier"] = flow.code_verifier
    return redirect(auth_url)


@app.route("/auth/callback")
def auth_callback():
    """Handle OAuth 2.0 callback."""
    if not os.path.exists(CLIENT_SECRET_FILE):
        return "Client secret not found.", 400
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES,
        redirect_uri=url_for("auth_callback", _external=True)
    )
    # Restore code_verifier from session for PKCE
    flow.code_verifier = session.get("code_verifier")
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())
    return """
    <html><body style="background:#0a0e1a;color:#10b981;font-family:Inter,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column;">
    <h1>✅ Google Drive Connected!</h1>
    <p>You can close this tab and go back to Dataset Collector.</p>
    <script>setTimeout(()=>window.close(),3000)</script>
    </body></html>
    """


@app.route("/auth/logout", methods=["POST"])
def auth_logout():
    """Remove saved token."""
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)
    return jsonify({"success": True, "message": "Logged out from Google Drive."})


@app.route("/counter", methods=["GET"])
def get_counter():
    try:
        count = 0
        if os.path.exists(COUNTER_FILE):
            with open(COUNTER_FILE, "r") as f:
                c = f.read().strip()
                count = int(c) if c else 0
        return jsonify({"counter": count, "next_id": f"{count + 1:06d}"})
    except Exception:
        return jsonify({"counter": 0, "next_id": "000001"})


@app.route("/test-drive", methods=["POST"])
def test_drive():
    if not DRIVE_AVAILABLE:
        return jsonify({"success": False, "error": "Google Drive libraries not installed."})
    svc = get_drive_service()
    if not svc:
        return jsonify({"success": False, "error": "Not authorized. Click 'Login Google Drive' first."})
    try:
        svc.files().list(pageSize=1, fields="files(id, name)").execute()
        return jsonify({"success": True, "message": "Google Drive connection successful!"})
    except Exception as e:
        return jsonify({"success": False, "error": f"Connection failed: {e}"})


if __name__ == "__main__":
    print("=" * 60)
    print("  Dataset Collector Starting...")
    print(f"  Temp uploads: {TEMP_DIR}")
    print(f"  Drive: {'Available' if DRIVE_AVAILABLE else 'Not installed'}")
    print(f"  Token: {'Found' if os.path.exists(TOKEN_FILE) else 'Not found'}")
    print("=" * 60)
    print("  Open http://localhost:5001 in your browser")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5001, debug=True)
