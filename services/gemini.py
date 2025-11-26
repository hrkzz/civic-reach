import io
import json
import os
from typing import Any, Dict, Iterable, List, Tuple

from google import genai
from google.genai import types

from models.schemas import CitizenGuide, SludgeAudit
from utils.file_processing import trim_black_borders


_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is not None:
        return _client

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured in the environment.")

    _client = genai.Client(api_key=api_key)
    return _client


def verify_safety(
    file_bytes: bytes,
    file_type: str,
    initial_json: Dict[str, Any],
    model_schema: Any,
) -> Dict[str, Any]:
    """
    Safety Layer: Uses a second AI pass to verify critical numbers (amounts, dates).
    This 'Double-Check' pattern reduces hallucinations in sensitive government contexts.
    """

    system_prompt = """
    You are a **Government Document Integrity Officer** and a **Safety Layer**.
    **STRICT VERIFICATION RULES:**
    1. **Numbers & Dates:** Check every monetary amount, deadline, and phone number.
    2. **No Invention:** If the extracted JSON contains details NOT found in the document, DELETE them.
    3. **Correction:** If a number is wrong, CORRECT it.
    4. **Structure:** Do not change the JSON keys.
    """
    try:
        client = _get_client()
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Content(
                    parts=[
                        types.Part(
                            text=(
                                "Verify this JSON data against the document:\n"
                                f"{json.dumps(initial_json, ensure_ascii=False)}"
                            )
                        ),
                        types.Part(inline_data=types.Blob(mime_type=file_type, data=file_bytes)),
                    ]
                )
            ],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=model_schema,
                temperature=0.0,
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Verification Error: {e}")
        return initial_json


