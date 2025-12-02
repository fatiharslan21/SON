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
import time
import sys
import os

# --- AYARLAR ---
st.set_page_config(page_title="BDDK Analiz", layout="wide", page_icon="🏦")

# CSS
st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; }
    [data-testid="stSidebar"] { background-color: #FCB131; }
    [data-testid="stSidebar"] * { color: #000000 !important; font-weight: bold; }
    div.stButton > button { background-color: #FCB131; color: black; border: 2px solid black; width: 100%; }
</style>
""", unsafe_allow_html=True)

# --- CONFIG ---
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


# --- DRIVER ---
def get_driver():
    if sys.platform == "linux":
        options = FirefoxOptions()
        options.add_argument("--headless")
        options.binary_location = "/usr/bin/firefox"
        try:
            service = FirefoxService(GeckoDriverManager().install())
        except:
            service = FirefoxService("/usr/local/bin/geckodriver")
        return webdriver.Firefox(service=service, options=options)
    else:
        options = ChromeOptions()
        # options.add_argument("--headless") # Localde görmek için kapattık
        service = ChromeService(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)


def scrape_bddk(bas_yil, bas_ay, bit_yil, bit_ay, secilen_taraflar, secilen_veriler, status_container):
    driver = None
    data = []

    try:
        driver = get_driver()
        driver.set_page_load_timeout(60)
        status_container.info("🌐 Siteye bağlanılıyor...")
        driver.get("https://www.bddk.org.tr/bultenaylik")

        # Sayfanın yüklenmesini bekle
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "ddlYil")))
        time.sleep(3)  # Garanti bekleme

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
                status_container.info(f"⏳ Veri Çekiliyor: **{donem}**")

                # --- YENİ YÖNTEM: GİZLİ ELEMENTİ AÇ VE TIKLA ---
                try:
                    # 1. YIL SEÇİMİ
                    # Gizli olan <select> elementini görünür yap
                    driver.execute_script("document.getElementById('ddlYil').style.display = 'block';")
                    select_yil = Select(driver.find_element(By.ID, "ddlYil"))
                    select_yil.select_by_visible_text(str(yil))
                    time.sleep(2)  # Postback bekle

                    # 2. AY SEÇİMİ
                    driver.execute_script("document.getElementById('ddlAy').style.display = 'block';")
                    select_ay = Select(driver.find_element(By.ID, "ddlAy"))
                    select_ay.select_by_visible_text(ay_str)
                    time.sleep(4)  # Tablo güncellemesi için uzun bekle

                    # 3. TARAF SEÇİMİ
                    for taraf in secilen_taraflar:
                        driver.execute_script("document.getElementById('ddlTaraf').style.display = 'block';")
                        select_taraf = Select(driver.find_element(By.ID, "ddlTaraf"))

                        # Taraf ismi eşleşmesi (Boşlukları temizleyerek)
                        try:
                            # Tam eşleşme dene
                            select_taraf.select_by_visible_text(taraf)
                        except:
                            # Bulamazsa options içinde ara
                            found = False
                            for opt in select_taraf.options:
                                if taraf in opt.text:
                                    select_taraf.select_by_visible_text(opt.text)
                                    found = True
                                    break

                        time.sleep(3)  # Veri gelmesini bekle

                        # 4. VERİ ÇEKME (BEAUTIFUL SOUP İLE)
                        # Sayfanın o anki HTML'ini al
                        soup = BeautifulSoup(driver.page_source, 'html.parser')

                        for veri in secilen_veriler:
                            conf = VERI_KONFIGURASYONU[veri]

                            # İlgili Sekmeye Geç (Gerekirse)
                            try:
                                # Sekme tıkla
                                driver.execute_script(f"document.getElementById('{conf['tab']}').click();")
                                time.sleep(1)
                                # HTML'i güncelle (Sekme değişti çünkü)
                                soup = BeautifulSoup(driver.page_source, 'html.parser')
                            except:
                                pass

                            # Satırı bul (Soup ile)
                            # "text" içeren tüm tr'leri bul
                            target_rows = soup.find_all("tr")
                            for row in target_rows:
                                if conf['row_text'] in row.get_text():
                                    # Hücreleri al
                                    cols = row.find_all("td")
                                    # Genelde son sütun veya aria-describedby olan sütun değerdir
                                    # Basit mantık: Sayı içeren ilk mantıklı hücreyi al
                                    for col in cols:
                                        text = col.get_text().strip()
                                        # Sayısal mı kontrol et (1.250,00 formatı)
                                        clean_text = text.replace('.', '').replace(',', '.')
                                        if clean_text.replace('-', '').isdigit() or (
                                                clean_text.replace('-', '').replace('.', '', 1).isdigit() and len(
                                                clean_text) > 0):

                                            # Eğer sayı çok küçükse (Sıra nosu gibi) ve asıl değer değilse atla
                                            if len(text) < 2 and float(clean_text) < 100:
                                                continue

                                            data.append({
                                                "Dönem": donem, "Taraf": taraf,
                                                "Kalem": veri, "Değer": float(clean_text)
                                            })
                                            break  # İlk anlamlı sayıyı alınca çık
                                    break  # Satırı bulunca çık

                except Exception as step_e:
                    print(f"Adım hatası: {step_e}")
                    # Hata olsa bile devam et
                    pass

                current_step += 1
                progress_bar.progress(current_step / max(1, total_steps))

    except Exception as e:
        st.error(f"GENEL HATA: {e}")
        if driver:
            driver.save_screenshot("debug_error.png")
            st.image("debug_error.png")
    finally:
        if driver: driver.quit()

    return pd.DataFrame(data)


# --- ANA EKRAN ---
with st.sidebar:
    st.title("🎛️ PANEL")
    c1, c2 = st.columns(2)
    bas_yil = c1.number_input("Başlangıç", 2024, 2030, 2024)
    bas_ay = c1.selectbox("Ay", AY_LISTESI, index=0)
    c3, c4 = st.columns(2)
    bit_yil = c3.number_input("Bitiş", 2024, 2030, 2024)
    bit_ay = c4.selectbox("Ay ", AY_LISTESI, index=0)
    st.markdown("---")
    secilen_taraflar = st.multiselect("Taraf", TARAF_SECENEKLERI, default=["Sektör"])
    secilen_veriler = st.multiselect("Veri", list(VERI_KONFIGURASYONU.keys()), default=["📌 TOPLAM AKTİFLER"])
    btn = st.button("🚀 BAŞLAT")

st.title("🏦 BDDK Analiz")

if btn:
    status = st.empty()
    df = scrape_bddk(bas_yil, bas_ay, bit_yil, bit_ay, secilen_taraflar, secilen_veriler, status)

    if not df.empty:
        status.success("✅ Veriler Çekildi!")
        tab1, tab2 = st.tabs(["📊 Grafik", "📥 Excel"])

        with tab1:
            try:
                kalem = st.selectbox("Grafik:", df["Kalem"].unique())
                df_c = df[df["Kalem"] == kalem]
                st.plotly_chart(px.line(df_c, x="Dönem", y="Değer", color="Taraf", markers=True))
            except:
                pass

        with tab2:
            buffer = "BDDK.xlsx"
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Data", index=False)
            with open(buffer, "rb") as f:
                st.download_button("İndir", f, file_name="BDDK.xlsx")
    else:
        status.error("Veri bulunamadı. Lütfen tekrar deneyin.")