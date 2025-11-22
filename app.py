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
        /* Google Fonts (Noto Sans JP) のインポート */
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap');

        /* 全体のフォント設定 */
        html, body, [class*="css"] {
            font-family: 'Noto Sans JP', sans-serif !important;
            color: #000000 !important;
        }

        /* メインエリア上部の空白を削除 */
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 5rem !important;
        }

        /* タイトル (h1) */
        h1 {
            font-size: 2.5rem !important;
            font-weight: 700 !important;
            padding-bottom: 0rem !important;
            margin-bottom: 0.5rem !important;
        }

        /* サブヘッダー (h3) */
        h3 {
            font-size: 1.2rem !important;
            font-weight: 700 !important;
            color: #334155 !important;
            margin-top: 0.2rem !important;
            padding-top: 0rem !important;
            margin-bottom: 0.5rem !important;
        }
        
        /* 区切り線 (st.divider) */
        hr {
            margin-top: 0.5rem !important;
            margin-bottom: 0.5rem !important;
        }
        
        /* テキスト */
        p, li, .stMarkdown {
            font-size: 1rem !important;
            line-height: 1.6 !important;
            margin-bottom: 0.5rem !important;
        }
        
        /* Expanderのヘッダー */
        .streamlit-expanderHeader {
            font-family: 'Noto Sans JP', sans-serif !important;
            font-weight: 700 !important;
            color: #000000 !important;
        }
        
        /* Expander内の本文テキストを黒にする */
        .streamlit-expanderContent p, 
        .streamlit-expanderContent li, 
        .streamlit-expanderContent div {
            color: #000000 !important;
        }
        
        /* Info boxの調整 */
        .stAlert {
            padding: 0.5rem !important;
        }
        
        /* メトリクスの文字サイズ調整 */
        [data-testid="stMetricValue"] {
            font-size: 2.5rem !important;
        }
    </style>
    """, unsafe_allow_html=True)

# --- データ構造の定義 (Pydantic) ---

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
    overall_summary: str = Field(..., description="文書全体の概要（Context）。")
    
    evaluation_summary: str = Field(..., description="今回の監査結果の総評。なぜこのスコアになったのか、全体的なスラッジの傾向についての簡潔な解説。★重要: improvement_summaryと同じくらいの文字数（200文字程度）で記述すること。")

    improvement_summary: str = Field(..., description="EASTフレームワークに基づく改善策の全体的な方向性と概要。★重要: evaluation_summaryと同じくらいの文字数（200文字程度）で記述すること。")

    key_details: str = Field(..., description="文書に含まれる絶対に変えてはいけない事実情報（日時、期限、場所、電話番号、URL、金額など）を箇条書きで抽出したもの。")
    
    search_cost: CostDetail = Field(..., description="探索コストの評価")
    decision_cost: CostDetail = Field(..., description="決断コストの評価")
    cognitive_cost: CostDetail = Field(..., description="認知的コストの評価")
    emotional_cost: CostDetail = Field(..., description="感情的コストの評価")
    east_suggestions: EastSuggestions = Field(..., description="EASTフレームワークに基づく改善案詳細")

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

# --- 分析ロジック関数 (キャッシュ有効) ---
@st.cache_data(show_spinner=False)
def analyze_sludge(file_bytes, file_type):
    system_prompt = """
    あなたはOECDの行動科学専門家（Behavioral Scientist）です。
    提供された行政文書（画像またはPDF）に対して「スラッジ監査」を行ってください。

    ## 重要: UIレイアウトのための指示
    - `evaluation_summary`（評価総評）と `improvement_summary`（改善の方向性）は、UI上で左右に並べて表示されます。
    - デザインの崩れを防ぐため、**必ずこの2つの要約の文字数（分量）を揃えてください**。
    - 目安: 日本語でそれぞれ約200〜250文字程度（3〜4文）。

    ## 1. 重要情報の抽出 (Key Details)
    デザイン再作成時にハルシネーションを防ぐため、日時・場所・連絡先・条件・金額などの事実情報を正確に抽出してください。

    ## 2. 文書概要と評価総評 (Summaries)
    - overall_summary: 文書の内容自体の客観的な要約（Context）。
    - evaluation_summary: 【重要】今回の監査結果の総評。なぜこのスコアになったのか、全体的なスラッジの傾向を解説。**文字数をimprovement_summaryと揃えること。**

    ## 3. スコアリング (100点満点)
    4つの心理的コスト（Search, Decision, Cognitive, Emotional）について減点評価し、解説してください。

    ## 4. 改善案 (EASTフレームワーク)
    - improvement_summary: 改善策の全体的な方向性。**文字数をevaluation_summaryと揃えること。**
    - east_suggestions: Easy, Attractive, Social, Timelyの各観点での詳細な改善案。

    出力は必ず指定されたJSON形式で行ってください。
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=[
                types.Content(
                    parts=[
                        types.Part(text="この文書を監査し、詳細なJSONレポートを出力してください。"),
                        types.Part(
                            inline_data=types.Blob(
                                mime_type=file_type,
                                data=file_bytes
                            )
                        )
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
        return json.loads(response.text)

    except Exception as e:
        st.error(f"分析エラー: {e}")
        return None

# --- 画像生成関数 ---
def generate_improved_image(summary, key_details, suggestions_list, aspect_ratio="3:4", doc_type="flyer"):
    formatted_suggestions = "\n".join([f"- {s}" for s in suggestions_list])

    # 1. チラシ用プロンプト
    prompt_flyer = f"""
    Create a **High-Quality Digital Graphic Design Asset** for a government flyer.
    
    **IMPORTANT STYLE RULES:**
    - **DO NOT** generate a photo of a physical paper on a table.
    - **DO NOT** use 3D perspective, shadows, or camera angles.
    - **MUST BE** a flat 2D vector-style layout.
    - **FULL FRAME:** The design should fill the entire image canvas (edge-to-edge).
    - **JAPANESE TEXT:** Use authentic Japanese typography.

    # 1. CONTEXT:
    {summary}

    # 2. REQUIRED TEXT (Content must be exact):
    {key_details}

    # 3. DESIGN IMPROVEMENTS (EAST Framework):
    {formatted_suggestions}

    Visual Style:
    - Clean, minimalist, and professional.
    - High contrast for readability (Universal Design).
    - Friendly and trustworthy color palette.
    - Information hierarchy using font sizes and whitespace.
    """

    # 2. 通知文用プロンプト
    prompt_notice = f"""
    Create a **DIGITAL FLAT IMAGE (PDF EXPORT)** of an Official Government Notice.
    
    **CRITICAL VISUAL CONSTRAINTS (DO NOT IGNORE):**
    1. **NO PHOTOREALISM:** This is NOT a photo of a paper on a desk. Do NOT include shadows, wrinkles, paper texture, background scenery, or camera perspective.
    2. **DIGITAL FLAT 2D:** This must look like a direct digital screenshot or PDF export. Everything must be perfectly flat and aligned.
    3. **PURE WHITE BACKGROUND:** The background color must be Hex #FFFFFF (Pure White). No beige, cream, or off-white paper tones.
    4. **FULL CANVAS / NO CROPPING:** The document borders must match the image borders exactly. Do not cut off the bottom or sides. Show the entire page content.

    **STYLE & CONTENT:**
    - **Structure:** Formal government letterhead (like IRS/Tax Agency).
    - **Font:** Professional Serif (Times) or Sans-Serif (Arial). Black text only.
    - **Layout:**
        - **TOP:** Agency Name/Logo and a **"KEY INFORMATION BOX"** (Bordered box with Deadline, Amount, Action).
        - **MIDDLE:** Main body text (Dense, official explanations).
        - **BOTTOM:** Contact info and next steps.

    # 1. DOCUMENT CONTEXT:
    {summary}

    # 2. REQUIRED KEY DETAILS (Must be accurate):
    {key_details}

    # 3. EAST FRAMEWORK SUGGESTIONS:
    {formatted_suggestions}
    """

    # プロンプトの選択
    target_prompt = prompt_notice if doc_type == "notice" else prompt_flyer
    
    try:
        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=target_prompt,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}], 
                image_config=types.ImageConfig(
                    aspect_ratio=aspect_ratio,
                    image_size="2K"
                )
            )
        )
        for part in response.parts:
            if part.inline_data:
                return Image.open(io.BytesIO(part.inline_data.data)), target_prompt
        return None, target_prompt
    except Exception as e:
        st.error(f"画像生成エラー: {e}")
        return None, target_prompt

