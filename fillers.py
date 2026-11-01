import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment
import docx
from typing import List, Dict, Any
from datetime import datetime

# STCW Denetim Renk Standartları
FILL_GREEN = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
FONT_GREEN = Font(color="006100", bold=True, name="Calibri", size=10)

FILL_RED = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
FONT_RED = Font(color="9C0006", bold=True, name="Calibri", size=10)

FILL_YELLOW = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
FONT_YELLOW = Font(color="9C6500", bold=True, name="Calibri", size=10)

ALIGN_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)

def fill_excel(template_path: str, output_path: str, results: List[Any], personel_info: Dict[str, str]):
    """35-101 Matrix Excel tablosunu orijinal metinleri bozmadan denetler ve renklendirir."""
    wb = openpyxl.load_workbook(template_path)
    ws = wb["DOC_MATRIX"] if "DOC_MATRIX" in wb.sheetnames else wb.active

    # 1. BAŞLIK VE KİMLİK ALANLARI (Tam Koordinat Eşleşmesi)
    ws["C6"] = personel_info.get("vessel", "")       # Gemi Adı (Vessel Name)
    ws["N6"] = personel_info.get("name", "")         # Adı Soyadı (Name & Surname)
    ws["N8"] = personel_info.get("rank", "Master")   # Rütbe (Rank)
    ws["G4"] = personel_info.get("date", datetime.now().strftime("%d.%m.%Y")) # Denetim Tarihi

    # 2. RÜTBE SÜTUNUNU BUL (Master: F=6, Chief Officer: G=7, vb.)
    target_rank = (personel_info.get("rank") or "Master").strip().upper()
    target_col = 6  # Varsayılan Master
    for col in range(6, 24):
        header_val = ws.cell(row=9, column=col).value
        if header_val and target_rank in str(header_val).strip().upper():
            target_col = col
            break

    # 3. KOD - SONUÇ HARİTASI
    res_map = {r.code: r for r in results}

    # 4. SATIRLARI DENETLE (Orijinal Sütun 2 Metinlerine Dokunulmaz!)
    # Kod eşleşmelerini ilgili satır aralıklarına uygula
    code_to_row_map = {
        "PASSPORT": 20,
        "SEAMAN_BOOK": 18,
        "COMPETENCY": 14,
        "GMDSS": 16,
        "MEDICAL_CERT": 22,
        "YELLOW_FEVER": 24,
        "FIRE_PREVENTION_AND_FIRE_FIGHTING": 26,
        "PERSONAL_SURVIVAL_TECHNIQUES": 28,
        "ELEMENTARY_FIRST_AID": 30,
        "PERSONAL_SAFETY_AND_SOCIAL_RESPONSIBILITY": 32,
        "SURVIVAL_CRAFT": 34,
        "SECURITY_AWARENESS": 36,
        "DESIGNATED_SECURITY": 38,
        "SSO": 40,
        "SECURITY_FAMILIARIZATION": 42,
        "ADV_FIRE": 44,
        "MEDICAL_CARE": 46,
        "MEDICAL_FIRST_AID": 48,
        "RADAR": 60,
        "ARPA": 62,
        "BRM_BTM": 64,
        "ECDIS_GENERIC": 74,
        "ECDIS_SPECIFIC": 76,
    }

    for code, row_idx in code_to_row_map.items():
        cell = ws.cell(row=row_idx, column=target_col)
        res = res_map.get(code)

        if res:
            if res.status == "OK":
                cell.value = "Geçerli"
                cell.fill = FILL_GREEN
                cell.font = FONT_GREEN
            elif res.status == "REVIEW":
                cell.value = "Onay Bekliyor"
                cell.fill = FILL_YELLOW
                cell.font = FONT_YELLOW
            elif res.status == "EXPIRED":
                cell.value = "Süresi Dolmuş"
                cell.fill = FILL_RED
                cell.font = FONT_RED
            else:
                cell.value = "Zorunlu Belge Eksik"
                cell.fill = FILL_RED
                cell.font = FONT_RED
        else:
            # Matriste varsa ve sonuç gelmemişse eksik işaretle
            req_val = str(cell.value or "").strip().upper()
            if req_val in ["X", "D"]:
                cell.value = "Zorunlu Belge Eksik"
                cell.fill = FILL_RED
                cell.font = FONT_RED

        cell.alignment = ALIGN_CENTER

    wb.save(output_path)


