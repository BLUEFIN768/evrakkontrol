import streamlit as st
import io
import os
from datetime import datetime
from crew_core import Evidence, evaluate
from ai_extract import process_document, parse_uab_pdf_local
from fillers import fill_excel, fill_word

st.set_page_config(page_title="SeaReady Compliance", layout="wide", page_icon="⚓")

st.markdown("""
<style>
    .stApp { background-color: #f0f4f8; }
    div[data-testid="metric-container"] {
        background-color: #ffffff; border: 1px solid #e2e8f0; padding: 15px 20px;
        border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #ffffff; border-radius: 8px 8px 0px 0px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02); padding-top: 10px; padding-bottom: 10px;
    }
    .stButton > button {
        background-color: #3b82f6; color: white; border-radius: 8px;
        border: none; font-weight: 600; transition: all 0.3s;
    }
    .stButton > button:hover { background-color: #2563eb; box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2); }
    .css-1n76uvr { background-color: #ffffff; border-radius: 12px; border: 2px dashed #cbd5e1; }
    .stTextInput>div>div>input, .stSelectbox>div>div>select { border-radius: 8px; border: 1px solid #cbd5e1; }
</style>
""", unsafe_allow_html=True)

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.markdown("### ⚓ Evrak Kontrol Portalı'na Giriş Yapın")
        pwd = st.text_input("Sistem Parolası:", type="password")
        if st.button("Giriş"):
            if pwd == st.secrets.get("APP_PASSWORD", "admin123"):
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Hatalı parola!")
        return False
    return True

if not check_password():
    st.stop()

# Güvenli Oturum (Session) Değişkenleri
if "evidences" not in st.session_state: st.session_state.evidences = []
if "results" not in st.session_state: st.session_state.results = []
if "uab_loaded" not in st.session_state: st.session_state.uab_loaded = False
if "auto_tckn" not in st.session_state: st.session_state.auto_tckn = ""
if "auto_cuzdan" not in st.session_state: st.session_state.auto_cuzdan = ""

col_title, col_user = st.columns([4, 1])
with col_title:
    st.title("⚓ Evrak Kontrol Portalı v2")
with col_user:
    st.markdown("<br>👤 **Kullanıcı:** Admin", unsafe_allow_html=True)
st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(["📋 1. Personel", "📁 2. Evrak Yükle", "⚙️ 3. Kontrol (Dashboard)", "📥 4. Çıktı Al"])

with tab1:
    st.subheader("Personel Kimlik & Atama Bilgileri")
    col1, col2 = st.columns(2)
    with col1:
        p_name = st.text_input("Ad Soyad")
        # Değerler zorla yazdırılmaz, "value=" ile bellekten çağrılır. Bu hatayı engeller.
        p_tckn = st.text_input("TCKN", value=st.session_state.auto_tckn)
        p_cuzdan = st.text_input("Cüzdan No", value=st.session_state.auto_cuzdan)
    with col2:
        p_rank = st.selectbox("Rütbe / Görev", ["Master", "Chief Officer", "2nd Officer", "3rd Officer", "Chief Engineer", "2nd Engineer", "Able Seafarer Engine", "Able Seaman", "Oiler"])
        p_vessel = st.text_input("Gemi Adı")
        is_tanker = st.checkbox("Gemi Tanker mi?")
        operator_name = st.text_input("Operatör Adı (İmza için)")

with tab2:
    st.subheader("UAB Doğrulama & Harici Evraklar")
    col_uab, col_ext = st.columns(2)
    with col_uab:
        st.markdown("#### 1. UAB Doğrulama Çıktısı")
        uab_file = st.file_uploader("UAB Belgesi (PDF)", type=["pdf"], key="uab_uploader")
        if uab_file and st.button("UAB Oku ve Otomatik Doldur", use_container_width=True):
            with st.spinner("Belge çözümleniyor..."):
                uab_evidences, extracted_info = parse_uab_pdf_local(uab_file.getvalue())
                if uab_evidences:
                    st.session_state.evidences.extend(uab_evidences)
                    st.session_state.uab_loaded = True
                    # Okunan verileri bellek havuzuna atarız
                    if extracted_info["tckn"]:
                        st.session_state.auto_tckn = extracted_info["tckn"]
                    if extracted_info["cuzdan"]:
                        st.session_state.auto_cuzdan = extracted_info["cuzdan"]
                    
                    st.success("✅ Başarılı! TCKN ve Cüzdan numaraları Personel sekmesine kopyalandı.")
                    st.rerun() # Sayfayı yeniler ve 1. Sekmedeki kutular yeni verilerle dolar
                else:
                    st.error("UAB Belgesi okunamadı.")
                    
    with col_ext:
        st.markdown("#### 2. Harici Evraklar (Yabancı)")
        uploaded_files = st.file_uploader("Harici Evrak Yükle", type=["jpg", "png", "jpeg", "pdf"], accept_multiple_files=True, key="main_uploader")
        if uploaded_files and st.button("Harici Evrakları Aktar", use_container_width=True):
            count = 0
            for up_file in uploaded_files:
                ev = process_document(data=up_file.getvalue(), mime=up_file.type or "application/pdf", provider_name="local", api_key="", model_name="", filename=up_file.name)
                if not any(e.code == ev.code and e.verified for e in st.session_state.evidences):
                    st.session_state.evidences.append(ev)
                    count += 1
            st.success(f"✅ {count} adet harici evrak aktarıldı.")

