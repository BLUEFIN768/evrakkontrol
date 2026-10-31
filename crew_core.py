import os
import openpyxl
import pandas as pd
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime

@dataclass
class Evidence:
    """UAB PDF'inden, AI'dan veya manuel girişten gelen ham belge verisi."""
    code: str
    document_no: Optional[str] = None
    issue_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    verified: bool = False
    raw_text: Optional[str] = None

@dataclass
class Result:
    """evaluate() fonksiyonundan çıkan sonuç objesi."""
    code: str
    status: str
    message: str
    evidence_used: Optional[Evidence] = None

# Şablondaki isimleri sistem kodlarına bağlama haritası
DOC_CODE_MAPPING = {
    "passport": "PASSPORT",
    "seamanbook": "SEAMAN_BOOK",
    "medical examination report": "MEDICAL_CERT",
    "certificate of yellow fewer vaccina": "YELLOW_FEVER",
    "basic safety": "BASIC_SAFETY",
    "competency": "COMPETENCY",
    "gmdss": "GMDSS",
}

def load_rules_from_excel(filepath: str, rank: str, vessel_type: str = "DEFAULT") -> Dict[str, str]:
    """35-101 Excel dosyasından ilgili rütbenin zorunlu ve atamaya bağlı kurallarını çeker."""
    if not os.path.exists(filepath):
        return {}
    
    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb["DOC_MATRIX"] if "DOC_MATRIX" in wb.sheetnames else wb.active
    
    # 9. satırdaki rütbe sütununu tespit et
    target_col = None
    rank_cleaned = rank.strip().lower()
    for col in range(6, ws.max_column + 1):
        val = ws.cell(9, col).value
        if val and str(val).strip().lower() in rank_cleaned:
            target_col = col
            break
            
    # Eğer birebir bulunamazsa varsayılan olarak Master (sütun 6) baz alınır
    if not target_col:
        target_col = 6

    rules = {}
    for row in range(14, ws.max_row + 1):
        doc_name = ws.cell(row, 2).value
        rule_val = ws.cell(row, target_col).value
        
        if doc_name and rule_val:
            rule_str = str(rule_val).strip().upper()
            if rule_str in ["X", "D"]:
                doc_clean = str(doc_name).strip().lower()
                matched_code = None
                for key, code in DOC_CODE_MAPPING.items():
                    if key in doc_clean:
                        matched_code = code
                        break
                if not matched_code:
                    matched_code = str(doc_name).strip().upper().replace(" ", "_")
                rules[matched_code] = rule_str

    # Temel asgari belgeler şablonda yoksa dahi eklenir
    if "PASSPORT" not in rules:
        rules["PASSPORT"] = "X"
    if "SEAMAN_BOOK" not in rules:
        rules["SEAMAN_BOOK"] = "X"
        
    return rules

def _check_dates(evidence: Evidence, rule_type: str) -> str:
    """Tarih geçerlilik kontrolü."""
    if not evidence.issue_date:
        return "REVIEW"
    
    if evidence.code == "YELLOW_FEVER" and not evidence.expiry_date:
        return "OK"
        
    if evidence.expiry_date and evidence.expiry_date < datetime.now():
        return "EXPIRED"
        
    return "OK"

def verify_identity(uab_tckn: str, uab_cuzdan_no: str, personel_tckn: str, personel_cuzdan_no: str) -> bool:
    """TCKN ve Cüzdan No ile kimlik doğrulaması."""
    if not uab_tckn or not personel_tckn:
        return False
    
    tckn_match = str(uab_tckn).strip() == str(personel_tckn).strip()
    cuzdan_match = str(uab_cuzdan_no).strip().upper() == str(personel_cuzdan_no).strip().upper()
    return tckn_match and cuzdan_match

def evaluate(evidences: List[Evidence], rank: str, excel_path: str, is_tanker: bool = False) -> List[Result]:
    """Kuralları değerlendirir."""
    rules = load_rules_from_excel(excel_path, rank)
    results = []
    
    for doc_code, rule_type in rules.items():
        if "TANKER" in doc_code and not is_tanker:
            continue
            
        matched_evidence = next((e for e in evidences if e.code == doc_code), None)
        
        if not matched_evidence:
            if rule_type == 'D':
                results.append(Result(code=doc_code, status="OK", message="Atamaya Bağlı - Belge Yok", evidence_used=None))
            else:
                results.append(Result(code=doc_code, status="MISSING", message="Zorunlu Belge Eksik", evidence_used=None))
            continue
            
        date_status = _check_dates(matched_evidence, rule_type)
        
        if date_status != "OK":
            msg = "Belge Süresi Dolmuş" if date_status == "EXPIRED" else "Tarih Okunamadı veya Eksik"
            results.append(Result(code=doc_code, status=date_status, message=msg, evidence_used=matched_evidence))
            continue
            
        if not matched_evidence.verified:
            results.append(Result(code=doc_code, status="REVIEW", message="Orijinalden Doğrulanmalı", evidence_used=matched_evidence))
            continue
            
        results.append(Result(code=doc_code, status="OK", message="Geçerli", evidence_used=matched_evidence))
        
    return results
