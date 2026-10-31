import json
import re
from typing import List, Dict, Callable
from datetime import datetime
import google.generativeai as genai
from crew_core import Evidence

CODES = ["PASSPORT", "SEAMAN_BOOK", "MEDICAL_CERT", "YELLOW_FEVER", "BASIC_SAFETY", "GMDSS", "COMPETENCY"]

PROMPT = f"""
Sen bir denizcilik evrak analiz uzmanısın. Aşağıdaki belgeyi (PDF veya Görsel) incele ve sadece geçerli bir JSON çıktısı üret:
{{
  "code": "Aşağıdaki listeden en uygun belge kodunu seç: {', '.join(CODES)}",
  "document_no": "Belge numarası veya TCKN",
  "issue_date": "YYYY-MM-DD formatında veriliş tarihi (yoksa null)",
  "expiry_date": "YYYY-MM-DD formatında geçerlilik bitiş tarihi (yoksa null)"
}}
Cevapta sadece saf JSON ver, markdown (```) veya fazladan hiçbir açıklama ekleme.
"""

def extract_with_gemini(data: bytes, mime: str, api_key: str, model_name: str) -> str:
    """Gemini API ile belgeyi analiz eder."""
    genai.configure(api_key=api_key)
    
    # Model adı güvenliği
    target_model = model_name if model_name else "gemini-1.5-flash"
    if target_model.startswith("models/"):
        target_model = target_model.replace("models/", "")
        
    try:
        model = genai.GenerativeModel(target_model)
        content_parts = [PROMPT, {"mime_type": mime, "data": data}]
        response = model.generate_content(content_parts)
        return response.text
    except Exception:
        # Alternatif fallback
        model = genai.GenerativeModel("gemini-1.5-flash")
        content_parts = [PROMPT, {"mime_type": mime, "data": data}]
        response = model.generate_content(content_parts)
        return response.text

PROVIDERS: Dict[str, Callable[[bytes, str, str, str], str]] = {
    "gemini": extract_with_gemini
}

def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d"):
        try:
            return datetime.strptime(str(date_str).strip(), fmt)
        except ValueError:
            pass
    return None

def process_document(data: bytes, mime: str, provider_name: str, api_key: str, model_name: str) -> Evidence:
    """Seçilen AI sağlayıcısı ile evrakı okur ve Evidence nesnesi oluşturur."""
    if provider_name not in PROVIDERS:
        raise ValueError(f"Desteklenmeyen AI sağlayıcısı: {provider_name}")
        
    extract_func = PROVIDERS[provider_name]
    raw_response = extract_func(data, mime, api_key, model_name)
    
    # JSON bloklarını temizle
    clean_json = re.sub(r"```(json)?", "", raw_response).strip()
    
    try:
        parsed_data = json.loads(clean_json)
    except Exception:
        # Fallback basit eşleme
        parsed_data = {"code": "UNKNOWN", "issue_date": None, "expiry_date": None}

    code = parsed_data.get("code", "UNKNOWN")
    if code not in CODES:
        # Metin içi tahmin
        for c in CODES:
            if c in str(code).upper():
                code = c
                break

    issue_dt = parse_date(parsed_data.get("issue_date"))
    expiry_dt = parse_date(parsed_data.get("expiry_date"))
    
    return Evidence(
        code=code,
        document_no=parsed_data.get("document_no"),
        issue_date=issue_dt,
        expiry_date=expiry_dt,
        verified=False,
        raw_text=clean_json
    )
