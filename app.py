import streamlit as st
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
import sys
import os
import time

st.set_page_config(page_title="Sunucu Gözü", layout="wide")

st.title("🕵️ BDDK Bağlantı Testi")
st.warning("Bu kod sunucunun BDDK sitesine girip giremediğini test eder.")


# --- DRIVER AYARLARI ---
def get_driver():
    if sys.platform == "linux":
        # CLOUD AYARLARI (FIREFOX)
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
        # LOCAL AYARLAR (CHROME - Test İçin)
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium.webdriver.chrome.service import Service as ChromeService
        from webdriver_manager.chrome import ChromeDriverManager
        options = ChromeOptions()
        service = ChromeService(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)


if st.button("BAĞLANTIYI TEST ET"):
    driver = None
    status = st.empty()

    try:
        status.info("🌐 Tarayıcı başlatılıyor...")
        driver = get_driver()

        status.info("🌐 BDDK sitesine gidiliyor...")
        driver.get("https://www.bddk.org.tr/bultenaylik")

        # 5 Saniye bekle (Yüklenmesi için)
        time.sleep(5)

        # 1. BAŞLIK KONTROLÜ
        site_title = driver.title
        st.write(f"**Site Başlığı:** {site_title}")

        # 2. EKRAN GÖRÜNTÜSÜ AL (HER DURUMDA)
        status.info("📸 Fotoğraf çekiliyor...")
        driver.save_screenshot("kanit.png")
        st.image("kanit.png", caption="Sunucunun Gördüğü Ekran", use_container_width=True)

        # 3. HTML KAYNAK KODUNDAN İLK 500 KARAKTER
        st.text("Sayfa Kaynağı (İlk 500 Karakter):")
        st.code(driver.page_source[:500])

        # 4. KONTROL
        if "ddlYil" in driver.page_source:
            st.success("✅ BAŞARILI! Site yüklendi ve veri çekilebilir.")
        elif "Access Denied" in driver.page_source or "Erişim Reddedildi" in driver.page_source:
            st.error("⛔ ERİŞİM ENGELLENDİ! BDDK, Streamlit Cloud IP adreslerini bloklamış.")
        else:
            st.warning("⚠️ Site açıldı ama beklenen içerik gelmedi. Ekran görüntüsüne bakın.")

    except Exception as e:
        st.error(f"HATA OLUŞTU: {e}")
    finally:
        if driver: driver.quit()