def fill_word(template_path: str, output_path: str, results: List[Any], personel_info: Dict[str, str], operator_name: str = "Admin"):
    """35-102 Word kontrol listesini doldurur ve Yes/No kutucuklarını denetim durumuna göre işaretler."""
    doc = docx.Document(template_path)
    if not doc.tables:
        doc.save(output_path)
        return

    table = doc.tables[0]
    res_map = {r.code: r for r in results}

    # 1. BAŞLIK BİLGİLERİ (Tablo 0 İlk Satırlar)
    table.cell(0, 3).text = personel_info.get("vessel", "")
    table.cell(0, 9).text = personel_info.get("date", datetime.now().strftime("%d.%m.%Y"))
    table.cell(1, 3).text = personel_info.get("name", "")
    table.cell(1, 9).text = "TUR"  # Bayrak
    table.cell(2, 3).text = personel_info.get("rank", "Master")
    table.cell(2, 9).text = "Generic & Specific"

    # Yardımcı kutucuk belirleyici
    def get_status_box(code: str, is_required: bool = True) -> str:
        res = res_map.get(code)
        if not is_required:
            return "Yes ☐ No☐ N/A☒"
        if res and res.status == "OK":
            return "Yes ☒ No☐ N/A☐"
        return "Yes ☐ No☒ N/A☐"

    # 2. DENETİM MADDELERİNİ İŞARETLE (Row indexleri 35-102.docx standardı)
    # Row 5: National Licence (CoC)
    table.cell(5, 10).text = get_status_box("COMPETENCY")
    
    # Row 6: National STCW Check
    stcw_ok = all(res_map.get(c) and res_map[c].status == "OK" for c in ["FIRE_PREVENTION_AND_FIRE_FIGHTING", "SURVIVAL_CRAFT", "ADV_FIRE"])
    table.cell(6, 10).text = "Yes ☒ No☐ N/A☐" if stcw_ok else "Yes ☐ No☒ N/A☐"

    # Row 7: Flag State Endorsement
    table.cell(7, 10).text = get_status_box("COMPETENCY")

    # Row 10: Diploma
    table.cell(10, 10).text = get_status_box("DIPLOMA", is_required=False)

    # Row 11: Criminal Record (Adli Sicil)
    table.cell(11, 10).text = get_status_box("CRIMINAL_RECORD", is_required=False)

    # Row 18: National Health (Medikal)
    med_res = res_map.get("MEDICAL_CERT")
    med_exp = med_res.evidence_used.expiry_date.strftime("%d.%m.%Y") if (med_res and med_res.evidence_used and med_res.evidence_used.expiry_date) else ""
    table.cell(18, 1).text = f"National Health certificate valid for the contract period? Expire date : {med_exp}"
    table.cell(18, 10).text = get_status_box("MEDICAL_CERT")

    # Row 21: ECDIS Specific
    table.cell(21, 10).text = get_status_box("ECDIS_SPECIFIC")

    # Row 22: ECDIS Generic (IMO Model)
    table.cell(22, 10).text = get_status_box("ECDIS_GENERIC")

    # Row 23: BTM / BRM (Son 5 yıl denetimli)
    table.cell(23, 10).text = get_status_box("BRM_BTM")

    # 3. YÖNETİM ONAYI VE OPERATÖR İMZASI (Row 30: Crew Operator)
    table.cell(30, 2).text = operator_name
    table.cell(30, 6).text = datetime.now().strftime("%d.%m.%Y")
    table.cell(30, 7).text = "Approved ☒   Rejected☐\nReason to rejection :"

    doc.save(output_path)
