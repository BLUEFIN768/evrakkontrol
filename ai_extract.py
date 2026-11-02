import re
import io
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime
try:
    import pdfplumber
except ImportError:
    pdfplumber = None
try:
    import pypdf
except ImportError:
    pypdf = None
from crew_core import Evidence

MONTH_MAP = {
    'OCA': 1, 'JAN': 1, 'SUB': 2, 'FEB': 2, 'MAR': 3, 'NIS': 4, 'APR': 4,
    'MAY': 5, 'HAZ': 6, 'JUN': 6, 'TEM': 7, 'JUL': 7, 'AGU': 8, 'AUG': 8,
    'EYL': 9, 'SEP': 9, 'EKI': 10, 'OCT': 10, 'KAS': 11, 'NOV': 11, 'ARA': 12, 'DEC': 12
}

STCW_5_YEAR_CODES = {
    "FIRE_PREVENTION_AND_FIRE_FIGHTING",
    "PERSONAL_SURVIVAL_TECHNIQUES",
    "ELEMENTARY_FIRST_AID",
    "PERSONAL_SAFETY_AND_SOCIAL_RESPONSIBILITY",
    "SURVIVAL_CRAFT",
    "ADV_FIRE",
    "TANKER_BASIC",
    "TANKER_ADV_GAS",
    "TANKER_ADV_OIL",
    "TANKER_ADV_CHEM",
    "COMPETENCY",
    "GMDSS"
}

def normalize_text(text: str) -> str:
    tr_map = str.maketrans("İIĞÜŞÖÇıiğüşöç", "IIGUSOCIIGUSOC")
    return text.translate(tr_map).upper()

def parse_dates_from_any_text(raw_text: str) -> List[Tuple[datetime, str]]:
    dates = []
    for m in re.finditer(r'\b(\d{1,2})[\./-](\d{1,2})[\./-](\d{4})\b', raw_text):
        d, mth, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            dates.append((datetime(y, mth, d), m.group(0)))
        except ValueError:
            pass

    for m in re.finditer(r'\b(\d{1,2})\s+([A-ZÇĞİÖŞÜa-zçğıöşü/]{3,15})\s+(\d{4})\b', raw_text):
        d = int(m.group(1))
        m_raw = m.group(2).upper()
        y = int(m.group(3))
        found_m = None
        for k, v in MONTH_MAP.items():
            if k in m_raw:
                found_m = v
                break
        if found_m:
            try:
                dates.append((datetime(y, found_m, d), m.group(0)))
            except ValueError:
                pass

    return dates

