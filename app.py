import os
import json
import re
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from PIL import Image
import io
import pypdf
from gtts import gTTS

# 1. Load Environment Variables
load_dotenv()
API_KEY = os.environ.get("GEMINI_API_KEY")

# 2. Page Configuration
st.set_page_config(
    page_title="Civic Reach",
    page_icon="🧭",
    layout="wide"
)

# 3. Initialize Client
if not API_KEY:
    st.error("Error: GEMINI_API_KEY is not set in the .env file.")
    st.stop()

client = genai.Client(api_key=API_KEY)

# --- CSS Styles ---
def apply_custom_styles():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif !important;
            color: #000000 !important;
        }
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 5rem !important;
        }
        /* Safety Badge Style */
        .safety-badge {
            background-color: #e8f5e9;
            border: 1px solid #4caf50;
            color: #2e7d32;
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 0.8rem;
            font-weight: bold;
            display: inline-flex;
            align-items: center;
            gap: 5px;
            margin-bottom: 10px;
        }
    </style>
    """, unsafe_allow_html=True)

# --- Data Structures (Pydantic) ---
# (変更なし)
class CostDetail(BaseModel):
    deduction: int = Field(..., description="Points deducted for this category (0-25).")
    comment: str = Field(..., description="Specific analysis and explanation of why these points were deducted.")

class EastSuggestions(BaseModel):
    easy: str = Field(..., description="Improvement suggestion based on 'Easy' (Simplify).")
    attractive: str = Field(..., description="Improvement suggestion based on 'Attractive' (Attention).")
    social: str = Field(..., description="Improvement suggestion based on 'Social' (Norms/Trust).")
    timely: str = Field(..., description="Improvement suggestion based on 'Timely' (Promptness).")

class SludgeAudit(BaseModel):
    total_score: int = Field(..., description="Total score out of 100 (100 minus sum of deductions).")
    overall_summary: str = Field(..., description="Brief summary of the document context.")
    evaluation_summary: str = Field(..., description="Overall assessment of the audit results.")
    improvement_summary: str = Field(..., description="Summary of recommended improvements.")
    key_details: str = Field(..., description="[CRITICAL] Exact extraction of factual information.")
    search_cost: CostDetail = Field(..., description="Evaluation of Search Cost.")
    decision_cost: CostDetail = Field(..., description="Evaluation of Decision Cost.")
    cognitive_cost: CostDetail = Field(..., description="Evaluation of Cognitive Cost.")
    emotional_cost: CostDetail = Field(..., description="Evaluation of Emotional Cost.")
    east_suggestions: EastSuggestions = Field(..., description="Detailed improvement suggestions based on the EAST framework.")

class CitizenGuide(BaseModel):
    sludge_observation: str = Field(..., description="Analysis of why this document is difficult (in the target language).")
    simple_summary: str = Field(..., description="A simple summary in the target language. Clearly state 'Who' needs to do 'What'.")
    action_guide_markdown: str = Field(..., description="Step-by-step action guide in Markdown (in the target language).")
    risks_and_penalties: list[str] = Field(..., description="★CRITICAL: List of warnings regarding disadvantages, penalties (in the target language).")
    required_documents: list[str] = Field(..., description="List of required documents (translated if necessary).")
    important_dates: list[str] = Field(..., description="List of important dates.")

# --- Utility Functions ---
def get_file_aspect_ratio(file_bytes, file_type):
    width = 0; height = 0
    try:
        if "pdf" in file_type:
            pdf_reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            if len(pdf_reader.pages) > 0:
                page = pdf_reader.pages[0]
                width = float(page.mediabox.width); height = float(page.mediabox.height)
        elif "image" in file_type:
            image = Image.open(io.BytesIO(file_bytes))
            width, height = image.size  
        if width > 0 and height > 0:
            ratio = width / height
            if ratio < 0.85: return "3:4"
            elif ratio > 1.15: return "4:3"
            else: return "1:1"
    except Exception: pass
    return "3:4"

# --- 追加機能: セッションクリア (Privacy Control) ---
def clear_session_data():
    """すべてのセッションデータを明示的に削除し、アプリをリセットする"""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    # Streamlitのキャッシュクリア（念のため）
    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()
    
# --- ★ Audio & Text Processing Functions ---

def clean_markdown(text):
    """Markdown記号を除去して読み上げやすくする"""
    if not text: return ""
    # 太字、見出し、リスト記号などを除去
    text = re.sub(r'[*#`_\[\]]', '', text) 
    text = re.sub(r'\n+', '. ', text) # 改行をピリオドとスペースに
    return text

def prepare_speech_script(data, mode="official"):
    """JSONデータから読み上げ用の全文スクリプトを作成する"""
    script = ""
    
    if mode == "official":
        script += f"Audit Report. Overall Score: {data['total_score']} out of 100. "
        script += f"Evaluation Summary: {clean_markdown(data['evaluation_summary'])}. "
        script += "Detailed Cost Analysis. "
        script += f"Search Cost: {clean_markdown(data['search_cost']['comment'])}. "
        script += f"Decision Cost: {clean_markdown(data['decision_cost']['comment'])}. "
        script += "Improvement Directions. "
        script += f"{clean_markdown(data['improvement_summary'])}. "
        
    elif mode == "citizen":
        # 修正: 英語の定型文を削除し、翻訳されたテキストだけを結合
        script += f"{clean_markdown(data['simple_summary'])}. "
        
        if data.get('risks_and_penalties'):
            for risk in data['risks_and_penalties']:
                script += f"{clean_markdown(risk)}. "
        
        script += f"{clean_markdown(data['action_guide_markdown'])}. "
        
        if data.get('required_documents'):
             script += ", ".join(data['required_documents']) + ". "
            
        if data.get('important_dates'):
             script += ", ".join(data['important_dates']) + ". "

    return script

def generate_audio_gtts(text, lang='en'):
    """Uses Google Text-to-Speech (gTTS) with language support"""
    try:
        if not text: return None
        # lang引数をgTTSに渡す
        tts = gTTS(text=text, lang=lang, slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except Exception as e:
        st.error(f"TTS Error: {e}")
        return None

# --- Analysis & Safety Functions (Unchanged) ---
def verify_safety(file_bytes, file_type, initial_json, model_schema):
    system_prompt = """
    You are a **Government Document Integrity Officer** and a **Safety Layer**.
    **STRICT VERIFICATION RULES:**
    1. **Numbers & Dates:** Check every monetary amount, deadline, and phone number.
    2. **No Invention:** If the extracted JSON contains details NOT found in the document, DELETE them.
    3. **Correction:** If a number is wrong, CORRECT it.
    4. **Structure:** Do not change the JSON keys.
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[types.Content(parts=[types.Part(text=f"Verify this JSON data against the document:\n{json.dumps(initial_json, ensure_ascii=False)}"), types.Part(inline_data=types.Blob(mime_type=file_type, data=file_bytes))])],
            config=types.GenerateContentConfig(system_instruction=system_prompt, response_mime_type="application/json", response_schema=model_schema, temperature=0.0)
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Verification Error: {e}")
        return initial_json