# --- 共通コンポーネント関数 ---
def render_tab_content(key_prefix):
    """
    通知文・チラシの各タブの中身を描画する共通関数。
    """
    
    # Session Stateのキー定義
    KEY_RESULT = f"{key_prefix}_audit_result"
    KEY_IMAGE = f"{key_prefix}_generated_image"
    KEY_PROMPT = f"{key_prefix}_last_prompt"
    KEY_UPLOADED_NAME = f"{key_prefix}_last_uploaded"
    KEY_ASPECT = f"{key_prefix}_target_aspect_ratio"

    # 初期化
    if KEY_RESULT not in st.session_state: st.session_state[KEY_RESULT] = None
    if KEY_IMAGE not in st.session_state: st.session_state[KEY_IMAGE] = None
    if KEY_PROMPT not in st.session_state: st.session_state[KEY_PROMPT] = ""
    if KEY_UPLOADED_NAME not in st.session_state: st.session_state[KEY_UPLOADED_NAME] = None
    
    # ==========================================
    #  上段エリア: アップロード & 分析レポート
    # ==========================================
    
    st.subheader("📂 1. ファイルアップロード / 分析実行")
    
    has_result = st.session_state[KEY_RESULT] is not None

    with st.expander("パネルを開く/閉じる", expanded=not has_result):
        uploaded_file = st.file_uploader(
            "ファイルをドラッグ＆ドロップまたは選択", 
            type=["pdf", "png", "jpg", "jpeg"],
            key=f"{key_prefix}_uploader",
            label_visibility="collapsed"
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
                with st.spinner("行動科学の観点から分析中..."):
                    file_bytes = uploaded_file.getvalue()
                    file_type = uploaded_file.type
                    result = analyze_sludge(file_bytes, file_type)
                    if result:
                        st.session_state[KEY_RESULT] = result
                        st.session_state[KEY_IMAGE] = None
                        st.rerun()

    # --- 2. 監査レポート表示 ---
    if st.session_state[KEY_RESULT]:
        result = st.session_state[KEY_RESULT]
        
        st.subheader("📊 2. 評価レポート")
        with st.container(border=True):
            
            score = result.get("total_score", 0)
            c_score_main, c_score_sub = st.columns([1, 3], gap="large")
            
            with c_score_main:
                st.metric("総合評価スコア", f"{score}/100")
            
            with c_score_sub:
                st.write("") 
                st.write("スコアメーター")
                st.progress(score)
                if score >= 80:
                    st.caption("素晴らしい！非常に分かりやすい文書です。")
                elif score >= 60:
                    st.caption("平均的です。いくつかの改善で大きく向上します。")
                else:
                    st.caption("改善の余地が大きいです。抜本的な見直しを推奨します。")
            
            st.divider()

            col_eval, col_improve = st.columns(2, gap="large")

            # 左カラム: 評価
            with col_eval:
                st.markdown("#### 🧐 評価総評")
                st.write(result.get("evaluation_summary"))
                
                st.write("") 
                with st.expander("▼ 詳細評価 (4つのコスト)", expanded=False):
                    def display_cost(label, data, icon):
                        s = 25 - data.get('deduction', 0)
                        st.markdown(f"**{icon} {label} ({s}/25)**") 
                        # ★修正: st.info(..., icon="ℹ️") を st.write() に変更
                        st.write(data.get('comment'))
                        st.write("") # 余白
                        
                    display_cost("探索コスト", result.get("search_cost"), "🔍")
                    display_cost("決断コスト", result.get("decision_cost"), "🤔")
                    display_cost("認知的コスト", result.get("cognitive_cost"), "🧠")
                    display_cost("感情的コスト", result.get("emotional_cost"), "❤️")

            # 右カラム: 改善
            with col_improve:
                st.markdown("#### ✨ 改善の方向性")
                st.write(result.get("improvement_summary"))

                st.write("") 
                with st.expander("▼ 詳細改善案 (EASTフレームワーク)", expanded=False):
                    east = result.get("east_suggestions", {})
                    
                    # ★修正: st.success() を st.write() に変更
                    st.markdown("**😌 Easy (かんたん)**")
                    st.write(east.get('easy'))
                    st.write("") 

                    st.markdown("**✨ Attractive (印象的)**")
                    st.write(east.get('attractive'))
                    st.write("")

                    st.markdown("**🗣️ Social (社会的)**")
                    st.write(east.get('social'))
                    st.write("")

                    st.markdown("**⏱️ Timely (タイムリー)**")
                    st.write(east.get('timely'))
                    st.write("")
        
        # ★修正: 導線デザイン (横並び・一行表示)
        st.markdown("""
        <div style="display: flex; align-items: center; justify-content: center; gap: 10px; padding: 20px; margin-top: 10px; margin-bottom: 10px;">
            <span style="font-size: 2rem;">⬇️</span>
            <span style="color: #555; font-weight: bold; font-size: 1rem;">評価結果に基づき、改善版のデザインを作成します</span>
        </div>
        """, unsafe_allow_html=True)

        # ==========================================
        #  下段エリア: 画像生成設定 & 生成結果
        # ==========================================
        
        col_settings, col_result = st.columns([1, 1], gap="medium")
        
        # --- 左: 生成設定 ---
        with col_settings:
            st.subheader("🎨 3. 画像生成設定")
            st.markdown("AIの抽出内容を確認・編集し、デザインを生成してください。")

            with st.form(f"{key_prefix}_generation_settings_form"):
                edited_summary = st.text_area(
                    "① 文書の概要・本文 (Context & Main Body)", 
                    value=result.get("overall_summary"), 
                    height=150, 
                    key=f"{key_prefix}_input_summary"
                )

                edited_key_details = st.text_area(
                    "② 記載すべき重要情報 (Required Details)", 
                    value=result.get("key_details"), 
                    height=120,
                    key=f"{key_prefix}_input_details"
                )

                east = result.get("east_suggestions", {})
                default_suggestions = (
                    f"Easy: {east.get('easy')}\n"
                    f"Attractive: {east.get('attractive')}\n"
                    f"Social: {east.get('social')}\n"
                    f"Timely: {east.get('timely')}"
                )
                edited_suggestions_text = st.text_area(
                    "③ デザイン改善指示 (EAST Suggestions)", 
                    value=default_suggestions, 
                    height=150,
                    key=f"{key_prefix}_input_suggestions"
                )

                submitted = st.form_submit_button("✨ 設定内容でデザインを生成 / 再生成", type="secondary", use_container_width=True)

            if submitted:
                with st.spinner("Gemini 3 Pro がデザインを生成中..."):
                    suggestions_list = [line.strip() for line in edited_suggestions_text.split('\n') if line.strip()]
                    
                    image, used_prompt = generate_improved_image(
                        edited_summary,
                        edited_key_details,
                        suggestions_list,
                        aspect_ratio=st.session_state[KEY_ASPECT],
                        doc_type=key_prefix 
                    )
                    
                    if image:
                        st.session_state[KEY_IMAGE] = image
                        st.session_state[KEY_PROMPT] = used_prompt
                        st.rerun()

        # --- 右: 生成結果 ---
        with col_result:
            st.subheader("🖼️ 4. 改善されたデザイン案")
            
            if st.session_state[KEY_IMAGE]:
                st.image(st.session_state[KEY_IMAGE], caption="AI生成プレビュー", use_container_width=True)
                
                with st.expander("🔍 プロンプトログ"):
                    st.code(st.session_state[KEY_PROMPT], language="text")

                buf = io.BytesIO()
                st.session_state[KEY_IMAGE].save(buf, format="PNG")
                st.download_button("⬇️ 画像を保存", data=buf.getvalue(), file_name=f"improved_{key_prefix}.png", mime="image/png", key=f"{key_prefix}_dl_btn", use_container_width=True)
            
            elif submitted: 
                 pass 
            
            else:
                st.info("👈 左側の設定を確認し、「生成」ボタンを押してください")

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

    # --- タブの作成 ---
    tab_notice, tab_flyer = st.tabs(["通知文", "チラシ"])

    with tab_notice:
        render_tab_content("notice")

    with tab_flyer:
        render_tab_content("flyer")

if __name__ == "__main__":
    main()