import openpyxl
from docx import Document
from typing import List, Dict, Optional
from crew_core import Result

# 35-102.docx tablosundaki satır indeksleri
WORD_ROW_MAP = {
    "PASSPORT": 5,
    "COMPETENCY": 5,
    "BASIC_SAFETY": 6,
    "SEAMAN_BOOK": 6,
    "GMDSS": 7,
    "CRIMINAL_RECORD": 11,
    "MILITARY_STATUS": 12,
    "RESIDENCE": 13,
    "ID_CARD": 14,
    "MEDICAL_CERT": 17,
    "YELLOW_FEVER": 18
}

def fill_excel(template_path: str, output_stream, results: List[Result], personel_info: dict):
    """35-101 Excel dosyasını doldurur."""
    wb = openpyxl.load_workbook(template_path)
    ws = wb["DOC_MATRIX"] if "DOC_MATRIX" in wb.sheetnames else wb.active

    # Orijinal 35-101.xlsx başlık hücreleri
    ws["H6"] = personel_info.get("name", "")
    ws["B6"] = personel_info.get("vessel", "")
    ws["B8"] = personel_info.get("date", "")
    ws["H8"] = personel_info.get("rank", "")

    wb.save(output_stream)

def fill_word(template_path: str, output_stream, results: List[Result], personel_info: dict, operator_name: str):
    """35-102 Word dosyasını doldurur."""
    doc = Document(template_path)
    table = doc.tables[0]

    # Başlık bilgileri (Satır 0, 1, 2)
    table.rows[0].cells[3].text = personel_info.get("vessel", "")
    table.rows[0].cells[9].text = personel_info.get("date", "")
    table.rows[1].cells[3].text = personel_info.get("name", "")
    table.rows[2].cells[3].text = personel_info.get("rank", "")

    results_dict = {r.code: r for r in results}

    # Tablo kutularını işaretle (Satır 5-25)
    for code, row_index in WORD_ROW_MAP.items():
        if row_index >= len(table.rows):
            continue
        res = results_dict.get(code)
        if not res or not res.evidence_used or not res.evidence_used.verified:
            continue
            
        if res.status == "OK":
            table.rows[row_index].cells[10].text = "Yes [X]  No [ ]  N/A [ ]"
        elif res.status == "MISSING":
            table.rows[row_index].cells[10].text = "Yes [ ]  No [X]  N/A [ ]"

    # Operatör imza alanı
    if len(table.rows) > 29:
        table.rows[29].cells[3].text = operator_name

    doc.save(output_stream)
