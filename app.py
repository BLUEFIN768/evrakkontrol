import streamlit as st
import io
import os
import zipfile
from datetime import datetime
from crew_core import Evidence, evaluate
from ai_extract import process_document, parse_uab_pdf_local
from fillers import fill_excel, fill_word

# 1. SAYFA AYARLARI (Geniş Ekran)
st.set_page_config(page_title="Compliance Portal", layout="wide", page_icon="⚓")

# 2. GÖRSELDEKİ ÖZEL CSS MAKYAJI (COMPLIANCE PORTAL)
st.markdown("""
<style>
    /* Arka Plan ve Yazı Tipleri */
    .stApp { background-color: #f0f4f8; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    
    /* Sol Menü (Sidebar) Rengi */
    [data-testid="stSidebar"] { background-color: #f8fafc; border-right: 1px solid #e2e8f0; }
    
    /* Üst Bilgi Kartı (Bora Yılmazgül profili gibi) */
    .profile-card {
        background-color: #ffffff; padding: 20px; border-radius: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px; border: 1px solid #e2e8f0;
        display: flex; justify-content: space-between; align-items: center;
    }
    
    /* Evrak Listesi Kartları */
    .doc-card {
        background-color: #ffffff; padding: 15px; border-radius: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-bottom: 15px; border: 1px solid #e2e8f0;
    }
    
    /* Sağ Panel (Matris ve Skor) */
    .right-panel-card {
        background-color: #ffffff; padding: 20px; border-radius: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; margin-bottom: 20px;
    }
    
    /* %100 Uygun Çemberi */
    .score-circle {
        width: 100px; height: 100px; border-radius: 50%; border: 6px solid #22c55e;
        display: flex; align-items: center; justify-content: center;
        font-size: 20px; font-weight: bold; color: #22c55e; margin: 20px auto;
    }

    /* Özel Buton Renkleri (Yeşil, Kırmızı, Mavi) */
    .btn-green button { background-color: #22c55e !important; color: white !important; border: none !important; border-radius: 6px !important; }
    .btn-red button { background-color: #ef4444 !important; color: white !important; border: none !important; border-radius: 6px !important; }
    .btn-blue button { background-color: #3b82f6 !important; color: white !important; border: none !important; border-radius: 8px !important; width: 100%; font-weight: bold !important; margin-bottom: 10px !important;}
</style>
""", unsafe_allow_html=True)

# Güvenlik Kontrolü
def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.markdown("### ⚓ Portal Girişi")
        pwd = st.text_input("Parola:", type="password")
        if st.button("Giriş"):
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
if "auto_tckn" not in st.session_state: st.session_state.auto_tckn = ""
if "auto_cuzdan" not in st.session_state: st.session_state.auto_cuzdan = ""
if "menu_selection" not in st.session_state: st.session_state.menu_selection = "Kontrol & Onay"

# 3. SOL MENÜ (SIDEBAR)
with st.sidebar:
    st.markdown("### ⚓ Compliance Portal")
    st.markdown("---")
    menu = st.radio("Menü", ["Ana Sayfa", "Personel", "Evrak Yükleme", "Kontrol & Onay", "Ayarlar"], index=3)
    st.session_state.menu_selection = menu
    
    st.markdown("---")
    st.markdown("👤 **Denetçi:** Admin")

# Üst Başlık
st.subheader(f"Evrak {st.session_state.menu_selection} (Auditing)")

