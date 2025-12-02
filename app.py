import streamlit as st
import pandas as pd
from selenium import webdriver
# Kütüphaneler
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from bs4 import BeautifulSoup
import plotly.express as px
import plotly.graph_objects as go
import time
import sys
import os

# --- 1. AYARLAR VE TASARIM ---
st.set_page_config(page_title="Finansal Analiz Pro", layout="wide", page_icon="🏦")

# VAKIFBANK TEMASI - GÜNCELLENMİŞ CSS
st.markdown("""
<style>
    /* Genel Arka Plan */
    .stApp { background-color: #F9F9F9; }

    /* Yan Menü - Vakıf Sarı */
    [data-testid="stSidebar"] { 
        background-color: #FCB131; 
        border-right: 1px solid #e0e0e0;
    }

    /* Yan Menü Yazı Rengi */
    [data-testid="stSidebar"] * { 
        color: #000000 !important; 
        font-family: 'Segoe UI', sans-serif;
    }

    /* BUTON DÜZELTMESİ: SİYAH ZEMİN, BEYAZ YAZI */
    div.stButton > button { 
        background-color: #000000 !important; 
        color: #FFFFFF !important; /* YAZI RENGİ ARTIK BEYAZ */
        font-weight: 900 !important; 
        border-radius: 8px; 
        border: 2px solid #FFFFFF; 
        width: 100%; 
        padding: 15px;
        font-size: 18px !important;
        transition: all 0.3s ease;
    }
    div.stButton > button:hover { 
        background-color: #333333 !important; 
        color: #FCB131 !important; /* Hoverda Sarı */
        border-color: #FCB131 !important;
        transform: scale(1.02);
    }

    /* Metrik Kartları */
    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border-top: 5px solid #FCB131;
    }
    [data-testid="stMetricLabel"] { font-weight: bold; color: #555; }
    [data-testid="stMetricValue"] { color: #000000; font-weight: 800; font-size: 26px !important; }

    /* Başlıklar */
    h1, h2, h3 { color: #d99000 !important; font-weight: 800; }

    /* Tablo Font */
    .dataframe { font-size: 14px !important; }
</style>
""", unsafe_allow_html=True)

# --- 2. CONFIG ---
AY_LISTESI = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım",
              "Aralık"]
TARAF_SECENEKLERI = ["Sektör", "Mevduat-Kamu", "Mevduat-Yerli Özel", "Mevduat-Yabancı", "Katılım"]

VERI_KONFIGURASYONU = {
    "📌 TOPLAM AKTİFLER": {"tab": "tabloListesiItem-1", "row_text": "TOPLAM AKTİFLER", "col_id": "grdRapor_Toplam"},
    "📌 TOPLAM ÖZKAYNAKLAR": {"tab": "tabloListesiItem-1", "row_text": "TOPLAM ÖZKAYNAKLAR",
                             "col_id": "grdRapor_Toplam"},
    "⚠️ Takipteki Alacaklar": {"tab": "tabloListesiItem-1", "row_text": "Takipteki Alacaklar",
                               "col_id": "grdRapor_Toplam"},
    "💰 DÖNEM NET KARI": {"tab": "tabloListesiItem-2", "row_text": "DÖNEM NET KARI (ZARARI)",
                         "col_id": "grdRapor_Toplam"},
    "🏦 Toplam Krediler": {"tab": "tabloListesiItem-3", "row_text": "Toplam Krediler", "col_id": "grdRapor_Toplam"},
    "🏠 Tüketici Kredileri": {"tab": "tabloListesiItem-4", "row_text": "Tüketici Kredileri",
                             "col_id": "grdRapor_Toplam"},
    "🏭 KOBİ Kredileri": {"tab": "tabloListesiItem-6", "row_text": "Toplam KOBİ Kredileri",
                         "col_id": "grdRapor_NakdiKrediToplam"}
}


# --- 3. DRIVER YÖNETİMİ ---
def get_driver():
    if sys.platform == "linux":
        # Cloud (Firefox)
        options = FirefoxOptions()
        options.add_argument("--headless")
        options.binary_location = "/usr/bin/firefox"
        try:
            service = FirefoxService(GeckoDriverManager().install())
        except:
            service = FirefoxService("/usr/local/bin/geckodriver")
        return webdriver.Firefox(service=service, options=options)
    else:
        # Local (Chrome)
        options = ChromeOptions()
        service = ChromeService(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)


