import openpyxl
from dataclasses import dataclass
from typing import Optional, List, Dict
from datetime import datetime
import re

@dataclass
class Evidence:
    code: str
    document_no: str
    issue_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    verified: bool = False
    raw_text: str = ""

@dataclass
class Result:
    code: str
    status: str
    message: str
    evidence_used: Optional[Evidence] = None

def normalize_text(text: str) -> str:
    tr_map = str.maketrans("İIĞÜŞÖÇıiğüşöç", "IIGUSOCIIGUSOC")
    return text.translate(tr_map).upper()

def map_excel_name_to_code(doc_name: str) -> Optional[str]:
    """Excel 35-101 matrisindeki satır başlıklarını standart sistem kodlarına eşler."""
    norm = normalize_text(doc_name)
    
    # 1. Pasaport, Cüzdan, Sağlık
    if "PASSPORT" in norm or "PASAPORT" in norm: return "PASSPORT"
    if "SEAMAN" in norm or "CUZDAN" in norm: return "SEAMAN_BOOK"
    if "MEDICAL CERTIFICATE" in norm or "SAGLIK" in norm: return "MEDICAL_CERT"
    if "YELLOW" in norm or "SARI" in norm: return "YELLOW_FEVER"
    if "COMPETENCY" in norm or "YETERLIK" in norm or "EHLIYET" in norm: return "COMPETENCY"
    if "GMDSS" in norm or "TELSIZ" in norm: return "GMDSS"

    # 2. Temel STCW Alt Sertifikaları
    if "FIRE PREVENTION" in norm or "YANGIN ONLEME" in norm: return "FIRE_PREVENTION_AND_FIRE_FIGHTING"
    if "PERSONAL SURVIVAL" in norm or "DENIZDE KISISEL CAN" in norm: return "PERSONAL_SURVIVAL_TECHNIQUES"
    if "ELEMENTARY FIRST AID" in norm or "TEMEL ILKYARDIM" in norm: return "ELEMENTARY_FIRST_AID"
    if "PERSONAL SAFETY AND SOCIAL" in norm or "PERSONEL GUVENLIGI" in norm: return "PERSONAL_SAFETY_AND_SOCIAL_RESPONSIBILITY"
    if "SURVIVAL CRAFT" in norm or "CANKURTARMA ARACLARI" in norm: return "SURVIVAL_CRAFT"
    if "BASIC SAFETY" in norm or "TEMEL GUVENLIK" in norm: return "BASIC_SAFETY"

    # 3. İleri STCW & Kaynak Yönetimi
    if "ADVANCED FIRE" in norm or "ILERI YANGIN" in norm: return "ADV_FIRE"
    if "MEDICAL CARE" in norm or "TIBBI BAKIM" in norm: return "MEDICAL_CARE"
    if "MEDICAL FIRST AID" in norm or "TIBBI ILK YARDIM" in norm: return "MEDICAL_FIRST_AID"
    if "RADAR OBSERVATION" in norm or "RADAR GOZLEM" in norm: return "RADAR"
    if "AUTOMATIC RADAR" in norm or "ARPA" in norm: return "ARPA"
    if "BRIDGE TEAM" in norm or "BRIDGE RESOURCE" in norm or "KOPRUUSTU KAYNAK" in norm or "BTM" in norm or "BRM" in norm: return "BRM_BTM"
    if "ENGINE ROOM" in norm or "MAKINE DAIRESI" in norm: return "ERM"
    if "NAVIGATIONAL WATCHKEEPING" in norm or "SEYIR VARDIYASI" in norm: return "NAV_WATCH"
    if "HIGH VOLTAGE" in norm or "YUKSEK VOLTAJ" in norm: return "HIGH_VOLTAGE"

    # 4. ECDIS
    if "ECDIS (SPECIFIC)" in norm or "SPECIFIC ECDIS" in norm: return "ECDIS_SPECIFIC"
    if "ECDIS" in norm: return "ECDIS_GENERIC"

    # 5. Güvenlik
    if "SECURITY AWARENESS" in norm or "FARKINDALIK" in norm: return "SECURITY_AWARENESS"
    if "DESIGNATED SECURITY" in norm or "BELIRLENMIS GUVENLIK" in norm: return "DESIGNATED_SECURITY"
    if "SHIP SECURITY OFFICER" in norm or "GEMI GUVENLIK ZABITI" in norm or "SSO" in norm: return "SSO"
    if "FAMILIRIZATION" in norm or "TANITIM" in norm: return "SECURITY_FAMILIARIZATION"

    # 6. Tanker
    if "BASIC TRAINING FOR GAS" in norm: return "TANKER_GAS"
    if "ADVANCED TRAINING FOR GAS" in norm: return "TANKER_GAS"
    if "BASIC TRAINING FOR OIL" in norm: return "TANKER_BASIC"
    if "ADVANCED TRAINING FOR OIL" in norm: return "TANKER_ADV_OIL"
    if "ADVANCED TRAINING FOR CHEM" in norm: return "TANKER_ADV_CHEM"

    # 7. Manevra, Elleçleme, Endorsement
    if "SHIP HANDLING" in norm or "GEMI MANEVRA" in norm: return "SHIP_HANDLING"
    if "CARGO HANDLING" in norm or "YUK ELLECLEME" in norm: return "CARGO_HANDLING"
    if "ENDORSEMENT" in norm: return "ENDORSEMENT"
    if "CRIMINAL" in norm or "SICIL" in norm: return "CRIMINAL_RECORD"
    if "DIPLOMA" in norm: return "DIPLOMA"

    return None

