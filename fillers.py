import openpyxl
from docx import Document
from typing import List, Dict
from crew_core import Result

def safe_write_excel(ws, coord=None, row=None, col=None, val=""):
    """
    Hem 'C3' formatında hem de (row=7, col=2) formatında güvenli yazma yapar.
    Birleştirilmiş hücre (MergedCell) hatalarını (read-only) engeller.
    """
    try:
        if coord:
            cell = ws[coord]
        else:
            cell = ws.cell(row=row, column=col)
            
        if type(cell).__name__ == 'MergedCell':
            for r in ws.merged_cells.ranges:
                if cell.coordinate in r:
                    # Birleştirilmiş hücrenin asıl (sol üst) sahibi olan hücreye yazdırır
                    ws.cell(row=r.min_row, column=r.min_col).value = val
                    return
        else:
            cell.value = val
    except Exception as e:
        pass # Hata olursa programı çökertme, atla

def fill_excel(template_path: str, output_stream, results: List[Result], personel_info: dict):
    """35-101 Excel dosyasını şablonu bozmadan güvenle doldurur."""
    wb = openpyxl.load_workbook(template_path)
    ws = wb["DOC_MATRIX"] if "DOC_MATRIX" in wb.sheetnames else wb.active
    
    # Şablonlardaki olası başlık hücrelerini doldur (Farklı 35-101 varyasyonları için)
    safe_write_excel(ws, coord="C3", val=personel_info.get("name", ""))
    safe_write_excel(ws, coord="C4", val=personel_info.get("rank", ""))
    safe_write_excel(ws, coord="G3", val=personel_info.get("vessel", ""))
    safe_write_excel(ws, coord="G4", val=personel_info.get("date", ""))
    
    safe_write_excel(ws, coord="C6", val=personel_info.get("name", ""))
    safe_write_excel(ws, coord="N6", val=personel_info.get("rank", ""))
    safe_write_excel(ws, coord="C8", val=personel_info.get("date", ""))
    safe_write_excel(ws, coord="N8", val=personel_info.get("vessel", ""))
    
    # Sonuçları listeye yaz (MergedCell hatasından korunarak)
    row_idx = 7
    for res in results:
        safe_write_excel(ws, row=row_idx, col=2, val=res.code)
        safe_write_excel(ws, row=row_idx, col=5, val=res.status)
        safe_write_excel(ws, row=row_idx, col=7, val=res.message)
        row_idx += 1
        
    wb.save(output_stream)

def fill_word(template_path: str, output_stream, results: List[Result], personel_info: dict, operator_name: str):
    """35-102 Word dosyasını doldurur."""
    doc = Document(template_path)
    
    replacements = {
        "{{NAME}}": personel_info.get("name", ""),
        "{{RANK}}": personel_info.get("rank", ""),
        "{{VESSEL}}": personel_info.get("vessel", ""),
        "{{DATE}}": personel_info.get("date", ""),
        "{{OPERATOR}}": operator_name
    }
    
    # Paragraflardaki etiketleri değiştir
    for p in doc.paragraphs:
        for k, v in replacements.items():
            if k in p.text:
                p.text = p.text.replace(k, v)
                
    # Tablolardaki etiketleri değiştir
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for k, v in replacements.items():
                    if k in cell.text:
                        cell.text = cell.text.replace(k, v)
                        
    doc.save(output_stream)
