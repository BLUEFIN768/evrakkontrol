import streamlit as st
import io
import os
import zipfile
from datetime import datetime
from crew_core import Evidence, evaluate
from ai_extract import process_document, parse_uab_pdf_local
from fillers import fill_excel, fill_word

# 1. SAYFA AYARLARI (Geniş Ekran)
st.set_page_config(page_title="Evrak Kontrol & Onay", layout="wide", page_icon="⚓")

# 2. GÖRSELDEKİ ÖZEL CSS MAKYAJI (TEK SAYFA DASHBOARD)
st.markdown("""
<style>
    /* Arka Plan ve Yazı Tipleri */
    .stApp { background-color: #f1f5f9; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    
    /* Ana Başlık */
    .main-title { font-size: 28px; font-weight: bold; color: #0f172a; margin-bottom: 20px; }
    
    /* Beyaz Kart Tasarımları (Personel, Matris, Listeler için) */
    .card {
        background-color: #ffffff; padding: 20px; border-radius: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1); border: 1px solid #e2e8f0; margin-bottom: 20px;
    }
    
    /* Bölüm Alt Başlıkları */
    .sub-title { font-size: 20px; font-weight: 600; color: #1e293b; margin-bottom: 15px; border-bottom: 2px solid #f1f5f9; padding-bottom: 10px; }
    
    /* Evrak Listesi Satır Tasarımı */
    .doc-row {
        background-color: #f8fafc; padding: 15px; border-radius: 8px;
        border: 1px solid #e2e8f0; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;
    }
    
    /* Özel Buton Renkleri (Yeşil, Kırmızı, Mavi) */
    .stButton > button { transition: all 0.3s ease; border-radius: 8px; font-weight: 600; width: 100%; }
    
    /* Input kutuları köşeleri */
    .stTextInput>div>div>input, .stSelectbox>div>div>select { border-radius: 8px; border: 1px solid #cbd5e1; }
</style>
""", unsafe_allow_html=True)

# Güvenlik Kontrolü
def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.markdown("### ⚓ Evrak Kontrol Portalı")
        pwd = st.text_input("Parola:", type="password")
        if st.button("Giriş Yap"):
            if pwd == st.secrets.get("APP_PASSWORD", "admin123"):
                st.session_state["password_correct"] = True
                st.rerun()
            else: st.error("Hatalı parola!")
        return False
    return True

if not check_password(): st.stop()

# Oturum Değişkenleri
if "evidences" not in st.session_state: st.session_state.evidences = []
if "results" not in st.session_state: st.session_state.results = []
if "p_name" not in st.session_state: st.session_state.p_name = ""
if "p_tckn" not in st.session_state: st.session_state.p_tckn = ""
if "p_cuzdan" not in st.session_state: st.session_state.p_cuzdan = ""
if "p_rank" not in st.session_state: st.session_state.p_rank = "Master"
if "p_vessel" not in st.session_state: st.session_state.p_vessel = ""
if "is_tanker" not in st.session_state: st.session_state.is_tanker = False
if "operator_name" not in st.session_state: st.session_state.operator_name = "Admin"
if "auto_tckn" not in st.session_state: st.session_state.auto_tckn = ""
if "auto_cuzdan" not in st.session_state: st.session_state.auto_cuzdan = ""

# 3. ANA BAŞLIK
st.markdown("<div class='main-title'>Evrak Kontrol & Onay (Auditing) 🔗</div>", unsafe_allow_html=True)

# 4. ÜST BÖLÜM: PERSONEL KİMLİK KARTI
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Personel Kimlik & Atama</div>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
with col1:
    p_name = st.text_input("Ad Soyad", key="p_name_input", value=st.session_state.p_name)
    p_rank = st.selectbox("Rütbe / Görev", ["Master", "Chief Officer", "2nd Officer", "3rd Officer", "Chief Engineer", "2nd Engineer", "Able Seafarer Engine", "Able Seaman", "Oiler"], key="p_rank_input")
with col2:
    p_tckn = st.text_input("TCKN", key="p_tckn_input", value=st.session_state.auto_tckn)
    p_cuzdan = st.text_input("Cüzdan No", key="p_cuzdan_input", value=st.session_state.auto_cuzdan)
with col3:
    p_vessel = st.text_input("Gemi Adı", key="p_vessel_input")
    operator_name = st.text_input("Operatör Adı", key="operator_name_input", value=st.session_state.operator_name)
    is_tanker = st.checkbox("Gemi Tanker mi?", key="is_tanker_input")
st.markdown("</div>", unsafe_allow_html=True)


# 5. ALT BÖLÜM: İKİ SÜTUNLU YAPI (SOL: EVRAKLAR, SAĞ: MATRİS)
col_left, col_right = st.columns([6, 4], gap="large")