# 4. SAYFA YÖNLENDİRMELERİ
if st.session_state.menu_selection == "Personel":
    st.markdown("<div class='profile-card'><h4>Personel Kayıt Formu</h4></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.p_name = st.text_input("Ad Soyad", value=st.session_state.get("p_name", ""))
        st.session_state.p_tckn = st.text_input("TCKN", value=st.session_state.auto_tckn)
        st.session_state.p_cuzdan = st.text_input("Cüzdan No", value=st.session_state.auto_cuzdan)
    with c2:
        st.session_state.p_rank = st.selectbox("Rütbe / Görev", ["Master", "Chief Officer", "2nd Officer", "3rd Officer", "Chief Engineer", "2nd Engineer", "Able Seafarer Engine", "Able Seaman", "Oiler"])
        st.session_state.p_vessel = st.text_input("Gemi Adı", value=st.session_state.get("p_vessel", ""))
        st.session_state.is_tanker = st.checkbox("Gemi Tanker mi?")
        st.session_state.operator_name = st.text_input("Operatör Adı", value="Admin")

elif st.session_state.menu_selection == "Evrak Yükleme":
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='profile-card'><h4>1. UAB Doğrulama (Otomatik)</h4></div>", unsafe_allow_html=True)
        uab_file = st.file_uploader("UAB Belgesi (PDF)", type=["pdf"])
        if uab_file and st.button("UAB Oku ve İçeri Aktar", use_container_width=True):
            with st.spinner("Okunuyor..."):
                uab_evidences, extracted_info = parse_uab_pdf_local(uab_file.getvalue())
                if uab_evidences:
                    st.session_state.evidences.extend(uab_evidences)
                    if extracted_info["tckn"]: st.session_state.auto_tckn = extracted_info["tckn"]
                    if extracted_info["cuzdan"]: st.session_state.auto_cuzdan = extracted_info["cuzdan"]
                    st.success("Evraklar başarıyla eklendi! TCKN/Cüzdan güncellendi.")
                else: st.error("UAB okunamadı.")
    with c2:
        st.markdown("<div class='profile-card'><h4>2. Harici Evrak (Manuel)</h4></div>", unsafe_allow_html=True)
        ext_files = st.file_uploader("Pasaport, Sağlık vb.", type=["jpg", "pdf"], accept_multiple_files=True)
        if ext_files and st.button("Harici Evrakları Aktar", use_container_width=True):
            for f in ext_files:
                ev = process_document(f.getvalue(), f.type or "application/pdf", "local", "", "", f.name)
                if not any(e.code == ev.code and e.verified for e in st.session_state.evidences):
                    st.session_state.evidences.append(ev)
            st.success("Harici evraklar eklendi.")

elif st.session_state.menu_selection == "Kontrol & Onay":
    # 5. GÖRSELDEKİ ANA EKRAN DİZİLİMİ (SOL: LİSTE, SAĞ: SKOR VE İNDİR)
    
    # Üst Profil Kartı
    name_display = st.session_state.get("p_name", "PERSONEL ADI GİRİLMEDİ")
    rank_display = st.session_state.get("p_rank", "Rütbe Seçilmedi")
    vessel_display = st.session_state.get("p_vessel", "Gemi Belirtilmedi")
    tckn_display = st.session_state.auto_tckn or "Yok"
    cuzdan_display = st.session_state.auto_cuzdan or "Yok"
    
    st.markdown(f"""
    <div class="profile-card">
        <div>
            <h3 style="margin:0; color:#1e293b;">👤 {name_display}</h3>
            <p style="margin:0; color:#64748b;">{rank_display} | {vessel_display}</p>
        </div>
        <div style="text-align:right;">
            <p style="margin:0;"><b>TCKN:</b> {tckn_display}</p>
            <p style="margin:0;"><b>Cüzdan No:</b> {cuzdan_display}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # İki Sütunlu Ana Yapı
    col_main, col_right = st.columns([7, 3], gap="large")
    
    with col_main:
        st.markdown("#### Evrak Doğrulama Listesi", unsafe_allow_html=True)
        if not st.session_state.evidences:
            st.info("Henüz yüklenmiş evrak bulunmuyor. Sol menüden 'Evrak Yükleme'ye geçiniz.")
        
        for i, ev in enumerate(st.session_state.evidences):
            st.markdown("<div class='doc-card'>", unsafe_allow_html=True)
            c_icon, c_info, c_btn1, c_btn2 = st.columns([1, 5, 2, 2])
            
            with c_icon:
                st.markdown(f"<h2 style='margin:0;'>{'📄'}</h2>", unsafe_allow_html=True)
            with c_info:
                exp = ev.expiry_date.strftime("%d.%m.%Y") if ev.expiry_date else "Süresiz"
                st.markdown(f"<b style='font-size:16px;'>{ev.code}</b><br><small>No: {ev.document_no} | Bitiş: {exp}</small>", unsafe_allow_html=True)
            
            with c_btn1:
                st.markdown("<div class='btn-green'>", unsafe_allow_html=True)
                if not ev.verified:
                    if st.button("Orijinali Onayla", key=f"ok_{i}"):
                        st.session_state.evidences[i].verified = True
                        st.rerun()
                else:
                    st.button("Doğrulandı ✅", key=f"ok_{i}", disabled=True)
                st.markdown("</div>", unsafe_allow_html=True)
                
            with c_btn2:
                st.markdown("<div class='btn-red'>", unsafe_allow_html=True)
                if st.button("Hatalı/Eksik", key=f"err_{i}"):
                    # Gerekirse silme veya kırmızı işaretleme eklenebilir
                    st.session_state.evidences.pop(i)
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    with col_right:
        st.markdown("<div class='right-panel-card'>", unsafe_allow_html=True)
        st.markdown("#### 35-101 Matris Uygunluğu")
        
        # Sonuç Listesi (Eğer kurallar işletildiyse)
        if st.session_state.results:
            for r in st.session_state.results:
                icon = "✅" if r.status == "OK" else "❌"
                color = "green" if r.status == "OK" else "red"
                st.markdown(f"<div style='border-bottom:1px solid #eee; padding:5px 0;'><span>{r.code}</span> <span style='float:right; color:{color}; font-weight:bold;'>{icon}</span></div>", unsafe_allow_html=True)
            
            # Skor Çemberi Hesaplama
            total = len(st.session_state.results)
            passed = sum(1 for r in st.session_state.results if r.status == "OK")
            score = int((passed / total) * 100) if total > 0 else 0
            
            st.markdown(f"<div class='score-circle'>%{score}</div>", unsafe_allow_html=True)
        else:
            st.info("Kurallar henüz işletilmedi.")
            st.markdown("<div class='score-circle'>%0</div>", unsafe_allow_html=True)
            
        st.markdown("<hr>", unsafe_allow_html=True)
        
        # Mavi İşlem Butonları
        st.markdown("<div class='btn-blue'>", unsafe_allow_html=True)
        if st.button("Kuralları İşlet & Değerlendir"):
            excel_template_path = "templates/35-101.xlsx" if os.path.exists("templates/35-101.xlsx") else "35-101.xlsx"
            if os.path.exists(excel_template_path):
                st.session_state.results = evaluate(
                    evidences=st.session_state.evidences, 
                    rank=st.session_state.get("p_rank", "Master"), 
                    excel_path=excel_template_path, 
                    is_tanker=st.session_state.get("is_tanker", False)
                )
                st.rerun()
            else:
                st.error("35-101.xlsx bulunamadı!")
        st.markdown("</div>", unsafe_allow_html=True)
        
        # ZIP İndirme (Word/Excel Raporu Üret)
        if st.session_state.results:
            personel_info = {
                "name": st.session_state.get("p_name", "Personel"),
                "rank": st.session_state.get("p_rank", "Rank"),
                "vessel": st.session_state.get("p_vessel", ""),
                "date": datetime.now().strftime("%d.%m.%Y")
            }
            try:
                import tempfile
                excel_template = "templates/35-101.xlsx" if os.path.exists("templates/35-101.xlsx") else "35-101.xlsx"
                word_template = "templates/35-102.docx" if os.path.exists("templates/35-102.docx") else "35-102.docx"
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_excel:
                    fill_excel(excel_template, tmp_excel.name, st.session_state.results, personel_info)
                    excel_path = tmp_excel.name
                    
                with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_word:
                    fill_word(word_template, tmp_word.name, st.session_state.results, personel_info, st.session_state.get("operator_name", "Admin"))
                    word_path = tmp_word.name
                
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                    zip_file.write(excel_path, f"35-101_{personel_info['name']}.xlsx")
                    zip_file.write(word_path, f"35-102_{personel_info['name']}.docx")
                
                st.markdown("<div class='btn-blue'>", unsafe_allow_html=True)
                st.download_button(
                    label="Word/Excel Raporu Üret (.ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name=f"Evrak_Kontrol_{personel_info['name']}.zip",
                    mime="application/zip"
                )
                st.markdown("</div>", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Dosya hatası: {str(e)}")
        
        st.markdown("</div>", unsafe_allow_html=True)
        
else:
    st.info("Lütfen sol menüden işlem seçiniz.")