# --- 4. VERİ ÇEKME MOTORU ---
def scrape_bddk(bas_yil, bas_ay, bit_yil, bit_ay, secilen_taraflar, secilen_veriler, status_container):
    driver = None
    data = []

    try:
        driver = get_driver()
        driver.set_page_load_timeout(60)
        status_container.info("🌐 BDDK sunucularına bağlanılıyor...")
        driver.get("https://www.bddk.org.tr/bultenaylik")

        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "ddlYil")))
        time.sleep(3)

        bas_idx = AY_LISTESI.index(bas_ay)
        bit_idx = AY_LISTESI.index(bit_ay)
        total_steps = (bit_yil - bas_yil) * 12 + (bit_idx - bas_idx) + 1
        current_step = 0
        progress_bar = st.progress(0)

        for yil in range(bas_yil, bit_yil + 1):
            s_m = bas_idx if yil == bas_yil else 0
            e_m = bit_idx if yil == bit_yil else 11

            for ay_i in range(s_m, e_m + 1):
                ay_str = AY_LISTESI[ay_i]
                donem = f"{ay_str} {yil}"
                status_container.info(f"⏳ İşleniyor: **{donem}**")

                try:
                    driver.execute_script("document.getElementById('ddlYil').style.display = 'block';")
                    Select(driver.find_element(By.ID, "ddlYil")).select_by_visible_text(str(yil))
                    time.sleep(2)

                    driver.execute_script("document.getElementById('ddlAy').style.display = 'block';")
                    Select(driver.find_element(By.ID, "ddlAy")).select_by_visible_text(ay_str)
                    time.sleep(4)

                    for taraf in secilen_taraflar:
                        driver.execute_script("document.getElementById('ddlTaraf').style.display = 'block';")
                        select_taraf = Select(driver.find_element(By.ID, "ddlTaraf"))

                        try:
                            select_taraf.select_by_visible_text(taraf)
                        except:
                            for opt in select_taraf.options:
                                if taraf in opt.text:
                                    select_taraf.select_by_visible_text(opt.text)
                                    break
                        time.sleep(3)

                        soup = BeautifulSoup(driver.page_source, 'html.parser')

                        for veri in secilen_veriler:
                            conf = VERI_KONFIGURASYONU[veri]
                            try:
                                driver.execute_script(f"document.getElementById('{conf['tab']}').click();")
                                time.sleep(1.5)
                                soup = BeautifulSoup(driver.page_source, 'html.parser')
                            except:
                                pass

                            target_rows = soup.find_all("tr")
                            for row in target_rows:
                                if conf['row_text'] in row.get_text():
                                    cols = row.find_all("td")
                                    found_val = None
                                    for col in cols:
                                        cell_attrs = str(col.attrs)
                                        if conf['col_id'] in cell_attrs:
                                            raw_text = col.get_text().strip()
                                            clean_text = raw_text.replace('.', '').replace(',', '.')
                                            try:
                                                found_val = float(clean_text)
                                            except:
                                                found_val = 0.0
                                            break

                                    if found_val is not None:
                                        data.append({
                                            "Dönem": donem, "Taraf": taraf, "Kalem": veri, "Değer": found_val,
                                            "TarihObj": pd.to_datetime(f"{yil}-{ay_i + 1}-01")
                                        })
                                    break

                except Exception as step_e:
                    pass

                current_step += 1
                progress_bar.progress(current_step / max(1, total_steps))

    except Exception as e:
        st.error(f"Sunucu Hatası: {e}")
    finally:
        if driver: driver.quit()

    return pd.DataFrame(data)