with tab3:
    st.subheader("Evrak Kontrol & Onay Paneli")
    total_docs = len(st.session_state.evidences)
    verified_docs = sum(1 for e in st.session_state.evidences if e.verified)
    pending_docs = total_docs - verified_docs
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(label="📄 Toplam Evrak", value=total_docs)
    m2.metric(label="✅ Doğrulanan", value=verified_docs)
    m3.metric(label="⚠️ Bekleyen Onay", value=pending_docs)
    m4.metric(label="🇹🇷 Entegrasyon", value="Aktif" if st.session_state.uab_loaded else "Pasif")
    st.markdown("---")
    
    if not st.session_state.evidences:
        st.info("Henüz yüklenmiş evrak bulunmuyor.")
    else:
        st.markdown("#### Yüklenen Belgeler")
        for i, ev in enumerate(st.session_state.evidences):
            col_icon, col_info, col_btn = st.columns([1, 6, 2])
            with col_icon: st.markdown(f"## {'✅' if ev.verified else '⚠️'}")
            with col_info:
                exp = ev.expiry_date.strftime("%d.%m.%Y") if ev.expiry_date else "Süresiz"
                st.markdown(f"**{ev.code}** | Belge No: `{ev.document_no}` | Bitiş: {exp}")
            with col_btn:
                if not ev.verified:
                    if st.button("Orijinali Onayla", key=f"verify_{i}", use_container_width=True):
                        st.session_state.evidences[i].verified = True
                        st.rerun()
                else:
                    st.button("Onaylandı", key=f"verified_{i}", disabled=True, use_container_width=True)
            st.markdown("---")
            
    if st.button(f"🚀 Kuralları İşlet ve Değerlendir ({p_rank})", type="primary", use_container_width=True):
        excel_template_path = "templates/35-101.xlsx" if os.path.exists("templates/35-101.xlsx") else "35-101.xlsx"
        if not os.path.exists(excel_template_path):
            st.error("Hata: Kural kaynağı bulunamadı!")
        else:
            try:
                st.session_state.results = evaluate(evidences=st.session_state.evidences, rank=p_rank, excel_path=excel_template_path, is_tanker=is_tanker)
                st.success("Kurallar başarıyla işletildi. '4. Çıktı Al' sekmesine geçebilirsiniz.")
                for r in st.session_state.results:
                    if r.status == "OK": st.success(f"**{r.code}**: {r.message}")
                    elif r.status in ["REVIEW", "EXPIRED", "MISSING"]: st.error(f"**{r.code}**: {r.message} ({r.status})")
            except Exception as e:
                st.error(f"Hata: {str(e)}")

with tab4:
    st.subheader("Evrak Raporlarını İndir")
    personel_info = {
        "name": p_name or "Personel", 
        "rank": p_rank, 
        "vessel": p_vessel or "Belirtilmedi", 
        "date": datetime.now().strftime("%d.%m.%Y")
    }
    
    if st.button("Excel ve Word Dosyalarını Hazırla", type="primary"):
        if not st.session_state.results:
            st.warning("Önce 'Kontrol' sekmesinden kuralları işletmeniz gerekiyor.")
        else:
            excel_template = "templates/35-101.xlsx" if os.path.exists("templates/35-101.xlsx") else "35-101.xlsx"
            word_template = "templates/35-102.docx" if os.path.exists("templates/35-102.docx") else "35-102.docx"
            try:
                excel_io, word_io = io.BytesIO()
                fill_excel(excel_template, excel_io, st.session_state.results, personel_info)
                fill_word(word_template, word_io, st.session_state.results, personel_info, operator_name or "Yetkili")
                
                st.success("🎉 Raporlar başarıyla üretildi!")
                col_dl1, col_dl2 = st.columns(2)
                with col_dl1: st.download_button("📥 35-101 İndir (Excel)", data=excel_io.getvalue(), file_name=f"35-101_{personel_info['name']}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                with col_dl2: st.download_button("📥 35-102 İndir (Word)", data=word_io.getvalue(), file_name=f"35-102_{personel_info['name']}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
            except Exception as e:
                st.error(f"Dosya oluşturulurken hata: {str(e)}")
