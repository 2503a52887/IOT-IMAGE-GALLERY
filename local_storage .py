"""
Local Storage Engine & AWS Simulator for IoT Image Gallery
Allows the application to run completely offline without an active AWS account,
simulating S3 bucket storage, DynamoDB table events, and Pillow-based Lambda thumbnail generation.
"""

import os
import json
import uuid
import io
import threading
from datetime import datetime
from PIL import Image, ImageDraw, ImageOps

# This file lives in <project>/utils/, so the project root is one level up from here.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
S3_LOCAL_DIR = os.path.join(DATA_DIR, "s3")
ORIGINALS_DIR = os.path.join(S3_LOCAL_DIR, "originals")
THUMBNAILS_DIR = os.path.join(S3_LOCAL_DIR, "thumbnails")
DB_FILE = os.path.join(DATA_DIR, "dynamodb_events.json")
STATE_FILE = os.path.join(DATA_DIR, "device_state.json")

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

# Ensure required folders exist
os.makedirs(ORIGINALS_DIR, exist_ok=True)
os.makedirs(THUMBNAILS_DIR, exist_ok=True)

# One lock guards every read-modify-write on the JSON "tables".
_LOCK = threading.RLock()


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _atomic_write_json(path, data):
    """Write JSON to a temp file, then atomically swap it in (no half-written files)."""
    tmp_path = f"{path}.{uuid.uuid4().hex[:6]}.tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, path)


# --------------------------------------------------------------------------- #
# Device state
# --------------------------------------------------------------------------- #
def save_device_state(state):
    """Save ESP32 and LED state to local file."""
    with _LOCK:
        _atomic_write_json(STATE_FILE, state)


def load_device_state():
    """Load ESP32 and LED state from local file."""
    with _LOCK:
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                pass
        default_state = {
            "device_id": "ESP32-CAM-01",
            "device_status": "Active",  # Active or Inactive
            "led_status": "OFF",         # ON or OFF
            "last_ping": _now(),
        }
        save_device_state(default_state)
        return default_state


def set_esp32_status(is_active: bool):
    """Update ESP32 device status."""
    with _LOCK:
        state = load_device_state()
        state["device_status"] = "Active" if is_active else "Inactive"
        state["last_ping"] = _now()
        save_device_state(state)
        return state


def set_led_status(is_on: bool):
    """Update ESP32 LED status."""
    with _LOCK:
        state = load_device_state()
        state["led_status"] = "ON" if is_on else "OFF"
        save_device_state(state)
        return state


# --------------------------------------------------------------------------- #
# Events ("DynamoDB")
# --------------------------------------------------------------------------- #
def _read_events_raw():
    """Read the events file. A corrupted file is backed up instead of silently lost."""
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, "r") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        backup = f"{DB_FILE}.corrupt-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            os.replace(DB_FILE, backup)
        except OSError:
            pass
        return []


def load_events():
    """Load all image events simulating DynamoDB scan (newest first)."""
    with _LOCK:
        events = _read_events_raw()
    return sorted(events, key=lambda x: x.get("timestamp", ""), reverse=True)


def save_events(events):
    """Save events list to local json file simulating DynamoDB put."""
    with _LOCK:
        _atomic_write_json(DB_FILE, events)


def get_event(event_id: str):
    """Return a single event by id, or None."""
    for event in load_events():
        if event.get("event_id") == event_id:
            return event
    return None


def delete_event(event_id: str) -> bool:
    """Delete an event and its files. Returns True if something was deleted."""
    with _LOCK:
        events = _read_events_raw()
        target = next((e for e in events if e.get("event_id") == event_id), None)
        if target is None:
            return False
        events = [e for e in events if e.get("event_id") != event_id]
        save_events(events)

    for folder, key in ((ORIGINALS_DIR, target.get("original_key")),
                        (THUMBNAILS_DIR, target.get("thumbnail_key"))):
        if key:
            try:
                os.remove(os.path.join(folder, os.path.basename(key)))
            except OSError:
                pass
    return True