def analyze_sludge(file_bytes, file_type, doc_type="flyer", status_container=None):
    # バイアス対策: 公務員への改善提案自体が偏らないように指示を追加
    bias_instruction = """
    **BIAS & INCLUSION PROTOCOLS:**
    1. Check if the document uses gendered or exclusionary language.
    2. Ensure your 'Improvement Suggestions' strictly adhere to Inclusive Design principles.
    3. Recommendations must be culturally neutral and accessible to diverse populations.
    """
    
    prompt_notice = f"You are a Behavioral Scientist. Audit the provided Official Administrative Notice. {bias_instruction} Output in JSON."
    prompt_flyer = f"You are a Public Information Design Specialist. Audit the provided flyer. {bias_instruction} Output in JSON."
    
    system_prompt = prompt_notice if doc_type == "notice" else prompt_flyer
    try:
        if status_container: status_container.markdown("🔄 **Phase 1/2:** Executing Behavioral Science Analysis...")
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=[types.Content(parts=[types.Part(text="Strictly audit this document and output in JSON."), types.Part(inline_data=types.Blob(mime_type=file_type, data=file_bytes))])],
            config=types.GenerateContentConfig(system_instruction=system_prompt, response_mime_type="application/json", response_schema=SludgeAudit, temperature=0.0)
        )
        initial_result = json.loads(response.text)
        if status_container: status_container.markdown("🛡️ **Phase 2/2:** Verifying Risk Data (Amounts/Dates)...")
        return verify_safety(file_bytes, file_type, initial_result, SludgeAudit)
    except Exception as e:
        st.error(f"Analysis Error: {e}")
        return None

