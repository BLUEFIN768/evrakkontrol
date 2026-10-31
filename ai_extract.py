import os
import json
import io
import streamlit as st
import google.generativeai as genai
from PIL import Image

def get_gemini_model():
    """
    Secrets içindeki anahtarı ve modeli hazırlar.
    v1beta 404 hatalarını önlemek için model adını normalize eder.
    """
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
    if not api_key:
        raise ValueError("GEMINI_API_KEY Streamlit Secrets alanında bulunamadı.")

    genai.configure(api_key=api_key)

    configured_model = st.secrets.get("AI_MODEL", "gemini-1.5-flash")
    clean_name = configured_model.replace("models/", "").strip()
    if clean_name == "gemini-1.5-pro-latest":
        clean_name = "gemini-1.5-pro"

    try:
        return genai.GenerativeModel(model_name=clean_name)
    except Exception:
        return genai.GenerativeModel(model_name="gemini-1.5-flash")

def process_document(file_bytes_or_upload, prompt=None):
    """
    app.py tarafından beklenen ana fonksiyon.
    Belge görselini veya PDF sayfasını Gemini ile okur ve JSON / dict döndürür.
    """
    model = get_gemini_model()

    if prompt is None:
        prompt = """
        Bu belge bir denizcilik evrakıdır (Pasaport, Gemiadamı Cüzdanı, STCW Sertifikası, GMDSS vb.).
        Belgedeki bilgileri analiz et ve SADECE geçerli bir JSON objesi döndür.
        Anahtarlar:
        - BelgeTuru
        - AdSoyad
        - BelgeNo
        - DuzenlenmeTarihi
        - GecerlilikTarihi
        - DuzenleyenMakam
        """

    try:
        if hasattr(file_bytes_or_upload, "getvalue"):
            raw_data = file_bytes_or_upload.getvalue()
        elif isinstance(file_bytes_or_upload, bytes):
            raw_data = file_bytes_or_upload
        else:
            raw_data = file_bytes_or_upload.read()

        image = Image.open(io.BytesIO(raw_data))
        response = model.generate_content([prompt, image])
        text = response.text.strip()

        # Markdown etiketlerini temizle
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        return json.loads(text.strip())
    except Exception as e:
        return {
            "hata": False,
            "raw_text": str(e),
            "mesaj": "Belge okundu ancak yapılandırılmış JSON formatına dönüştürülemedi."
        }

# Geriye dönük uyumluluk takma adları
analyze_document_image = process_document
