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

# --- 1. RENK VE STİL AYARLARI (VakıfBank Teması) ---
st.set_page_config(page_title="Finansal Analiz Paneli", layout="wide", page_icon="🏦")


def local_css():
    st.markdown("""
    <style>
        /* Ana Arka Planı Beyaz Yap */
        .stApp { background-color: #FFFFFF; }

        /* Yan Menü (Sidebar) Rengi - VakıfBank Sarısı */
        [data-testid="stSidebar"] { background-color: #FCB131; }

        /* Yan menüdeki yazıları siyah ve bold yap */
        [data-testid="stSidebar"] * { color: #000000 !important; font-weight: bold !important; }

        /* Başlıklar - Sarı ve Bold */
        h1, h2, h3 { color: #d99000 !important; font-weight: 800 !important; font-family: 'Segoe UI', sans-serif; }

        /* Buton Stili */
        div.stButton > button {
            background-color: #FCB131; color: black; font-weight: bold;
            border-radius: 10px; border: 2px solid #000000; width: 100%;
        }
        div.stButton > button:hover {
            background-color: #e5a02d; border-color: #000000; color: white;
        }

        /* Metrik Kartları */
        [data-testid="stMetricValue"] { font-size: 24px; color: #333333; }
    </style>
    """, unsafe_allow_html=True)


local_css()

# --- 2. AYARLAR VE DATA HARİTASI ---
AY_LISTESI = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
              "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

VERI_KONFIGURASYONU = {
    "📌 TOPLAM AKTİFLER": {"tab": "tabloListesiItem-1", "row_text": "TOPLAM AKTİFLER", "col_id": "grdRapor_Toplam"},
    "📌 TOPLAM ÖZKAYNAKLAR": {"tab": "tabloListesiItem-1", "row_text": "TOPLAM ÖZKAYNAKLAR",
                             "col_id": "grdRapor_Toplam"},
    "⚠️ Takipteki Alacaklar": {"tab": "tabloListesiItem-1", "row_text": "Takipteki Alacaklar",
                               "col_id": "grdRapor_Toplam"},
    "💰 DÖNEM NET KARI/ZARARI": {"tab": "tabloListesiItem-2", "row_text": "DÖNEM NET KARI (ZARARI)",
                                "col_id": "grdRapor_Toplam"},
    "📊 Sermaye Yeterliliği Rasyosu": {"tab": "tabloListesiItem-7", "row_text": "Sermaye Yeterliliği Standart Rasyosu",
                                      "col_id": "grdRapor_Toplam"},
    "🏦 Toplam Krediler": {"tab": "tabloListesiItem-3", "row_text": "Toplam Krediler", "col_id": "grdRapor_Toplam"},
    "🏠 Tüketici Kredileri": {"tab": "tabloListesiItem-4", "row_text": "Tüketici Kredileri",
                             "col_id": "grdRapor_Toplam"},
    "💳 Bireysel Kredi Kartları": {"tab": "tabloListesiItem-4", "row_text": "Bireysel Kredi Kartları",
                                  "col_id": "grdRapor_Toplam"},
    "🏭 KOBİ Kredileri": {"tab": "tabloListesiItem-6", "row_text": "Toplam KOBİ Kredileri",
                         "col_id": "grdRapor_NakdiKrediToplam"},
}

TARAF_SECENEKLERI = ["Sektör", "Mevduat-Kamu", "Mevduat-Yerli Özel", "Mevduat-Yabancı", "Katılım"]


# --- 3. AKILLI DRIVER (Cloud & Local Uyumlu) ---
def get_driver():
    """
    Linux (Cloud) -> Firefox kullanır.
    Windows (Local) -> Chrome kullanır.
    """
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
        # options.add_argument("--headless") # İstersen localde de gizli çalıştırabilirsin
        options.add_argument("--start-maximized")
        service = ChromeService(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)


# --- 4. DATA SCRAPING MOTORU ---
def scrape_bddk(bas_yil, bas_ay, bit_yil, bit_ay, secilen_taraflar, secilen_veriler, status_container):
    driver = None
    master_data = []

    try:
        driver = get_driver()
        driver.get("https://www.bddk.org.tr/bultenaylik")

        # Sayfa yüklenene kadar bekle
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "ddlYil")))

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
                tarih_obj = pd.to_datetime(f"{yil}-{ay_i + 1}-01")

                status_container.info(f"⏳ Veri Çekiliyor: **{donem}**")

                # Tarih Değiştir (JS ile)
                driver.execute_script(f"""
                    $('#ddlYil').val('{yil}').trigger('chosen:updated').trigger('change');
                    $('#ddlAy').val('{ay_str}').trigger('chosen:updated').trigger('change');
                """)
                time.sleep(2.0)  # Verinin yüklenmesi için bekle

                for taraf in secilen_taraflar:
                    # Taraf Değiştir
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
                    time.sleep(1.2)

                    for veri in secilen_veriler:
                        conf = VERI_KONFIGURASYONU[veri]
                        try:
                            # Sekmeye Tıkla
                            driver.execute_script(f"document.getElementById('{conf['tab']}').click();")
                            time.sleep(0.5)

                            # Veriyi Bul
                            # XPath: Hem satır ismini hem de sütun ID'sini içeren hücreyi bul
                            xpath = f"//tr[contains(., '{conf['row_text']}')]//td[contains(@aria-describedby, '{conf['col_id']}')]"
                            element = driver.find_element(By.XPATH, xpath)

                            val_text = element.text
                            val_num = float(val_text.replace('.', '').replace(',', '.')) if val_text else 0.0

                            master_data.append({
                                "Tarih": tarih_obj,
                                "Dönem": donem,
                                "Taraf": taraf,
                                "Kalem": veri,
                                "Değer": val_num
                            })
                        except:
                            pass  # Veri yoksa devam et

                current_step += 1
                progress_bar.progress(current_step / max(1, total_steps))

        return pd.DataFrame(master_data)

    except Exception as e:
        st.error(f"HATA: {e}")
        return pd.DataFrame()
    finally:
        if driver: driver.quit()