def analyze_citizen_doc(file_bytes, file_type, target_lang="English", status_container=None):
    # 修正: 言語を指定して翻訳・要約するようにプロンプトを変更
    system_prompt = f"""
    You are a High-Reliability AI Assistant. Analyze the provided government document.
    
    **TASK:** 1. Identify "Sludge" (frictions/difficulties).
    2. **Translate and Summarize the content into {target_lang}**.
    3. Extract Risks, Requirements, and Dates in **{target_lang}**.

    **MANDATORY BIAS & SAFETY PROTOCOLS:**
    1. **Inclusive Language:** Use gender-neutral terms suitable for {target_lang}.
    2. **Cultural Neutrality:** Avoid idioms specific to English. Use plain language (CEFR B1 level equivalent in {target_lang}).
    3. **Objectivity:** Present facts without judgmental adjectives.
    
    Output strictly in JSON using the defined schema.
    """
    try:
        if status_container: status_container.markdown(f"🔄 **Phase 1/2:** Analyzing & Translating to {target_lang}...")
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=[types.Content(parts=[types.Part(text="Perform a sludge audit and explain simply."), types.Part(inline_data=types.Blob(mime_type=file_type, data=file_bytes))])],
            config=types.GenerateContentConfig(system_instruction=system_prompt, response_mime_type="application/json", response_schema=CitizenGuide, temperature=0.0)
        )
        initial_result = json.loads(response.text)
        if status_container: status_container.markdown("🛡️ **Phase 2/2:** Self-Correcting Penalties & Deadlines...")
        return verify_safety(file_bytes, file_type, initial_result, CitizenGuide)
    except Exception as e:
        st.error(f"Analysis Error: {e}")
        return None

def generate_improved_image(summary, key_details, suggestions_list, aspect_ratio="3:4", doc_type="flyer"):
    formatted_suggestions = "\n".join([f"- {s}" for s in suggestions_list])
    
    # バイアス対策: 画像生成時に多様性を確保する指示を追加
    bias_prompt = "**DESIGN REQUIREMENT:** Ensure diverse representation in any human imagery. Use high-contrast colors for accessibility (WCAG AA compliance)."
    
    prompt_notice = f"""
    Generate a **DIGITAL BORN PDF DOCUMENT**. NO paper texture. Background: #FFFFFF.
    {bias_prompt}
    **⚠️ FOOTER:** "**※ AI-Generated Draft for Review Only**"
    CONTEXT: {summary}
    DETAILS: {key_details}
    IMPROVEMENTS: {formatted_suggestions}
    """
    prompt_flyer = f"""
    Create a **High-Quality Digital Graphic Design Asset**.
    {bias_prompt}
    **⚠️ FOOTER:** "**※ AI-Generated Draft Image**"
    CONTEXT: {summary}
    DETAILS: {key_details}
    IMPROVEMENTS: {formatted_suggestions}
    """
    target_prompt = prompt_notice if doc_type == "notice" else prompt_flyer
    try:
        response = client.models.generate_content(
            model="gemini-3-pro-image-preview", 
            contents=target_prompt,
            config=types.GenerateContentConfig(tools=[{"google_search": {}}], image_config=types.ImageConfig(aspect_ratio=aspect_ratio, image_size="2K"))
        )
        for part in response.parts:
            if part.inline_data:
                return Image.open(io.BytesIO(part.inline_data.data)), target_prompt
        return None, target_prompt
    except Exception as e:
        st.error(f"Image Generation Error: {e}")
        return None, target_prompt