# --- ANA EKRAN ---
with st.sidebar:
    # FOTOĞRAF KALDIRILDI
    st.title("🎛️ KONTROL PANELİ")
    st.markdown("---")
    c1, c2 = st.columns(2)
    bas_yil = c1.number_input("Başlangıç Yılı", 2024, 2030, 2024)
    bas_ay = c1.selectbox("Başlangıç Ayı", AY_LISTESI, index=0)
    c3, c4 = st.columns(2)
    bit_yil = c3.number_input("Bitiş Yılı", 2024, 2030, 2024)
    bit_ay = c4.selectbox("Bitiş Ayı", AY_LISTESI, index=0)
    st.markdown("---")
    secilen_taraflar = st.multiselect("Karşılaştır:", TARAF_SECENEKLERI, default=["Sektör"])
    secilen_veriler = st.multiselect("Veri:", list(VERI_KONFIGURASYONU.keys()), default=["📌 TOPLAM AKTİFLER"])
    st.markdown("---")
    st.markdown("### 🚀 İŞLEM MERKEZİ")
    btn = st.button("ANALİZİ BAŞLAT")

st.title("🏦 BDDK Finansal Analiz Pro")

if 'df_sonuc' not in st.session_state:
    st.session_state['df_sonuc'] = None

if btn:
    status = st.empty()
    st.session_state['df_sonuc'] = None
    df = scrape_bddk(bas_yil, bas_ay, bit_yil, bit_ay, secilen_taraflar, secilen_veriler, status)

    if not df.empty:
        st.session_state['df_sonuc'] = df
        status.success("✅ Veriler Başarıyla Çekildi!")
        st.balloons()
        time.sleep(1)
        st.rerun()
    else:
        status.error("Veri bulunamadı. Lütfen tekrar deneyin.")