# --- 5. ANA UYGULAMA ---
def main():
    # --- YAN MENÜ ---
    with st.sidebar:
        st.title("🎛️ KONTROL PANELİ")
        st.markdown("---")

        c1, c2 = st.columns(2)
        bas_yil = c1.number_input("Başlangıç Yılı", 2020, 2030, 2024)
        bas_ay = c1.selectbox("Ay", AY_LISTESI, index=0)

        c3, c4 = st.columns(2)
        bit_yil = c3.number_input("Bitiş Yılı", 2020, 2030, 2024)
        bit_ay = c4.selectbox("Ay ", AY_LISTESI, index=0)

        st.markdown("---")
        st.subheader("🏦 Taraf Seçimi")
        secilen_taraflar = st.multiselect("Karşılaştır:", TARAF_SECENEKLERI, default=["Sektör", "Mevduat-Kamu"])

        st.subheader("📈 Veri Kalemleri")
        secilen_veriler = st.multiselect("Analiz Et:", list(VERI_KONFIGURASYONU.keys()),
                                         default=["📌 TOPLAM AKTİFLER", "💰 DÖNEM NET KARI/ZARARI"])

        st.markdown("---")
        calistir = st.button("🚀 ANALİZİ BAŞLAT")

    # --- ANA EKRAN ---
    st.title("🏦 BDDK Gelişmiş Analiz Dashboard'u")

    # Session State Başlatma
    if 'scraped_data' not in st.session_state:
        st.session_state['scraped_data'] = None

    # Butona basıldığında
    if calistir:
        if not secilen_taraflar or not secilen_veriler:
            st.error("⚠️ Lütfen en az bir Taraf ve Veri Kalemi seçiniz!")
        else:
            status_text = st.empty()
            # Veriyi Çek
            df_yeni = scrape_bddk(bas_yil, bas_ay, bit_yil, bit_ay, secilen_taraflar, secilen_veriler, status_text)

            if not df_yeni.empty:
                st.session_state['scraped_data'] = df_yeni
                status_text.success("✅ Veri Çekme Başarıyla Tamamlandı!")
                time.sleep(1)
                st.rerun()  # Sayfayı yenile ki aşağıdaki IF bloğu çalışsın ve Dashboard görünsün
            else:
                status_text.warning("Veri çekilemedi veya boş döndü. Lütfen tekrar deneyin.")

    # --- DASHBOARD & ANALİZ BÖLÜMÜ (Veri Varsa Göster) ---
    if st.session_state['scraped_data'] is not None:
        df = st.session_state['scraped_data']

        # Sekmeler
        tab1, tab2, tab3 = st.tabs(["📊 GÖRSEL ANALİZ", "📑 DETAYLI RAPOR", "📥 EXCEL İNDİR"])

        with tab1:
            st.subheader("🔍 Karşılaştırmalı Trend Analizi")
            # Grafik Seçimi
            secilen_grafik_kalemi = st.selectbox("Hangi Kalemi İncelemek İstersiniz?", df["Kalem"].unique())

            # Filtreleme
            df_chart = df[df["Kalem"] == secilen_grafik_kalemi].sort_values("Tarih")

            # Grafik
            fig = px.line(df_chart, x="Dönem", y="Değer", color="Taraf", markers=True,
                          title=f"{secilen_grafik_kalemi} - Zaman İçindeki Değişim",
                          color_discrete_sequence=["#FCB131", "#000000", "#FF5733"])

            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig, use_container_width=True)

            # Metrik Kartları
            st.markdown("#### 🏁 Son Dönem Durumu")
            try:
                son_tarih = df_chart["Tarih"].max()
                df_son = df_chart[df_chart["Tarih"] == son_tarih]

                cols = st.columns(len(df_son["Taraf"].unique()))
                for idx, row in enumerate(df_son.itertuples()):
                    fmt_deger = f"{row.Değer:,.0f}".replace(",", ".")
                    with cols[idx]:
                        st.metric(label=f"🏷️ {row.Taraf}", value=fmt_deger)
            except:
                pass

        with tab2:
            st.subheader("📋 Pivot Tablo Görünümü")
            pivot_df = df.pivot_table(index="Dönem", columns=["Kalem", "Taraf"], values="Değer", aggfunc="sum")
            st.dataframe(pivot_df, use_container_width=True)

        with tab3:
            st.subheader("💾 Excel Raporu")

            excel_buffer = "BDDK_Analiz_Raporu.xlsx"
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Ham Veri", index=False)
                for kalem in df["Kalem"].unique():
                    df_k = df[df["Kalem"] == kalem]
                    pivot_k = df_k.pivot(index="Dönem", columns="Taraf", values="Değer")
                    safe_name = kalem.replace("📌 ", "").replace("⚠️ ", "").replace("💰 ", "")[:30]
                    safe_name = "".join(c for c in safe_name if c.isalnum() or c in " -_")[:30]
                    pivot_k.to_excel(writer, sheet_name=safe_name)

            with open(excel_buffer, "rb") as f:
                st.download_button(
                    label="📥 EXCEL DOSYASINI İNDİR",
                    data=f,
                    file_name="Vakif_Stil_BDDK_Analiz.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )


if __name__ == "__main__":
    main()