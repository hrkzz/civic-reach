import io

import streamlit as st

from services.gemini import analyze_sludge, generate_improved_image
from services.tts import generate_audio_gtts, prepare_speech_script
from utils.file_processing import get_file_aspect_ratio
from utils.helpers import parse_integrated_details


def render_officials_tab(doc_type: str) -> None:
    """
    Renders the 'Official' persona tab (Notice/Leaflet Audit).
    Features a dashboard for Sludge scores and an image generator for improvements.
    """
    key_prefix = doc_type

    # Session State Management
    KEY_RESULT = f"{key_prefix}_audit_result"
    KEY_IMAGE = f"{key_prefix}_generated_image"
    KEY_PROMPT = f"{key_prefix}_last_prompt"
    KEY_UPLOADED_NAME = f"{key_prefix}_last_uploaded"
    KEY_ASPECT = f"{key_prefix}_target_aspect_ratio"
    KEY_AUDIO = f"{key_prefix}_audio_bytes"
    KEY_LANG = f"{key_prefix}_target_lang"

    if KEY_RESULT not in st.session_state:
        st.session_state[KEY_RESULT] = None
    if KEY_IMAGE not in st.session_state:
        st.session_state[KEY_IMAGE] = None
    if KEY_PROMPT not in st.session_state:
        st.session_state[KEY_PROMPT] = ""
    if KEY_UPLOADED_NAME not in st.session_state:
        st.session_state[KEY_UPLOADED_NAME] = None
    if KEY_AUDIO not in st.session_state:
        st.session_state[KEY_AUDIO] = None
    if KEY_LANG not in st.session_state:
        st.session_state[KEY_LANG] = "English"

    # Header & Language Selection
    c_header, c_lang = st.columns([3, 1], vertical_alignment="bottom")
    with c_header:
        st.markdown("#### 📂 1. Upload File / Run Analysis")
    with c_lang:
        lang_options = [
            "English",
            "French",
            "Spanish",
            "Japanese",
            "German",
            "Italian",
            "Portuguese",
        ]
        lang_code_map = {
            "English": "en",
            "French": "fr",
            "Spanish": "es",
            "Japanese": "ja",
            "German": "de",
            "Italian": "it",
            "Portuguese": "pt",
        }
        target_lang = st.selectbox(
            "Analysis Language",
            lang_options,
            index=0,
            key=f"{key_prefix}_lang_select",
            label_visibility="collapsed",
            format_func=lambda x: f"🌐 {x}",
        )
        st.session_state[KEY_LANG] = target_lang
        selected_lang_code = lang_code_map[target_lang]

    has_result = st.session_state[KEY_RESULT] is not None

    # Upload & Action Panel
    with st.expander("Open/Close Panel", expanded=not has_result):
        # File Uploader
        uploaded_file = st.file_uploader(
            "Upload File",
            type=["pdf", "png", "jpg", "jpeg"],
            key=f"{key_prefix}_uploader",
            label_visibility="collapsed",
        )

        if uploaded_file is not None:
            if st.session_state[KEY_UPLOADED_NAME] != uploaded_file.name:
                st.session_state[KEY_RESULT] = None
                st.session_state[KEY_IMAGE] = None
                st.session_state[KEY_AUDIO] = None
                st.session_state[KEY_UPLOADED_NAME] = uploaded_file.name
                file_bytes = uploaded_file.getvalue()
                st.session_state[KEY_ASPECT] = get_file_aspect_ratio(
                    file_bytes, uploaded_file.type
                )
                st.rerun()

            if st.button(
                "🚀 Run Analysis",
                type="secondary",
                key=f"{key_prefix}_analyze_btn",
                width="stretch",
            ):
                status_box = st.empty()
                file_bytes = uploaded_file.getvalue()
                file_type = uploaded_file.type
                try:
                    result = analyze_sludge(
                        file_bytes,
                        file_type,
                        target_lang=st.session_state[KEY_LANG],
                        doc_type=key_prefix,
                        status_container=status_box,
                    )
                except Exception as e:
                    status_box.empty()
                    st.error(str(e))
                    result = None

                if result:
                    status_box.empty()
                    st.session_state[KEY_RESULT] = result
                    st.session_state[KEY_IMAGE] = None
                    st.session_state[KEY_AUDIO] = None
                    st.rerun()

    # Results Display
    if st.session_state[KEY_RESULT]:
        result = st.session_state[KEY_RESULT]
        st.markdown("#### 📊 2. Audit Report")
        st.markdown(
            f'<div class="safety-badge">🛡️ Safety Protocol Verified ({st.session_state[KEY_LANG]})</div> ',
            unsafe_allow_html=True,
        )

        # Dashboard Container
        with st.container(border=True):
            # Audio Controls
            c_audio_btn, c_audio_player = st.columns([1, 2], vertical_alignment="center")
            with c_audio_btn:
                if st.button(
                    "🗣️ Read Report",
                    key=f"{key_prefix}_tts_btn",
                    width="stretch",
                ):
                    with st.spinner("Generating audio report..."):
                        script = prepare_speech_script(result, mode="official")
                        tld_param = "co.uk" if selected_lang_code == "en" else "com"
                        audio_data = generate_audio_gtts(
                            script, lang=selected_lang_code, tld=tld_param
                        )
                        if audio_data:
                            st.session_state[KEY_AUDIO] = audio_data
                        else:
                            st.error("Failed to generate audio.")
            with c_audio_player:
                if st.session_state[KEY_AUDIO]:
                    st.audio(st.session_state[KEY_AUDIO], format="audio/mp3")

            # Score Calculations & Display
            s_deduction = result.get("search_cost", {}).get("deduction", 0)
            s_score = 25 - s_deduction
            d_deduction = result.get("decision_cost", {}).get("deduction", 0)
            d_score = 25 - d_deduction
            c_deduction = result.get("cognitive_cost", {}).get("deduction", 0)
            c_score = 25 - c_deduction
            e_deduction = result.get("emotional_cost", {}).get("deduction", 0)
            e_score = 25 - e_deduction
            total_score = result.get("total_score", 0)

            col_main, col_breakdown = st.columns(
                [1.5, 3], gap="large", vertical_alignment="center"
            )

            with col_main:
                st.metric("Audit Score", f"{total_score}/100")
            with col_breakdown:
                b1, b2, b3, b4 = st.columns(4)
                with b1:
                    st.metric("🔍 Search", f"{s_score}/25")
                with b2:
                    st.metric("🤔 Decision", f"{d_score}/25")
                with b3:
                    st.metric("🧠 Cognitive", f"{c_score}/25")
                with b4:
                    st.metric("😫 Emotional", f"{e_score}/25")

            st.markdown(
                '<hr style="margin-top: 0.5rem; margin-bottom: 0.5rem; border: 0; border-top: 1px solid #eee;" />',
                unsafe_allow_html=True,
            )

            # Textual Analysis
            col_text_1, col_text_2 = st.columns(2, gap="large")
            with col_text_1:
                st.markdown("#### 🧐 Evaluation Summary")
                st.write(result.get("evaluation_summary"))
            with col_text_2:
                st.markdown("#### ✨ Improvement Direction")
                st.write(result.get("improvement_summary"))

            # Expanders aligned in a new row
            col_exp_1, col_exp_2 = st.columns(2, gap="large")
            with col_exp_1:
                with st.expander("▼ Detailed Evaluation (4 Sludge Scores)", expanded=False):
                    st.write(f"**🔍 Search:** {result.get('search_cost', {}).get('comment')}")
                    st.write(f"**🤔 Decision:** {result.get('decision_cost', {}).get('comment')}")
                    st.write(
                        f"**🧠 Cognitive:** {result.get('cognitive_cost', {}).get('comment')}"
                    )
                    st.write(
                        f"**😫 Emotional:** {result.get('emotional_cost', {}).get('comment')}"
                    )
            with col_exp_2:
                with st.expander("▼ EAST Suggestions", expanded=False):
                    east = result.get("east_suggestions", {})
                    st.write(f"**😌 Easy:** {east.get('easy')}")
                    st.write(f"**✨ Attractive:** {east.get('attractive')}")
                    st.write(f"**🗣️ Social:** {east.get('social')}")
                    st.write(f"**⏱️ Timely:** {east.get('timely')}")

        # Generation Section
        st.markdown(
            """
            <div style="display: flex; align-items: center; justify-content: center; gap: 10px; padding: 20px; margin-top: 10px; margin-bottom: 10px;">
                <span style="font-size: 2rem;">⬇️</span>
                <span style="color: #555; font-weight: bold; font-size: 1rem;">Create improved design based on this audit</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_settings, col_result = st.columns([1, 1], gap="medium")
        with col_settings:
            st.markdown("#### 📝 3. Generation Settings")
            with st.form(f"{key_prefix}_generation_settings_form"):
                edited_summary = st.text_area(
                    "Context", value=result.get("overall_summary"), height=150
                )

                formatted_text_lines: list[str] = []
                extracted_sender = result.get("sender_details")
                if extracted_sender and "Not Found" not in extracted_sender:
                    formatted_text_lines.append(
                        f"SENDER: {extracted_sender.replace(chr(10), ', ')}"
                    )
                extracted_recipient = result.get("recipient_details")
                if extracted_recipient and "Not Found" not in extracted_recipient:
                    formatted_text_lines.append(
                        f"RECIPIENT: {extracted_recipient.replace(chr(10), ', ')}"
                    )
                if formatted_text_lines:
                    formatted_text_lines.append("")

                key_details_data = result.get("key_details", [])
                if isinstance(key_details_data, list):
                    for item in key_details_data:
                        label = ""
                        value = ""
                        if hasattr(item, "label"):
                            label = item.label
                            value = item.value
                        elif isinstance(item, dict):
                            label = item.get("label", "Info")
                            value = item.get("value", "")
                        formatted_text_lines.append(f"{label}: {value}")
                elif isinstance(key_details_data, str):
                    formatted_text_lines.append(key_details_data)

                default_text_value = "\n".join(formatted_text_lines)

                edited_key_details_text = st.text_area(
                    "Key Details (Edit Text)",
                    value=default_text_value,
                    height=350,
                    help="Simply edit the text lines. format is 'Label: Value'.",
                )
                east = result.get("east_suggestions", {})
                combined_suggestions = (
                    f"- Easy: {east.get('easy', '')}\n"
                    f"- Attractive: {east.get('attractive', '')}\n"
                    f"- Social: {east.get('social', '')}\n"
                    f"- Timely: {east.get('timely', '')}"
                )
                edited_suggestions_text = st.text_area(
                    "Instructions (EAST Framework)", value=combined_suggestions, height=250
                )
                submitted = st.form_submit_button(
                    "📄 Generate Improved Document",
                    type="secondary",
                    width="stretch",
                )

            if submitted:
                with st.spinner("AI is designing..."):
                    parsed_sender, parsed_recipient, parsed_details = parse_integrated_details(
                        edited_key_details_text
                    )
                    suggestions_list = [
                        line.strip() for line in edited_suggestions_text.split("\n") if line.strip()
                    ]
                    try:
                        image, used_prompt = generate_improved_image(
                            edited_summary,
                            parsed_details,
                            suggestions_list,
                            sender_info=parsed_sender,
                            recipient_info=parsed_recipient,
                            aspect_ratio=st.session_state[KEY_ASPECT],
                            doc_type=key_prefix,
                        )
                    except Exception as e:
                        st.error(str(e))
                        image, used_prompt = None, ""

                    if image:
                        st.session_state[KEY_IMAGE] = image
                        st.session_state[KEY_PROMPT] = used_prompt
                        st.rerun()

        with col_result:
            st.markdown("#### 📄 4. Improved Draft")
            if st.session_state[KEY_IMAGE]:
                st.image(
                    st.session_state[KEY_IMAGE],
                    caption="AI Generated Preview",
                    width="stretch",
                )
                buf = io.BytesIO()
                st.session_state[KEY_IMAGE].save(buf, format="PNG")
                st.download_button(
                    "⬇️ Download Image",
                    data=buf.getvalue(),
                    file_name=f"improved_{key_prefix}.png",
                    mime="image/png",
                    key=f"{key_prefix}_dl_btn",
                    width="stretch",
                )
                st.write("")
                st.caption(
                    "💡 To refine the result, adjust details in 3. Generation Settings and regenerate."
                )


