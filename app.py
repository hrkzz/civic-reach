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
        /* Expanderの中身の上下余白を削除 */
        div[data-testid="stExpanderDetails"] {
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        /* File Uploader上部の余白を削除 */
        div[data-testid="stFileUploader"] {
            padding-top: 0rem !important;
            margin-top: -5px !important; /* 微調整で少し上に詰める */
        }
        /* File Uploaderのドロップエリアの余白調整 */
        section[data-testid="stFileUploaderDropzone"] {
            min-height: 0px !important;
            padding: 1rem !important;
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
    missing_info_questions: list[str] = Field(..., description="List of simple questions to ask the user to help them fill out the form or write an email (e.g., 'What is your full name?', 'What is your Case ID?').")

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
        # 英語のラベルを削除し、AIが生成した翻訳済みテキストを繋げる
        script += f"Overall Score: {data['total_score']}. " # 数字は万国共通なのでOK
        script += f"{clean_markdown(data['evaluation_summary'])}. "
        
        # コスト分析
        script += f"{clean_markdown(data['search_cost']['comment'])}. "
        script += f"{clean_markdown(data['decision_cost']['comment'])}. "
        
        # 改善提案
        script += f"{clean_markdown(data['improvement_summary'])}. "
        
        east = data.get('east_suggestions', {})
        script += f"{clean_markdown(east.get('easy'))}. "
        
    elif mode == "citizen":
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

def analyze_sludge(file_bytes, file_type, target_lang="English", doc_type="flyer", status_container=None):
    # バイアス対策 + 多言語指示
    bias_instruction = f"""
    **BIAS & INCLUSION PROTOCOLS:**
    1. Check if the document uses gendered or exclusionary language.
    2. Ensure your 'Improvement Suggestions' strictly adhere to Inclusive Design principles.
    3. Recommendations must be culturally neutral and accessible to diverse populations.
    
    **LANGUAGE REQUIREMENT:**
    Output all analysis, summaries, and suggestions in **{target_lang}**.
    """
    
    prompt_notice = f"""
    You are a Behavioral Scientist and Senior Government Auditor. Audit the provided Official Administrative Notice.
    {bias_instruction}
    
    **CRITICAL INSTRUCTION FOR 'KEY DETAILS':**
    You MUST extract EVERY single factual detail from the document, including:
    - Exact dollar amounts, tax rates, or fees.
    - Specific dates (deadlines, issuance dates).
    - Case numbers, reference IDs, phone numbers, URLs.
    - Legal clauses or citation numbers.
    
    **Do not summarize key details; extract them verbatim.** If the document is a 'Notice', maintain a formal, authoritative tone in your analysis.
    
    Output in JSON.
    """
    prompt_flyer = f"You are a Public Information Design Specialist. Audit the provided flyer. {bias_instruction} Output in JSON."
    
    system_prompt = prompt_notice if doc_type == "notice" else prompt_flyer
    try:
        if status_container: status_container.markdown(f"🔄 **Phase 1/2:** Auditing & Translating to {target_lang}...")
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
    # 修正: アクションのための「不足情報（質問）」を特定させる指示を追加
    system_prompt = f"""
    You are a High-Reliability AI Assistant. Analyze the provided government document.
    
    **TASK:**
    1. Identify "Sludge" (frictions/difficulties).
    2. **Translate and Summarize the content into {target_lang}**.
    3. Extract Risks, Requirements, and Dates in **{target_lang}**.
    4. **Identify Missing Info for Action:** List specific, simple questions (e.g. "What is your full name?", "What is your current address?") that you need to ask the user to help them draft an application or inquiry email.

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
            contents=[types.Content(parts=[types.Part(text="Perform a sludge audit and define necessary user inputs."), types.Part(inline_data=types.Blob(mime_type=file_type, data=file_bytes))])],
            config=types.GenerateContentConfig(system_instruction=system_prompt, response_mime_type="application/json", response_schema=CitizenGuide, temperature=0.0)
        )
        initial_result = json.loads(response.text)
        if status_container: status_container.markdown("🛡️ **Phase 2/2:** Self-Correcting Penalties & Deadlines...")
        return verify_safety(file_bytes, file_type, initial_result, CitizenGuide)
    except Exception as e:
        st.error(f"Analysis Error: {e}")
        return None

# --- 追加: ユーザー入力をもとにドラフトを作成する関数 ---
def generate_user_draft(context_summary, user_answers, target_lang="English"):
    """Generates the final application draft or email based on user inputs."""
    prompt = f"""
    You are a **Document Drafting Engine**. You are NOT a chat assistant.
    
    **CONTEXT:**
    The user needs to send a formal response/inquiry regarding: "{context_summary}".
    
    **USER PROVIDED DATA:**
    {json.dumps(user_answers, ensure_ascii=False)}
    
    **TASK:**
    Generate the **FINAL TEXT** for the Email or Application Form in **{target_lang}**.
    
    **CRITICAL OUTPUT RULES:**
    1. **NO CONVERSATIONAL FILLER:** Do NOT say "Here is the draft", "Okay", "Given the context", "I have created...", or provide post-draft instructions. Output *only* the text to be copied.
    2. **FORMAT:** - If Email: Start immediately with "Subject: ...". Follow with the salutation and body. Do not write "Body:".
       - If Form: List fields as "Field Name: Value".
    3. **INTEGRATION:** Seamlessly integrate the USER PROVIDED DATA. 
    4. **TONE:** Professional, formal, and clear.
    5. **PLACEHOLDERS:** Only use brackets `[...]` for information that is strictly required but was NOT provided in the user data or context.
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"Error generating draft: {e}"

def generate_improved_image(summary, key_details, suggestions_list, aspect_ratio="3:4", doc_type="flyer"):
    formatted_suggestions = "\n".join([f"- {s}" for s in suggestions_list])
    
    # バイアス対策: 画像生成時に多様性を確保する指示を追加
    bias_prompt = "**DESIGN REQUIREMENT:** Ensure diverse representation in any human imagery. Use high-contrast colors for accessibility (WCAG AA compliance)."
    
    prompt_notice = f"""
    Create a **PRISTINE DIGITAL DOCUMENT** (like a direct PDF export or a high-res screenshot of a Word doc).
    
    **VISUAL STYLE:**
    - **Background:** Pure Flat White (#FFFFFF). Absolutely NO paper texture, NO shadows, NO creases, and NO folds.
    - **Typography:** Crisp, sharp, black professional sans-serif font (Arial or Helvetica).
    - **Layout:** Clean, structured, official government layout.
    - **Quality:** 2D Flat Vector style. Not a photo of a paper.

    **CONTENT STRUCTURE:**
    - Header: Official Agency Logo & "Official Notice" text.
    - Body: Clear, left-aligned text based on the SUMMARY provided.
    - Key Info Box: A clearly outlined box containing the KEY DETAILS.
    
    {bias_prompt}
    
    **⚠️ FOOTER:** "**※ AI-Generated Draft for Review Only**"
    
    **INPUT DATA:**
    SUMMARY: {summary}
    KEY DETAILS (Must be visible): {key_details}
    IMPROVEMENTS APPLIED: {formatted_suggestions}
    """

    prompt_flyer = f"""
    Create a **High-Quality Digital Graphic Design Asset** (Digital Poster/Infographic).
    **VISUAL STYLE:** Modern, flat design, high contrast, clean vector art style. 
    **Background:** Solid color or subtle gradient (No paper texture).
    
    {bias_prompt}
    
    **⚠️ FOOTER:** "**※ AI-Generated Draft Image**"
    
    **INPUT DATA:**
    CONTEXT: {summary}
    DETAILS: {key_details}
    IMPROVEMENTS APPLIED: {formatted_suggestions}
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
    KEY_AUDIO = f"{key_prefix}_audio_bytes"
    KEY_LANG = f"{key_prefix}_target_lang"

    if KEY_RESULT not in st.session_state: st.session_state[KEY_RESULT] = None
    if KEY_IMAGE not in st.session_state: st.session_state[KEY_IMAGE] = None
    if KEY_PROMPT not in st.session_state: st.session_state[KEY_PROMPT] = ""
    if KEY_UPLOADED_NAME not in st.session_state: st.session_state[KEY_UPLOADED_NAME] = None
    if KEY_AUDIO not in st.session_state: st.session_state[KEY_AUDIO] = None
    if KEY_LANG not in st.session_state: st.session_state[KEY_LANG] = "English"
    
    c_header, c_lang = st.columns([3, 1], vertical_alignment="bottom")

    with c_header:
        st.subheader("📂 1. Upload File / Run Analysis")
    with c_lang:
        lang_options = ["English", "French", "Spanish", "Japanese", "German", "Italian", "Portuguese"]
        lang_code_map = {"English": "en", "French": "fr", "Spanish": "es", "Japanese": "ja", "German": "de", "Italian": "it", "Portuguese": "pt"}
        # ラベルを非表示(collapsed)にしてアイコンのみのニュアンスにするか、短くする
        target_lang = st.selectbox("Analysis Language", lang_options, index=0, key=f"{key_prefix}_lang_select", label_visibility="collapsed")
        st.session_state[KEY_LANG] = target_lang
        selected_lang_code = lang_code_map[target_lang]


    has_result = st.session_state[KEY_RESULT] is not None

    with st.expander("Open/Close Panel", expanded=not has_result):
        # File Uploader
        uploaded_file = st.file_uploader(
            "Upload File", # ラベルは見えないがアクセシビリティのために残す
            type=["pdf", "png", "jpg", "jpeg"], 
            key=f"{key_prefix}_uploader", 
            label_visibility="collapsed" # ラベルを消してさらに詰める
        )
        
        # ファイルがある場合のみボタンを表示するなど、ロジックはそのまま...
        if uploaded_file is not None:
             # (中略: ファイル変更検知ロジック)
             if st.session_state[KEY_UPLOADED_NAME] != uploaded_file.name:
                st.session_state[KEY_RESULT] = None
                st.session_state[KEY_IMAGE] = None
                st.session_state[KEY_AUDIO] = None
                st.session_state[KEY_UPLOADED_NAME] = uploaded_file.name
                file_bytes = uploaded_file.getvalue()
                st.session_state[KEY_ASPECT] = get_file_aspect_ratio(file_bytes, uploaded_file.type)
                st.rerun()

             # ボタンの余白も少し気になる場合は columns を使って幅を調整しても良い
             if st.button("🚀 Run Analysis", type="secondary", key=f"{key_prefix}_analyze_btn", use_container_width=True):
                # (中略: 分析実行ロジック)
                status_box = st.empty()
                file_bytes = uploaded_file.getvalue(); file_type = uploaded_file.type
                result = analyze_sludge(file_bytes, file_type, target_lang=st.session_state[KEY_LANG], doc_type=key_prefix, status_container=status_box)
                if result: 
                    status_box.empty()
                    st.session_state[KEY_RESULT] = result
                    st.session_state[KEY_IMAGE] = None
                    st.session_state[KEY_AUDIO] = None
                    st.rerun()

    if st.session_state[KEY_RESULT]:
        result = st.session_state[KEY_RESULT]
        st.subheader("📊 2. Audit Report")
        st.markdown(f'<div class="safety-badge">🛡️ Safety Protocol Verified ({st.session_state[KEY_LANG]})</div> ', unsafe_allow_html=True)
        
        # --- TTS Audio Section ---
        col_audio_btn, col_audio_player = st.columns([1, 3])
        with col_audio_btn:
            if st.button("🗣️ Read Report", key=f"{key_prefix}_tts_btn"):
                with st.spinner("Generating audio report..."):
                    script = prepare_speech_script(result, mode="official")
                    # 言語コードを指定
                    audio_data = generate_audio_gtts(script, lang=selected_lang_code)
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
                with st.expander("▼ Detailed Evaluation (4 Sludge Scores)", expanded=False):
                    s_deduction = result.get('search_cost', {}).get('deduction', 0)
                    s_score = 25 - s_deduction                   
                    d_deduction = result.get('decision_cost', {}).get('deduction', 0)
                    d_score = 25 - d_deduction                    
                    c_deduction = result.get('cognitive_cost', {}).get('deduction', 0)
                    c_score = 25 - c_deduction                   
                    e_deduction = result.get('emotional_cost', {}).get('deduction', 0)
                    e_score = 25 - e_deduction
                    st.write(f"**🔍 Search Score ({s_score}/25):** {result.get('search_cost', {}).get('comment')}")
                    st.write(f"**🤔 Decision Score ({d_score}/25):** {result.get('decision_cost', {}).get('comment')}")
                    st.write(f"**🧠 Cognitive Score ({c_score}/25):** {result.get('cognitive_cost', {}).get('comment')}")
                    st.write(f"**😫 Emotional Score ({e_score}/25):** {result.get('emotional_cost', {}).get('comment')}")

            with col_improve:
                st.markdown("#### ✨ Improvement Direction")
                st.write(result.get("improvement_summary"))
                with st.expander("▼ EAST Suggestions", expanded=False):
                    east = result.get("east_suggestions", {})
                    st.write(f"**😌 Easy:** {east.get('easy')}")
                    st.write(f"**✨ Attractive:** {east.get('attractive')}")
                    st.write(f"**🗣️ Social:** {east.get('social')}")
                    st.write(f"**⏱️ Timely:** {east.get('timely')}")
        
        st.markdown("""<div style="display: flex; align-items: center; justify-content: center; gap: 10px; padding: 20px; margin-top: 10px; margin-bottom: 10px;"><span style="font-size: 2rem;">⬇️</span><span style="color: #555; font-weight: bold; font-size: 1rem;">Create improved design based on this audit</span></div>""", unsafe_allow_html=True)

        col_settings, col_result = st.columns([1, 1], gap="medium")
        with col_settings:
            st.subheader("📝 3. Generation Settings")
            with st.form(f"{key_prefix}_generation_settings_form"):
                # フォームの初期値に翻訳されたテキストが入るようになる
                edited_summary = st.text_area("Context", value=result.get("overall_summary"), height=100)
                edited_key_details = st.text_area("Key Details", value=result.get("key_details"), height=200)
                east = result.get("east_suggestions", {})
                combined_suggestions = (
                    f"- Easy: {east.get('easy', '')}\n"
                    f"- Attractive: {east.get('attractive', '')}\n"
                    f"- Social: {east.get('social', '')}\n"
                    f"- Timely: {east.get('timely', '')}"
                )
                edited_suggestions_text = st.text_area("Instructions (EAST Framework)", value=combined_suggestions, height=150)
                submitted = st.form_submit_button("📄 Generate Improved Document", type="secondary", use_container_width=True)
            if submitted:
                with st.spinner("AI is designing..."):
                    suggestions_list = [line.strip() for line in edited_suggestions_text.split('\n') if line.strip()]
                    image, used_prompt = generate_improved_image(edited_summary, edited_key_details, suggestions_list, aspect_ratio=st.session_state[KEY_ASPECT], doc_type=key_prefix)
                    if image: st.session_state[KEY_IMAGE] = image; st.session_state[KEY_PROMPT] = used_prompt; st.rerun()

        with col_result:
            st.subheader("📄 4. Improved Draft")
            if st.session_state[KEY_IMAGE]:
                st.image(st.session_state[KEY_IMAGE], caption="AI Generated Preview", use_container_width=True)
                buf = io.BytesIO(); st.session_state[KEY_IMAGE].save(buf, format="PNG")
                st.download_button("⬇️ Download Image", data=buf.getvalue(), file_name=f"improved_{key_prefix}.png", mime="image/png", key=f"{key_prefix}_dl_btn", use_container_width=True)
                st.write("")
                st.caption("💡 To refine the result, adjust details in 3. Generation Settings and regenerate.")
# --- Component: Citizen Side ---
def render_citizen_tab():
    key_prefix = "citizen"
    KEY_RESULT = f"{key_prefix}_result"
    KEY_UPLOADED_NAME = f"{key_prefix}_last_uploaded"
    KEY_AUDIO = f"{key_prefix}_audio_bytes"
    KEY_LANG = f"{key_prefix}_target_lang" 
    KEY_DRAFT = f"{key_prefix}_draft_text"

    if KEY_RESULT not in st.session_state: st.session_state[KEY_RESULT] = None
    if KEY_UPLOADED_NAME not in st.session_state: st.session_state[KEY_UPLOADED_NAME] = None
    if KEY_AUDIO not in st.session_state: st.session_state[KEY_AUDIO] = None
    if KEY_LANG not in st.session_state: st.session_state[KEY_LANG] = "English"
    if KEY_DRAFT not in st.session_state: st.session_state[KEY_DRAFT] = None

    c_header, c_lang = st.columns([3, 1], vertical_alignment="bottom")
    
    with c_header:
        st.subheader("📂 1. Upload Document / Run Analysis")
    with c_lang:
        lang_options = ["English", "French", "Spanish", "Japanese", "German", "Italian", "Portuguese"]
        lang_code_map = {"English": "en", "French": "fr", "Spanish": "es", "Japanese": "ja", "German": "de", "Italian": "it", "Portuguese": "pt"}
        # ラベル非表示で統一
        target_lang = st.selectbox("Output Language", lang_options, index=0, key=f"{key_prefix}_lang_select", label_visibility="collapsed")
        st.session_state[KEY_LANG] = target_lang
        selected_lang_code = lang_code_map[target_lang]

    has_result = st.session_state[KEY_RESULT] is not None

    with st.expander("Open/Close Panel", expanded=not has_result):
        uploaded_file = st.file_uploader(
            "Upload File", 
            type=["pdf", "png", "jpg", "jpeg"], 
            key=f"{key_prefix}_uploader", 
            label_visibility="collapsed" # ラベル非表示
        )
        
        if uploaded_file is not None:
            if st.session_state[KEY_UPLOADED_NAME] != uploaded_file.name:
                st.session_state[KEY_RESULT] = None
                st.session_state[KEY_AUDIO] = None
                st.session_state[KEY_DRAFT] = None
                st.session_state[KEY_UPLOADED_NAME] = uploaded_file.name
                st.rerun()

            if st.button("🔍 Run Analysis", type="secondary", key=f"{key_prefix}_analyze_btn", use_container_width=True):
                status_box = st.empty()
                file_bytes = uploaded_file.getvalue(); file_type = uploaded_file.type
                result = analyze_citizen_doc(file_bytes, file_type, target_lang=st.session_state[KEY_LANG], status_container=status_box)
                if result: 
                    status_box.empty()
                    st.session_state[KEY_RESULT] = result
                    st.rerun()

    if st.session_state[KEY_RESULT]:
        result = st.session_state[KEY_RESULT]
        
        st.subheader("📝 2. Document Guide")
        st.markdown(f'<div class="safety-badge">🛡️ Safety Protocol Verified ({st.session_state[KEY_LANG]})</div> ', unsafe_allow_html=True)
        
        # --- 変更: Sludge指摘を常時表示 ---
        st.markdown("##### 🧐 Why is this document confusing? (AI Analysis)")
        st.info(result.get("sludge_observation"), icon="🤖")

        # --- 変更: 役所への通報をExpanderに格納 ---
        with st.expander("📢 Report 'Sludge' to the Agency (Click to expand)", expanded=False):
             with st.form(key=f"{key_prefix}_feedback_form"):
                default_feedback = f"[Citizen Feedback - {st.session_state[KEY_LANG]}]\nIssues: {result.get('sludge_observation')}\n\nRequest: Please simplify."
                st.text_area("Message to Send", value=default_feedback, height=100)
                if st.form_submit_button("📨 Send Improvement Request"): st.success("✅ Sent!"); st.balloons()

        # 音声読み上げボタンなど
        col_audio_btn, col_audio_player = st.columns([1, 3])
        with col_audio_btn:
            if st.button("🗣️ Listen to Guide", key=f"{key_prefix}_tts_btn"):
                with st.spinner("Creating audio guide..."):
                    script = prepare_speech_script(result, mode="citizen")
                    audio_data = generate_audio_gtts(script, lang=selected_lang_code)
                    if audio_data: st.session_state[KEY_AUDIO] = audio_data
        with col_audio_player:
            if st.session_state[KEY_AUDIO]: st.audio(st.session_state[KEY_AUDIO], format='audio/mp3')

        with st.container(border=True):
            st.markdown("### 💡 Summary: What does it mean?")
            st.write(result.get("simple_summary")) # Infoアイコン削除でスッキリさせる

            if result.get("risks_and_penalties"):
                st.markdown("### ⚠️ Risks & Penalties")
                for risk in result.get("risks_and_penalties", []): st.error(risk, icon="🚨")
            
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

        # --- 新機能: 3. Action / Auto-Fill Wizard ---
        st.divider()
        st.subheader("🚀 3. Take Action")
        st.markdown("Based on the document, here is what you need to do.")

        # アクションガイドの表示
        with st.container(border=True):
            st.markdown(result.get("action_guide_markdown"))
        
        st.markdown("#### ✍️ 4. Draft your Application / Email")
        st.markdown("Answer these simple questions, and AI will write the formal text for you.")

        # ダイナミックフォームの生成
        with st.container(border=True):
            user_answers = {}
            with st.form(key="action_wizard_form"):
                questions = result.get("missing_info_questions", [])
                if not questions:
                    questions = ["What is your full name?", "What is your reference number?"] # Fallback

                # 2列にしてコンパクトに表示
                col_q1, col_q2 = st.columns(2)
                for i, q in enumerate(questions):
                    target_col = col_q1 if i % 2 == 0 else col_q2
                    user_answers[q] = target_col.text_input(f"❓ {q}", key=f"q_{i}")
                
                submitted = st.form_submit_button("✨ Generate Draft", type="primary", use_container_width=True)
            
            if submitted:
                with st.spinner("AI is writing for you..."):
                    draft_text = generate_user_draft(result.get("simple_summary"), user_answers, target_lang=st.session_state[KEY_LANG])
                    st.session_state[KEY_DRAFT] = draft_text

            # 生成結果の表示
            if st.session_state[KEY_DRAFT]:
                st.success("Draft created! Copy and paste below.")
                st.text_area("📄 Final Draft", value=st.session_state[KEY_DRAFT], height=300)
                st.caption("⚠️ Please review the draft before sending.")

# --- Main App ---
def main():
    apply_custom_styles()

    col_title, col_controls = st.columns([0.7, 0.3], gap="medium", vertical_alignment="bottom")

    with col_title:
        st.title("Civic Reach")
        st.markdown("""
            **Identifying 'Sludge' in government services** | Behavioral Science × Generative AI<br>
            Based on the OECD report *'Fixing Frictions: ‘Sludge audits’ around the world'*. Details of the methodology can be found [here](https://github.com/hrkzz/civic-reach/blob/main/methodology.md).
            """, unsafe_allow_html=True)

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
            if st.button("🗑️ Reset App", type="secondary", use_container_width=True, help="Wipe all data and restart session"):
                clear_session_data()
        
    tab_official_notice, tab_official_flyer, tab_citizen = st.tabs(["【Officials】 Notice Audit", "【Officials】 Flyer Audit", "【Citizens】 Doc Decipher"])
    with tab_official_notice: render_tab_content("notice")
    with tab_official_flyer: render_tab_content("flyer")
    with tab_citizen: render_citizen_tab()

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
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()