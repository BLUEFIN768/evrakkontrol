import streamlit as st
import io
import os
from datetime import datetime
from crew_core import Evidence, evaluate
from ai_extract import process_document
from fillers import fill_excel, fill_word

st.set_page_config(page_title="Evrak Kontrol Portalı v2", layout="wide")

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        pwd = st.text_input("Sistem Parolası:", type="password")
        if st.button("Giriş"):
            if pwd == st.secrets.get("APP_PASSWORD", "bluefin2026*-"):
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Hatalı parola!")
        return False
    return True

if not check_password():
    st.stop()

st.title("Evrak Kontrol Portalı v2")

tab1, tab2, tab3, tab4 = st.tabs(["1. Personel", "2. Evrak Yükle", "3. Kontrol", "4. Çıktı Al"])

if "evidences" not in st.session_state:
    st.session_state.evidences = []
if "results" not in st.session_state:
    st.session_state.results = []

# --- SEKME 1: PERSONEL VE RÜTBE BİLGİLERİ ---
with tab1:
    st.header("Personel Kimlik & Atama Bilgileri")
    col1, col2 = st.columns(2)
    with col1:
        p_name = st.text_input("Ad Soyad", value="CAN TANGUÇ")
        p_tckn = st.text_input("TCKN", value="12345678901")
        p_cuzdan = st.text_input("Cüzdan No", value="G000123")
    with col2:
        p_rank = st.selectbox(
            "Rütbe / Görev", 
            ["Master", "Chief Officer", "2nd Officer", "3rd Officer", "Chief Engineer", "2nd Engineer", "Able Seaman", "Oiler"]
        )
        p_vessel = st.text_input("Gemi Adı", value="BLUEFIN-1")
        is_tanker = st.checkbox("Gemi Tanker mi?", value=True)
        
    operator_name = st.text_input("Operatör Adı (İmza için)", value="Admin")

# --- SEKME 2: EVRAK YÜKLEME ---
with tab2:
    st.header("Evrak Yükleme")
    
    uploaded_files = st.file_uploader(
        "Evrakları Yükleyin (Resim veya PDF)", 
        type=["jpg", "png", "jpeg", "pdf"],
        accept_multiple_files=True,
        key="main_uploader"
    )
    
    if uploaded_files and st.button("Evrakları Sisteme Aktar", type="primary"):
        st.session_state.evidences = []
        for up_file in uploaded_files:
            file_bytes = up_file.getvalue()
            mime_type = up_file.type or "application/pdf"
            
            ev = process_document(
                data=file_bytes,
                mime=mime_type,
                provider_name="local",
                api_key="",
                model_name="",
                filename=up_file.name
            )
            st.session_state.evidences.append(ev)
            
        st.success(f"{len(uploaded_files)} adet evrak anında yüklendi! '3. Kontrol' sekmesine geçebilirsiniz.")

# --- SEKME 3: KONTROL VE KURAL DENETİMİ ---
with tab3:
    st.header("Kanıtlar ve Sonuçlar")
    st.subheader("Yüklenen Evraklar (Operatör Onayı)")
    
    if not st.session_state.evidences:
        st.info("Henüz yüklenmiş evrak bulunmuyor. Lütfen '2. Evrak Yükle' sekmesinden dosyaları aktarın.")
    else:
        for i, ev in enumerate(st.session_state.evidences):
            col_a, col_b = st.columns([3, 1])
            with col_a:
                exp = ev.expiry_date.strftime("%d.%m.%Y") if ev.expiry_date else "Süresiz"
                st.write(f"📄 **{ev.code}** | Belge: `{ev.document_no}` | Bitiş: {exp} | Durum: {'✅ Doğrulandı' if ev.verified else '⚠️ Bekliyor'}")
            with col_b:
                if not ev.verified:
                    if st.button("Doğrula", key=f"verify_{i}"):
                        st.session_state.evidences[i].verified = True
                        st.rerun()
                else:
                    st.write("✅ Onaylı")
                
    st.divider()
    
    if st.button(f"Kuralları İşlet ({p_rank})", type="primary"):
        excel_path = "templates/35-101.xlsx" if os.path.exists("templates/35-101.xlsx") else "35-101.xlsx"
        if not os.path.exists(excel_path):
            st.error("Hata: 35-101.xlsx şablon dosyası bulunamadı!")
        else:
            try:
                st.session_state.results = evaluate(
                    evidences=st.session_state.evidences, 
                    rank=p_rank, 
                    excel_path=excel_path, 
                    is_tanker=is_tanker
                )
                st.success(f"{p_rank} için kurallar başarıyla işletildi. '4. Çıktı Al' sekmesinden raporları alabilirsiniz.")
                for r in st.session_state.results:
                    if r.status == "OK":
                        st.write(f"🟢 **{r.code}**: {r.message}")
                    else:
                        st.write(f"🔴 **{r.code}**: {r.message} ({r.status})")
            except Exception as e:
                st.error(f"Kural değerlendirme hatası: {str(e)}")

# --- SEKME 4: RAPOR ÇIKTILARI ---
with tab4:
    st.header("Evrak Raporlarını İndir")
    personel_info = {
        "name": p_name, 
        "rank": p_rank, 
        "vessel": p_vessel, 
        "date": datetime.now().strftime("%d.%m.%Y")
    }
    
    if st.button("Excel ve Word Dosyalarını Hazırla"):
        if not st.session_state.results:
            st.warning("Önce '3. Kontrol' sekmesinden kuralları işletmeniz gerekiyor.")
        else:
            excel_template = "templates/35-101.xlsx" if os.path.exists("templates/35-101.xlsx") else "35-101.xlsx"
            word_template = "templates/35-102.docx" if os.path.exists("templates/35-102.docx") else "35-102.docx"
            
            try:
                excel_io = io.BytesIO()
                word_io = io.BytesIO()
                
                fill_excel(excel_template, excel_io, st.session_state.results, personel_info)
                fill_word(word_template, word_io, st.session_state.results, personel_info, operator_name)
                
                st.success("Tüm raporlar hazır!")
                st.download_button("📥 35-101 İndir (Excel)", data=excel_io.getvalue(), file_name=f"35-101_{p_name}.xlsx")
                st.download_button("📥 35-102 İndir (Word)", data=word_io.getvalue(), file_name=f"35-102_{p_name}.docx")
            except Exception as e:
                st.error(f"Dosya üretme hatası: {str(e)}")