# SOL PANEL: YÜKLEME VE LİSTE
with col_left:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='sub-title'>Evrak Doğrulama Listesi</div>", unsafe_allow_html=True)
    
    # Tek Yükleme Kutusu (Hem UAB hem Harici)
    uploaded_files = st.file_uploader("UAB PDF veya Harici Evrak Sürükle-Bırak", accept_multiple_files=True)
    if uploaded_files and st.button("Yüklenen Evrakları İşle", type="primary", use_container_width=True):
        with st.spinner("Evraklar sistem tarafından taranıyor..."):
            for f in uploaded_files:
                file_bytes = f.getvalue()
                is_uab_processed = False
                
                # Eğer PDF ise önce UAB motoruna sokmayı dene
                if f.name.lower().endswith(".pdf"):
                    uab_evs, ext_info = parse_uab_pdf_local(file_bytes)
                    if uab_evs: # UAB başarıyla okundu demektir
                        st.session_state.evidences.extend(uab_evs)
                        if ext_info["tckn"]: st.session_state.auto_tckn = ext_info["tckn"]
                        if ext_info["cuzdan"]: st.session_state.auto_cuzdan = ext_info["cuzdan"]
                        is_uab_processed = True
                        
                # Eğer UAB değilse veya resimse, Harici Evrak olarak ekle
                if not is_uab_processed:
                    ev = process_document(file_bytes, f.type or "application/pdf", "local", "", "", f.name)
                    if not any(e.code == ev.code and e.verified for e in st.session_state.evidences):
                        st.session_state.evidences.append(ev)
            
            st.rerun()

    st.markdown("---")
    
    # Yüklenen Evrakların Listelenmesi
    if not st.session_state.evidences:
        st.info("Henüz sisteme evrak yüklenmedi.")
    else:
        for i, ev in enumerate(st.session_state.evidences):
            st.markdown("<div class='doc-row'>", unsafe_allow_html=True)
            c_icon, c_info, c_btn1, c_btn2 = st.columns([1, 5, 2, 2])
            
            with c_icon:
                st.markdown(f"<h2>{'✅' if ev.verified else '📄'}</h2>", unsafe_allow_html=True)
            with c_info:
                exp = ev.expiry_date.strftime("%d.%m.%Y") if ev.expiry_date else "Süresiz"
                st.markdown(f"<b>{ev.code}</b><br><small>No: {ev.document_no} | Bitiş: {exp}</small>", unsafe_allow_html=True)
            
            with c_btn1:
                if not ev.verified:
                    if st.button("Orijinali Onayla", key=f"ok_{i}"):
                        st.session_state.evidences[i].verified = True
                        st.rerun()
                else:
                    st.button("Doğrulandı ✅", key=f"ok_{i}", disabled=True)
            
            with c_btn2:
                if st.button("Hatalı/Sil", key=f"del_{i}"):
                    st.session_state.evidences.pop(i)
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# SAĞ PANEL: MATRİS VE İNDİRME (OTOMATİK DEĞERLENDİRME)
with col_right:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown(f"<div class='sub-title'>35-101 Matris Uygunluğu ({p_rank})</div>", unsafe_allow_html=True)
    
    excel_template_path = "templates/35-101.xlsx" if os.path.exists("templates/35-101.xlsx") else "35-101.xlsx"
    
    if os.path.exists(excel_template_path):
        # Arka planda anında işletilir (Butona gerek kalmadan)
        st.session_state.results = evaluate(
            evidences=st.session_state.evidences, 
            rank=p_rank, 
            excel_path=excel_template_path, 
            is_tanker=is_tanker
        )
        
        # Sonuçların Gösterilmesi
        if st.session_state.results:
            for r in st.session_state.results:
                icon = "✅" if r.status == "OK" else "❌"
                color = "#22c55e" if r.status == "OK" else "#ef4444"
                st.markdown(f"""
                    <div style='display:flex; justify-content:space-between; border-bottom:1px solid #e2e8f0; padding:8px 0;'>
                        <span style='font-weight:500; color:#334155;'>{r.code}</span> 
                        <span style='color:{color}; font-weight:bold; font-size:18px;'>{icon}</span>
                    </div>
                """, unsafe_allow_html=True)
                
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Word/Excel ZIP İndirme Butonu
            personel_info = {
                "name": p_name or "Personel", "rank": p_rank, 
                "vessel": p_vessel or "Belirtilmedi", "date": datetime.now().strftime("%d.%m.%Y")
            }
            
            try:
                import tempfile
                word_template = "templates/35-102.docx" if os.path.exists("templates/35-102.docx") else "35-102.docx"
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_excel:
                    fill_excel(excel_template_path, tmp_excel.name, st.session_state.results, personel_info)
                    excel_path = tmp_excel.name
                    
                with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_word:
                    fill_word(word_template, tmp_word.name, st.session_state.results, personel_info, operator_name)
                    word_path = tmp_word.name
                
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                    zip_file.write(excel_path, f"35-101_{personel_info['name']}.xlsx")
                    zip_file.write(word_path, f"35-102_{personel_info['name']}.docx")
                
                st.download_button(
                    label="📥 Word/Excel Raporu Üret (.ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name=f"Evrak_Kontrol_{personel_info['name']}.zip",
                    mime="application/zip",
                    use_container_width=True,
                    type="primary"
                )
            except Exception as e:
                st.error(f"Dosya oluşturulurken hata: {str(e)}")
        else:
            st.info("Kurallar matriste bulunamadı veya evrak eklenmedi.")
    else:
        st.error("35-101.xlsx şablonu bulunamadı!")
        
    st.markdown("</div>", unsafe_allow_html=True)
