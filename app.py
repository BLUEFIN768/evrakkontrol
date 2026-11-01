import streamlit as st
import io
import os
from datetime import datetime
from crew_core import Evidence, evaluate
from ai_extract import process_document, parse_uab_pdf_local
from fillers import fill_excel, fill_word

st.set_page_config(page_title="SeaReady Compliance", layout="wide", page_icon="⚓")

# --- SEAREADY ÖZEL CSS TASARIMI (BUNU EKLİYORUZ) ---
st.markdown("""
<style>
    /* Ana Arka Plan Rengi (Açık Mavi/Gri) */
    .stApp {
        background-color: #f0f4f8;
    }
    
    /* Metrik (İstatistik) Kutuları - Beyaz Kart Görünümü */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 15px 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    
    /* Sekme (Tab) Tasarımları */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #ffffff;
        border-radius: 8px 8px 0px 0px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        padding-top: 10px;
        padding-bottom: 10px;
    }
    
    /* Ana Butonların Tasarımı (Mavi ve Yuvarlak) */
    .stButton > button {
        background-color: #3b82f6;
        color: white;
        border-radius: 8px;
        border: none;
        font-weight: 600;
        transition: all 0.3s;
    }
    .stButton > button:hover {
        background-color: #2563eb;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
    }
    
    /* Yükleme (Uploader) Alanı Tasarımı */
    .css-1n76uvr {
        background-color: #ffffff;
        border-radius: 12px;
        border: 2px dashed #cbd5e1;
    }
    
    /* Girdi (Input) Kutuları */
    .stTextInput>div>div>input, .stSelectbox>div>div>select {
        border-radius: 8px;
        border: 1px solid #cbd5e1;
    }
</style>
""", unsafe_allow_html=True)
# --- CSS BİTİŞ ---

# Gizlilik ve Şifre Kontrolü (Kodun geri kalanı aynı şekilde devam ediyor...)
def check_password():
# ...