def load_rules_from_excel(filepath: str, rank: str, is_tanker: bool = False) -> Dict[str, str]:
    """Excel'den seçili rütbeye göre kural haritası çıkarır."""
    try:
        wb = openpyxl.load_workbook(filepath, data_only=True)
        ws = wb["DOC_MATRIX"] if "DOC_MATRIX" in wb.sheetnames else wb.active
        
        norm_rank = normalize_text(rank)
        rank_col = 6  # Varsayılan Master
        
        # 9. Satırda rütbe sütununu ara
        for col in range(6, ws.max_column + 1):
            val = ws.cell(row=9, column=col).value
            if val and normalize_text(str(val)) in norm_rank:
                rank_col = col
                break
                
        rules = {}
        for row in range(14, ws.max_row + 1):
            doc_name = ws.cell(row=row, column=2).value
            rule_val = ws.cell(row=row, column=rank_col).value
            
            if doc_name and rule_val:
                rule_str = str(rule_val).strip().upper()
                if rule_str in ["X", "D"]:
                    code = map_excel_name_to_code(str(doc_name))
                    if code and code not in rules:
                        rules[code] = rule_str
                        
        # 1-13 satırlarındaki temel kimlik gereksinimleri
        if "PASSPORT" not in rules: rules["PASSPORT"] = "X"
        if "SEAMAN_BOOK" not in rules: rules["SEAMAN_BOOK"] = "X"
        if "MEDICAL_CERT" not in rules: rules["MEDICAL_CERT"] = "X"
        if "YELLOW_FEVER" not in rules: rules["YELLOW_FEVER"] = "D"

        return rules
    except Exception as e:
        print(f"Excel kural okuma hatası: {e}")
        return {}

def _check_dates(evidence: Evidence) -> str:
    if not evidence.issue_date and evidence.code != "YELLOW_FEVER":
        return "REVIEW"
    if evidence.code == "YELLOW_FEVER":
        return "OK"
    if evidence.expiry_date and evidence.expiry_date < datetime.now():
        return "EXPIRED"
    return "OK"

def evaluate(evidences: List[Evidence], rank: str, excel_path: str, is_tanker: bool = False) -> List[Result]:
    rules = load_rules_from_excel(excel_path, rank, is_tanker)
    results = []

    # Evidence kodlarını hızlı arama kümesine al
    evidence_map = {}
    for ev in evidences:
        evidence_map[ev.code] = ev

    # Üst paket eşleşmeleri (BASIC_SAFETY varsa alt 4 modülü de sağlar)
    basic_safety_modules = [
        "PERSONAL_SURVIVAL_TECHNIQUES",
        "FIRE_PREVENTION_AND_FIRE_FIGHTING",
        "ELEMENTARY_FIRST_AID",
        "PERSONAL_SAFETY_AND_SOCIAL_RESPONSIBILITY"
    ]

    for req_code, rule_type in rules.items():
        if "TANKER" in req_code and not is_tanker:
            continue

        matched_evidence = evidence_map.get(req_code)

        # Eğer tekil alt STCW yoksa ama BASIC_SAFETY varsa geçerli kabul et
        if not matched_evidence and req_code in basic_safety_modules:
            matched_evidence = evidence_map.get("BASIC_SAFETY")

        # RADAR / ARPA karşılıklı karşılama
        if not matched_evidence and req_code in ["RADAR", "ARPA"]:
            matched_evidence = evidence_map.get("RADAR") or evidence_map.get("ARPA")

        if not matched_evidence:
            if rule_type == 'D':
                results.append(Result(code=req_code, status="OK", message="Atamaya Bağlı - Belge Yok", evidence_used=None))
            else:
                results.append(Result(code=req_code, status="MISSING", message="Zorunlu Belge Eksik", evidence_used=None))
            continue

        date_status = _check_dates(matched_evidence)
        if date_status != "OK":
            msg = "Belge Süresi Dolmuş" if date_status == "EXPIRED" else "Tarih Eksik/Doğrulanmalı"
            results.append(Result(code=req_code, status=date_status, message=msg, evidence_used=matched_evidence))
            continue

        # Harici evrak doğrudan onaylı değilse inceleme durumu
        if not matched_evidence.verified:
            results.append(Result(code=req_code, status="REVIEW", message="Orijinalden Doğrulanmalı", evidence_used=matched_evidence))
            continue

        results.append(Result(code=req_code, status="OK", message="Geçerli", evidence_used=matched_evidence))

    return results