# --- Component: Official Side ---
def render_tab_content(key_prefix):
    KEY_RESULT = f"{key_prefix}_audit_result"
    KEY_IMAGE = f"{key_prefix}_generated_image"
    KEY_PROMPT = f"{key_prefix}_last_prompt"
    KEY_UPLOADED_NAME = f"{key_prefix}_last_uploaded"
    KEY_ASPECT = f"{key_prefix}_target_aspect_ratio"
    KEY_AUDIO = f"{key_prefix}_audio_bytes" # 音声データ保持用

    if KEY_RESULT not in st.session_state: st.session_state[KEY_RESULT] = None
    if KEY_IMAGE not in st.session_state: st.session_state[KEY_IMAGE] = None
    if KEY_PROMPT not in st.session_state: st.session_state[KEY_PROMPT] = ""
    if KEY_UPLOADED_NAME not in st.session_state: st.session_state[KEY_UPLOADED_NAME] = None
    if KEY_AUDIO not in st.session_state: st.session_state[KEY_AUDIO] = None
    
    st.subheader("📂 1. Upload File / Run Analysis")
    has_result = st.session_state[KEY_RESULT] is not None
    with st.expander("Open/Close Panel", expanded=not has_result):
        uploaded_file = st.file_uploader("Drag & Drop or Select File", type=["pdf", "png", "jpg", "jpeg"], key=f"{key_prefix}_uploader", label_visibility="collapsed")
        if uploaded_file is not None:
            if st.session_state[KEY_UPLOADED_NAME] != uploaded_file.name:
                # リセット
                st.session_state[KEY_RESULT] = None
                st.session_state[KEY_IMAGE] = None
                st.session_state[KEY_AUDIO] = None
                st.session_state[KEY_UPLOADED_NAME] = uploaded_file.name
                file_bytes = uploaded_file.getvalue()
                st.session_state[KEY_ASPECT] = get_file_aspect_ratio(file_bytes, uploaded_file.type)
                st.rerun()

            if st.button("🚀 Run Analysis", type="primary", key=f"{key_prefix}_analyze_btn", use_container_width=True):
                status_box = st.empty()
                file_bytes = uploaded_file.getvalue(); file_type = uploaded_file.type
                result = analyze_sludge(file_bytes, file_type, doc_type=key_prefix, status_container=status_box)
                if result: 
                    status_box.empty()
                    st.session_state[KEY_RESULT] = result
                    st.session_state[KEY_IMAGE] = None
                    st.session_state[KEY_AUDIO] = None
                    st.rerun()

    if st.session_state[KEY_RESULT]:
        result = st.session_state[KEY_RESULT]
        st.subheader("📊 2. Audit Report")
        st.markdown('<div class="safety-badge">🛡️ Safety Protocol Verified</div> ', unsafe_allow_html=True)
        
        # --- ★ TTS Audio Section for Officials ---
        col_audio_btn, col_audio_player = st.columns([1, 3])
        with col_audio_btn:
            if st.button("🗣️ Read Full Report", key=f"{key_prefix}_tts_btn"):
                with st.spinner("Generating audio report..."):
                    script = prepare_speech_script(result, mode="official")
                    audio_data = generate_audio_gtts(script)
                    if audio_data:
                        st.session_state[KEY_AUDIO] = audio_data
        with col_audio_player:
            if st.session_state[KEY_AUDIO]:
                st.audio(st.session_state[KEY_AUDIO], format='audio/mp3')
        # ----------------------------------------

        with st.container(border=True):
            score = result.get("total_score", 0)
            c_score_main, c_score_sub = st.columns([1, 3], gap="large")
            with c_score_main: st.metric("Overall Score", f"{score}/100")
            with c_score_sub: st.write(""); st.write("Score Meter"); st.progress(score)
            st.divider()
            col_eval, col_improve = st.columns(2, gap="large")
            with col_eval:
                st.markdown("#### 🧐 Evaluation Summary")
                st.write(result.get("evaluation_summary"))
                with st.expander("▼ Detailed Evaluation", expanded=False):
                    st.write(f"**Search Cost:** {result.get('search_cost', {}).get('comment')}")
                    st.write(f"**Decision Cost:** {result.get('decision_cost', {}).get('comment')}")
            with col_improve:
                st.markdown("#### ✨ Improvement Direction")
                st.write(result.get("improvement_summary"))
                with st.expander("▼ EAST Suggestions", expanded=False):
                    st.write(f"**Easy:** {result.get('east_suggestions', {}).get('easy')}")
        
        st.markdown("""<div style="display: flex; align-items: center; justify-content: center; gap: 10px; padding: 20px; margin-top: 10px; margin-bottom: 10px;"><span style="font-size: 2rem;">⬇️</span><span style="color: #555; font-weight: bold; font-size: 1rem;">Create improved design based on this audit</span></div>""", unsafe_allow_html=True)

        col_settings, col_result = st.columns([1, 1], gap="medium")
        with col_settings:
            st.subheader("📝 3. Generation Settings")
            with st.form(f"{key_prefix}_generation_settings_form"):
                edited_summary = st.text_area("Context", value=result.get("overall_summary"), height=100)
                edited_key_details = st.text_area("Key Details", value=result.get("key_details"), height=200)
                edited_suggestions_text = st.text_area("Instructions", value=result.get("east_suggestions", {}).get('easy'), height=150)
                submitted = st.form_submit_button("📄 Generate Improved Document", type="secondary", use_container_width=True)
            if submitted:
                with st.spinner("Gemini 3 Pro is designing..."):
                    suggestions_list = [line.strip() for line in edited_suggestions_text.split('\n') if line.strip()]
                    image, used_prompt = generate_improved_image(edited_summary, edited_key_details, suggestions_list, aspect_ratio=st.session_state[KEY_ASPECT], doc_type=key_prefix)
                    if image: st.session_state[KEY_IMAGE] = image; st.session_state[KEY_PROMPT] = used_prompt; st.rerun()

        with col_result:
            st.subheader("📄 4. Improved Draft")
            if st.session_state[KEY_IMAGE]:
                st.image(st.session_state[KEY_IMAGE], caption="AI Generated Preview", use_container_width=True)
                buf = io.BytesIO(); st.session_state[KEY_IMAGE].save(buf, format="PNG")
                st.download_button("⬇️ Download Image", data=buf.getvalue(), file_name=f"improved_{key_prefix}.png", mime="image/png", key=f"{key_prefix}_dl_btn", use_container_width=True)

