import streamlit as st
import os
from utils import local_storage as storage

# ---------------- PAGE CONFIGURATION ----------------

st.set_page_config(
    page_title="IoT Image Gallery",
    page_icon="🖼️",
    layout="wide"
)

# ---------------- CUSTOM CSS ----------------

st.markdown("""
<style>
.main-title {
    font-size: 36px;
    font-weight: bold;
    color: #2563eb;
    text-align: center;
}
.subtitle {
    text-align: center;
    color: #64748b;
    font-size: 16px;
}
.metric-card {
    background-color: #f1f5f9;
    padding: 20px;
    border-radius: 12px;
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

# ---------------- INITIALIZE DATA ----------------

storage.seed_sample_data()

# ---------------- HEADER ----------------

st.markdown(
    '<div class="main-title">🖼️ IoT Image Gallery</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">Monitor devices and view captured images</div>',
    unsafe_allow_html=True
)

st.divider()

# ---------------- SIDEBAR ----------------

st.sidebar.title("⚙️ Controls")

page = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Image Gallery",
        "Device Controls",
        "About Project"
    ]
)

st.sidebar.divider()

st.sidebar.info(
    "This version uses simulated device controls "
    "and locally stored demonstration images."
)

# ---------------- LOAD DATA ----------------

device = storage.load_device_state()
events = storage.load_events()

# ---------------- DASHBOARD ----------------

if page == "Dashboard":

    st.subheader("📊 Dashboard Overview")

    total_images = len(events)

    esp32_status = device.get("esp32_on", False)
    led_status = device.get("led_on", False)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Total Images",
            total_images
        )

    with col2:
        st.metric(
            "ESP32 Status",
            "ON" if esp32_status else "OFF"
        )

    with col3:
        st.metric(
            "LED Status",
            "ON" if led_status else "OFF"
        )

    st.divider()

    st.subheader("🕒 Recent Images")

    if events:
        recent_events = events[:4]
        columns = st.columns(4)

        for index, event in enumerate(recent_events):
            with columns[index]:
                image_path = storage.thumbnail_path_for(event)

                if os.path.isfile(image_path):
                    st.image(
                        image_path,
                        use_container_width=True
                    )
                else:
                    st.info("Thumbnail unavailable")

                st.caption(event.get("title", "Captured Image"))

                st.caption(
                    f"Time: {event.get('timestamp', 'Unknown')}"
                )

                st.caption(
                    f"Size: {event.get('file_size_kb', 0)} KB"
                )
    else:
        st.info("No images available.")

    st.divider()

    if st.button("🔄 Refresh Dashboard"):
        st.rerun()

# ---------------- IMAGE GALLERY ----------------

elif page == "Image Gallery":

    st.subheader("🖼️ Image Gallery")

    if not events:
        st.info("No images available.")
    else:
        search_text = st.text_input(
            "Search images by title"
        )

        filtered_events = [
            event for event in events
            if search_text.lower()
            in event.get("title", "").lower()
        ]

        st.write(f"Images found: {len(filtered_events)}")

        if filtered_events:
            columns_per_row = 3

            for start in range(
                0,
                len(filtered_events),
                columns_per_row
            ):
                columns = st.columns(columns_per_row)

                for index, event in enumerate(
                    filtered_events[
                        start:start + columns_per_row
                    ]
                ):
                    with columns[index]:

                        image_path = storage.thumbnail_path_for(
                            event
                        )

                        if os.path.isfile(image_path):
                            st.image(
                                image_path,
                                use_container_width=True
                            )
                        else:
                            st.warning("Image file unavailable")

                        st.markdown(
                            f"**{event.get('title', 'Captured Image')}**"
                        )

                        st.caption(
                            f"Date: {event.get('timestamp', 'Unknown')}"
                        )

                        st.caption(
                            f"File size: "
                            f"{event.get('file_size_kb', 0)} KB"
                        )

                        with st.expander("Image Details"):
                            st.write("Image ID:", event.get("id", "N/A"))
                            st.write(
                                "Filename:",
                                event.get("filename", "N/A")
                            )

                            original_path = storage.original_path_for(
                                event
                            )

                            if os.path.isfile(original_path):
                                with open(original_path, "rb") as file:
                                    st.download_button(
                                        "⬇️ Download Image",
                                        data=file.read(),
                                        file_name=os.path.basename(
                                            original_path
                                        ),
                                        mime="image/jpeg",
                                        key=f"download_{event.get('id', start)}"
                                    )

                            if st.button(
                                "🗑️ Delete Image",
                                key=f"delete_{event.get('id', start)}"
                            ):
                                storage.delete_event(
                                    event.get("id")
                                )
                                st.rerun()
        else:
            st.info("No matching images found.")

    st.divider()

    if st.button("📸 Simulate Image Capture"):
        storage.trigger_esp32_capture_simulation()
        st.success("Demonstration image created!")
        st.rerun()

# ---------------- DEVICE CONTROLS ----------------

elif page == "Device Controls":

    st.subheader("🔌 Device Controls")

    st.warning(
        "These controls update simulated device states. "
        "They do not control a physical ESP32."
    )

    device = storage.load_device_state()

    esp32_status = device.get("esp32_on", False)
    led_status = device.get("led_on", False)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### ESP32 Device")

        st.write(
            "Current status:",
            "🟢 ON" if esp32_status else "🔴 OFF"
        )

        if not esp32_status:
            if st.button("Turn ESP32 ON"):
                storage.set_esp32_status(True)
                st.rerun()
        else:
            if st.button("Turn ESP32 OFF"):
                storage.set_esp32_status(False)
                st.rerun()

    with col2:
        st.markdown("### LED Control")

        st.write(
            "Current status:",
            "🟢 ON" if led_status else "🔴 OFF"
        )

        if not led_status:
            if st.button("Turn LED ON"):
                storage.set_led_status(True)
                st.rerun()
        else:
            if st.button("Turn LED OFF"):
                storage.set_led_status(False)
                st.rerun()

    st.divider()

    st.markdown("### Capture Image")

    if st.button("📷 Capture Demonstration Image"):
        storage.trigger_esp32_capture_simulation()
        st.success("Demonstration image created successfully!")
        st.rerun()

# ---------------- ABOUT PROJECT ----------------

elif page == "About Project":

    st.subheader("ℹ️ About IoT Image Gallery")

    st.write("""
    The IoT Image Gallery is a demonstration dashboard
    designed to display images and simulate IoT device controls.
    """)

    st.markdown("""
    **Technologies used:**

    - Python
    - Streamlit
    - Pillow
    - GitHub
    - Streamlit Community Cloud
    """)

    st.markdown("### Main Features")

    st.write("""
    - Image gallery with thumbnails
    - Image search
    - Image download
    - Image deletion
    - Simulated ESP32 status
    - Simulated LED control
    - Demonstration image capture
    """)

    st.info(
        "This version does not connect to a real ESP32 "
        "or AWS S3. Those integrations must be implemented separately."
    )

# ---------------- FOOTER ----------------

st.divider()

st.caption(
    "IoT Image Gallery | Python & Streamlit"
)
