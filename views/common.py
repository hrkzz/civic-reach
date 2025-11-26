import streamlit as st

from utils.helpers import clear_session_data, img_to_base64


def render_header() -> None:
    """Render the main app header, logo, and security/reset controls."""
    col_title, col_controls = st.columns([0.7, 0.3], gap="medium", vertical_alignment="bottom")

    with col_title:
        logo_path = "assets/logo.png"
        logo_base64 = img_to_base64(logo_path)
        if logo_base64:
            st.markdown(
                f"""
                <div style="display: flex; align-items: center; gap: 15px;">
                    <img src="data:image/png;base64,{logo_base64}" style="width: 50px; height: auto; border-radius: 5px;">
                    <h1 style="margin: 0; padding: 0;">
                        <a href='.' target='_self' style='text-decoration: none; color: inherit;'>Civic Reach</a>
                    </h1>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<h1><a href='.' target='_self' style='text-decoration: none; color: inherit;'>Civic Reach</a></h1>",
                unsafe_allow_html=True,
            )

        st.markdown(
            """
            **Reducing Friction in Government Services** | Behavioural Science × Generative AI<br>
            Based on the OECD report *'Fixing Frictions: ‘Sludge audits’ around the world'*. Details of the methodology can be found [here](https://github.com/hrkzz/civic-reach/blob/main/methodology.md).
            """,
            unsafe_allow_html=True,
        )

    with col_controls:
        c_policy, c_reset = st.columns([1, 1], gap="small")

        with c_policy:
            with st.popover("🔐 Security", use_container_width=True):
                st.markdown("### Zero-Retention Policy")
                st.info(
                    """
                    **Stateless Architecture:**
                    * Data is processed in-memory (RAM) only.
                    * No data persists after session ends.
                    * **Enterprise Protection:** Inputs are NOT used for model training.
                    """
                )

        with c_reset:
            if st.button(
                "🗑️ Reset App",
                type="secondary",
                use_container_width=True,
                help="Wipe all data and restart session",
            ):
                clear_session_data()


def render_footer() -> None:
    """Render the global disclaimer/footer."""
    st.divider()
    st.markdown(
        """
        <div style="text-align: center; color: #666; font-size: 0.8rem;">
            <strong>Disclaimer:</strong> Generative AI can produce inaccurate information. 
            Please verify all generated outputs, especially critical dates and legal details, against the original official documents.
            <br>
            This tool is a prototype for the G7 GovAI Grand Challenge.
        </div>
        """,
        unsafe_allow_html=True,
    )


