import os
import json
import io
import streamlit as st
import google.generativeai as genai
from PIL import Image

def get_gemini_model():
    """
    Secrets içinden API anahtarını ve model adını yapılandırır.
    v1beta 404 hatasını önlemek için model adını normalize eder.
    """
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
    if not api_key:
        raise ValueError("GEMINI_API_KEY Streamlit Secrets alanında bulunamadı.")

    genai.configure(api_key=api_key)

    # Secrets'tan model adını al veya kararlı varsayılanı kullan
    configured_model = st.secrets.get("AI_MODEL", "gemini-1.5-flash")
    
    # Model adı normalize etme
    clean_name = configured_model.replace("models/", "").strip()
    if clean_name == "gemini-1.5-pro-latest":
        clean_name = "gemini-1.5-pro"
    
    # Model oluşturma
    try:
        model = genai.GenerativeModel(model_name=clean_name)
        return model
    except Exception:
        # Alternatif doğrudan kararlı model
        return genai.GenerativeModel(model_name="gemini-1.5-flash")

def analyze_document_image(uploaded_file, prompt_instruction=None):
    """
    Yüklenen evrak görselini veya taranmış belgeyi Gemini Vision ile analiz eder.
    """
    model = get_gemini_model()

    if prompt_instruction is None:
        prompt_instruction = """
        Bu belge bir denizcilik/personel evrakıdır (Pasaport, Gemiadamı Cüzdanı, STCW Sertifikası, GMDSS, vb.).
        Belgedeki tüm kritik alanları tespit et ve çıktıyı SADECE geçerli bir JSON objesi olarak ver.
        Bulunması gereken anahtarlar:
        - BelgeTuru
        - AdSoyad
        - BelgeNo
        - DuzenlenmeTarihi
        - GecerlilikTarihi
        - DuzenleyenMakam
        - DigerBilgiler
        JSON dışında hiçbir markdown bloğu veya açıklama yazma.
        """

    try:
        # Dosyayı PIL Image formatına dönüştür
        file_bytes = uploaded_file.getvalue()
        image = Image.open(io.BytesIO(file_bytes))

        response = model.generate_content([prompt_instruction, image])
        response_text = response.text.strip()

        # Markdown ```json ``` etiketlerini temizle
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        response_text = response_text.strip()
        return json.loads(response_text)
    except Exception as e:
        # JSON parse edilemezse ham metni döndür
        return {
            "hata": False,
            "raw_text": getattr(response, "text", str(e)),
            "mesaj": "Analiz tamamlandı ancak format düz metin olarak alındı."
        }

def analyze_multiple_documents(files_list):
    """
    Yüklenen birden çok evrak dosyasını topluca analiz eder.
    """
    results = {}
    for f in files_list:
        try:
            doc_result = analyze_document_image(f)
            results[f.name] = doc_result
        except Exception as err:
            results[f.name] = {"hata": True, "detay": str(err)}
    return results
