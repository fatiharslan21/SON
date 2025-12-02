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

# VAKIFBANK TEMASI VE ŞIK GÖRÜNÜM
st.markdown("""
<style>
    /* Genel Arka Plan */
    .stApp { background-color: #F9F9F9; }

    /* Yan Menü - Vakıf Sarı */
    [data-testid="stSidebar"] { 
        background-color: #FCB131; 
        border-right: 1px solid #e0e0e0;
    }
    [data-testid="stSidebar"] * { 
        color: #000000 !important; 
        font-family: 'Segoe UI', sans-serif;
    }

    /* Butonlar */
    div.stButton > button { 
        background-color: #000000; 
        color: #FCB131 !important; 
        font-weight: bold; 
        border-radius: 8px; 
        border: none; 
        width: 100%; 
        padding: 10px;
        transition: all 0.3s ease;
    }
    div.stButton > button:hover { 
        background-color: #333333; 
        color: #FFFFFF !important;
        transform: scale(1.02);
    }

    /* Metrik Kartları */
    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border-left: 5px solid #FCB131;
    }
    [data-testid="stMetricLabel"] { font-weight: bold; color: #555; }
    [data-testid="stMetricValue"] { color: #000000; font-weight: 800; }

    /* Başlıklar */
    h1, h2, h3 { color: #d99000 !important; font-weight: 800; }
</style>
""", unsafe_allow_html=True)

# --- 2. CONFIG ---
AY_LISTESI = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım",
              "Aralık"]
TARAF_SECENEKLERI = ["Sektör", "Mevduat-Kamu", "Mevduat-Yerli Özel", "Mevduat-Yabancı", "Katılım"]