# --------------------------------------------------------------------------- #
# Image processing
# --------------------------------------------------------------------------- #
def generate_thumbnail(image_bytes: bytes, max_size=(300, 300)) -> bytes:
    """
    Generate a thumbnail from image bytes using Pillow, matching AWS Lambda logic.
    Maintains aspect ratio, respects EXIF rotation and converts to JPEG.
    """
    with Image.open(io.BytesIO(image_bytes)) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode != "RGB":
            if img.mode in ("RGBA", "LA", "P"):
                # Flatten transparency onto white instead of black
                rgba = img.convert("RGBA")
                background = Image.new("RGB", rgba.size, "white")
                background.paste(rgba, mask=rgba.split()[-1])
                img = background
            else:
                img = img.convert("RGB")
        try:
            resample = Image.Resampling.LANCZOS  # Pillow >= 9.1
        except AttributeError:
            resample = Image.LANCZOS
        img.thumbnail(max_size, resample)
        out_io = io.BytesIO()
        img.save(out_io, format="JPEG", quality=85)
        return out_io.getvalue()


def store_image_event(image_bytes: bytes, original_filename: str, event_source: str = "Dashboard Upload"):
    """
    Process image:
    1. Save original to local S3 simulation folder
    2. Generate thumbnail using Pillow and save to local thumbnails folder
    3. Record metadata in DynamoDB simulation file
    """
    timestamp = _now()
    event_id = f"evt_{uuid.uuid4().hex[:10]}"
    ext = os.path.splitext(original_filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        ext = ".jpg"

    safe_original_name = f"{event_id}_original{ext}"
    safe_thumb_name = f"{event_id}_thumb.jpg"

    original_path = os.path.join(ORIGINALS_DIR, safe_original_name)
    thumb_path = os.path.join(THUMBNAILS_DIR, safe_thumb_name)

    # Generate the thumbnail FIRST: if the bytes aren't a valid image we fail
    # before anything is written, so no orphan files are left behind.
    thumb_bytes = generate_thumbnail(image_bytes)

    # Save original image (S3 Originals simulator)
    with open(original_path, "wb") as f:
        f.write(image_bytes)

    # Save thumbnail (AWS Lambda + Pillow simulator)
    with open(thumb_path, "wb") as f:
        f.write(thumb_bytes)

    dev_state = load_device_state()

    # DynamoDB event record. Only keys are stored (not absolute paths) so the
    # project can be moved or deployed elsewhere.
    event_record = {
        "event_id": event_id,
        "timestamp": timestamp,
        "filename": os.path.basename(original_filename or safe_original_name),
        "original_key": safe_original_name,
        "thumbnail_key": safe_thumb_name,
        "file_size_kb": round(len(image_bytes) / 1024, 2),
        "device_id": dev_state.get("device_id", "ESP32-CAM-01"),
        "device_status": dev_state.get("device_status", "Active"),
        "led_status": dev_state.get("led_status", "OFF"),
        "event_source": event_source,
        "storage": "Local S3 Simulator",
    }

    with _LOCK:
        events = _read_events_raw()
        events.insert(0, event_record)
        save_events(events)

    return event_record


def original_path_for(event: dict) -> str:
    return os.path.join(ORIGINALS_DIR, os.path.basename(event["original_key"]))


def thumbnail_path_for(event: dict) -> str:
    return os.path.join(THUMBNAILS_DIR, os.path.basename(event["thumbnail_key"]))


# --------------------------------------------------------------------------- #
# Synthetic camera frames / simulation
# --------------------------------------------------------------------------- #
def create_synthetic_iot_image(title: str, subtitle: str, color_scheme="cyan") -> bytes:
    """Generate a clean synthetic camera frame image for mock captures."""
    width, height = 800, 600
    img = Image.new("RGB", (width, height), color="#0f172a")
    draw = ImageDraw.Draw(img)

    colors = {
        "cyan": ("#082f49", "#0284c7", "#06b6d4"),
        "blue": ("#0c4a6e", "#0369a1", "#38bdf8"),
        "amber": ("#451a03", "#d97706", "#fbbf24"),
    }.get(color_scheme, ("#082f49", "#0284c7", "#06b6d4"))

    # Top banner
    draw.rectangle([0, 0, width, 60], fill=colors[0])
    draw.line([0, 60, width, 60], fill=colors[2], width=2)

    # Camera viewfinder crosshairs
    cx, cy = width // 2, height // 2
    draw.line([cx - 40, cy, cx + 40, cy], fill=colors[2], width=2)
    draw.line([cx, cy - 40, cx, cy + 40], fill=colors[2], width=2)
    draw.ellipse([cx - 70, cy - 70, cx + 70, cy + 70], outline=colors[2], width=1)

    # Corner brackets (viewfinder)
    bracket_len = 30
    draw.line([40, 90, 40 + bracket_len, 90], fill="#38bdf8", width=3)
    draw.line([40, 90, 40, 90 + bracket_len], fill="#38bdf8", width=3)
    draw.line([width - 40 - bracket_len, 90, width - 40, 90], fill="#38bdf8", width=3)
    draw.line([width - 40, 90, width - 40, 90 + bracket_len], fill="#38bdf8", width=3)
    draw.line([40, height - 50, 40 + bracket_len, height - 50], fill="#38bdf8", width=3)
    draw.line([40, height - 50 - bracket_len, 40, height - 50], fill="#38bdf8", width=3)
    draw.line([width - 40 - bracket_len, height - 50, width - 40, height - 50], fill="#38bdf8", width=3)
    draw.line([width - 40, height - 50 - bracket_len, width - 40, height - 50], fill="#38bdf8", width=3)

    # Info text (default Pillow font has no "●" glyph, so use a plain "REC" label)
    ts = _now()
    draw.text((30, 20), f"ESP32-CAM FEED // {title.upper()}", fill="#ffffff")
    draw.text((width - 220, 20), f"REC  {ts}", fill="#ef4444")

    # Center label box
    draw.rectangle([cx - 200, cy + 120, cx + 200, cy + 180], fill="#1e293b", outline=colors[1], width=2)
    draw.text((cx - 180, cy + 130), title, fill="#e0f2fe")
    draw.text((cx - 180, cy + 155), subtitle, fill="#94a3b8")

    out_io = io.BytesIO()
    img.save(out_io, format="JPEG", quality=90)
    return out_io.getvalue()


def seed_sample_data():
    """Seeds 3 realistic initial IoT captures if the gallery is empty."""
    if len(load_events()) > 0:
        return

    samples = [
        ("Laboratory Entrance Gate", "Motion Trigger - Authorized Access", "cyan"),
        ("IoT Edge Node Station #4", "Periodic Telemetry Snapshot", "blue"),
        ("Optical Sensor Checkpoint", "Ambient Lux Threshold Triggered", "amber"),
    ]

    for title, subtitle, scheme in samples:
        img_bytes = create_synthetic_iot_image(title, subtitle, scheme)
        filename = f"{title.lower().replace(' ', '_').replace('#', '')}.jpg"
        store_image_event(img_bytes, filename, event_source="ESP32 Edge Cam Trigger")


def trigger_esp32_capture_simulation():
    """
    Simulates a full ESP32 capture event cycle:
    1. Turn LED status ON
    2. Capture frame from camera
    3. Generate thumbnail with Pillow
    4. Save to S3 & DynamoDB
    5. Turn LED status OFF (always, even if storing fails)
    """
    set_led_status(True)
    try:
        title = f"ESP32-CAM Capture #{uuid.uuid4().hex[:4].upper()}"
        subtitle = "On-Demand Trigger Event via Dashboard"
        img_bytes = create_synthetic_iot_image(title, subtitle, "cyan")

        filename = f"capture_{uuid.uuid4().hex[:6]}.jpg"
        return store_image_event(img_bytes, filename, event_source="Capture Event Button")
    finally:
        set_led_status(False)
