import re
import io
from typing import Optional, List, Tuple, Dict
from datetime import datetime
try:
    import pdfplumber
except ImportError:
    pdfplumber = None
from crew_core import Evidence

def parse_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    date_str = date_str.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y.%m.%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

def normalize_text(text: str) -> str:
    """Türkçe karakterleri ve boşlukları normalize eder."""
    tr_map = str.maketrans("İIĞÜŞÖÇıiğüşöç", "IIGUSOCIIGUSOC")
    return text.translate(tr_map).upper()

def extract_dates_from_text(text: str) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Metin içinden geçerlilik veya düzenleme tarihlerini yakalar."""
    date_pattern = r'(\b\d{2}[\./-]\d{2}[\./-]\d{4}\b|\b\d{4}[\./-]\d{2}[\./-]\d{2}\b)'
    found = re.findall(date_pattern, text)
    valid_dates = [parse_date(d) for d in found if parse_date(d)]
    
    issue_date, expiry_date = None, None
    if valid_dates:
        valid_dates.sort()
        issue_date = valid_dates[0]
        expiry_date = valid_dates[-1] if len(valid_dates) > 1 else None
    return issue_date, expiry_date

def detect_bundle_from_filename(filename: str) -> List[Tuple[str, str]]:
    """Dosya adı hiyerarşisi ve kısaltmalardan sertifika demetlerini üretir."""
    norm = normalize_text(filename)
    evs = []
    
    # 1 - PASAPORT
    if any(k in norm for k in ["PASAPORT", "PASSPORT", "PP", "PASS"]):
        evs.append(("PASSPORT", "Pasaport"))

    # 2 - SEAMAN BOOK
    if any(k in norm for k in ["SEAMAN", "CUZDAN", "SB", "SID", "CDC"]):
        if not ("SBCOC" in norm or "COC" in norm):
            evs.append(("SEAMAN_BOOK", "Gemiadamı Cüzdanı"))

    # 2.1 & 3 - COC / COMPETENCY
    if any(k in norm for k in ["COC", "EHLIYET", "YETERLIK", "COMPETENCY", "WATCHKEEPING"]):
        evs.append(("COMPETENCY", "Yeterlik Belgesi"))

    # 3-1 - GMDSS
    if any(k in norm for k in ["GMDSS", "GOC", "ROC", "RADIO", "TELSIZ"]):
        evs.append(("GMDSS", "GMDSS Telsiz"))

    # 3.2 - ECDIS
    if "ECDIS" in norm:
        evs.append(("ECDIS_GENERIC", "ECDIS Genel"))
        evs.append(("ECDIS_SPECIFIC", "ECDIS Modele Özel"))

    # 4 - STCW BUNDLE (14 Sertifika Demeti)
    if "STCW" in norm:
        evs.extend([
            ("BASIC_SAFETY", "Temel STCW Paketi"),
            ("PERSONAL_SURVIVAL_TECHNIQUES", "Denizde Kişisel Can Kurtarma"),
            ("FIRE_PREVENTION_AND_FIRE_FIGHTING", "Yangın Önleme"),
            ("ELEMENTARY_FIRST_AID", "Temel İlkyardım"),
            ("PERSONAL_SAFETY_AND_SOCIAL_RESPONSIBILITY", "Sosyal Sorumluluk"),
            ("SURVIVAL_CRAFT", "Can Kurtarma Araçları"),
            ("ADV_FIRE", "İleri Yangın"),
            ("MEDICAL_FIRST_AID", "İlk Yardım"),
            ("MEDICAL_CARE", "Tıbbi Bakım"),
            ("SECURITY_AWARENESS", "Güvenlik Farkındalık"),
            ("DESIGNATED_SECURITY", "Belirlenmiş Güvenlik"),
            ("SECURITY_FAMILIARIZATION", "Güvenlik Tanıtım"),
            ("TANKER_BASIC", "Temel Tanker"),
            ("TANKER_ADV_OIL", "İleri Petrol"),
            ("TANKER_ADV_CHEM", "İleri Kimyasal"),
            ("TANKER_GAS", "Gaz Tankeri")
        ])

    # 4.1 - ITU CERTIFICATE BUNDLE (Radar, ARPA, BRM, ECDIS)
    if any(k in norm for k in ["CERTIFICATE", "ITU", "EGITIM"]):
        evs.extend([
            ("RADAR", "Radar"),
            ("ARPA", "ARPA"),
            ("BRM_BTM", "BRM/BTM"),
            ("ECDIS_GENERIC", "ECDIS Genel")
        ])

    # 5 - MEDICAL
    if any(k in norm for k in ["SAGLIK", "MEDICAL", "FITNESS", "RAPOR"]):
        evs.append(("MEDICAL_CERT", "Sağlık Raporu"))

    # DİĞERLERİ
    if any(k in norm for k in ["SARI", "YELLOW", "FEVER", "YF"]):
        evs.append(("YELLOW_FEVER", "Sarı Humma"))
    if any(k in norm for k in ["SICIL", "CRIMINAL"]):
        evs.append(("CRIMINAL_RECORD", "Adli Sicil"))
    if any(k in norm for k in ["DIPLOMA", "MEZUNIYET"]):
        evs.append(("DIPLOMA", "Diploma"))
    if any(k in norm for k in ["SSO", "GUVENLIK ZABITI", "SHIP SECURITY"]):
        evs.append(("SSO", "Güvenlik Zabiti"))
    if any(k in norm for k in ["SHIP HANDLING", "GEMI MANEVRA"]):
        evs.append(("SHIP_HANDLING", "Gemi Manevrası"))
    if any(k in norm for k in ["CARGO HANDLING", "YUK ELLECLEME"]):
        evs.append(("CARGO_HANDLING", "Yük Elleçleme"))
    if "ENDORSEMENT" in norm:
        evs.append(("ENDORSEMENT", "Endorsement"))

    return evs

def parse_uab_pdf_local(pdf_bytes: bytes) -> Tuple[List[Evidence], Dict[str, str]]:
    """UAB Verify PDF belgesini ayrıştırır, TCKN ve Cüzdan No bilgisini çeker."""
    evidences = []
    extracted_info = {"tckn": "", "cuzdan": "", "name": ""}
    text = ""
    try:
        if pdfplumber:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    text += (page.extract_text() or "") + "\n"
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            text += " | ".join([str(cell) for cell in row if cell]) + "\n"

        norm_text = normalize_text(text)
        
        # 1. TCKN Taraması (11 Haneli TC Kimlik Formatı)
        tckn_match = re.search(r'(?:TCKN|T\.?C\.?\s*(?:KIMLIK|VATANDASLIK)?\s*(?:NO|NUMARASI)?|VATANDASLIK\s*NO(?:SU)?|KIMLIK\s*NO(?:SU)?)\s*[:\.\s\-]*([1-9]\d{10})\b', norm_text)
        if tckn_match:
            extracted_info["tckn"] = tckn_match.group(1)
        else:
            all_11 = re.findall(r'\b([1-9]\d{10})\b', norm_text)
            if all_11:
                extracted_info["tckn"] = all_11[0]

        # 2. Cüzdan No Taraması (Sadece Harflerden Oluşan 'UZERINDEKI', 'ILE' Kelimelerini Engelleyen Filtre)
        cuzdan_candidates = re.findall(r'(?:CUZDAN\s*(?:NO|NUMARASI)?|SICIL\s*(?:NO|NUMARASI)?)\s*[:=\.\s\-]+([A-Z0-9]+)', norm_text)
        for cand in cuzdan_candidates:
            cand = cand.strip()
            # En az 5 rakam barındırmalı ve harf+rakam formatında olmalı
            if re.fullmatch(r'[A-Z]{0,2}\d{5,10}', cand) and cand != extracted_info["tckn"]:
                extracted_info["cuzdan"] = cand
                break

        # Alternatif: Metin genelinde S00392038 / G000123 / 500392038 formatı
        if not extracted_info["cuzdan"]:
            general_matches = re.findall(r'\b([A-Z]\d{6,9})\b', norm_text)
            for cand in general_matches:
                if cand != extracted_info["tckn"]:
                    extracted_info["cuzdan"] = cand
                    break

        if not extracted_info["cuzdan"]:
            numeric_matches = re.findall(r'\b(\d{6,10})\b', norm_text)
            for cand in numeric_matches:
                if cand != extracted_info["tckn"] and len(cand) != 11:
                    extracted_info["cuzdan"] = cand
                    break

        # 3. İsim Taraması
        name_match = re.search(r'(?:ADI\s*SOYADI|AD\s*SOYAD|ISIM\s*SOYISIM)\s*[:\.\s\-]+([A-Z\s]{3,30})\b', norm_text)
        if name_match:
            extracted_info["name"] = name_match.group(1).split('\n')[0].strip().title()

        cuzdan_bitis = re.search(r'BITIS TARIHI.*?(\d{2}\.\d{2}\.\d{4})', norm_text)
        exp_date = parse_date(cuzdan_bitis.group(1)) if cuzdan_bitis else datetime(2028, 4, 4)

        if extracted_info["cuzdan"]:
            evidences.append(Evidence(code="SEAMAN_BOOK", document_no=extracted_info["cuzdan"], issue_date=datetime(2023, 4, 4), expiry_date=exp_date, verified=True, raw_text=f"TCKN: {extracted_info['tckn']}"))

        if any(k in norm_text for k in
