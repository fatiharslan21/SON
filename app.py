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
import plotly.express as px
import time
import sys
import os

# --- 1. AYARLAR ---
st.set_page_config(page_title="BDDK Analiz", layout="wide", page_icon="🏦")


def local_css():
    st.markdown("""
    <style>
        .stApp { background-color: #FFFFFF; }
        [data-testid="stSidebar"] { background-color: #FCB131; }
        [data-testid="stSidebar"] * { color: #000000 !important; font-weight: bold; }
        h1, h2, h3 { color: #d99000 !important; font-weight: 800; }
        div.stButton > button { background-color: #FCB131; color: black; border: 2px solid black; width: 100%; }
        /* Tablo Başlıkları */
        [data-testid="stDataFrame"] { border: 1px solid #FCB131; }
    </style>
    """, unsafe_allow_html=True)


local_css()

# --- 2. SABİTLER ---
AY_LISTESI = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım",
              "Aralık"]
TARAF_SECENEKLERI = ["Sektör", "Mevduat-Kamu", "Mevduat-Yerli Özel", "Mevduat-Yabancı", "Katılım"]

# BDDK Sitesindeki ID haritası
VERI_KONFIGURASYONU = {
    "📌 TOPLAM AKTİFLER": {"tab": "tabloListesiItem-1", "row_text": "TOPLAM AKTİFLER", "col_id": "grdRapor_Toplam"},
    "📌 TOPLAM ÖZKAYNAKLAR": {"tab": "tabloListesiItem-1", "row_text": "TOPLAM ÖZKAYNAKLAR",
                             "col_id": "grdRapor_Toplam"},
    "⚠️ Takipteki Alacaklar": {"tab": "tabloListesiItem-1", "row_text": "Takipteki Alacaklar",
                               "col_id": "grdRapor_Toplam"},
    "💰 DÖNEM NET KARI/ZARARI": {"tab": "tabloListesiItem-2", "row_text": "DÖNEM NET KARI (ZARARI)",
                                "col_id": "grdRapor_Toplam"},
    "🏦 Toplam Krediler": {"tab": "tabloListesiItem-3", "row_text": "Toplam Krediler", "col_id": "grdRapor_Toplam"},
    "🏠 Tüketici Kredileri": {"tab": "tabloListesiItem-4", "row_text": "Tüketici Kredileri",
                             "col_id": "grdRapor_Toplam"},
    "💳 Bireysel Kredi Kartları": {"tab": "tabloListesiItem-4", "row_text": "Bireysel Kredi Kartları",
                                  "col_id": "grdRapor_Toplam"},
    "🏭 KOBİ Kredileri": {"tab": "tabloListesiItem-6", "row_text": "Toplam KOBİ Kredileri",
                         "col_id": "grdRapor_NakdiKrediToplam"},
}


# --- 3. DRIVER (Bağlantı Testinde Çalışan Kod) ---
def get_driver():
    if sys.platform == "linux":
        # Cloud (Firefox)
        options = FirefoxOptions()
        options.add_argument("--headless")
        options.add_argument("--width=1920")
        options.add_argument("--height=1080")
        options.binary_location = "/usr/bin/firefox"
        try:
            service = FirefoxService(GeckoDriverManager().install())
        except:
            service = FirefoxService("/usr/local/bin/geckodriver")
        return webdriver.Firefox(service=service, options=options)
    else:
        # Local (Chrome)
        options = ChromeOptions()
        options.add_argument("--start-maximized")
        service = ChromeService(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)


