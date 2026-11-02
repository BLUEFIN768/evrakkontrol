import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment
import docx
from typing import List, Dict, Any
from datetime import datetime

FILL_GREEN = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
FONT_GREEN = Font(color="006100", bold=True, name="Calibri", size=10)

FILL_RED = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
FONT_RED = Font(color="9C0006", bold=True, name="Calibri", size=10)

FILL_YELLOW = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
FONT_YELLOW = Font(color="9C6500", bold=True, name="Calibri", size=10)

ALIGN_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)

RANK_TO_COLUMN_MAP = {
    "MASTER": 6,
    "CHIEF OFFICER": 7,
    "2ND OFFICER": 8,
    "2 ND OFFICER": 8,
    "3RD OFFICER": 9,
    "3 RD OFFICER": 9,
    "CHIEF ENGINEER": 10,
    "2ND ENGINEER": 11,
    "2 ND ENGINEER": 11,
    "3RD ENGINEER": 12,
    "ELECTRICIAN": 13,
    "BOSUN": 14,
    "PUMPMAN": 15,
    "AB": 16,
    "ABLE SEAMAN": 16,
    "ABLE SEAFARER DECK": 16,
    "OS": 17,
    "O/S": 17,
    "ORDINARY SEAMAN": 17,
    "FITTER": 18,
    "OILER": 19,
    "ABLE SEAFARER ENGINE": 19,
    "MOTORMAN": 19,
    "WIPER": 20,
    "COOK": 21,
    "STEWARD": 22,
    "CADET": 23
}

CODE_TO_ROW_MAP = {
    "COMPETENCY": 14,
    "SEAMAN_BOOK": 16,
    "PASSPORT": 18,
    "MEDICAL_CERT": 20,
    "YELLOW_FEVER": 22,
    "GMDSS": 24,
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
    "TANKER_BASIC": 50,
    "TANKER_ADV_GAS": 52,
    "TANKER_BASIC_OIL_CHEM": 54,
    "TANKER_ADV_OIL": 56,
    "TANKER_ADV_CHEM": 58,
    "RADAR": 60,
    "ARPA": 62,
    "BRM_BTM": 64,
    "ERM": 66,
    "NAV_WATCH": 68,
    "ENG_WATCH": 70,
    "HIGH_VOLTAGE": 72,
    "ECDIS_GENERIC": 74,
    "ECDIS_SPECIFIC": 76,
    "SHIP_HANDLING": 78,
    "CARGO_HANDLING": 80,
    "ENDORSEMENT": 82
}

def fill_excel(template_path: str, output_path: str, results: List[Any], personel_info: Dict[str, str]):
    wb = openpyxl.load_workbook(template_path)
    ws = wb["DOC_MATRIX"] if "DOC_MATRIX" in wb.sheetnames else wb.active

    ws["C6"] = personel_info.get("vessel", "")
    ws["N6"] = personel_info.get("name", "")
    ws["N8"] = personel_info.get("rank", "Master")
    ws["G4"] = personel_info.get("date", datetime.now().strftime("%d.%m.%Y"))

    target_rank = (personel_info.get("rank") or "Master").strip().upper()
    target_col = 6
    for key, col in RANK_TO_COLUMN_MAP.items():
        if key == target_rank or key in target_rank:
            target_col = col
            break

    res_map = {r.code: r for r in results}

    for code, row_idx in CODE_TO_ROW_MAP.items():
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
            req_val = str(cell.value or "").strip().upper()
            if req_val in ["X", "D"]:
                cell.value = "Zorunlu Belge Eksik"
                cell.fill = FILL_RED
                cell.font = FONT_RED
        cell.alignment = ALIGN_CENTER

    wb.save(output_path)

def fill_word(template_path: str, output_path: str, results: List[Any], personel_info: Dict[str, str], operator_name: str = "Admin"):
    doc = docx.Document(template_path)
    if not doc.tables:
        doc.save(output_path)
        return

    table = doc.tables[0]
    res_map = {r.code: r for r in results}

    table.cell(0, 3).text = personel_info.get("vessel", "")
    table.cell(0, 9).text = personel_info.get("date", datetime.now().strftime("%d.%m.%Y"))
    table.cell(1, 3).text = personel_info.get("name", "")
    table.cell(1, 9).text = "TUR"
    table.cell(2, 3).text = personel_info.get("rank", "Master")
    table.cell(2, 9).text = "Generic & Specific"

    def get_status_box(code: str, is_required: bool = True) -> str:
        res = res_map.get(code)
        if not is_required:
            return "Yes ☐ No☐ N/A☒"
        if res and res.status == "OK":
            return "Yes ☒ No☐ N/A☐"
        return "Yes ☐ No☒ N/A☐"

    table.cell(5, 10).text = get_status_box("COMPETENCY")
    stcw_ok = all(res_map.get(c) and res_map[c].status == "OK" for c in ["FIRE_PREVENTION_AND_FIRE_FIGHTING", "SURVIVAL_CRAFT", "ADV_FIRE"])
    table.cell(6, 10).text = "Yes ☒ No☐ N/A☐" if stcw_ok else "Yes ☐ No☒ N/A☐"
    table.cell(7, 10).text = get_status_box("COMPETENCY")
    table.cell(10, 10).text = get_status_box("DIPLOMA", is_required=False)
    table.cell(11, 10).text = get_status_box("CRIMINAL_RECORD", is_required=False)

    med_res = res_map.get("MEDICAL_CERT")
    med_exp = med_res.evidence_used.expiry_date.strftime("%d.%m.%Y") if (med_res and med_res.evidence_used and med_res.evidence_used.expiry_date) else ""
    table.cell(18, 1).text = f"National Health certificate valid for the contract period? Expire date : {med_exp}"
    table.cell(18, 10).text = get_status_box("MEDICAL_CERT")
    table.cell(21, 10).text = get_status_box("ECDIS_SPECIFIC")
    table.cell(22, 10).text = get_status_box("ECDIS_GENERIC")
    table.cell(23, 10).text = get_status_box("BRM_BTM")

    table.cell(30, 2).text = operator_name
    table.cell(30, 6).text = datetime.now().strftime("%d.%m.%Y")
    table.cell(30, 7).text = "Approved ☒   Rejected☐\nReason to rejection :"

    doc.save(output_path)