# col_id: HTML içinde veriyi tutan hücrenin özel kimliği
VERI_KONFIGURASYONU = {
    "📌 TOPLAM AKTİFLER": {"tab": "tabloListesiItem-1", "row_text": "TOPLAM AKTİFLER", "col_id": "grdRapor_Toplam"},
    "📌 TOPLAM ÖZKAYNAKLAR": {"tab": "tabloListesiItem-1", "row_text": "TOPLAM ÖZKAYNAKLAR",
                             "col_id": "grdRapor_Toplam"},
    "⚠️ Takipteki Alacaklar": {"tab": "tabloListesiItem-1", "row_text": "Takipteki Alacaklar",
                               "col_id": "grdRapor_Toplam"},
    "📊 Sermaye Yeterliliği Rasyosu": {"tab": "#tabloListesiItem-12", "row_text": "Sermaye Yeterliliği Standart Rasyosu",
                                      "col_attr": "grdRapor_Toplam"},
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
                    # 1. YIL SEÇİMİ (Mekanik)
                    driver.execute_script("document.getElementById('ddlYil').style.display = 'block';")
                    Select(driver.find_element(By.ID, "ddlYil")).select_by_visible_text(str(yil))
                    time.sleep(2)

                    # 2. AY SEÇİMİ
                    driver.execute_script("document.getElementById('ddlAy').style.display = 'block';")
                    Select(driver.find_element(By.ID, "ddlAy")).select_by_visible_text(ay_str)
                    time.sleep(4)

                    # 3. TARAF SEÇİMİ
                    for taraf in secilen_taraflar:
                        driver.execute_script("document.getElementById('ddlTaraf').style.display = 'block';")
                        select_taraf = Select(driver.find_element(By.ID, "ddlTaraf"))

                        try:
                            select_taraf.select_by_visible_text(taraf)
                        except:
                            # Opsiyonel: Kısmi eşleşme
                            for opt in select_taraf.options:
                                if taraf in opt.text:
                                    select_taraf.select_by_visible_text(opt.text)
                                    break

                        time.sleep(3)

                        # HTML ÇEKME
                        soup = BeautifulSoup(driver.page_source, 'html.parser')

                        for veri in secilen_veriler:
                            conf = VERI_KONFIGURASYONU[veri]

                            # Sekme Tıklama
                            try:
                                driver.execute_script(f"document.getElementById('{conf['tab']}').click();")
                                time.sleep(1.5)  # Sekme geçişi için beklet
                                soup = BeautifulSoup(driver.page_source, 'html.parser')  # HTML'i yenile
                            except:
                                pass

                            # --- DÜZELTİLMİŞ DEĞER ALMA (FIX) ---
                            # Satırı bul
                            target_rows = soup.find_all("tr")
                            for row in target_rows:
                                if conf['row_text'] in row.get_text():
                                    # Şimdi hücreleri tarıyoruz ama rastgele değil!
                                    cols = row.find_all("td")

                                    found_val = None
                                    for col in cols:
                                        # HÜCRENİN KİMLİĞİNE BAK: 'aria-describedby' veya 'headers'
                                        # Bizim aradığımız ID (örn: grdRapor_Toplam) bu hücrede var mı?

                                        cell_attrs = str(col.attrs)  # Tüm özellikleri string yap

                                        if conf['col_id'] in cell_attrs:
                                            # İŞTE ARADIĞIMIZ DEĞER BU HÜCREDE!
                                            raw_text = col.get_text().strip()

                                            # Temizle ve Kaydet
                                            clean_text = raw_text.replace('.', '').replace(',', '.')
                                            try:
                                                found_val = float(clean_text)
                                            except:
                                                found_val = 0.0
                                            break  # Değeri bulduk, hücre döngüsünden çık

                                    if found_val is not None:
                                        data.append({
                                            "Dönem": donem,
                                            "Taraf": taraf,
                                            "Kalem": veri,
                                            "Değer": found_val,
                                            # Grafik sıralaması için tarih objesi
                                            "TarihObj": pd.to_datetime(f"{yil}-{ay_i + 1}-01")
                                        })
                                    break  # Satır döngüsünden çık

                except Exception as step_e:
                    print(f"Adım hatası: {step_e}")
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
    st.image("https://upload.wikimedia.org/wikipedia/commons/e/e0/Vak%C4%B1fBank_logo.svg", width=200)  # Logo Şovu
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
    btn = st.button("🚀 ANALİZİ BAŞLAT")

st.title("🏦 BDDK Finansal Analiz Pro")

if 'df_sonuc' not in st.session_state:
    st.session_state['df_sonuc'] = None

if btn:
    status = st.empty()
    st.session_state['df_sonuc'] = None  # Reset
    df = scrape_bddk(bas_yil, bas_ay, bit_yil, bit_ay, secilen_taraflar, secilen_veriler, status)

    if not df.empty:
        st.session_state['df_sonuc'] = df
        status.success("✅ Veriler Başarıyla Çekildi!")
        st.balloons()  # ŞOV ZAMANI: KONFETİLER!
        time.sleep(1)
        st.rerun()
    else:
        status.error("Veri bulunamadı. Lütfen tekrar deneyin.")

# --- DASHBOARD (Veri Varsa) ---
if st.session_state['df_sonuc'] is not None:
    df = st.session_state['df_sonuc']
    df = df.sort_values("TarihObj")  # Tarihe göre sırala

    # 1. KPI KARTLARI (ŞOV KISMI)
    st.subheader("📊 Özet Performans (Son Dönem)")
    try:
        son_tarih = df["TarihObj"].max()
        df_son = df[df["TarihObj"] == son_tarih]

        # En fazla 4 kolon göster
        cols = st.columns(min(len(df_son), 4))
        for i, (idx, row) in enumerate(df_son.head(4).iterrows()):
            with cols[i]:
                # Varsa önceki ayı bul
                prev_val = 0
                df_prev = df[df["TarihObj"] < son_tarih]
                if not df_prev.empty:
                    prev_rows = df_prev[(df_prev["Kalem"] == row["Kalem"]) & (df_prev["Taraf"] == row["Taraf"])]
                    if not prev_rows.empty:
                        prev_val = prev_rows.iloc[-1]["Değer"]

                delta_val = row["Değer"] - prev_val
                delta_pct = (delta_val / prev_val * 100) if prev_val != 0 else 0

                st.metric(
                    label=f"{row['Taraf']} - {row['Kalem'][:15]}...",
                    value=f"{row['Değer']:,.0f}",
                    delta=f"%{delta_pct:.1f}"
                )
    except:
        pass

    st.markdown("---")

    # 2. GRAFİK VE TABLOLAR
    tab1, tab2, tab3 = st.tabs(["📈 Trend Analizi", "📑 Detaylı Tablo", "📥 Rapor İndir"])

    with tab1:
        kalem = st.selectbox("Grafik Kalemi Seçiniz:", df["Kalem"].unique())
        df_chart = df[df["Kalem"] == kalem]

        # Area Chart (Daha Dolgun Görünüm)
        fig = px.area(df_chart, x="Dönem", y="Değer", color="Taraf",
                      title=f"{kalem} Gelişimi",
                      markers=True,
                      color_discrete_sequence=["#FCB131", "#000000", "#A6A6A6"])
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        pivot_df = df.pivot_table(index="Dönem", columns=["Kalem", "Taraf"], values="Değer", aggfunc="sum")
        st.dataframe(pivot_df, use_container_width=True)

    with tab3:
        buffer = "BDDK_Rapor.xlsx"
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.drop(columns=["TarihObj"]).to_excel(writer, sheet_name="Ham Veri", index=False)
            for k in df["Kalem"].unique():
                safe_name = "".join(c for c in k if c.isalnum())[:30]
                df[df["Kalem"] == k].pivot(index="Dönem", columns="Taraf", values="Değer").to_excel(writer,
                                                                                                    sheet_name=safe_name)

        with open(buffer, "rb") as f:
            st.download_button(
                label="📥 Excel Raporunu İndir",
                data=f,
                file_name="Vakif_Analiz.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )