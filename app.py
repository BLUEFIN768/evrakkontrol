import streamlit as st
import io
import os
from datetime import datetime
from crew_core import Evidence, evaluate, verify_identity
from ai_extract import process_document
from fillers import fill_excel, fill_word

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

# --- SEKME 1: PERSONEL BİLGİLERİ ---
with tab1:
    st.header("Personel Kimlik & Atama Bilgileri")
    col1, col2 = st.columns(2)
    with col1:
        p_name = st.text_input("Ad Soyad", value="CAN TANGUÇ")
        p_tckn = st.text_input("TCKN")
        p_cuzdan = st.text_input("Cüzdan No")
    with col2:
        p_rank = st.text_input("Rütbe (Master, Chief officer vb.)", value="Master")
        p_vessel = st.text_input("Gemi Adı")
        is_tanker = st.checkbox("Gemi Tanker mi?")
        
    operator_name = st.text_input("Operatör Adı (İmza için)")

# --- SEKME 2: EVRAK YÜKLEME VE YAPAY ZEKA ---
with tab2:
    st.header("Evrak Yükleme")
    
    uab_file = st.file_uploader("UAB Çıktısı (PDF)", type=["pdf"])
    if uab_file and st.button("UAB Oku"):
        st.info("UAB Okuma Modülü tetiklendi.")
        
    # Çoklu dosya yükleyici (PDF, PNG, JPG)
    uploaded_files = st.file_uploader(
        "Yapay Zeka için Evraklar (Resim veya PDF)", 
        type=["jpg", "png", "jpeg", "pdf"],
        accept_multiple_files=True
    )
    
    if uploaded_files and st.button("Yapay Zeka ile Analiz Et"):
        try:
            ai_provider = st.secrets.get("AI_PROVIDER", "gemini")
            api_key = st.secrets["GEMINI_API_KEY"]
            model_name = st.secrets.get("AI_MODEL", "gemini-1.5-flash")
            
            with st.spinner(f"Yapay Zeka {len(uploaded_files)} evrakı analiz ediyor..."):
                for up_file in uploaded_files:
                    file_bytes = up_file.getvalue()
                    mime_type = up_file.type if up_file.type else (
                        "application/pdf" if up_file.name.lower().endswith(".pdf") else "image/jpeg"
                    )
                    evidence = process_document(file_bytes, mime_type, ai_provider, api_key, model_name)
                    st.session_state.evidences.append(evidence)
                    
            st.success(f"{len(uploaded_files)} adet evrak analiz edildi. 3. Kontrol sekmesine geçebilirsiniz.")
        except Exception as e:
            st.error(f"AI Analiz Hatası: {str(e)}")

# --- SEKME 3: KONTROL VE ONAY ---
with tab3:
    st.header("Kanıtlar ve Sonuçlar")
    
    st.subheader("Okunan Kanıtlar (Operatör Doğrulaması)")
    if not st.session_state.evidences:
        st.info("Henüz evrak yüklenmedi.")
    else:
        for i, ev in enumerate(st.session_state.evidences):
            status = "✅ Doğrulandı" if ev.verified else "⚠️ Bekliyor"
            date_str = ev.issue_date.strftime("%d.%m.%Y") if ev.issue_date else "Tarih Yok"
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.write(f"**{ev.code}** | Tarih: {date_str} | Durum: {status}")
            with col_b:
                if not ev.verified:
                    if st.button("Doğrula", key=f"verify_{i}"):
                        st.session_state.evidences[i].verified = True
                        st.rerun()
                
    st.divider()
    
    if st.button("Kuralları İşlet (Evaluate)", type="primary"):
        # Depoda templates altında veya ana dizinde bulunma durumunu kontrol et
        excel_path = "templates/35-101.xlsx" if os.path.exists("templates/35-101.xlsx") else "35-101.xlsx"
        
        if not os.path.exists(excel_path):
            st.error(f"Hata: 35-101.xlsx dosyası bulunamadı!")
        else:
            try:
                st.session_state.results = evaluate(
                    evidences=st.session_state.evidences, 
                    rank=p_rank, 
                    excel_path=excel_path, 
                    is_tanker=is_tanker
                )
                st.success("Değerlendirme başarıyla tamamlandı. 4. Çıktı Al sekmesine geçebilirsiniz.")
                
                for r in st.session_state.results:
                    if r.status == "OK":
                        st.write(f"🟢 **{r.code}**: {r.message}")
                    elif r.status in ["REVIEW", "EXPIRED", "MISSING"]:
                        st.write(f"🔴 **{r.code}**: {r.message} ({r.status})")
            except Exception as e:
                st.error(f"Değerlendirme sırasında hata oluştu: {str(e)}")

# --- SEKME 4: ÇIKTI AL ---
with tab4:
    st.header("Evrakları İndir")
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
                
                st.success("Dosyalar hazır!")
                st.download_button("35-101 İndir (Excel)", data=excel_io.getvalue(), file_name=f"35-101_{p_name}.xlsx")
                st.download_button("35-102 İndir (Word)", data=word_io.getvalue(), file_name=f"35-102_{p_name}.docx")
            except Exception as e:
                st.error(f"Dosya oluşturulurken hata: {str(e)}")
