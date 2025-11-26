import base64
import re
from typing import Tuple

import streamlit as st


def img_to_base64(image_path: str) -> str | None:
    """Converts a local image file to a Base64 string for HTML embedding."""
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception:
        return None


def parse_integrated_details(text: str) -> Tuple[str, str, str]:
    """
    Parses the single text area content to extract Sender, Recipient, and other details.
    Expected format:
    SENDER: ...
    RECIPIENT: ...
    Label: Value
    """
    lines = text.split("\n")
    sender = ""
    recipient = ""
    other_details: list[str] = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for specific reserved keys
        upper = line.upper()
        if upper.startswith("SENDER:"):
            sender = line.split(":", 1)[1].strip()
        elif upper.startswith("RECIPIENT:"):
            recipient = line.split(":", 1)[1].strip()
        else:
            # Keep other lines as Key Details
            other_details.append(line)

    return sender, recipient, "\n".join(other_details)


def clear_session_data() -> None:
    """
    Security Feature: Completely wipes the session state.
    Ensures no data persists after the user finishes their session.
    """
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()


def clean_markdown(text: str | None) -> str:
    """Removes markdown formatting for cleaner Text-to-Speech output."""
    if not text:
        return ""
    text = re.sub(r"[*#`_\[\]]", "", text)
    text = re.sub(r"\n+", ". ", text)
    return text


def load_css(css_path: str = "assets/style.css") -> None:
    """
    Load a CSS file from disk and inject it into the Streamlit app.
    """
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"CSS file not found: {css_path}")


