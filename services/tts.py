import io
from typing import Any, Dict

from gtts import gTTS

from utils.helpers import clean_markdown


def generate_audio_gtts(text: str, lang: str = "en", tld: str = "com") -> io.BytesIO | None:
    """
    Generates audio using Google Text-to-Speech (gTTS).
    Note: In a production environment, this could be swapped for the Google Cloud TTS API.
    """
    try:
        if not text:
            return None
        tts = gTTS(text=text, lang=lang, tld=tld, slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except Exception as e:
        # Keep services decoupled from Streamlit; log to stdout.
        print(f"TTS Error: {e}")
        return None


def prepare_speech_script(data: Dict[str, Any], mode: str = "official") -> str:
    """Constructs a coherent script for the TTS engine based on the structured JSON data."""
    script = ""
    if mode == "official":
        script += f"Audit Score: {data['total_score']}. "
        script += "Evaluation Summary. "
        script += f"{clean_markdown(data['evaluation_summary'])}. "
        script += "Detailed Evaluation. "
        script += "Search cost. "
        script += f"{clean_markdown(data['search_cost']['comment'])}. "
        script += "Decision cost. "
        script += f"{clean_markdown(data['decision_cost']['comment'])}. "
        script += "Cognitive cost. "
        script += f"{clean_markdown(data['cognitive_cost']['comment'])}. "
        script += "Emotional cost. "
        script += f"{clean_markdown(data['emotional_cost']['comment'])}. "

        east = data.get("east_suggestions", {})
        script += "Improvement Direction. "
        script += f"{clean_markdown(data['improvement_summary'])}. "
        script += "EAST Suggestions."
        script += "Easy. "
        script += f"{clean_markdown(east.get('easy'))}. "
        script += "Attractive. "
        script += f"{clean_markdown(east.get('attractive'))}. "
        script += "Social. "
        script += f"{clean_markdown(east.get('social'))}. "
        script += "Timely. "
        script += f"{clean_markdown(east.get('timely'))}. "

    elif mode == "citizen":
        script += f"{clean_markdown(data['simple_summary'])}. "
        if data.get("risks_and_penalties"):
            for risk in data["risks_and_penalties"]:
                script += f"{clean_markdown(risk)}. "
        script += f"{clean_markdown(data['action_guide_markdown'])}. "
        if data.get("required_documents"):
            script += ", ".join(data["required_documents"]) + ". "
        if data.get("important_dates"):
            script += ", ".join(data["important_dates"]) + ". "
    return script