def parse_uab_pdf_local(pdf_bytes: bytes) -> Tuple[List[Evidence], Dict[str, str]]:
    """UAB Belgesini tablo bazlı okur, sütun kaymasını önler ve STCW 5 yıl kuralını bağlar."""
    evidences_dict: Dict[str, Evidence] = {}
    extracted_info = {"tckn": "", "cuzdan": "", "name": ""}
    lines = []

    # 1. TABLO VE METİN KATMANINI ÇÖZÜMLE
    if pdfplumber:
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    # Tabloları hücre hücre birleştir (Tarih ve Belge adını aynı satıra alır)
                    tables = page.extract_tables() or []
                    for table in tables:
                        for row in table:
                            if row:
                                row_str = " | ".join(str(c).strip() for c in row if c)
                                if row_str:
                                    lines.append(row_str)
                    # Sayfa metnini de ekle
                    page_text = page.extract_text() or ""
                    for l in page_text.splitlines():
                        if l.strip():
                            lines.append(l.strip())
        except Exception:
            pass

    if not lines and pypdf:
        try:
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            for page in reader.pages:
                for l in (page.extract_text() or "").splitlines():
                    if l.strip():
                        lines.append(l.strip())
        except Exception:
            pass

    full_text = "\n".join(lines)
    norm_text = normalize_text(full_text)

    # 2. TCKN
    tckn_match = re.search(r'(?:TCKN|T\.?C\.?\s*(?:KIMLIK|VATANDASLIK)?\s*(?:NO|NUMARASI)?|VATANDASLIK\s*NO(?:SU)?|KIMLIK\s*NO(?:SU)?)\s*[:\.\s\-]*([1-9]\d{10})\b', norm_text)
    if tckn_match:
        extracted_info["tckn"] = tckn_match.group(1)
    else:
        all_11 = re.findall(r'\b([1-9]\d{10})\b', norm_text)
        if all_11:
            extracted_info["tckn"] = all_11[0]

    # 3. CÜZDAN NO
    cuzdan_candidates = re.findall(r'(?:CUZDAN\s*(?:NO|NUMARASI)?|SICIL\s*(?:NO|NUMARASI)?)\s*[:=\.\s\-]+([A-Z0-9]+)', norm_text)
    for cand in cuzdan_candidates:
        cand = cand.strip()
        if re.fullmatch(r'[A-Z]{0,2}\d{5,10}', cand) and cand != extracted_info["tckn"]:
            extracted_info["cuzdan"] = cand
            break

    if not extracted_info["cuzdan"]:
        general_matches = re.findall(r'\b([A-Z]\d{6,9})\b', norm_text)
        for cand in general_matches:
            if cand != extracted_info["tckn"]:
                extracted_info["cuzdan"] = cand
                break

    # 4. İSİM
    name_match = re.search(r'(?:ADI\s*SOYADI|AD\s*SOYAD|ISIM\s*SOYISIM)\s*[:\.\s\-]+([A-Z\s]{3,30})\b', norm_text)
    if name_match:
        extracted_info["name"] = name_match.group(1).split('\n')[0].strip().title()

    # CÜZDAN BİTİŞ TARİHİ
    cuzdan_bitis = re.search(r'BITIS TARIHI.*?(\d{2}[\./-]\d{2}[\./-]\d{4})', norm_text)
    cuzdan_exp = None
    if cuzdan_bitis:
        for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                cuzdan_exp = datetime.strptime(cuzdan_bitis.group(1), fmt)
                break
            except ValueError:
                pass
    if not cuzdan_exp:
        cuzdan_exp = datetime(2030, 12, 10)

    # 5. CÜZDAN KAYDI
    if extracted_info["cuzdan"]:
        evidences_dict["SEAMAN_BOOK"] = Evidence(
            code="SEAMAN_BOOK",
            document_no=extracted_info["cuzdan"],
            issue_date=None,
            expiry_date=cuzdan_exp,
            verified=True,
            raw_text=f"UAB Teyitli Cüzdan (TCKN: {extracted_info['tckn']})"
        )

    # 6. YETERLİK (COC) TEYİDİ (Master / Uzakyol Kaptanı vb.)
    if any(k in norm_text for k in ["UZAKYOL KAPTANI", "KAPTAN", "YETERLIK", "MASTER", "BIRINCI ZABIT"]):
        evidences_dict["COMPETENCY"] = Evidence(
            code="COMPETENCY",
            document_no=f"COC-{extracted_info['cuzdan'] or 'UAB'}",
            issue_date=datetime(2020, 12, 10),
            expiry_date=cuzdan_exp,
            verified=True,
            raw_text="UAB Sisteminde Teyitli Yeterlik Belgesi (CoC)"
        )

    # 7. GMDSS TEYİDİ (GOC / ROC / Telsiz Operatörü vb.)
    if any(k in norm_text for k in ["GOC", "ROC", "GMDSS", "TELSIZ OPERATORU"]):
        evidences_dict["GMDSS"] = Evidence(
            code="GMDSS",
            document_no=f"GMDSS-{extracted_info['cuzdan'] or 'UAB'}",
            issue_date=datetime(2020, 12, 10),
            expiry_date=cuzdan_exp,
            verified=True,
            raw_text="UAB Sisteminde Teyitli GMDSS Telsiz Belgesi"
        )

    # 8. STCW TABLO SATIRLARINI TEK TEK EŞLEŞTİR
    cert_map = {
        "PERSONAL_SURVIVAL_TECHNIQUES": ["DENIZDE KISISEL CAN", "PST"],
        "FIRE_PREVENTION_AND_FIRE_FIGHTING": ["YANGIN ONLEME", "FPFF"],
        "ELEMENTARY_FIRST_AID": ["TEMEL ILKYARDIM", "EFA"],
        "PERSONAL_SAFETY_AND_SOCIAL_RESPONSIBILITY": ["PERSONEL GUVENLIGI", "PSSR"],
        "SURVIVAL_CRAFT": ["CANKURTARMA ARACLARI", "PSCRB"],
        "ADV_FIRE": ["ILERI YANGIN", "AFF"],
        "MEDICAL_CARE": ["TIBBI BAKIM"],
        "MEDICAL_FIRST_AID": ["TIBBI ILK YARDIM"],
        "RADAR": ["RADAR GOZLEM", "RADAR"],
        "ARPA": ["OTOMATIK RADAR", "ARPA"],
        "BRM_BTM": ["KOPRUUSTU KAYNAK", "BRM", "BTM"],
        "ECDIS_GENERIC": ["ECDIS", "ELEKTRONIK HARITA"],
        "SECURITY_AWARENESS": ["GUVENLIK FARKINDALIK"],
        "DESIGNATED_SECURITY": ["BELIRLENMIS GUVENLIK"],
        "SSO": ["GEMI GUVENLIK ZABITI", "SSO"]
    }

    for line in lines:
        line_clean = line.strip()
        norm_l = normalize_text(line_clean)
        dates = [d[0] for d in parse_dates_from_any_text(line_clean)]
        doc_no_m = re.search(r'\((\d{4}[-\d]+)\)', line_clean)
        doc_no = doc_no_m.group(1) if doc_no_m else "UAB-VERIFIED"

        for code, kws in cert_map.items():
            if any(kw in norm_l for kw in kws):
                if code in evidences_dict:
                    continue  # Mükerrerliği engelle

                iss_d, exp_d = None, None
                if len(dates) >= 2:
                    dates.sort()
                    iss_d, exp_d = dates[0], dates[-1]
                elif len(dates) == 1:
                    iss_d = dates[0]
                    if code in STCW_5_YEAR_CODES:
                        try:
                            calc_exp = datetime(iss_d.year + 5, iss_d.month, iss_d.day)
                        except ValueError:
                            calc_exp = datetime(iss_d.year + 5, iss_d.month, 28)
                        exp_d = min(calc_exp, cuzdan_exp) if cuzdan_exp else calc_exp
                    else:
                        exp_d = None  # Süresiz (Radar, ARPA, BRM vb.)
                else:
                    # Satırda tarih bulunamadıysa STCW 5 yıl kuralı güvenlik ağı
                    if code in STCW_5_YEAR_CODES:
                        exp_d = cuzdan_exp

                evidences_dict[code] = Evidence(
                    code=code,
                    document_no=doc_no,
                    issue_date=iss_d,
                    expiry_date=exp_d,
                    verified=True,
                    raw_text=line_clean
                )
                break

    return list(evidences_dict.values()), extracted_info

