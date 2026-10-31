import os
import json
import io
import streamlit as st
import google.generativeai as genai
from PIL import Image

def get_gemini_model():
    """
    Secrets içindeki anahtarı ve modeli hazırlar.
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

def process_document(*args, **kwargs):
    """
    app.py'den gelen tüm pozisyonel ve anahtar kelime argümanlarını (*args, **kwargs) kabul eder.
    Böylece parametre sayısı uyumsuzluğu hatası tamamen engellenir.
    """
    # İlk argüman genellikle dosya/dosya listesidir
    file_input = args[0] if len(args) > 0 else kwargs.get("file", kwargs.get("document", None))
    
    # İkinci veya sonraki argümanlar (prompt, model, api_key vb.)
    prompt = None
    for item in args[1:]:
        if isinstance(item, str):
            prompt = item
            break
            
    if prompt is None:
        prompt = kwargs.get("prompt", """
        Bu belge bir denizcilik evrakıdır (Pasaport, Gemiadamı Cüzdanı, STCW Sertifikası, GMDSS vb.).
        Belgedeki bilgileri analiz et ve SADECE geçerli bir JSON objesi döndür.
        Anahtarlar:
        - BelgeTuru
        - AdSoyad
        - BelgeNo
        - DuzenlenmeTarihi
        - GecerlilikTarihi
        - DuzenleyenMakam
        """)

    model = get_gemini_model()

    try:
        if hasattr(file_input, "getvalue"):
            raw_data = file_input.getvalue()
        elif isinstance(file_input, bytes):
            raw_data = file_input
        elif hasattr(file_input, "read"):
            raw_data = file_input.read()
        else:
            raw_data = file_input

        image = Image.open(io.BytesIO(raw_data))
        response = model.generate_content([prompt, image])
        text = response.text.strip()

        # Markdown etiketlerini ayıkla
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
            "mesaj": "Belge okundu ancak JSON formatına dönüştürülemedi."
        }

# Geriye dönük uyumluluk takma adları
analyze_document_image = process_document