def analyze_sludge(
    file_bytes: bytes,
    file_type: str,
    target_lang: str = "English",
    doc_type: str = "leaflet",
    status_container: Any | None = None,
) -> Dict[str, Any] | None:
    """
    [Officials] Conducts a comprehensive 'Sludge Audit' on the document.
    Evaluates costs (Search, Decision, etc.) and suggests EAST framework improvements.
    """
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

    **TASK 1: LAYOUT DATA EXTRACTION (Verbatim)**
    Extract the following strictly from the document text.
    - **sender_details**: The full text block identifying the Sender (Agency Name, Department, Address, Return Address). *If strictly generic or not present, return null.*
    - **recipient_details**: The full text block identifying the Recipient (Name, Address, Postcode). *If it is a template/form without a specific recipient, return null.*

    **TASK 2: CRITICAL INSTRUCTION FOR 'KEY DETAILS' (DO NOT OMIT):**
    1. First, determine the **CORE PURPOSE** of this document (e.g., Demand for Payment, Information Update, Legal Summons).
    2. Based on that purpose, extract the **5-10 most critical pieces of information** that the user absolutely needs.
    
    **Examples of adaptability:**
    - If it's a **Tax Bill**: Extract Amount, Deadline, Tax Year, Payment Reference.
    - If it's a **Voting Card**: Extract Polling Station Address, Voting Date, Voter ID requirements.
    - If it's a **License**: Extract License Number, Expiry Date, License Class.
    
    **RULES:**
    - Extract details verbatim.
    - Do NOT summarize IDs or Reference Numbers.
    - Categorize each detail correctly (Deadline, Financial, Identifier, etc.).
    
    Output in JSON.
    """

    prompt_leaflet = (
        f"You are a Public Information Design Specialist. Audit the provided leaflet. {bias_instruction} "
        "Output in JSON."
    )
    system_prompt = prompt_notice if doc_type == "notice" else prompt_leaflet

    try:
        if status_container:
            status_container.markdown(f"🔄 **Phase 1/2:** Auditing & Translating to {target_lang}...")
        client = _get_client()
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Content(
                    parts=[
                        types.Part(text="Strictly audit this document and output in JSON."),
                        types.Part(inline_data=types.Blob(mime_type=file_type, data=file_bytes)),
                    ]
                )
            ],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=SludgeAudit,
                temperature=0.0,
            ),
        )
        initial_result = json.loads(response.text)

        if status_container:
            status_container.markdown("🛡️ **Phase 2/2:** Verifying Risk Data...")
        return verify_safety(file_bytes, file_type, initial_result, SludgeAudit)
    except Exception as e:
        raise RuntimeError(f"Analysis Error: {e}") from e


def analyze_citizen_doc(
    file_bytes: bytes,
    file_type: str,
    target_lang: str = "English",
    status_container: Any | None = None,
) -> Dict[str, Any] | None:
    """
    [Citizens] Translates, simplifies, and extracts actionable steps from the document.
    Identifies specific inputs needed for the user to take action.
    """
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
        if status_container:
            status_container.markdown(
                f"🔄 **Phase 1/2:** Analyzing & Translating to {target_lang}..."
            )
        client = _get_client()
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Content(
                    parts=[
                        types.Part(
                            text="Perform a sludge audit and define necessary user inputs."
                        ),
                        types.Part(inline_data=types.Blob(mime_type=file_type, data=file_bytes)),
                    ]
                )
            ],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=CitizenGuide,
                temperature=0.0,
            ),
        )
        initial_result = json.loads(response.text)

        if status_container:
            status_container.markdown(
                "🛡️ **Phase 2/2:** Self-Correcting Penalties & Deadlines..."
            )
        return verify_safety(file_bytes, file_type, initial_result, CitizenGuide)
    except Exception as e:
        raise RuntimeError(f"Analysis Error: {e}") from e


def generate_user_draft(
    context_summary: str,
    user_answers: Dict[str, str],
    target_lang: str = "English",
) -> str:
    """
    Generates a formal application draft or email inquiry based on user inputs.
    This reduces the 'Cognitive Cost' of writing formal government correspondence.
    """
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
        client = _get_client()
        response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        return response.text
    except Exception as e:
        return f"Error generating draft: {e}"


def generate_improved_image(
    summary: str,
    key_details: str | Iterable[Any],
    suggestions_list: List[str],
    sender_info: str | None = None,
    recipient_info: str | None = None,
    aspect_ratio: str = "3:4",
    doc_type: str = "leaflet",
) -> Tuple[Any | None, str]:
    """
    [Officials] Generates a visual prototype of an improved document.
    Applies EAST framework suggestions to create a cleaner, more accessible layout.
    """
    formatted_suggestions = "\n".join([f"- {s}" for s in suggestions_list])
    formatted_details = ""
    if isinstance(key_details, str):
        formatted_details = key_details
    elif isinstance(key_details, list):
        for item in key_details:
            if hasattr(item, "label") and hasattr(item, "value"):
                formatted_details += f"{item.label}: {item.value}\n"
            elif isinstance(item, dict):
                formatted_details += (
                    f"{item.get('label', 'INFO')}: {item.get('value', '')}\n"
                )

    bias_prompt = (
        "**DESIGN REQUIREMENT:** Ensure diverse representation in any human imagery. "
        "Use high-contrast colors for accessibility (WCAG AA compliance)."
    )

    if sender_info and sender_info.strip():
        header_instruction = (
            "Official Agency Logo alongside the Agency Name and return address. "
            "**MANDATORY: Use this EXACT text for the sender:**\n"
            f">>> {sender_info}"
        )
    else:
        header_instruction = (
            "Official Agency Logo alongside a generic Agency Name. "
            "(Do not invent a specific address if none provided)."
        )

    if recipient_info and recipient_info.strip():
        recipient_instruction = (
            "Place this **EXACT RECIPIENT TEXT** in the standard window envelope position:\n"
            f">>> {recipient_info}"
        )
    else:
        recipient_instruction = (
            "Leave the recipient address block BLANK (as if for a template) or use "
            "'[Recipient Name/Address]' placeholder."
        )

    prompt_notice = f"""
    Create a **DIRECT DIGITAL EXPORT** (e.g., a clean PDF screenshot) of a **FORMAL GOVERNMENT BUSINESS LETTER** (A4 standard layout).
    The final image must be a strictly **2D, full-bleed, borderless** digital graphic. The image canvas represents the document boundaries exactly.

    **VISUAL STYLE RESTRICTIONS (CRITICAL - DO NOT IGNORE):**
    - **ABSOLUTELY NO PHOTOREALISM:** The image must NOT look like a photograph of a physical paper lying on a surface.
    - **NO** shadows, **NO** paper texture, **NO** creases, **NO** curled edges, and **NO** background environment (like a desk).
    - **Background:** **PURE FLAT WHITE HEX #FFFFFF** only, extending precisely to all four edges of the image canvas.
    - **NO** large colorful banners, **NO** excessive icons, **NO** giant QR codes dominating the page.
    - Keep it highly professional, authoritative, and clean.
    - **Typography:** Professional, formal serif or clear sans-serif fonts standard for business correspondence (e.g., Times New Roman, Arial).
    
    **LAYOUT STRUCTURE (Strictly follow standard letter format):**
    1. **Header (Top Right):**
       - Place the Official Agency Logo alongside the Agency Name prominently.
       - Below them, organize the {header_instruction}, **Date**, and relevant **Reference Numbers**.
       - **CRITICAL DESIGN RULE:** Do NOT cram this section. **Prioritize whitespace.** If the input contains general helplines or websites, move them out of this header and place them near the closing or in the Key Information Section to keep the top-right clean and uncluttered.
    2. **Recipient Block (Top Left):** {recipient_instruction}
    3. **Salutation:** Formal greeting (e.g., "Dear [Recipient Name],").
    4. **Main Body:** Clear paragraphs based strictly on the provided SUMMARY text. Use plain English principles.
    5. **Key Information Section:** A distinct, scannable section integrated into the letter's flow (e.g., a clean table with borders, or a bolded list) containing the KEY DETAILS. **Do not make this a giant colored infographic box.**
    6. **Closing:** Formal closing (e.g., "Yours sincerely,") followed by a signature block/official role title.

    {bias_prompt}
    
    **FOOTER (Small, bottom center):** "AI-Generated Draft for Review Only - Not for Circulation"
    
    **INPUT DATA TO INTEGRATE:**
    SUMMARY (Body Text Content): {summary}
    KEY DETAILS (To be placed in the Key Information Section): 
    {formatted_details}
    IMPROVEMENTS TO APPLY (EAST Framework guidelines for tone and clarity): 
    {formatted_suggestions}
    """

    prompt_leaflet = f"""
    Create a **High-Quality Digital Graphic Design Asset** (Digital Poster/Infographic/Flyer).
    The image must be a **full-bleed, borderless** design, filling the entire canvas with **NO extra background or padding**.
    
    **VISUAL STYLE:** Modern, flat design, high contrast, clean vector art style with engaging visual hierarchy. 
    **Background:** Solid color or subtle gradient (No paper texture), extending to **all edges**.

    **CRITICAL CONTENT RULES (DO NOT IGNORE):**
    1. **NO INTERNAL LABELS:** Do **NOT** print the words "EAST", "ATTRACTIVE", "EASY", "SOCIAL", or "TIMELY" on the poster. These are design principles for YOU to follow, not text to display to the citizen.
    2. **QR CODE LIMIT:** Generate **MAXIMUM ONE** clear QR code if a digital action is required. Do not place multiple decorative QR codes.
    3. **CLARITY:** Use icons and visual sections to explain the content, but keep text labels natural (e.g., use "How to Pay" instead of "Easy").

    {bias_prompt}
    
    **FOOTER:** "AI-Generated Draft Image"
    
    **INPUT DATA:**
    CONTEXT: {summary}
    DETAILS: {key_details}
    IMPROVEMENTS TO APPLY (Use these as design instructions, do not print them): 
    {suggestions_list}
    """

    target_prompt = prompt_notice if doc_type == "notice" else prompt_leaflet

    try:
        client = _get_client()
        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=target_prompt,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}],
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio, image_size="2K"),
            ),
        )
        for part in response.parts:
            if part.inline_data:
                raw_image = io.BytesIO(part.inline_data.data)
                from PIL import Image  # Local import to avoid unnecessary dependency at module import time

                image = Image.open(raw_image)
                trimmed_image = trim_black_borders(image)
                return trimmed_image, target_prompt
        return None, target_prompt
    except Exception as e:
        raise RuntimeError(f"Image Generation Error: {e}") from e