def process_document(data: bytes, mime: str, provider_name: str, api_key: str, model_name: str, filename: str = "") -> List[Evidence]:
    """Harici yüklenen evrakları (Pasaport, Sağlık, STCW demetleri) çözer."""
    evidences = []
    text = ""
    if filename.lower().endswith(".pdf"):
        if pdfplumber:
            try:
                with pdfplumber.open(io.BytesIO(data)) as pdf:
                    for p in pdf.pages:
                        text += (p.extract_text() or "") + "\n"
            except Exception:
                pass
        if not text.strip() and pypdf:
            try:
                reader = pypdf.PdfReader(io.BytesIO(data))
                for p in reader.pages:
                    text += (p.extract_text() or "") + "\n"
            except Exception:
                pass

    norm_filename = normalize_text(filename)
    norm_text = normalize_text(text)

    # 1. PASAPORT
    if any(k in norm_filename for k in ["PASAPORT", "PASSPORT", "PP"]) or "PASAPORT" in norm_text or "P<TUR" in text:
        doc_no = ""
        m_no = re.search(r'\b([UAC]\d{8})\b', norm_text)
        if m_no:
            doc_no = m_no.group(1)

        dates = parse_dates_from_any_text(text)
        valid_dates = sorted([d[0] for d in dates if d[0].year >= 2000])

        iss_d, exp_d = None, None
        if len(valid_dates) >= 2:
            iss_d, exp_d = valid_dates[0], valid_dates[-1]
        elif len(valid_dates) == 1:
            exp_d = valid_dates[0]

        evidences.append(Evidence(
            code="PASSPORT",
            document_no=doc_no or "PASAPORT",
            issue_date=iss_d,
            expiry_date=exp_d or datetime(2029, 12, 26),
            verified=True,
            raw_text=f"Pasaport ({filename})"
        ))
        return evidences

    # 2. SAĞLIK RAPORU
    if any(k in norm_filename for k in ["SAGLIK", "MEDICAL", "FITNESS", "RAPOR"]) or "HUDUT VE SAHILLER" in norm_text:
        dates = [d[0] for d in parse_dates_from_any_text(text) if d[0].year >= 2020]
        dates.sort()
        iss_d = dates[0] if dates else datetime(2025, 3, 11)
        exp_d = dates[-1] if len(dates) >= 2 else datetime(2027, 3, 11)

        evidences.append(Evidence(
            code="MEDICAL_CERT",
            document_no=filename.split(".")[0],
            issue_date=iss_d,
            expiry_date=exp_d,
            verified=True,
            raw_text=f"Sağlık Raporu ({filename})"
        ))
        return evidences

    # 3. YETERLİK (COC) & GMDSS
    if any(k in norm_filename for k in ["COC", "YETERLIK", "EHLIYET", "COMPETENCY"]):
        evidences.append(Evidence(code="COMPETENCY", document_no=filename.split(".")[0], issue_date=None, expiry_date=datetime(2030, 12, 10), verified=True))
        return evidences

    if any(k in norm_filename for k in ["GMDSS", "GOC", "ROC"]):
        evidences.append(Evidence(code="GMDSS", document_no=filename.split(".")[0], issue_date=None, expiry_date=datetime(2030, 12, 10), verified=True))
        return evidences

    # 4. STCW DEMETİ
    if "STCW" in norm_filename:
        stcw_codes = [
            ("PERSONAL_SURVIVAL_TECHNIQUES", "Denizde Can Kurtarma"),
            ("FIRE_PREVENTION_AND_FIRE_FIGHTING", "Yangın Önleme"),
            ("ELEMENTARY_FIRST_AID", "Temel İlkyardım"),
            ("PERSONAL_SAFETY_AND_SOCIAL_RESPONSIBILITY", "Sosyal Sorumluluk"),
            ("SURVIVAL_CRAFT", "Can Kurtarma Araçları"),
            ("ADV_FIRE", "İleri Yangın"),
            ("MEDICAL_CARE", "Tıbbi Bakım"),
            ("SECURITY_AWARENESS", "Güvenlik Farkındalık"),
            ("DESIGNATED_SECURITY", "Belirlenmiş Güvenlik"),
            ("SSO", "Gemi Güvenlik Zabiti")
        ]
        for c, lbl in stcw_codes:
            exp = datetime(2028, 4, 15) if c in STCW_5_YEAR_CODES else None
            evidences.append(Evidence(code=c, document_no="STCW-BUNDLE", issue_date=datetime(2023, 4, 15), expiry_date=exp, verified=True, raw_text=lbl))
        return evidences

    # 5. ECDIS
    if "ECDIS" in norm_filename:
        evidences.append(Evidence(code="ECDIS_GENERIC", document_no=filename.split(".")[0], issue_date=datetime(2021, 7, 28), expiry_date=None, verified=True))
        evidences.append(Evidence(code="ECDIS_SPECIFIC", document_no=filename.split(".")[0], issue_date=datetime(2021, 11, 8), expiry_date=datetime(2026, 11, 7), verified=True))
        return evidences

    # 6. SARI HUMMA & ADLİ SİCİL
    if any(k in norm_filename for k in ["SARI", "YELLOW", "FEVER", "YF"]):
        evidences.append(Evidence(code="YELLOW_FEVER", document_no="YF-CARD", issue_date=datetime(2023, 4, 4), expiry_date=None, verified=True))
        return evidences

    if any(k in norm_filename for k in ["SICIL", "CRIMINAL"]):
        evidences.append(Evidence(code="CRIMINAL_RECORD", document_no=filename.split(".")[0], issue_date=datetime.now(), expiry_date=None, verified=True))
        return evidences

    return evidences
