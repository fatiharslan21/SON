import streamlit as st
import pandas as pd
from selenium import webdriver
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
import locale

# --- 1. AYARLAR VE TASARIM ---
st.set_page_config(page_title="BDDK Analiz Pro", layout="wide", page_icon="🏦")

# CSS AYARLARI (BUTON RENGİ DÜZELTİLDİ)
st.markdown("""
<style>
    /* Genel Arka Plan */
    .stApp { background-color: #F8F9FA; }

    /* Yan Menü */
    [data-testid="stSidebar"] { 
        background-color: #FCB131; 
        border-right: 1px solid #d1d1d1;
    }
    [data-testid="stSidebar"] * { 
        color: #000000 !important; 
        font-family: 'Arial', sans-serif;
    }

    /* BUTON AYARLARI - DÜZELTİLDİ: Sarı Zemin, Siyah Yazı */
    div.stButton > button { 
        background-color: #000000 !important; 
        color: #FCB131 !important; /* Sarı yazı */
        font-weight: 900; 
        border-radius: 8px; 
        border: 2px solid #000000; 
        width: 100%; 
        padding: 12px;
        font-size: 16px;
        transition: all 0.3s ease;
    }
    div.stButton > button:hover { 
        background-color: #FCB131 !important; /* Üzerine gelince Sarı */
        color: #000000 !important; /* Yazı siyah */
        border: 2px solid #000000;
        transform: scale(1.02);
    }

    /* Metrik Kartları */
    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        border-top: 5px solid #FCB131;
    }
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
    "📊 Sermaye Yeterliliği Rasyosu": {"tab": "#tabloListesiItem-12", "row_text": "Sermaye Yeterliliği Standart Rasyosu",
                                      "col_id": "grdRapor_Toplam"},
    "💰 DÖNEM NET KARI": {"tab": "tabloListesiItem-2", "row_text": "DÖNEM NET KARI (ZARARI)",
                         "col_id": "grdRapor_Toplam"},
    "🏦 Toplam Krediler": {"tab": "tabloListesiItem-3", "row_text": "Toplam Krediler", "col_id": "grdRapor_Toplam"},
    "🏠 Tüketici Kredileri": {"tab": "tabloListesiItem-4", "row_text": "Tüketici Kredileri",
                             "col_id": "grdRapor_Toplam"},
    "🏭 KOBİ Kredileri": {"tab": "tabloListesiItem-6", "row_text": "Toplam KOBİ Kredileri",
                         "col_id": "grdRapor_NakdiKrediToplam"}
}


# --- 3. DRIVER ---
@st.cache_resource
def get_driver():
    if sys.platform == "linux":
        options = FirefoxOptions()
        options.add_argument("--headless")
        try:
            service = FirefoxService(GeckoDriverManager().install())
        except:
            service = FirefoxService("/usr/local/bin/geckodriver")
        return webdriver.Firefox(service=service, options=options)
    else:
        options = ChromeOptions()
        # Debug yaparken headless'ı kapatabilirsin, production'da aç
        options.add_argument("--headless")
        service = ChromeService(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)


# --- 4. VERİ ÇEKME MOTORU (GARANTİCİ YÖNTEM) ---
def scrape_bddk(bas_yil, bas_ay, bit_yil, bit_ay, secilen_taraflar, secilen_veriler, status_container):
    driver = None
    data = []

    try:
        driver = get_driver()
        # Sayfa yüklenmezse beklemesin, timeout verip devam etsin
        driver.set_page_load_timeout(30)

        status_container.info("🌐 BDDK sunucularına bağlanılıyor...")
        driver.get("https://www.bddk.org.tr/bultenaylik")
        time.sleep(3)  # İlk açılış beklemesi

        bas_idx = AY_LISTESI.index(bas_ay)
        bit_idx = AY_LISTESI.index(bit_ay)

        # İlerleme Çubuğu İçin
        total_steps = (bit_yil - bas_yil) * 12 + (bit_idx - bas_idx) + 1
        current_step = 0
        progress_bar = st.progress(0)

        # --- YIL DÖNGÜSÜ ---
        for yil in range(bas_yil, bit_yil + 1):
            s_m = bas_idx if yil == bas_yil else 0
            e_m = bit_idx if yil == bit_yil else 11

            # YILI SEÇ (Her yıl değiştiğinde)
            try:
                driver.execute_script("document.getElementById('ddlYil').style.display = 'block';")
                select_yil = Select(driver.find_element(By.ID, "ddlYil"))
                select_yil.select_by_visible_text(str(yil))
                time.sleep(2)  # Yıl değişince sayfa yenilenir
            except Exception as e:
                st.error(f"Yıl seçilemedi: {e}")

            # --- AY DÖNGÜSÜ ---
            for ay_i in range(s_m, e_m + 1):
                ay_str = AY_LISTESI[ay_i]
                donem = f"{ay_str} {yil}"
                status_container.warning(f"🔄 Veri Çekiliyor: **{donem}**")

                try:
                    # AYI SEÇ
                    driver.execute_script("document.getElementById('ddlAy').style.display = 'block';")
                    # DİKKAT: Elementi her seferinde yeniden buluyoruz (Stale Element Hatası Olmasın diye)
                    select_ay = Select(driver.find_element(By.ID, "ddlAy"))
                    select_ay.select_by_visible_text(ay_str)

                    # KRİTİK BEKLEME: Sayfanın yenilenmesini bekle
                    time.sleep(3)

                    # --- TARAF DÖNGÜSÜ ---
                    for taraf in secilen_taraflar:
                        # TARAFI SEÇ
                        driver.execute_script("document.getElementById('ddlTaraf').style.display = 'block';")
                        select_taraf = Select(driver.find_element(By.ID, "ddlTaraf"))

                        # Tarafı bul ve seç
                        for opt in select_taraf.options:
                            if taraf in opt.text:
                                select_taraf.select_by_visible_text(opt.text)
                                break

                        # KRİTİK BEKLEME: Taraf değişince tablo yenilenir
                        time.sleep(2.5)

                        # ARTIK HTML'İ ALABİLİRİZ
                        # Bu komut en son yüklenen sayfanın HTML'ini alır
                        soup = BeautifulSoup(driver.page_source, 'html.parser')

                        # İSTENEN VERİLERİ BUL
                        for veri in secilen_veriler:
                            conf = VERI_KONFIGURASYONU[veri]

                            # Sekme Değiştirme (Eğer gerekliyse)
                            if conf['tab'] not in driver.page_source:
                                try:
                                    driver.execute_script(f"document.getElementById('{conf['tab']}').click();")
                                    time.sleep(1)
                                    soup = BeautifulSoup(driver.page_source, 'html.parser')  # HTML'i güncelle
                                except:
                                    pass

                            # Tablo Satırlarını Tara
                            target_rows = soup.find_all("tr")
                            for row in target_rows:
                                if conf['row_text'] in row.get_text():
                                    cols = row.find_all("td")
                                    found_val = None

                                    # Sütunları tara
                                    for col in cols:
                                        if conf['col_id'] in str(col.attrs):
                                            raw_text = col.get_text().strip()
                                            # Sayıya çevir (1.250,50 -> 1250.50)
                                            clean_text = raw_text.replace('.', '').replace(',', '.')
                                            try:
                                                found_val = float(clean_text)
                                            except:
                                                found_val = 0.0
                                            break

                                    if found_val is not None:
                                        data.append({
                                            "Dönem": donem,
                                            "Taraf": taraf,
                                            "Kalem": veri,
                                            "Değer": found_val,
                                            "TarihObj": pd.Timestamp(year=yil, month=ay_i + 1, day=1)
                                        })
                                    break  # Satırı bulduk, diğer satırlara bakma

                except Exception as loop_e:
                    st.error(f"Döngü hatası ({donem}): {loop_e}")

                current_step += 1
                progress_bar.progress(min(current_step / max(1, total_steps), 1.0))

    except Exception as e:
        st.error(f"Genel Hata: {e}")
    finally:
        if driver: driver.quit()

    return pd.DataFrame(data)


# --- YAN MENÜ ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/e/e0/Vak%C4%B1fBank_logo.svg", width=200)
    st.header("⚙️ AYARLAR")

    col1, col2 = st.columns(2)
    bas_yil = col1.number_input("Başlangıç Yıl", 2020, 2030, 2024)
    bas_ay = col2.selectbox("Başlangıç Ay", AY_LISTESI, index=0)

    col3, col4 = st.columns(2)
    bit_yil = col3.number_input("Bitiş Yıl", 2020, 2030, 2024)
    bit_ay = col4.selectbox("Bitiş Ay", AY_LISTESI, index=2)  # Mart

    st.markdown("---")
    secilen_taraflar = st.multiselect("Banka Grubu", TARAF_SECENEKLERI, default=["Sektör"])
    secilen_veriler = st.multiselect("Veri Kalemleri", list(VERI_KONFIGURASYONU.keys()), default=["📌 TOPLAM AKTİFLER"])

    st.markdown("---")
    btn = st.button("VERİLERİ ÇEK 🚀")

st.title("🏦 BDDK Finansal Analiz Paneli")

# Session State Tanımla
if 'df_sonuc' not in st.session_state:
    st.session_state['df_sonuc'] = None

if btn:
    status_box = st.empty()
    st.session_state['df_sonuc'] = None  # Eski veriyi temizle

    df = scrape_bddk(bas_yil, bas_ay, bit_yil, bit_ay, secilen_taraflar, secilen_veriler, status_box)

    if not df.empty:
        # Sayısal düzeltme
        df["Değer"] = pd.to_numeric(df["Değer"], errors='coerce')
        df = df.sort_values("TarihObj")

        st.session_state['df_sonuc'] = df
        status_box.success("✅ Veriler başarıyla çekildi!")
        time.sleep(1)
        st.rerun()
    else:
        status_box.error("Veri bulunamadı veya bağlantı hatası.")

# --- DASHBOARD ---
if st.session_state['df_sonuc'] is not None:
    df = st.session_state['df_sonuc']

    # SON DURUM KARTLARI
    son_tarih = df["TarihObj"].max()
    df_son = df[df["TarihObj"] == son_tarih]

    st.markdown(f"### 📊 Pazar Durumu ({df_son.iloc[0]['Dönem']})")
    cols = st.columns(4)
    for i, (idx, row) in enumerate(df_son.head(4).iterrows()):
        with cols[i]:
            st.metric(f"{row['Taraf']}", f"{row['Değer']:,.0f}", f"{row['Kalem'][:15]}...")

    st.markdown("---")

    # SEKMELER
    tab1, tab2, tab3 = st.tabs(["📈 Trend", "🔮 Simülasyon", "📥 Excel"])

    with tab1:
        # GRAFİK
        g_kalem = st.selectbox("Grafik Verisi:", df["Kalem"].unique())
        df_g = df[df["Kalem"] == g_kalem].sort_values("TarihObj")

        fig = px.area(df_g, x="TarihObj", y="Değer", color="Taraf",
                      title=f"{g_kalem} Zaman Serisi",
                      color_discrete_sequence=["#FCB131", "#333333", "#A6A6A6"])
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        # SİMÜLASYON
        c1, c2 = st.columns([1, 3])
        with c1:
            oran = st.slider("Aylık Büyüme Tahmini (%)", -5.0, 10.0, 3.0)
            s_kalem = st.selectbox("Hangi Veri?", df["Kalem"].unique())

        with c2:
            # Basit projeksiyon
            df_sim = df[df["Kalem"] == s_kalem].copy()
            future_data = []
            for taraf in df_sim["Taraf"].unique():
                last_val = df_sim[df_sim["Taraf"] == taraf].iloc[-1]["Değer"]
                last_date = df_sim["TarihObj"].max()

                # Geçmiş
                for _, r in df_sim[df_sim["Taraf"] == taraf].iterrows():
                    future_data.append({"Tarih": r["TarihObj"], "Değer": r["Değer"], "Tip": "Gerçek"})

                # Gelecek
                curr = last_val
                dt = last_date
                for _ in range(6):
                    dt += pd.DateOffset(months=1)
                    curr *= (1 + oran / 100)
                    future_data.append({"Tarih": dt, "Değer": curr, "Tip": "Tahmin"})

            df_f = pd.DataFrame(future_data)
            fig_f = px.line(df_f, x="Tarih", y="Değer", line_dash="Tip", title="6 Aylık Tahmin")
            st.plotly_chart(fig_f, use_container_width=True)

    with tab3:
        st.dataframe(df)