# --- DASHBOARD (ŞOV KISMI) ---
if st.session_state['df_sonuc'] is not None:
    df = st.session_state['df_sonuc']
    df = df.sort_values("TarihObj")

    # 1. KPI KARTLARI
    st.subheader("📊 Özet Performans (Son Dönem)")
    try:
        son_tarih = df["TarihObj"].max()
        df_son = df[df["TarihObj"] == son_tarih]

        cols = st.columns(4)
        for i, (idx, row) in enumerate(df_son.head(4).iterrows()):
            with cols[i % 4]:
                prev_val = 0
                df_prev = df[df["TarihObj"] < son_tarih]
                if not df_prev.empty:
                    prev_rows = df_prev[(df_prev["Kalem"] == row["Kalem"]) & (df_prev["Taraf"] == row["Taraf"])]
                    if not prev_rows.empty:
                        prev_val = prev_rows.iloc[-1]["Değer"]

                delta_val = row["Değer"] - prev_val
                delta_pct = (delta_val / prev_val * 100) if prev_val != 0 else 0

                val_fmt = f"{row['Değer']:,.0f}".replace(",", ".")

                st.metric(
                    label=f"{row['Taraf']}",
                    value=f"{val_fmt}",
                    delta=f"%{delta_pct:.1f} ({row['Kalem'][:15]}...)"
                )
    except:
        pass

    st.markdown("---")

    # 2. GELİŞMİŞ GRAFİK SEKMELERİ
    st.subheader("📈 Gelişmiş Analiz ve Simülasyon")

    # YENİ EKLENEN 3D SİMÜLASYON SEKME 4 OLARAK GELDİ
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["📉 Trend (Area)", "📊 Sektör Payı (Bar)", "🪐 3D Simülasyon", "🍩 Pazar (Pie)", "📑 Veri Tablosu"])

    # 1. SEKME: AREA CHART (GRAFİK DÜZELTME EKLENDİ)
    with tab1:
        kalem_sec = st.selectbox("Grafik Kalemi:", df["Kalem"].unique(), key="ts_select")
        df_chart = df[df["Kalem"] == kalem_sec].copy()

        # --- KRİTİK DÜZELTME: Veriyi zorla float yapıyoruz ki grafik ters dönmesin ---
        df_chart["Değer"] = df_chart["Değer"].astype(float)

        fig = px.area(df_chart, x="Dönem", y="Değer", color="Taraf",
                      title=f"📅 {kalem_sec} - Tarihsel Gelişim",
                      markers=True,
                      # Y ekseninin otomatik ayarlanmasını sağla (Ters dönmeyi engeller)
                      category_orders={"Dönem": sorted(df_chart["Dönem"].unique())},
                      color_discrete_sequence=["#FCB131", "#000000", "#555555", "#A6A6A6"])

        # Y eksenini 0'dan başlat ve formatla
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", hovermode="x unified")
        fig.update_yaxes(autorange=True, tickformat=",")
        st.plotly_chart(fig, use_container_width=True)

    # 2. SEKME: BAR CHART
    with tab2:
        df_son_chart = df[df["TarihObj"] == df["TarihObj"].max()].copy()
        df_son_chart["Değer"] = df_son_chart["Değer"].astype(float)  # Float garanti

        fig_bar = px.bar(df_son_chart, x="Kalem", y="Değer", color="Taraf", barmode="group",
                         text_auto='.2s',
                         title="Son Dönem Karşılaştırmalı Büyüklük",
                         color_discrete_sequence=["#FCB131", "#000000", "#555555"])
        fig_bar.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        fig_bar.update_yaxes(autorange=True)
        st.plotly_chart(fig_bar, use_container_width=True)

    # 3. SEKME: 3D SİMÜLASYON (YENİ İSTEK)
    with tab3:
        st.markdown("#### 🪐 Finansal Veri Uzayı (3D)")
        st.info("Bu grafik verileri 3 boyutlu uzayda simüle eder. Mouse ile döndürebilirsiniz.")

        df_3d = df.copy()
        df_3d["Değer"] = df_3d["Değer"].astype(float)

        # 3D Scatter Plot
        fig_3d = px.scatter_3d(df_3d, x='TarihObj', y='Taraf', z='Değer',
                               size='Değer', color='Kalem',
                               hover_data=['Dönem', 'Değer'],
                               title="Zaman - Taraf - Tutar Uzayı",
                               color_discrete_sequence=px.colors.qualitative.Dark24)

        fig_3d.update_layout(
            scene=dict(
                xaxis_title='Zaman Ekseni',
                yaxis_title='Taraf (Sektör/Kamu)',
                zaxis_title='Tutar (TL)',
                xaxis=dict(backgroundcolor="black", gridcolor="gray"),
                yaxis=dict(backgroundcolor="black", gridcolor="gray"),
                zaxis=dict(backgroundcolor="black", gridcolor="gray"),
            ),
            paper_bgcolor="#1E1E1E",  # Koyu mod
            font=dict(color="white")
        )
        st.plotly_chart(fig_3d, use_container_width=True)

    # 4. SEKME: PIE CHART
    with tab4:
        col1, col2 = st.columns([1, 2])
        with col1:
            pie_kalem = st.radio("Kalem Seç:", df["Kalem"].unique(), key="pie_rad")
        with col2:
            df_pie = df[(df["TarihObj"] == df["TarihObj"].max()) & (df["Kalem"] == pie_kalem)]
            fig_pie = px.pie(df_pie, values="Değer", names="Taraf", hole=0.4,
                             title=f"{pie_kalem} Dağılımı",
                             color_discrete_sequence=["#FCB131", "#000000", "#333333", "#666666"])
            fig_pie.update_traces(textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)

    # 5. SEKME: TABLO
    with tab5:
        pivot_df = df.pivot_table(index="Dönem", columns=["Kalem", "Taraf"], values="Değer", aggfunc="sum")
        display_df = pivot_df.applymap(lambda x: f"{x:,.0f}".replace(",", ".") if pd.notnull(x) else "-")

        st.dataframe(display_df, use_container_width=True, height=400)

        st.markdown("---")
        buffer = "BDDK_Rapor.xlsx"
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.drop(columns=["TarihObj"]).to_excel(writer, sheet_name="Ham Veri", index=False)
            for k in df["Kalem"].unique():
                safe_name = "".join(c for c in k if c.isalnum())[:30]
                df[df["Kalem"] == k].pivot(index="Dönem", columns="Taraf", values="Değer").to_excel(writer,
                                                                                                    sheet_name=safe_name)

        with open(buffer, "rb") as f:
            st.download_button(
                label="📥 EXCEL RAPORUNU İNDİR (Tam Formatlı)",
                data=f,
                file_name="Vakif_Analiz_Pro.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )