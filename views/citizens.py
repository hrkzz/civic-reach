import streamlit as st

from services.gemini import analyze_citizen_doc, generate_user_draft
from services.tts import generate_audio_gtts
from utils.helpers import clean_markdown


def render_citizen_tab() -> None:
    """
    Renders the 'Citizen' persona tab.
    Focuses on simplified explanation, risk highlighting, and action drafting.
    """
    key_prefix = "citizen"
    KEY_RESULT = f"{key_prefix}_result"
    KEY_UPLOADED_NAME = f"{key_prefix}_last_uploaded"
    KEY_AUDIO_GUIDE = f"{key_prefix}_audio_guide"
    KEY_AUDIO_ACTION = f"{key_prefix}_audio_action"
    KEY_LANG = f"{key_prefix}_target_lang"
    KEY_DRAFT = f"{key_prefix}_draft_text"

    if KEY_RESULT not in st.session_state:
        st.session_state[KEY_RESULT] = None
    if KEY_UPLOADED_NAME not in st.session_state:
        st.session_state[KEY_UPLOADED_NAME] = None
    if KEY_AUDIO_GUIDE not in st.session_state:
        st.session_state[KEY_AUDIO_GUIDE] = None
    if KEY_AUDIO_ACTION not in st.session_state:
        st.session_state[KEY_AUDIO_ACTION] = None
    if KEY_LANG not in st.session_state:
        st.session_state[KEY_LANG] = "English"
    if KEY_DRAFT not in st.session_state:
        st.session_state[KEY_DRAFT] = None

    # Header & Language
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
        current_tld = "co.uk" if selected_lang_code == "en" else "com"

    has_result = st.session_state[KEY_RESULT] is not None

    with st.expander("Open/Close Panel", expanded=not has_result):
        uploaded_file = st.file_uploader(
            "Upload File",
            type=["pdf", "png", "jpg", "jpeg"],
            key=f"{key_prefix}_uploader",
            label_visibility="collapsed",
        )

        if uploaded_file is not None:
            if st.session_state[KEY_UPLOADED_NAME] != uploaded_file.name:
                st.session_state[KEY_RESULT] = None
                st.session_state[KEY_AUDIO_GUIDE] = None
                st.session_state[KEY_AUDIO_ACTION] = None
                st.session_state[KEY_DRAFT] = None
                st.session_state[KEY_UPLOADED_NAME] = uploaded_file.name
                st.rerun()

            if st.button(
                "🔍 Run Analysis",
                type="secondary",
                key=f"{key_prefix}_analyze_btn",
                use_container_width=True,
            ):
                status_box = st.empty()
                file_bytes = uploaded_file.getvalue()
                file_type = uploaded_file.type
                try:
                    result = analyze_citizen_doc(
                        file_bytes,
                        file_type,
                        target_lang=st.session_state[KEY_LANG],
                        status_container=status_box,
                    )
                except Exception as e:
                    status_box.empty()
                    st.error(str(e))
                    result = None

                if result:
                    status_box.empty()
                    st.session_state[KEY_RESULT] = result
                    st.rerun()

    if st.session_state[KEY_RESULT]:
        result = st.session_state[KEY_RESULT]

        st.markdown("#### 📝 2. Document Guide")
        st.markdown(
            f'<div class="safety-badge">🛡️ Safety Protocol Verified ({st.session_state[KEY_LANG]})</div> ',
            unsafe_allow_html=True,
        )

        # Guide Content (Summary, Risks, Dates)
        with st.container(border=True):
            # Audio Player for Guide
            c_audio_btn, c_audio_player = st.columns([1, 2])
            with c_audio_btn:
                if st.button(
                    "🗣️ Listen to Guide",
                    key=f"{key_prefix}_guide_tts_btn",
                    use_container_width=True,
                ):
                    with st.spinner("Generating audio..."):
                        script = f"Summary. {clean_markdown(result.get('simple_summary'))}. "
                        if result.get("risks_and_penalties"):
                            script += "Risks and Penalties. "
                            for r in result["risks_and_penalties"]:
                                script += f"{clean_markdown(r)}. "
                        if result.get("required_documents"):
                            script += "Required Documents. "
                            for d in result["required_documents"]:
                                script += f"{clean_markdown(d)}. "
                        if result.get("important_dates"):
                            script += "Important Dates. "
                            for d in result["important_dates"]:
                                script += f"{clean_markdown(d)}. "

                        audio_data = generate_audio_gtts(
                            script, lang=selected_lang_code, tld=current_tld
                        )
                        if audio_data:
                            st.session_state[KEY_AUDIO_GUIDE] = audio_data
                        else:
                            st.error("Failed to generate audio.")
            with c_audio_player:
                if st.session_state[KEY_AUDIO_GUIDE]:
                    st.audio(st.session_state[KEY_AUDIO_GUIDE], format="audio/mp3")

            # Summary
            st.markdown("#### 💡 Summary: What does it mean?")
            summary_text = result.get("simple_summary", "")
            if summary_text:
                summary_text = summary_text.replace("$", "\\$")
            st.markdown(summary_text)

            # Risks
            if result.get("risks_and_penalties"):
                st.markdown("#### ⚠️ Risks & Penalties")
                risk_md = ""
                for risk in result.get("risks_and_penalties", []):
                    safe_risk = risk.replace("$", "\\$")
                    risk_md += f"- {safe_risk}\n"
                st.markdown(risk_md)

            st.markdown(
                '<hr style="margin-top: 0.5rem; margin-bottom: 0.5rem; border: 0; border-top: 1px solid #eee;" />',
                unsafe_allow_html=True,
            )

            # Docs & Dates
            c1, c2 = st.columns(2, gap="large")
            with c1:
                st.markdown("#### 📄 Required Documents")
                if result.get("required_documents"):
                    req_md = ""
                    for doc in result.get("required_documents", []):
                        safe_doc = doc.replace("$", "\\$")
                        req_md += f"- {safe_doc}\n"
                    st.markdown(req_md)
                else:
                    st.write("None explicitly stated.")
            with c2:
                st.markdown("#### 📅 Important Dates")
                if result.get("important_dates"):
                    date_md = ""
                    for date in result.get("important_dates", []):
                        safe_date = date.replace("$", "\\$")
                        date_md += f"- {safe_date}\n"
                    st.markdown(date_md)
                else:
                    st.write("None explicitly stated.")

        # Action Section
        st.divider()
        st.markdown("#### 🚀 3. Take Action")

        with st.container(border=True):
            c_act_btn, c_act_player = st.columns([1, 2])
            with c_act_btn:
                if st.button(
                    "🗣️ Listen to Steps",
                    key=f"{key_prefix}_action_tts_btn",
                    use_container_width=True,
                ):
                    with st.spinner("Generating audio..."):
                        script = (
                            "Here are the steps to take. "
                            f"{clean_markdown(result.get('action_guide_markdown'))}"
                        )
                        audio_data = generate_audio_gtts(
                            script, lang=selected_lang_code, tld=current_tld
                        )
                        if audio_data:
                            st.session_state[KEY_AUDIO_GUIDE] = audio_data
                        else:
                            st.error("Failed to generate audio.")

            with c_act_player:
                if st.session_state[KEY_AUDIO_ACTION]:
                    st.audio(st.session_state[KEY_AUDIO_ACTION], format="audio/mp3")

            st.markdown("Based on the document, here is what you need to do.")
            st.markdown(result.get("action_guide_markdown"))

        # Draft Wizard
        st.markdown("#### ✍️ 4. Draft Wizard")
        st.markdown("Answer these simple questions, and AI will write the formal text for you.")

        # Dynamic form
        with st.container(border=True):
            user_answers: dict[str, str] = {}
            with st.form(key="action_wizard_form"):
                questions = result.get("missing_info_questions", [])
                if not questions:
                    questions = [
                        "What is your full name?",
                        "What is your reference number?",
                    ]  # Fallback

                col_q1, col_q2 = st.columns(2)
                for i, q in enumerate(questions):
                    target_col = col_q1 if i % 2 == 0 else col_q2
                    user_answers[q] = target_col.text_input(
                        f"❓ {q}", key=f"q_{i}"
                    )

                submitted = st.form_submit_button(
                    "✨ Generate Draft", type="primary", use_container_width=True
                )

            if submitted:
                with st.spinner("AI is writing for you..."):
                    draft_text = generate_user_draft(
                        result.get("simple_summary"),
                        user_answers,
                        target_lang=st.session_state[KEY_LANG],
                    )
                    st.session_state[KEY_DRAFT] = draft_text

            if st.session_state[KEY_DRAFT]:
                st.success("Draft created! Copy and paste below.")
                st.text_area(
                    "📄 Final Draft", value=st.session_state[KEY_DRAFT], height=300
                )
                st.caption("⚠️ Please review the draft before sending.")

        st.divider()

        # Why is this confusing? (Sludge Analysis)
        with st.container(border=True):
            st.markdown("##### Why is this document confusing? (AI Analysis)")
            st.markdown(result.get("sludge_observation"))

            with st.expander(
                "📢 Report 'Sludge' to the Agency (Click to expand)", expanded=False
            ):
                with st.form(key=f"{key_prefix}_feedback_form"):
                    default_feedback = (
                        f"[Citizen Feedback - {st.session_state[KEY_LANG]}]\n"
                        f"Issues: {result.get('sludge_observation')}\n\n"
                        "Request: Please simplify."
                    )
                    st.text_area(
                        "Message to Send", value=default_feedback, height=150
                    )
                    if st.form_submit_button("📨 Send Improvement Request"):
                        st.success("✅ Sent!")
                        st.balloons()


