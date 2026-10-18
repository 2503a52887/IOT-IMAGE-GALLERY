"""
IoT Image Gallery & Edge Vision Hub  -  Streamlit dashboard
Runs fully offline using the local AWS simulator (utils/local_storage.py).

Run:  streamlit run app.py        (then open http://localhost:8501)
"""

import os
import streamlit as st

from utils import local_storage as storage

st.set_page_config(
    page_title="IoT Image Gallery",
    page_icon="📷",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Create the 3 demo captures the first time the app runs
storage.seed_sample_data()


# --------------------------------------------------------------------------- #
# Styling
# --------------------------------------------------------------------------- #
st.markdown(
    """
<style>
.stApp { background: linear-gradient(180deg, #f0f9ff 0%, #e0f2fe 100%); }
.hero {
    background: linear-gradient(135deg, #0284c7 0%, #06b6d4 100%);
    color: white; padding: 28px 32px; border-radius: 18px;
    box-shadow: 0 8px 24px rgba(2,132,199,.25); margin-bottom: 22px;
    display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap;
}
.hero h1 { color: white; margin: 0; font-size: 2rem; padding: 0; }
.hero p  { margin: 6px 0 0 0; opacity: .95; }
.hero .pill { background: rgba(255,255,255,.22); padding: 8px 16px; border-radius: 999px;
              font-weight: 600; font-size: .9rem; white-space: nowrap; }
.stat {
    background: white; border-radius: 14px; padding: 16px 12px; text-align: center;
    border-top: 4px solid #0284c7; box-shadow: 0 4px 14px rgba(15,23,42,.08); min-height: 130px;
    display: flex; flex-direction: column; justify-content: center; align-items: center;
}
.stat .label { font-size: .72rem; font-weight: 700; letter-spacing: .08em; color: #475569; text-transform: uppercase; }
.stat .value { font-size: 1.7rem; font-weight: 800; color: #0369a1; margin-top: 8px; }
.stat .value.small { font-size: 1rem; line-height: 1.6; }
.badge { display: inline-block; margin-top: 8px; padding: 6px 16px; border-radius: 999px; font-weight: 700; font-size: .95rem; }
.badge.on  { background: #dcfce7; color: #166534; border: 1px solid #86efac; }
.badge.off { background: #f1f5f9; color: #64748b; border: 1px solid #cbd5e1; }
.badge.led-on { background: #cffafe; color: #0e7490; border: 1px solid #22d3ee; }
div.stButton > button, div.stDownloadButton > button { width: 100%; border-radius: 10px; font-weight: 600; }
div.stButton > button[kind="primary"] {
    background: linear-gradient(90deg, #0284c7, #06b6d4); border: 0; color: white; padding: .7rem 1rem;
}
.info-box { background: #dbeafe; color: #1e3a8a; padding: 14px 16px; border-radius: 10px; font-size: .92rem; }
.thumb-meta { font-size: .78rem; color: #475569; line-height: 1.5; margin: 4px 0 8px 0; }
</style>
""",
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- #
# Session state
# --------------------------------------------------------------------------- #
st.session_state.setdefault("uploader_key", 0)      # changing this resets the file uploader
st.session_state.setdefault("upload_status", "Ready")
st.session_state.setdefault("flash", None)          # (level, message) shown once after an action


def flash(level: str, message: str):
    st.session_state["flash"] = (level, message)


# --------------------------------------------------------------------------- #
# Callbacks (run BEFORE the page redraws, so the dashboard always shows fresh data)
# --------------------------------------------------------------------------- #
def on_power_toggle():
    is_on = st.session_state["power_toggle"]
    storage.set_esp32_status(is_on)
    if not is_on:
        storage.set_led_status(False)  # powering off also turns the LED off
    flash("info", f"ESP32 power {'ON' if is_on else 'OFF'}.")


def on_led(turn_on: bool):
    storage.set_led_status(turn_on)
    flash("info", f"Onboard LED turned {'ON' if turn_on else 'OFF'}.")


def on_capture():
    try:
        event = storage.trigger_esp32_capture_simulation()
        st.session_state["upload_status"] = "Capture stored"
        flash("success", f"Capture complete: {event['filename']} saved to S3 and logged in DynamoDB.")
    except Exception as exc:
        st.session_state["upload_status"] = "Failed"
        flash("error", f"Capture failed: {exc}")


def on_upload():
    uploaded = st.session_state.get(f"uploader_{st.session_state['uploader_key']}")
    if uploaded is None:
        flash("warning", "Choose an image first.")
        return
    try:
        event = storage.store_image_event(uploaded.getvalue(), uploaded.name, event_source="Dashboard Upload")
        st.session_state["upload_status"] = "Uploaded"
        st.session_state["uploader_key"] += 1  # clears the uploader so it can't be re-saved on rerun
        flash("success", f"Uploaded {event['filename']} - thumbnail generated.")
    except Exception:
        st.session_state["upload_status"] = "Failed"
        flash("error", "That file couldn't be read as an image. Please use a valid JPG or PNG.")


def on_delete(event_id: str):
    if storage.delete_event(event_id):
        flash("success", "Image deleted.")
    else:
        flash("error", "Image not found.")


# --------------------------------------------------------------------------- #
# Load current data
# --------------------------------------------------------------------------- #
device = storage.load_device_state()
events = storage.load_events()
device_active = device.get("device_status") == "Active"
led_on = device.get("led_status") == "ON"

# Keep the toggle in sync with the saved device state
st.session_state["power_toggle"] = device_active


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.markdown("### 📡 ESP32 Hardware Status")
    st.toggle(
        "ESP32 Device Power",
        key="power_toggle",
        on_change=on_power_toggle,
        help="Simulates powering the ESP32-CAM node on or off.",
    )

    st.markdown("### 💡 Onboard LED Test")
    c1, c2 = st.columns(2)
    c1.button("Turn LED ON", key="led_on_btn", on_click=on_led, args=(True,), disabled=not device_active)
    c2.button("Turn LED OFF", key="led_off_btn", on_click=on_led, args=(False,), disabled=not device_active)
    if not device_active:
        st.caption("Power the device on to use the LED.")

    st.divider()
    st.markdown("### ☁️ AWS Cloud Health Check")
    st.markdown(
        '<div class="info-box">Operating in <b>Local Simulator Mode</b>. '
        "All S3, DynamoDB, and Lambda Pillow functions run locally.</div>",
        unsafe_allow_html=True,
    )
    n_orig = len(os.listdir(storage.ORIGINALS_DIR))
    n_thumb = len(os.listdir(storage.THUMBNAILS_DIR))
    st.markdown(
        f"- **S3 originals:** {n_orig} object(s)\n"
        f"- **S3 thumbnails:** {n_thumb} object(s)\n"
        f"- **DynamoDB events:** {len(events)} record(s)\n"
        f"- **Lambda (Pillow):** ready"
    )

    st.divider()
    st.caption("College Submission Project • IoT Image Gallery")


# --------------------------------------------------------------------------- #
# Header
# --------------------------------------------------------------------------- #
st.markdown(
    """
<div class="hero">
  <div>
    <h1>📷 IoT Image Gallery &amp; Edge Vision Hub</h1>
    <p>ESP32 Microcontroller • AWS IoT Core • S3 • Lambda (Pillow) • DynamoDB • API Gateway</p>
  </div>
  <div class="pill">Mode: Local Demo</div>
</div>
""",
    unsafe_allow_html=True,
)

# One-time message from the last action
if st.session_state["flash"]:
    level, message = st.session_state["flash"]
    st.session_state["flash"] = None
    {"success": st.success, "error": st.error, "warning": st.warning}.get(level, st.info)(message)


# --------------------------------------------------------------------------- #
# Stat cards
# --------------------------------------------------------------------------- #
latest = events[0]["timestamp"] if events else "—"
upload_status = st.session_state["upload_status"]

cols = st.columns(5)
cards = [
    ("Total Images", f'<div class="value">{len(events)}</div>'),
    ("Latest Event Time", f'<div class="value small">{latest}</div>'),
    (
        "ESP32 Device Status",
        f'<span class="badge {"on" if device_active else "off"}">'
        f'{"🟢" if device_active else "⚪"} {device.get("device_status", "Unknown")}</span>',
    ),
    (
        "LED Status",
        f'<span class="badge {"led-on" if led_on else "off"}">'
        f'{"🔵 LED ON" if led_on else "⚫ LED OFF"}</span>',
    ),
    ("Upload Status", f'<div class="value small">{upload_status}</div>'),
]
for col, (label, body) in zip(cols, cards):
    col.markdown(f'<div class="stat"><div class="label">{label}</div>{body}</div>', unsafe_allow_html=True)

st.write("")


# --------------------------------------------------------------------------- #
# Actions: capture + upload
# --------------------------------------------------------------------------- #
left, right = st.columns(2, gap="large")

with left:
    st.markdown("## 🚀 Trigger Capture Event")
    st.write(
        "Send a live capture trigger to the ESP32 node. "
        "The onboard LED will illuminate while capturing."
    )
    st.button(
        "📸 Capture Event",
        type="primary",
        on_click=on_capture,
        disabled=not device_active,
    )
    if not device_active:
        st.caption("ESP32 is powered off. Turn it on from the sidebar to capture.")

with right:
    st.markdown("## 📤 Upload Custom Image")
    st.write("Upload a JPG, JPEG, or PNG image. Thumbnails are auto-generated via Pillow & stored in S3.")
    key = f"uploader_{st.session_state['uploader_key']}"
    st.file_uploader("Choose an image file", type=["jpg", "jpeg", "png"], key=key)
    st.button("☁️ Upload to S3", on_click=on_upload, disabled=st.session_state.get(key) is None)

st.divider()


# --------------------------------------------------------------------------- #
# Gallery
# --------------------------------------------------------------------------- #
st.markdown(f"## 🖼️ Image Gallery ({len(events)})")

if not events:
    st.info("No images yet. Trigger a capture or upload an image above.")
else:
    per_row = 4
    for start in range(0, len(events), per_row):
        row = st.columns(per_row)
        for col, event in zip(row, events[start:start + per_row]):
            with col:
                with st.container(border=True):
                    thumb = storage.thumbnail_path_for(event)
                    if os.path.exists(thumb):
                        st.image(thumb)
                    else:
                        st.warning("Thumbnail missing")
                    st.markdown(
                        f'<div class="thumb-meta"><b>{event["filename"]}</b><br>'
                        f'{event["timestamp"]} • {event["file_size_kb"]} KB<br>'
                        f'{event["event_source"]}</div>',
                        unsafe_allow_html=True,
                    )
                    original = storage.original_path_for(event)
                    if os.path.exists(original):
                        with open(original, "rb") as f:
                            st.download_button(
                                "⬇️ Original",
                                data=f.read(),
                                file_name=event["filename"],
                                key=f"dl_{event['event_id']}",
                            )
                    st.button(
                        "🗑️ Delete",
                        key=f"del_{event['event_id']}",
                        on_click=on_delete,
                        args=(event["event_id"],),
                    )