# --- Component: Citizen Side ---
def render_citizen_tab():
    key_prefix = "citizen"
    KEY_RESULT = f"{key_prefix}_result"
    KEY_UPLOADED_NAME = f"{key_prefix}_last_uploaded"
    KEY_AUDIO = f"{key_prefix}_audio_bytes"
    KEY_LANG = f"{key_prefix}_target_lang" # 言語保持用

    if KEY_RESULT not in st.session_state: st.session_state[KEY_RESULT] = None
    if KEY_UPLOADED_NAME not in st.session_state: st.session_state[KEY_UPLOADED_NAME] = None
    if KEY_AUDIO not in st.session_state: st.session_state[KEY_AUDIO] = None
    if KEY_LANG not in st.session_state: st.session_state[KEY_LANG] = "English"

    st.subheader("📂 1. Upload Document")
    
    # --- ★ 言語選択 UI (アクセシビリティ向上) ---
    c_upload_text, c_lang_select = st.columns([2, 1], vertical_alignment="bottom")
    with c_upload_text:
        st.markdown("Upload a difficult government document. The AI will analyze, verify, and explain it in your preferred language.")
    with c_lang_select:
        # 言語リスト
        lang_options = ["English", "French", "Spanish", "Japanese", "German", "Italian", "Portuguese"]
        # gTTS用言語コードマップ
        lang_code_map = {
            "English": "en", "French": "fr", "Spanish": "es", "Japanese": "ja",
            "German": "de", "Italian": "it", "Portuguese": "pt"
        }
        target_lang = st.selectbox("🗣️ Output Language", lang_options, index=0, key=f"{key_prefix}_lang_select")
        st.session_state[KEY_LANG] = target_lang
        selected_lang_code = lang_code_map[target_lang]

    has_result = st.session_state[KEY_RESULT] is not None
    with st.expander("Open/Close Panel", expanded=not has_result):
        uploaded_file = st.file_uploader("Drag & Drop or Select File", type=["pdf", "png", "jpg", "jpeg"], key=f"{key_prefix}_uploader", label_visibility="collapsed")
        if uploaded_file is not None:
            if st.session_state[KEY_UPLOADED_NAME] != uploaded_file.name:
                st.session_state[KEY_RESULT] = None
                st.session_state[KEY_AUDIO] = None
                st.session_state[KEY_UPLOADED_NAME] = uploaded_file.name
                file_bytes = uploaded_file.getvalue()
                st.rerun()

            if st.button("🔍 Decipher Document", type="primary", key=f"{key_prefix}_analyze_btn", use_container_width=True):
                status_box = st.empty()
                file_bytes = uploaded_file.getvalue(); file_type = uploaded_file.type
                # 引数に target_lang を渡す
                result = analyze_citizen_doc(file_bytes, file_type, target_lang=st.session_state[KEY_LANG], status_container=status_box)
                if result: 
                    status_box.empty()
                    st.session_state[KEY_RESULT] = result
                    st.session_state[KEY_AUDIO] = None
                    st.rerun()

    if st.session_state[KEY_RESULT]:
        result = st.session_state[KEY_RESULT]
        
        st.subheader("📝 2. Document Guide")
        st.markdown(f'<div class="safety-badge">🛡️ Safety Protocol Verified ({st.session_state[KEY_LANG]})</div> ', unsafe_allow_html=True)
        
        with st.expander("🔍 Why is this document confusing? (AI Analysis)", expanded=False):
            st.write(result.get("sludge_observation"))

        # --- ★ TTS Audio Section for Citizens (Multilingual) ---
        col_audio_btn, col_audio_player = st.columns([1, 3])
        with col_audio_btn:
            if st.button("🗣️ Listen to Guide", key=f"{key_prefix}_tts_btn"):
                with st.spinner("Creating audio guide..."):
                    script = prepare_speech_script(result, mode="citizen")
                    # 言語コードを指定して音声を生成
                    audio_data = generate_audio_gtts(script, lang=selected_lang_code)
                    if audio_data:
                        st.session_state[KEY_AUDIO] = audio_data
        with col_audio_player:
            if st.session_state[KEY_AUDIO]:
                st.audio(st.session_state[KEY_AUDIO], format='audio/mp3')
        # ---------------------------------------------------

        with st.container(border=True):
            st.markdown("### 💡 Summary: What does it mean?")
            st.info(result.get("simple_summary"), icon="💁")

            if result.get("risks_and_penalties"):
                st.markdown("### ⚠️ What happens if I ignore this? (Risks & Penalties)")
                for risk in result.get("risks_and_penalties", []): st.error(risk, icon="🚨")
            st.divider()
            st.markdown("### ✅ Your Action Guide")
            with st.container(border=True): st.markdown(result.get("action_guide_markdown"))
            st.divider()
            c1, c2 = st.columns(2, gap="large")
            with c1:
                st.markdown("### 📄 Required Documents")
                if result.get("required_documents"):
                    for doc in result.get("required_documents", []): st.write(f"- {doc}")
                else: st.write("None explicitly stated.")
            with c2:
                st.markdown("### 📅 Important Dates")
                if result.get("important_dates"):
                    for date in result.get("important_dates", []): st.warning(f"🗓️ {date}")
                else: st.write("None explicitly stated.")
            
        with st.container(border=True):
            st.subheader("📢 Report 'Sludge' to the Agency")
            with st.form(key=f"{key_prefix}_feedback_form"):
                default_feedback = f"[Citizen Feedback - {st.session_state[KEY_LANG]}]\nIssues: {result.get('sludge_observation')}\n\nRequest: Please simplify."
                feedback_text = st.text_area("Message to Send", value=default_feedback, height=150)
                submit_feedback = st.form_submit_button("📨 Send Improvement Request", type="primary", use_container_width=True)
            if submit_feedback: st.success("✅ Sent!"); st.balloons()

