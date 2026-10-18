import os
import json
import uuid
from datetime import datetime
from PIL import Image, ImageDraw

# Project directories
BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

DATA_DIR = os.path.join(BASE_DIR, "data")
ORIGINALS_DIR = os.path.join(DATA_DIR, "originals")
THUMBNAILS_DIR = os.path.join(DATA_DIR, "thumbnails")

EVENTS_FILE = os.path.join(DATA_DIR, "events.json")
DEVICE_FILE = os.path.join(DATA_DIR, "device.json")

# Create required folders
for folder in [DATA_DIR, ORIGINALS_DIR, THUMBNAILS_DIR]:
    os.makedirs(folder, exist_ok=True)


# Load image events
def load_events():
    if not os.path.exists(EVENTS_FILE):
        return []

    try:
        with open(EVENTS_FILE, "r", encoding="utf-8") as file:
            events = json.load(file)

        # Ensure older events have the required fields
        for event in events:
            event.setdefault("timestamp", "Unknown")
            event.setdefault("file_size_kb", 0)
            event.setdefault("title", "Captured Image")

        return events

    except (json.JSONDecodeError, OSError):
        return []


# Save image events
def save_events(events):
    with open(EVENTS_FILE, "w", encoding="utf-8") as file:
        json.dump(events, file, indent=2)


# Load device state
def load_device_state():
    default_state = {
        "esp32_on": False,
        "led_on": False
    }

    if not os.path.exists(DEVICE_FILE):
        return default_state

    try:
        with open(DEVICE_FILE, "r", encoding="utf-8") as file:
            state = json.load(file)

        return {**default_state, **state}

    except (json.JSONDecodeError, OSError):
        return default_state


# Save device state
def save_device_state(state):
    with open(DEVICE_FILE, "w", encoding="utf-8") as file:
        json.dump(state, file, indent=2)


# Create a sample image
def create_sample_image(path, title):
    image = Image.new("RGB", (600, 400), "#dbeafe")
    draw = ImageDraw.Draw(image)

    draw.text(
        (30, 30),
        title,
        fill="#1e3a8a"
    )

    image.save(path, format="JPEG")


# Store an image event
def store_image_event(title="Captured Image", filename=None):
    event_id = str(uuid.uuid4())

    filename = filename or f"{event_id}.jpg"

    # Prevent a supplied filename from escaping the image folder
    filename = os.path.basename(filename)

    original_path = os.path.join(
        ORIGINALS_DIR,
        filename
    )

    # Create sample image for demonstration
    create_sample_image(original_path, title)

    # Calculate actual file size
    file_size_kb = round(
        os.path.getsize(original_path) / 1024,
        2
    )

    # Create thumbnail
    thumbnail_name = f"{event_id}_thumb.jpg"

    thumbnail_path = os.path.join(
        THUMBNAILS_DIR,
        thumbnail_name
    )

    with Image.open(original_path) as image:
        image.thumbnail((250, 180))
        image.save(thumbnail_path, format="JPEG")

    # Build event record
    event = {
        "id": event_id,
        "title": title,
        "filename": filename,
        "thumbnail": thumbnail_name,
        "timestamp": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "file_size_kb": file_size_kb
    }

    events = load_events()
    events.insert(0, event)
    save_events(events)

    return event_id


# Create sample images on the first run
def seed_sample_data():
    if not load_events():
        store_image_event("Sample Image 1")
        store_image_event("Sample Image 2")


# Update ESP32 status
def set_esp32_status(is_on):
    state = load_device_state()
    state["esp32_on"] = bool(is_on)
    save_device_state(state)


# Update LED status
def set_led_status(is_on):
    state = load_device_state()
    state["led_on"] = bool(is_on)
    save_device_state(state)


# Simulate an ESP32 image capture
def trigger_esp32_capture_simulation():
    return store_image_event("ESP32 Simulated Capture")


# Delete an image event
def delete_event(event_id):
    events = load_events()
    remaining_events = []

    for event in events:
        if event.get("id") == event_id:

            for folder, key in [
                (ORIGINALS_DIR, "filename"),
                (THUMBNAILS_DIR, "thumbnail")
            ]:
                filename = event.get(key, "")

                if filename:
                    path = os.path.join(
                        folder,
                        os.path.basename(filename)
                    )

                    if os.path.isfile(path):
                        os.remove(path)

        else:
            remaining_events.append(event)

    save_events(remaining_events)


# Get thumbnail path
def thumbnail_path_for(event):
    return os.path.join(
        THUMBNAILS_DIR,
        os.path.basename(event.get("thumbnail", ""))
    )


# Get original image path
def original_path_for(event):
    return os.path.join(
        ORIGINALS_DIR,
        os.path.basename(event.get("filename", ""))
    )
