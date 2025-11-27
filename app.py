import os

from dotenv import load_dotenv
import streamlit as st

from utils.helpers import load_css
from views.citizens import render_citizen_tab
from views.common import render_footer, render_header
from views.officials import render_officials_tab


def main() -> None:
    """Main entry point for the Civic Reach Streamlit app."""
    # Load environment variables
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")

    # Streamlit Page Config (must be called before any other Streamlit commands)
    st.set_page_config(
        page_title="Civic Reach",
        page_icon="assets/logo.png",
        layout="wide",
    )

    if not api_key:
        st.error("Error: GEMINI_API_KEY is not set in the .env file.")
        st.stop()

    # Global styles
    load_css()

    # Shared header (logo, title, security/reset)
    render_header()

    # Tabs for Different Personas
    tab_official_notice, tab_official_leaflet, tab_citizen = st.tabs(
        [
            "[Officials] Notice Audit",
            "[Officials] Leaflet Audit",
            "[Citizens] Doc Decipher",
        ]
    )
    with tab_official_notice:
        render_officials_tab("notice")
    with tab_official_leaflet:
        render_officials_tab("leaflet")
    with tab_citizen:
        render_citizen_tab()

    # Shared footer / disclaimer
    render_footer()


if __name__ == "__main__":
    main()