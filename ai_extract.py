def parse_uab_pdf_local(pdf_bytes: bytes) -> Tuple[List[Evidence], Dict[str, str]]:
    evidences = []
    extracted_info = {"tckn": "", "cuzdan": "", "name": ""}
    text = ""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        text += " | ".join([str(cell) for cell in row if cell]) + "\n"

        norm_text = normalize_text(text)
        
        # 1. TCKN Taraması (11 Haneli TC Kimlik Kuralı)
        tckn_match = re.search(r'(?:TCKN|T\.?C\.?\s*(?:KIMLIK|VATANDASLIK)?\s*(?:NO|NUMARASI)?|VATANDASLIK\s*NO(?:SU)?|KIMLIK\s*NO(?:SU)?)\s*[:\.\s\-]*([1-9]\d{10})\b', norm_text)
        if tckn_match:
            extracted_info["tckn"] = tckn_match.group(1)
        else:
            all_11 = re.findall(r'\b([1-9]\d{10})\b', norm_text)
            if all_11:
                extracted_info["tckn"] = all_11[0]

        # 2. Cüzdan No Taraması (Sadece Harflerden Oluşan Kelimeleri Engelleyen Nümerik Filtre)
        # Öncelik 1: CUZDAN NO / NUMARASI veya SICIL NO etiketinin hemen yanındaki geçerli numara
        cuzdan_candidates = re.findall(r'(?:CUZDAN\s*(?:NO|NUMARASI)?|SICIL\s*(?:NO|NUMARASI)?)\s*[:=\.\s\-]+([A-Z0-9]+)', norm_text)
        for cand in cuzdan_candidates:
            cand = cand.strip()
            # En az 5 rakam barındırmalı ve harf+rakam formatında olmalı (UZERINDEKI gibi kelimeleri eler)
            if re.fullmatch(r'[A-Z]{0,2}\d{5,10}', cand) and cand != extracted_info["tckn"]:
                extracted_info["cuzdan"] = cand
                break

        # Öncelik 2: Eğer etiket yanında bulunamadıysa metin genelindeki S00392038 / G000123 formatı
        if not extracted_info["cuzdan"]:
            general_matches = re.findall(r'\b([A-Z]\d{6,9})\b', norm_text)
            for cand in general_matches:
                if cand != extracted_info["tckn"]:
                    extracted_info["cuzdan"] = cand
                    break

        # Öncelik 3: TCKN harici 6-10 haneli müstakil sicil numaraları
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

        if any(k in norm_text for k in ["UZAKYOL", "KAPTAN", "ZABIT", "MUHENDIS", "TAYFA"]):
            evidences.append(Evidence(code="COMPETENCY", document_no="UAB-COC", issue_date=datetime(2023, 4, 4), expiry_date=exp_date, verified=True))
        if "GMDSS" in norm_text or "TELSIZ" in norm_text or "GOC" in norm_text:
            evidences.append(Evidence(code="GMDSS", document_no="UAB-GMDSS", issue_date=datetime(2023, 4, 4), expiry_date=exp_date, verified=True))

        kw_map = {
            "BASIC_SAFETY": ["CAN KURTARMA", "YANGIN", "ILK YARDIM", "ILKYARDIM", "KISEL EMNIYET"],
            "SURVIVAL_CRAFT": ["CANKURTARMA ARACLARI", "SURVIVAL CRAFT"],
            "ADV_FIRE": ["ILERI YANGIN"],
            "RADAR": ["RADAR GOZLEM", "RADAR OBSERVATION"],
            "ARPA": ["OTOMATIK RADAR", "ARPA"],
            "BRM_BTM": ["KOPRUUSTU KAYNAK", "KOPRUUSTU TAKIM", "BRM", "BTM"],
            "ECDIS_GENERIC": ["ECDIS", "ELEKTRONIK HARITA"],
        }

        for code, kws in kw_map.items():
            if any(kw in norm_text for kw in kws):
                evidences.append(Evidence(code=code, document_no=f"UAB-{code}", issue_date=datetime(2023, 4, 4), expiry_date=exp_date, verified=True))

        return evidences, extracted_info
    except Exception as e:
        print(f"UAB Parse Hatası: {e}")
        return [], extracted_info
