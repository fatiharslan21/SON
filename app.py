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

# Türkçe Tarih Ayarı (Linux/Windows uyumlu)
try:
    locale.setlocale(locale.LC_ALL, 'tr_TR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'Turkish_Turkey.1254')
    except:
        pass

# --- 1. AYARLAR VE TASARIM ---
st.set_page_config(page_title="Finansal Analiz Pro", layout="wide", page_icon="🏦")

st.markdown("""
<style>
    .stApp { background-color: #F4F4F4; }
    [data-testid="stSidebar"] { background-color: #FCB131; border-right: 1px solid #e0e0e0; }
    [data-testid="stSidebar"] * { color: #000000 !important; }
    div.stButton > button { background-color: #000000; color: #FCB131 !important; border-radius: 8px; width: 100%; padding: 12px; }
    div.stButton > button:hover { background-color: #333333; color: #FFFFFF !important; transform: scale(1.02); }
    [data-testid="stMetric"] { background-color: #FFFFFF; padding: 15px; border-radius: 12px; border-left: 6px solid #FCB131; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
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


# --- 3. DRIVER YÖNETİMİ ---
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
        # options.add_argument("--headless") # Hata ayıklarken bunu kapatabilirsin
        service = ChromeService(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)


# --- 4. VERİ ÇEKME MOTORU (SENİN SAĞLAM MANTIĞIN) ---
def scrape_bddk(bas_yil, bas_ay, bit_yil, bit_ay, secilen_taraflar, secilen_veriler, status_container):
    driver = None
    data = []

    try:
        driver = get_driver()
        driver.set_page_load_timeout(60)
        status_container.info("🌐 BDDK Bağlantısı Kuruluyor...")
        driver.get("https://www.bddk.org.tr/bultenaylik")

        # Sayfanın oturması için bekle
        time.sleep(3)

        bas_idx = AY_LISTESI.index(bas_ay)
        bit_idx = AY_LISTESI.index(bit_ay)

        # Toplam adım sayısı (Progress Bar için)
        total_steps = (bit_yil - bas_yil) * 12 + (bit_idx - bas_idx) + 1
        current_step = 0
        progress_bar = st.progress(0)

        # --- DÖNGÜ MANTIĞI: Yıl -> Ay ---
        for yil in range(bas_yil, bit_yil + 1):
            s_m = bas_idx if yil == bas_yil else 0
            e_m = bit_idx if yil == bit_yil else 11

            for ay_i in range(s_m, e_m + 1):
                ay_str = AY_LISTESI[ay_i]
                donem = f"{ay_str} {yil}"
                status_container.info(f"⏳ İşleniyor: **{donem}** (Lütfen bekleyiniz, sayfa yenileniyor...)")

                try:
                    # 1. YIL SEÇİMİ
                    driver.execute_script("document.getElementById('ddlYil').style.display = 'block';")
                    select_yil = Select(driver.find_element(By.ID, "ddlYil"))
                    select_yil.select_by_visible_text(str(yil))
                    time.sleep(2.5)  # Sayfa refresh süresi

                    # 2. AY SEÇİMİ
                    driver.execute_script("document.getElementById('ddlAy').style.display = 'block';")
                    select_ay = Select(driver.find_element(By.ID, "ddlAy"))
                    select_ay.select_by_visible_text(ay_str)
                    time.sleep(2.5)  # Sayfa refresh süresi

                    # 3. TARAF SEÇİMİ
                    for taraf in secilen_taraflar:
                        driver.execute_script("document.getElementById('ddlTaraf').style.display = 'block';")
                        select_taraf = Select(driver.find_element(By.ID, "ddlTaraf"))

                        # Kısmi eşleşme ile seç
                        found = False
                        for opt in select_taraf.options:
                            if taraf in opt.text:
                                select_taraf.select_by_visible_text(opt.text)
                                found = True
                                break
                        if not found: continue

                        time.sleep(2)  # Taraf değişince tablo güncelleniyor, bekle!

                        # 4. VERİ ÇEKME (HTML Parse)
                        soup = BeautifulSoup(driver.page_source, 'html.parser')

                        for veri in secilen_veriler:
                            conf = VERI_KONFIGURASYONU[veri]

                            # Sekme Tıklama (Gerekirse)
                            if conf['tab'] not in driver.page_source:
                                try:
                                    driver.execute_script(f"document.getElementById('{conf['tab']}').click();")
                                    time.sleep(1)
                                    soup = BeautifulSoup(driver.page_source, 'html.parser')
                                except:
                                    pass

                            # Satır ve Sütun Bulma
                            target_rows = soup.find_all("tr")
                            for row in target_rows:
                                if conf['row_text'] in row.get_text():
                                    cols = row.find_all("td")
                                    found_val = None

                                    for col in cols:
                                        if conf['col_id'] in str(col.attrs):
                                            raw_text = col.get_text().strip()
                                            # Temizlik: 1.234,56 -> 1234.56 formatına
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
                                            # Sıralama için gerçek tarih objesi
                                            "TarihObj": pd.Timestamp(year=yil, month=ay_i + 1, day=1)
                                        })
                                    break  # Satırı bulduk, çık

                except Exception as step_e:
                    st.warning(f"Veri atlandı ({donem}): {step_e}")

                current_step += 1
                progress_bar.progress(min(current_step / max(1, total_steps), 1.0))

    except Exception as e:
        st.error(f"Bağlantı Hatası: {e}")
    finally:
        if driver: driver.quit()

    return pd.DataFrame(data)


# --- ANA EKRAN ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/e/e0/Vak%C4%B1fBank_logo.svg", width=200)
    st.title("BDDK ANALİZÖR")
    st.markdown("---")

    c1, c2 = st.columns(2)
    bas_yil = c1.number_input("Başlangıç Yılı", 2020, 2030, 2024)
    bas_ay = c1.selectbox("Başlangıç Ayı", AY_LISTESI, index=0)

    c3, c4 = st.columns(2)
    bit_yil = c3.number_input("Bitiş Yılı", 2020, 2030, 2024)
    bit_ay = c4.selectbox("Bitiş Ayı", AY_LISTESI, index=2)  # Mart varsayılan

    st.markdown("---")
    secilen_taraflar = st.multiselect("Banka Grubu:", TARAF_SECENEKLERI, default=["Sektör"])
    secilen_veriler = st.multiselect("Veri:", list(VERI_KONFIGURASYONU.keys()), default=["📌 TOPLAM AKTİFLER"])

    st.markdown("---")
    btn = st.button("🚀 VERİLERİ ÇEK VE ANALİZ ET")

st.title("🏦 BDDK Finansal Zeka ve Simülasyonu")

if 'df_sonuc' not in st.session_state:
    st.session_state['df_sonuc'] = None

if btn:
    status = st.empty()
    st.session_state['df_sonuc'] = None

    # Veri Çekme Fonksiyonunu Çağır
    df = scrape_bddk(bas_yil, bas_ay, bit_yil, bit_ay, secilen_taraflar, secilen_veriler, status)

    if not df.empty:
        # Sayısal Dönüşüm ve Sıralama (HAYATİ!)
        df["Değer"] = pd.to_numeric(df["Değer"], errors='coerce')
        df = df.sort_values("TarihObj")

        st.session_state['df_sonuc'] = df
        status.success("✅ Veriler Başarıyla Güncellendi!")
        time.sleep(1)
        st.rerun()
    else:
        status.error("Veri çekilemedi. Bağlantıyı kontrol edip tekrar deneyin.")

# --- DASHBOARD MODÜLÜ ---
if st.session_state['df_sonuc'] is not None:
    df = st.session_state['df_sonuc']

    # 1. KPI KARTLARI (SON AY)
    son_tarih = df["TarihObj"].max()
    df_son = df[df["TarihObj"] == son_tarih]

    st.markdown(f"### 📊 Özet Durum ({df_son.iloc[0]['Dönem']})")
    cols = st.columns(4)

    for i, (idx, row) in enumerate(df_son.head(4).iterrows()):
        # Önceki Ayı Bul
        prev_date = son_tarih - pd.DateOffset(months=1)
        df_prev = df[(df["TarihObj"].dt.year == prev_date.year) &
                     (df["TarihObj"].dt.month == prev_date.month) &
                     (df["Kalem"] == row["Kalem"]) &
                     (df["Taraf"] == row["Taraf"])]

        prev_val = df_prev.iloc[0]["Değer"] if not df_prev.empty else row["Değer"]
        degisim = ((row["Değer"] - prev_val) / prev_val * 100) if prev_val != 0 else 0

        with cols[i % 4]:
            st.metric(f"{row['Taraf']} - {row['Kalem'][:10]}..", f"{row['Değer']:,.0f}", f"%{degisim:.2f}")

    st.markdown("---")

    # SEKMELER
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Trend Analizi", "🔮 Gelecek Simülasyonu", "🌡️ Heatmap", "📥 Excel İndir"])

    # --- TAB 1: GRAFİK ---
    with tab1:
        g_kalem = st.selectbox("Grafik Kalemi:", df["Kalem"].unique())
        df_g = df[df["Kalem"] == g_kalem]

        fig = px.area(df_g, x="TarihObj", y="Değer", color="Taraf",
                      title=f"{g_kalem} Gelişimi",
                      color_discrete_sequence=["#FCB131", "#333333", "#A6A6A6"])
        st.plotly_chart(fig, use_container_width=True)

        # Waterfall (Değişim) Grafiği
        st.subheader("Aylık Değişim Analizi")
        df_g = df_g.sort_values("TarihObj")
        df_g['Onceki'] = df_g.groupby('Taraf')['Değer'].shift(1)
        df_g['Fark'] = df_g['Değer'] - df_g['Onceki']

        fig_water = px.bar(df_g.dropna(), x="Dönem", y="Fark", color="Taraf",
                           title="Aylık Net Değişim (Miktar)", barmode="group")
        st.plotly_chart(fig_water, use_container_width=True)

    # --- TAB 2: SİMÜLASYON ---
    with tab2:
        c_sim1, c_sim2 = st.columns([1, 3])
        with c_sim1:
            st.info("Aylık büyüme oranını değiştirerek gelecek 6 ayı tahminle.")
            s_oran = st.slider("Aylık Büyüme (%)", -5.0, 10.0, 2.0)
            s_kalem = st.selectbox("Simülasyon Kalemi", df["Kalem"].unique())

        with c_sim2:
            df_sim_base = df[df["Kalem"] == s_kalem]
            sim_list = []

            for taraf in df_sim_base["Taraf"].unique():
                base_val = df_sim_base[df_sim_base["Taraf"] == taraf].sort_values("TarihObj").iloc[-1]["Değer"]
                current_date = df_sim_base["TarihObj"].max()

                # Geçmiş veriyi ekle
                for _, r in df_sim_base[df_sim_base["Taraf"] == taraf].iterrows():
                    sim_list.append({"Tarih": r["TarihObj"], "Değer": r["Değer"], "Tip": "Gerçekleşen", "Taraf": taraf})

                # Gelecek 6 ay
                temp_val = base_val
                for m in range(1, 7):
                    current_date += pd.DateOffset(months=1)
                    temp_val *= (1 + s_oran / 100)
                    sim_list.append({"Tarih": current_date, "Değer": temp_val, "Tip": "Tahmin", "Taraf": taraf})

            df_sim = pd.DataFrame(sim_list)
            fig_sim = px.line(df_sim, x="Tarih", y="Değer", color="Taraf", line_dash="Tip", title="6 Aylık Projeksiyon")
            st.plotly_chart(fig_sim, use_container_width=True)

    # --- TAB 3: HEATMAP ---
    with tab3:
        h_kalem = st.selectbox("Heatmap Verisi:", df["Kalem"].unique(), key="hm")
        df_h = df[df["Kalem"] == h_kalem].copy()
        df_h["Ay"] = df_h["TarihObj"].dt.strftime("%Y-%m")

        pivot = df_h.pivot(index="Taraf", columns="Ay", values="Değer")
        fig_hm = px.imshow(pivot, text_auto=".2s", color_continuous_scale="Viridis", aspect="auto")
        st.plotly_chart(fig_hm, use_container_width=True)

    # --- TAB 4: EXCEL ---
    with tab4:
        st.dataframe(df)
        # Excel indirme logic'i buraya eklenebilir