# --- Main App ---
def main():
    apply_custom_styles()

    col_title, col_controls = st.columns([0.7, 0.3], gap="medium", vertical_alignment="bottom")

    with col_title:
        st.title("Civic Reach")
        st.markdown("""
            **Identifying 'Sludge' in government services** | Behavioral Science × Generative AI

            Based on the OECD report *'Fixing Frictions: ‘Sludge audits’ around the world'*. Details of the methodology can be found [here](https://github.com/hrkzz/civic-reach/blob/main/methodology.md).
            """)

    with col_controls:
        # コントロールエリア内をさらに左右に分割してボタンを並べる
        c_policy, c_reset = st.columns([1, 1], gap="small")
        
        with c_policy:
            # Expanderの代わりに Popover を使用 (見た目がボタンになりスッキリする)
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
                st.caption("Status: ● System Active")

        with c_reset:
            # "Reset" ボタン: 赤色は維持しつつ、ラベルを短くして圧迫感を減らす
            if st.button("🗑️ Reset App", type="primary", use_container_width=True, help="Wipe all data and restart session"):
                clear_session_data()
        
    tab_official_notice, tab_official_flyer, tab_citizen = st.tabs(["【Officials】 Notice Audit", "【Officials】 Flyer Audit", "【Citizens】 Doc Decipher"])
    with tab_official_notice: render_tab_content("notice")
    with tab_official_flyer: render_tab_content("flyer")
    with tab_citizen: render_citizen_tab()

if __name__ == "__main__":
    main()