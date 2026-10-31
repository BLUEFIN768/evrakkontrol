import re
from typing import Optional
from datetime import datetime
from crew_core import Evidence

CODES = [
    "PASSPORT", "SEAMAN_BOOK", "MEDICAL_CERT", 
    "YELLOW_FEVER", "BASIC_SAFETY", "GMDSS", "COMPETENCY"
]

def detect_code(filename: str) -> str:
    """Dosya adındaki anahtar kelimelerden belge türünü tespit eder."""
    fn = filename.upper()
    if any(k in fn for k in ["PASAPORT", "PASSPORT", "PAS"]):
        return "PASSPORT"
    if any(k in fn for k in ["SEAMAN", "CUZDAN", "CÜZDAN", "BOOK"]):
        return "SEAMAN_BOOK"
    if any(k in fn for k in ["SAGLIK", "SAĞLIK", "MEDICAL", "FITNESS"]):
        return "MEDICAL_CERT"
    if any(k in fn for k in ["SARI", "YELLOW", "HUMMA", "FEVER"]):
        return "YELLOW_FEVER"
    if any(k in fn for k in ["STCW", "SAFETY", "BASIC", "GUVENLIK", "GÜVENLİK"]):
        return "BASIC_SAFETY"
    if any(k in fn for k in ["GMDSS", "RADIO", "TELSİZ", "GOC", "ROC"]):
        return "GMDSS"
    if any(k in fn for k in ["EHLIYET", "EHLİYET", "COMPETENCY", "YETERLIK", "YETERLİLİK", "COC"]):
        return "COMPETENCY"
    return "UNKNOWN"

def process_document(data: bytes, mime: str, provider_name: str, api_key: str, model_name: str, filename: str = "") -> Evidence:
    """Google API'ye gitmeden, yerel sunucuda anında kanıt nesnesi üretir."""
    code = detect_code(filename)
    
    # Dosya adından temiz numara çıkarma
    doc_no = re.sub(r"[^\w\s-]", "", filename.split(".")[0]).strip()
    
    # Standart geçerlilik aralığı (Denetim sekmesinde düzenlenebilir)
    issue_dt = datetime(2024, 1, 1)
    expiry_dt = datetime(2028, 12, 31)
    
    return Evidence(
        code=code,
        document_no=doc_no,
        issue_date=issue_dt,
        expiry_date=expiry_dt,
        verified=False,
        raw_text=f"Yerel okuyucu tarafından dosya adı üzerinden eşleştirildi: {filename}"
    )