# --- 4. GÜÇLENDİRİLMİŞ VERİ ÇEKME ---
def scrape_bddk(bas_yil, bas_ay, bit_yil, bit_ay, secilen_taraflar, secilen_veriler, status_container):
    driver = None
    master_data = []

    try:
        driver = get_driver()
        status_container.info("🌐 BDDK Sayfası Yükleniyor...")
        driver.get("https://www.bddk.org.tr/bultenaylik")

        # Sayfanın ilk yüklenişi için uzun bekleme
        WebDriverWait(driver, 40).until(EC.presence_of_element_located((By.ID, "ddlYil")))
        time.sleep(5)

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

                # 1. TARİH SEÇİMİ (Güvenli JS)
                # jQuery trigger'larını çiftliyoruz ki kesin algılasın
                driver.execute_script(f"""
                    $('#ddlYil').val('{yil}').trigger('chosen:updated').trigger('change');
                    setTimeout(function() {{ $('#ddlAy').val('{ay_str}').trigger('chosen:updated').trigger('change'); }}, 500);
                """)
                # Tarih değişimi sonrası tablonun güncellenmesi için bekleme
                time.sleep(5.0)

                for taraf in secilen_taraflar:
                    # 2. TARAF SEÇİMİ
                    driver.execute_script(f"""
                        var t = document.getElementById('ddlTaraf');
                        for(var i=0; i<t.options.length; i++){{
                            if(t.options[i].text.trim() == '{taraf}'){{
                                t.selectedIndex = i;
                                break;
                            }}
                        }}
                        $(t).trigger('chosen:updated').trigger('change');
                    """)
                    time.sleep(2.0)

                    for veri in secilen_veriler:
                        conf = VERI_KONFIGURASYONU[veri]

                        # --- RETRY (TEKRAR DENEME) MEKANİZMASI ---
                        # Veriyi bulamazsa 3 kere daha dener.
                        success = False
                        attempt = 0
                        while not success and attempt < 3:
                            try:
                                # Sekmeye Tıkla
                                driver.execute_script(f"document.getElementById('{conf['tab']}').click();")
                                time.sleep(1.0)

                                # XPath ile veriyi ara
                                xpath = f"//tr[contains(., '{conf['row_text']}')]//td[contains(@aria-describedby, '{conf['col_id']}')]"
                                element = driver.find_element(By.XPATH, xpath)
                                val_text = element.text.strip()

                                if val_text:
                                    val_num = float(val_text.replace('.', '').replace(',', '.'))
                                    master_data.append({
                                        "Dönem": donem, "Taraf": taraf,
                                        "Kalem": veri, "Değer": val_num
                                    })
                                    success = True  # Başardık, döngüden çık
                                else:
                                    raise Exception("Boş veri")

                            except:
                                # Başarısız olursa bekle ve tekrar dene
                                time.sleep(2)
                                attempt += 1

                        if not success:
                            print(f"UYARI: {donem} - {taraf} - {veri} bulunamadı.")

                current_step += 1
                progress_bar.progress(current_step / max(1, total_steps))

        return pd.DataFrame(master_data)

    except Exception as e:
        st.error(f"❌ HATA: {e}")
        if driver:
            driver.save_screenshot("final_error.png")
            st.image("final_error.png")
        return pd.DataFrame()

    finally:
        if driver: driver.quit()


# --- 5. ANA UYGULAMA ---
def main():
    with st.sidebar:
        st.title("🎛️ PANEL")
        st.markdown("---")

        c1, c2 = st.columns(2)
        bas_yil = c1.number_input("Başlangıç", 2024, 2030, 2024)
        bas_ay = c1.selectbox("Ay", AY_LISTESI, index=0)

        c3, c4 = st.columns(2)
        bit_yil = c3.number_input("Bitiş", 2024, 2030, 2024)
        bit_ay = c4.selectbox("Ay ", AY_LISTESI, index=0)

        st.markdown("---")
        secilen_taraflar = st.multiselect("Taraf", TARAF_SECENEKLERI, default=["Sektör"])
        secilen_veriler = st.multiselect("Veri", list(VERI_KONFIGURASYONU.keys()), default=["📌 TOPLAM AKTİFLER"])

        st.markdown("---")
        calistir = st.button("🚀 ANALİZİ BAŞLAT")

    st.title("🏦 BDDK Gelişmiş Analiz")

    if 'scraped_data' not in st.session_state:
        st.session_state['scraped_data'] = None

    if calistir:
        if not secilen_taraflar or not secilen_veriler:
            st.error("Lütfen Taraf ve Veri seçiniz.")
        else:
            status_text = st.empty()
            st.session_state['scraped_data'] = None

            df_yeni = scrape_bddk(bas_yil, bas_ay, bit_yil, bit_ay, secilen_taraflar, secilen_veriler, status_text)

            if not df_yeni.empty:
                st.session_state['scraped_data'] = df_yeni
                status_text.success("✅ İŞLEM BAŞARILI! Analiz yükleniyor...")
                time.sleep(1)
                st.rerun()
            else:
                status_text.error("⚠️ Veri seti boş döndü. Süre yetmemiş olabilir, tekrar deneyin.")

    # --- DASHBOARD ---
    if st.session_state['scraped_data'] is not None and not st.session_state['scraped_data'].empty:
        df = st.session_state['scraped_data']

        tab1, tab2, tab3 = st.tabs(["📊 GRAFİK", "📑 TABLO", "📥 İNDİR"])

        with tab1:
            try:
                kalem = st.selectbox("Grafik Kalemi:", df["Kalem"].unique())
                df_c = df[df["Kalem"] == kalem]
                fig = px.line(df_c, x="Dönem", y="Değer", color="Taraf", markers=True,
                              title=f"{kalem} Analizi",
                              color_discrete_sequence=["#FCB131", "#000000", "#FF5733"])
                st.plotly_chart(fig, use_container_width=True)
            except:
                st.warning("Grafik oluşturulamadı.")

        with tab2:
            st.dataframe(df.pivot_table(index="Dönem", columns=["Kalem", "Taraf"], values="Değer", aggfunc="sum"),
                         use_container_width=True)

        with tab3:
            buffer = "BDDK_Rapor.xlsx"
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Ham Veri", index=False)
                for k in df["Kalem"].unique():
                    safe_name = "".join(c for c in k if c.isalnum())[:30]
                    df[df["Kalem"] == k].pivot(index="Dönem", columns="Taraf", values="Değer").to_excel(writer,
                                                                                                        sheet_name=safe_name)

            with open(buffer, "rb") as f:
                st.download_button("Excel Raporunu İndir", f, file_name="BDDK_Analiz.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


if __name__ == "__main__":
    main()