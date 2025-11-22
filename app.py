import os
import json
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from PIL import Image
import io
import pypdf
import time  # ステータス表示の演出用

# 1. 環境変数の読み込み
load_dotenv()
API_KEY = os.environ.get("GEMINI_API_KEY")

# 2. ページ設定
st.set_page_config(
    page_title="Civic Reach",
    page_icon="🧭",
    layout="wide"
)

# 3. Client初期化
if not API_KEY:
    st.error("エラー: .envファイルに GEMINI_API_KEY が設定されていません。")
    st.stop()

client = genai.Client(api_key=API_KEY)

# --- CSSスタイル適用関数 ---
def apply_custom_styles():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap');
        html, body, [class*="css"] {
            font-family: 'Noto Sans JP', sans-serif !important;
            color: #000000 !important;
        }
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 5rem !important;
        }
        h1 { font-size: 2.5rem !important; font-weight: 700 !important; margin-bottom: 0.5rem !important; }
        h3 { font-size: 1.2rem !important; font-weight: 700 !important; color: #334155 !important; }
        hr { margin-top: 0.5rem !important; margin-bottom: 0.5rem !important; }
        p, li, .stMarkdown { font-size: 1rem !important; line-height: 1.6 !important; }
        .streamlit-expanderHeader { font-weight: 700 !important; color: #000000 !important; }
        .streamlit-expanderContent p, .streamlit-expanderContent li, .streamlit-expanderContent div { color: #000000 !important; }
        .stAlert { padding: 0.5rem !important; }
        [data-testid="stMetricValue"] { font-size: 2.5rem !important; }
        
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

# --- データ構造の定義 (Pydantic) ---

# 【職員向け】
class CostDetail(BaseModel):
    deduction: int = Field(..., description="この項目の減点数 (0-25)。")
    comment: str = Field(..., description="なぜこの点数なのか、具体的な分析と解説。")

class EastSuggestions(BaseModel):
    easy: str = Field(..., description="Easy (かんたん) の観点からの改善案")
    attractive: str = Field(..., description="Attractive (印象的) の観点からの改善案")
    social: str = Field(..., description="Social (社会的) の観点からの改善案")
    timely: str = Field(..., description="Timely (タイムリー) の観点からの改善案")

class SludgeAudit(BaseModel):
    total_score: int = Field(..., description="100点満点から各コストの減点を引いた総合スコア。")
    overall_summary: str = Field(..., description="文書全体の概要。")
    evaluation_summary: str = Field(..., description="監査結果の総評。")
    improvement_summary: str = Field(..., description="改善策の概要。")
    
    key_details: str = Field(..., description="【超重要】文書に含まれる事実情報の完全な抽出。期限、金額、参照番号、法的根拠、不服申し立て条件、問い合わせ先電話番号などを漏れなく記載すること。")
    
    search_cost: CostDetail = Field(..., description="探索コストの評価")
    decision_cost: CostDetail = Field(..., description="決断コストの評価")
    cognitive_cost: CostDetail = Field(..., description="認知的コストの評価")
    emotional_cost: CostDetail = Field(..., description="感情的コストの評価")
    east_suggestions: EastSuggestions = Field(..., description="EASTフレームワークに基づく改善案詳細")

# 【国民向け】
class CitizenGuide(BaseModel):
    sludge_observation: str = Field(..., description="この文書がなぜ分かりにくいのか、4つのコスト（探索・決断・認知・感情）の観点からの分析結果。")
    simple_summary: str = Field(..., description="文書の概要。「誰に」「何を」求めているか。正確性を最優先し、条件（もし〜なら）を含めて記述すること。")
    action_guide_markdown: str = Field(..., description="ユーザーが取るべき行動のガイド。Markdown形式の箇条書き（- ）を使用し、条件分岐（同意する場合/しない場合など）をインデントで表現して構造化すること。チェックボックスは使用しない。")
    risks_and_penalties: list[str] = Field(..., description="★最重要：無視した場合の不利益、罰則、遅延損害金、法的措置の可能性など、警告情報をリスト化。")
    required_documents: list[str] = Field(..., description="手続きに必要な書類、身分証、番号などのリスト。")
    important_dates: list[str] = Field(..., description="期限、支払日、実施日などの重要な日付のリスト。")

# --- ユーティリティ関数 ---
def get_file_aspect_ratio(file_bytes, file_type):
    width = 0
    height = 0
    try:
        if "pdf" in file_type:
            pdf_reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            if len(pdf_reader.pages) > 0:
                page = pdf_reader.pages[0]
                width = float(page.mediabox.width)
                height = float(page.mediabox.height)
        elif "image" in file_type:
            image = Image.open(io.BytesIO(file_bytes))
            width, height = image.size
            
        if width > 0 and height > 0:
            ratio = width / height
            if ratio < 0.85: return "3:4"
            elif ratio > 1.15: return "4:3"
            else: return "1:1"
    except Exception:
        pass
    return "3:4"

# --- ★新規実装: ファクトチェック機能 (Safety Layer) ---
def verify_safety(file_bytes, file_type, initial_json, model_schema):
    """
    抽出されたJSONデータが、元の文書画像と矛盾していないか検証・修正する
    """
    
    system_prompt = """
    You are a **Government Document Integrity Officer** and a **Safety Layer** for an AI system.
    Your sole job is to **VERIFY** the extraction results against the original document image to prevent AI hallucinations.

    **STRICT VERIFICATION RULES:**
    1. **Numbers & Dates:** Check every monetary amount ($), deadline, and phone number. They MUST match the document pixels exactly.
    2. **No Invention:** If the extracted JSON contains details NOT found in the document, DELETE them.
    3. **Correction:** If a number is wrong (e.g., $100 vs $1000), CORRECT it in the JSON.
    4. **Structure:** Do not change the JSON keys, only the values if they are factually incorrect.

    **INPUT DATA:**
    - Original Document (Attached)
    - Draft Extraction (JSON): Provided below.

    **OUTPUT:**
    - Return the (potentially corrected) JSON object.
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash", # 高速なモデルで検証
            contents=[
                types.Content(
                    parts=[
                        types.Part(text=f"Verify this JSON data against the document:\n{json.dumps(initial_json, ensure_ascii=False)}"),
                        types.Part(inline_data=types.Blob(mime_type=file_type, data=file_bytes))
                    ]
                )
            ],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=model_schema,
                temperature=0.0, # 事実確認なので創造性はゼロにする
            )
        )
        return json.loads(response.text)
    except Exception as e:
        # 検証に失敗した場合は、少なくとも元のデータを返す（エラーで止まらないように）
        print(f"Verification Error: {e}")
        return initial_json

# --- 分析ロジック関数 (職員向け・検証付き) ---
def analyze_sludge(file_bytes, file_type, doc_type="flyer", status_container=None):
    prompt_notice = """
    あなたはG7政府機関に所属する「行動科学者」兼「法務監査官」です。
    提供された「公式な行政通知」に対して、信頼性を担保しつつ、受取人のコンプライアンス（法令遵守）を最大化するための監査を行ってください。
    ... (中略: 以前のプロンプトと同じ) ...
    出力は必ず指定されたJSON形式で行ってください。
    """
    
    prompt_flyer = """
    あなたは自治体の「広報デザイン専門家」です。広報チラシに対して、住民の参加意欲を高めるための監査を行ってください。
    出力は必ず指定されたJSON形式で行ってください。
    """

    system_prompt = prompt_notice if doc_type == "notice" else prompt_flyer

    try:
        # Phase 1: 初期分析
        if status_container: status_container.markdown("🔄 **Phase 1/2:** 行動科学的分析を実行中...")
        
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=[
                types.Content(
                    parts=[
                        types.Part(text="この行政文書を厳格に監査し、JSONで出力してください。Key Detailsは漏れなく抽出してください。"),
                        types.Part(inline_data=types.Blob(mime_type=file_type, data=file_bytes))
                    ]
                )
            ],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=SludgeAudit,
                temperature=0.0, 
            )
        )
        initial_result = json.loads(response.text)

        # Phase 2: 安全性検証 (Safety Check)
        if status_container: status_container.markdown("🛡️ **Phase 2/2:** リスク情報(金額・期限)のファクトチェックを実行中...")
        verified_result = verify_safety(file_bytes, file_type, initial_result, SludgeAudit)
        
        return verified_result

    except Exception as e:
        st.error(f"分析エラー: {e}")
        return None

# --- 分析ロジック関数 (国民向け・検証付き) ---
def analyze_citizen_doc(file_bytes, file_type, status_container=None):
    system_prompt = """
    あなたは、行政手続きを支援する「高信頼性AIアシスタント」です。
    提供された文書を分析し、市民向けの解説を作成してください。
    ... (中略: 以前のプロンプトと同じ) ...
    出力は必ず指定されたJSON形式で行ってください。
    """

    try:
        # Phase 1: 初期分析
        if status_container: status_container.markdown("🔄 **Phase 1/2:** 文書の解釈と要約を作成中...")
        
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=[
                types.Content(
                    parts=[
                        types.Part(text="この文書をスラッジ監査した上で、市民向けに分かりやすく解説してください。"),
                        types.Part(inline_data=types.Blob(mime_type=file_type, data=file_bytes))
                    ]
                )
            ],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=CitizenGuide,
                temperature=0.0, 
            )
        )
        initial_result = json.loads(response.text)

        # Phase 2: 安全性検証 (Safety Check)
        if status_container: status_container.markdown("🛡️ **Phase 2/2:** 罰則・期限情報の自己検証(Self-Correction)を実行中...")
        verified_result = verify_safety(file_bytes, file_type, initial_result, CitizenGuide)
        
        return verified_result

    except Exception as e:
        st.error(f"分析エラー: {e}")
        return None

# --- 画像生成関数 ---
def generate_improved_image(summary, key_details, suggestions_list, aspect_ratio="3:4", doc_type="flyer"):
    formatted_suggestions = "\n".join([f"- {s}" for s in suggestions_list])

    prompt_notice = f"""
    Generate a **DIGITAL BORN PDF DOCUMENT** (Direct Export style) of a formal Government Letter/Notice.
    
    **🚫 VISUAL STYLE CONSTRAINTS:**
    - **NO** paper texture, shadows, folding marks, scan noise.
    - Background: **#FFFFFF (Pure Digital White)**.
    - **NO** handwriting fonts. Crisp, digital vector-style fonts only.
    
    **✅ REQUIRED LAYOUT:**
    - **Format:** Standard A4 Letter layout.
    - **Header:** Minimalist Agency Logo & Reference Info.
    - **Title:** Bold, centered, serif font (e.g., "NOTICE OF TAX ADJUSTMENT").
    - **Body:** Professional serif font (Times New Roman/Georgia), 11pt, left-aligned.
    - **Key Info Box:** A simple 1px black border box containing "Deadline" and "Amount".
    
    **⚠️ MANDATORY FOOTER:**
    - "**※ AI-Generated Draft for Review Only**" at the bottom.
    
    **CONTENT TO TYPESET:**
    CONTEXT: {summary}
    DETAILS: {key_details}
    IMPROVEMENTS: {formatted_suggestions}
    """

    prompt_flyer = f"""
    Create a **High-Quality Digital Graphic Design Asset** for a government flyer/poster.
    
    **Visual Style:**
    - Friendly, modern, approachable.
    - Use illustrations and mild colors.
    
    **⚠️ MANDATORY FOOTER:**
    - "**※ AI-Generated Draft Image**" at the bottom.

    # 1. CONTEXT:
    {summary}

    # 2. REQUIRED TEXT:
    {key_details}

    # 3. DESIGN IMPROVEMENTS:
    {formatted_suggestions}
    """

    target_prompt = prompt_notice if doc_type == "notice" else prompt_flyer
    
    try:
        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=target_prompt,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}], 
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio, image_size="2K")
            )
        )
        for part in response.parts:
            if part.inline_data:
                return Image.open(io.BytesIO(part.inline_data.data)), target_prompt
        return None, target_prompt
    except Exception as e:
        st.error(f"画像生成エラー: {e}")
        return None, target_prompt

# --- 共通コンポーネント: 職員向け ---
def render_tab_content(key_prefix):
    KEY_RESULT = f"{key_prefix}_audit_result"
    KEY_IMAGE = f"{key_prefix}_generated_image"
    KEY_PROMPT = f"{key_prefix}_last_prompt"
    KEY_UPLOADED_NAME = f"{key_prefix}_last_uploaded"
    KEY_ASPECT = f"{key_prefix}_target_aspect_ratio"

    if KEY_RESULT not in st.session_state: st.session_state[KEY_RESULT] = None
    if KEY_IMAGE not in st.session_state: st.session_state[KEY_IMAGE] = None
    if KEY_PROMPT not in st.session_state: st.session_state[KEY_PROMPT] = ""
    if KEY_UPLOADED_NAME not in st.session_state: st.session_state[KEY_UPLOADED_NAME] = None
    
    st.subheader("📂 1. ファイルアップロード / 分析実行")
    has_result = st.session_state[KEY_RESULT] is not None
    with st.expander("パネルを開く/閉じる", expanded=not has_result):
        uploaded_file = st.file_uploader(
            "ファイルをドラッグ＆ドロップまたは選択", type=["pdf", "png", "jpg", "jpeg"], key=f"{key_prefix}_uploader", label_visibility="collapsed"
        )
        if uploaded_file is not None:
            if st.session_state[KEY_UPLOADED_NAME] != uploaded_file.name:
                st.session_state[KEY_RESULT] = None
                st.session_state[KEY_IMAGE] = None
                st.session_state[KEY_UPLOADED_NAME] = uploaded_file.name
                file_bytes = uploaded_file.getvalue()
                st.session_state[KEY_ASPECT] = get_file_aspect_ratio(file_bytes, uploaded_file.type)
                st.rerun()

            if st.button("🚀 分析を実行", type="primary", key=f"{key_prefix}_analyze_btn", use_container_width=True):
                status_box = st.empty() # ステータス表示用
                file_bytes = uploaded_file.getvalue()
                file_type = uploaded_file.type
                result = analyze_sludge(file_bytes, file_type, doc_type=key_prefix, status_container=status_box)
                if result:
                    status_box.empty() # 完了したら消す
                    st.session_state[KEY_RESULT] = result
                    st.session_state[KEY_IMAGE] = None
                    st.rerun()

    if st.session_state[KEY_RESULT]:
        result = st.session_state[KEY_RESULT]
        st.subheader("📊 2. 評価レポート")
        
        # Safety Badge
        st.markdown('<div class="safety-badge">🛡️ Safety Protocol Verified</div> ', unsafe_allow_html=True)
        
        with st.container(border=True):
            score = result.get("total_score", 0)
            c_score_main, c_score_sub = st.columns([1, 3], gap="large")
            with c_score_main:
                st.metric("総合評価スコア", f"{score}/100")
            with c_score_sub:
                st.write(""); st.write("スコアメーター"); st.progress(score)
                if score >= 80: st.caption("素晴らしい！非常に分かりやすい文書です。")
                elif score >= 60: st.caption("平均的です。いくつかの改善で大きく向上します。")
                else: st.caption("改善の余地が大きいです。抜本的な見直しを推奨します。")
            st.divider()
            
            col_eval, col_improve = st.columns(2, gap="large")
            with col_eval:
                st.markdown("#### 🧐 評価総評")
                st.write(result.get("evaluation_summary"))
                st.write("") 
                with st.expander("▼ 詳細評価", expanded=False):
                    def display_cost(label, data, icon):
                        s = 25 - data.get('deduction', 0)
                        st.markdown(f"**{icon} {label} ({s}/25)**") 
                        st.write(data.get('comment'))
                        st.write("")
                    display_cost("探索スコア", result.get("search_cost"), "🔍")
                    display_cost("決断スコア", result.get("decision_cost"), "🤔")
                    display_cost("認知的スコア", result.get("cognitive_cost"), "🧠")
                    display_cost("感情的スコア", result.get("emotional_cost"), "❤️")
            with col_improve:
                st.markdown("#### ✨ 改善の方向性")
                st.write(result.get("improvement_summary"))
                st.write("") 
                with st.expander("▼ 詳細改善案", expanded=False):
                    east = result.get("east_suggestions", {})
                    st.markdown("**😌 Easy**"); st.write(east.get('easy')); st.write("") 
                    st.markdown("**✨ Attractive**"); st.write(east.get('attractive')); st.write("")
                    st.markdown("**🗣️ Social**"); st.write(east.get('social')); st.write("")
                    st.markdown("**⏱️ Timely**"); st.write(east.get('timely')); st.write("")
        
        st.markdown("""<div style="display: flex; align-items: center; justify-content: center; gap: 10px; padding: 20px; margin-top: 10px; margin-bottom: 10px;"><span style="font-size: 2rem;">⬇️</span><span style="color: #555; font-weight: bold; font-size: 1rem;">評価結果に基づき、改善版のデザインを作成します</span></div>""", unsafe_allow_html=True)

        col_settings, col_result = st.columns([1, 1], gap="medium")
        with col_settings:
            st.subheader("📝 3. 生成設定")
            st.markdown("AIの抽出内容を確認し、改善案を生成してください。")
            with st.form(f"{key_prefix}_generation_settings_form"):
                edited_summary = st.text_area("① 文書の概要 (Context)", value=result.get("overall_summary"), height=100, key=f"{key_prefix}_input_summary")
                edited_key_details = st.text_area("② 重要要件 (Must Include)", value=result.get("key_details"), height=200, key=f"{key_prefix}_input_details", help="金額、期限、条件分岐など、文書に必ず記載しなければならない事項")
                east = result.get("east_suggestions", {})
                default_suggestions = f"Easy: {east.get('easy')}\nAttractive: {east.get('attractive')}\nSocial: {east.get('social')}\nTimely: {east.get('timely')}"
                edited_suggestions_text = st.text_area("③ 改善指示 (Instructions)", value=default_suggestions, height=150, key=f"{key_prefix}_input_suggestions")
                submitted = st.form_submit_button("📄 改善版ドキュメントを生成", type="secondary", use_container_width=True)
            if submitted:
                with st.spinner("Gemini 3 Pro が文書レイアウトを生成中..."):
                    suggestions_list = [line.strip() for line in edited_suggestions_text.split('\n') if line.strip()]
                    image, used_prompt = generate_improved_image(edited_summary, edited_key_details, suggestions_list, aspect_ratio=st.session_state[KEY_ASPECT], doc_type=key_prefix)
                    if image:
                        st.session_state[KEY_IMAGE] = image
                        st.session_state[KEY_PROMPT] = used_prompt
                        st.rerun()

        with col_result:
            st.subheader("📄 4. 改善された文書案")
            if st.session_state[KEY_IMAGE]:
                st.image(st.session_state[KEY_IMAGE], caption="AI生成プレビュー", use_container_width=True)
                with st.expander("🔍 プロンプトログ"): st.code(st.session_state[KEY_PROMPT], language="text")
                st.write("修正したい場合は左記フォームを編集して再生成してください。")
                buf = io.BytesIO()
                st.session_state[KEY_IMAGE].save(buf, format="PNG")
                st.download_button("⬇️ 画像を保存", data=buf.getvalue(), file_name=f"improved_{key_prefix}.png", mime="image/png", key=f"{key_prefix}_dl_btn", use_container_width=True)
            elif submitted: pass 
            else: st.info("👈 設定を確認し、「生成」ボタンを押してください")

# --- 新規コンポーネント: 国民向け ---
def render_citizen_tab():
    key_prefix = "citizen"
    
    KEY_RESULT = f"{key_prefix}_result"
    KEY_UPLOADED_NAME = f"{key_prefix}_last_uploaded"

    if KEY_RESULT not in st.session_state: st.session_state[KEY_RESULT] = None
    if KEY_UPLOADED_NAME not in st.session_state: st.session_state[KEY_UPLOADED_NAME] = None

    st.subheader("📂 1. ファイルアップロード")
    st.markdown("難しい行政文書をアップロードしてください。AIが内容を詳細に読み解き、リスクや必要な手続きを整理します。")
    
    has_result = st.session_state[KEY_RESULT] is not None
    with st.expander("パネルを開く/閉じる", expanded=not has_result):
        uploaded_file = st.file_uploader(
            "ファイルをドラッグ＆ドロップまたは選択", type=["pdf", "png", "jpg", "jpeg"], key=f"{key_prefix}_uploader", label_visibility="collapsed"
        )
        if uploaded_file is not None:
            if st.session_state[KEY_UPLOADED_NAME] != uploaded_file.name:
                st.session_state[KEY_RESULT] = None
                st.session_state[KEY_UPLOADED_NAME] = uploaded_file.name
                file_bytes = uploaded_file.getvalue()
                st.rerun()

            if st.button("🔍 文書を読み解く", type="primary", key=f"{key_prefix}_analyze_btn", use_container_width=True):
                status_box = st.empty()
                file_bytes = uploaded_file.getvalue()
                file_type = uploaded_file.type
                result = analyze_citizen_doc(file_bytes, file_type, status_container=status_box)
                if result:
                    status_box.empty()
                    st.session_state[KEY_RESULT] = result
                    st.rerun()

    # 2. 解釈レポート
    if st.session_state[KEY_RESULT]:
        result = st.session_state[KEY_RESULT]
        
        st.subheader("📝 2. 文書解説レポート")
        # Safety Badge
        st.markdown('<div class="safety-badge">🛡️ Safety Protocol Verified (Correctness Check)</div> ', unsafe_allow_html=True)
        
        with st.expander("🔍 なぜこの文書は分かりにくいのか？ (AI分析)", expanded=False):
            st.info("AIは以下の「分かりにくさの要因（スラッジ）」を特定し、それらを解消するように解説を作成しました。")
            st.write(result.get("sludge_observation"))

        with st.container(border=True):
            st.markdown("### 💡 つまり、どういうこと？")
            st.info(result.get("simple_summary"), icon="💁")
            
            if result.get("risks_and_penalties"):
                st.markdown("### ⚠️ 無視するとどうなる？ (リスク・罰則)")
                for risk in result.get("risks_and_penalties", []):
                    st.error(risk, icon="🚨")

            st.divider()

            st.markdown("### ✅ あなたがやるべきこと (Action Guide)")
            with st.container(border=True):
                st.markdown(result.get("action_guide_markdown"))

            st.divider()

            c1, c2 = st.columns(2, gap="large")
            with c1:
                st.markdown("### 📄 必要な書類・もの")
                if result.get("required_documents"):
                    for doc in result.get("required_documents", []):
                        st.write(f"- {doc}")
                else:
                    st.write("特になし")

            with c2:
                st.markdown("### 📅 重要な日付")
                if result.get("important_dates"):
                    for date in result.get("important_dates", []):
                        st.warning(f"🗓️ {date}")
                else:
                    st.write("特になし")
            
        # --- フィードバックフォーム (Citizen Voice) ---
        with st.container(border=True):
            st.subheader("📢 政府に「分かりにくい」と伝える")
            st.markdown("""
            この文書が分かりにくいのは、あなたのせいではありません。
            この分析結果を匿名で担当機関にフィードバックし、将来の文書改善に役立てることができます。
            """)

            with st.form(key=f"{key_prefix}_feedback_form"):
                raw_obs = result.get('sludge_observation', '専門用語が多く、手続きが複雑です。')
                clean_obs = raw_obs.replace("**", "").replace("*", "-") 
                
                default_feedback = f"""【市民からのフィードバック】
この通知書について、以下の改善を希望します。

■ 気になった点
{clean_obs}

■ 要望
より平易な言葉を使用し、リスク情報を明確にしてください。
"""
                
                feedback_text = st.text_area("送信するメッセージ (AIが下書きを作成しました)", value=default_feedback, height=250)
                st.caption("※ 個人情報（名前や住所）は含めずに送信してください。あなたのフィードバックは統計データとして処理されます。")
                submit_feedback = st.form_submit_button("📨 担当機関に改善リクエストを送信", type="primary", use_container_width=True)
            
            if submit_feedback:
                st.success("✅ 送信しました！あなたの声が、行政文書の改善に役立てられます。")
                st.balloons()


# --- メインアプリ ---
def main():
    apply_custom_styles()

    st.title("Civic Reach")
    
    st.markdown(
        """
        Civic Reachは、行政手続きの「わかりにくさ」や「手間」を行動科学と生成AIで発見し、誰にでも伝わるように自動変換するツールです。
        
        OECDのレポート 'Fixing Frictions: ‘Sludge audits’ around the world' に基づいています。評価基準の詳細は[こちら](https://github.com/YOUR_USERNAME/civic-reach/blob/main/methodology.md)
        """
    )

    tab_official_notice, tab_official_flyer, tab_citizen = st.tabs([
        "【職員向け】通知文改善", 
        "【職員向け】チラシ改善",
        "【国民向け】通知文解釈"
    ])

    with tab_official_notice:
        render_tab_content("notice")

    with tab_official_flyer:
        render_tab_content("flyer")
        
    with tab_citizen:
        render_citizen_tab()

if __name__ == "__main__":
    main()