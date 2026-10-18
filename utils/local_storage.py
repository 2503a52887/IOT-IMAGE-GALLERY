import os
import json
import uuid
from datetime import datetime
from PIL import Image, ImageDraw

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
ORIGINALS_DIR = os.path.join(DATA_DIR, "originals")
THUMBNAILS_DIR = os.path.join(DATA_DIR, "thumbnails")
EVENTS_FILE = os.path.join(DATA_DIR, "events.json")
DEVICE_FILE = os.path.join(DATA_DIR, "device.json")

for folder in [DATA_DIR, ORIGINALS_DIR, THUMBNAILS_DIR]:
    os.makedirs(folder, exist_ok=True)


def load_events():
    if not os.path.exists(EVENTS_FILE):
        return []
    try:
        with open(EVENTS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return []


def save_events(events):
    with open(EVENTS_FILE, "w", encoding="utf-8") as file:
        json.dump(events, file, indent=2)


def load_device_state():
    if not os.path.exists(DEVICE_FILE):
        return {"esp32_on": False, "led_on": False}
    try:
        with open(DEVICE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return {"esp32_on": False, "led_on": False}


def save_device_state(state):
    with open(DEVICE_FILE, "w", encoding="utf-8") as file:
        json.dump(state, file, indent=2)


def seed_sample_data():
    if not load_events():
        store_image_event("Sample Image 1", "sample_1.jpg")
        store_image_event("Sample Image 2", "sample_2.jpg")


def set_esp32_status(is_on):
    state = load_device_state()
    state["esp32_on"] = is_on
    save_device_state(state)


def set_led_status(is_on):
    state = load_device_state()
    state["led_on"] = is_on
    save_device_state(state)


def create_sample_image(path, title):
    image = Image.new("RGB", (600, 400), "#dbeafe")
    draw = ImageDraw.Draw(image)
    draw.text((30, 30), title, fill="#1e3a8a")
    image.save(path)


def store_image_event(title="Captured Image", filename=None):
    event_id = str(uuid.uuid4())
    filename = filename or f"{event_id}.jpg"
    original_path = os.path.join(ORIGINALS_DIR, filename)

    create_sample_image(original_path, title)

    thumbnail_name = f"{event_id}_thumb.jpg"
    thumbnail_path = os.path.join(THUMBNAILS_DIR, thumbnail_name)

    with Image.open(original_path) as image:
        image.thumbnail((250, 180))
        image.save(thumbnail_path, "JPEG")

    events = load_events()
    events.insert(0, {
        "id": event_id,
        "title": title,
        "filename": filename,
        "thumbnail": thumbnail_name,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_events(events)
    return event_id


def trigger_esp32_capture_simulation():
    return store_image_event("ESP32 Simulated Capture")


def delete_event(event_id):
    events = load_events()
    remaining = []

    for event in events:
        if event.get("id") == event_id:
            for folder, key in [
                (ORIGINALS_DIR, "filename"),
                (THUMBNAILS_DIR, "thumbnail")
            ]:
                path = os.path.join(folder, event.get(key, ""))
                if os.path.isfile(path):
                    os.remove(path)
        else:
            remaining.append(event)

    save_events(remaining)


def thumbnail_path_for(event):
    return os.path.join(THUMBNAILS_DIR, event.get("thumbnail", ""))


def original_path_for(event):
    return os.path.join(ORIGINALS_DIR, event.get("filename", ""))
