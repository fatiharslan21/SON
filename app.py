import streamlit as st
import pandas as pd
import numpy as np
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import plotly.express as px
import plotly.graph_objects as go
import time
import sys
import io

# --- 1. AYARLAR VE TASARIM ---
st.set_page_config(page_title="BDDK ULTRA HIZLI", layout="wide", page_icon="⚡", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stApp { background-color: #F0F2F6; }
    [data-testid="stSidebar"] { background-color: #1E1E1E; border-right: 1px solid #333; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; font-family: 'Segoe UI', sans-serif; }

    /* BUTON TASARIMI */
    div.stButton > button { 
        background-color: #FF4B4B !important; 
        color: #FFFFFF !important; 
        font-weight: 900 !important; 
        border: none; 
        border-radius: 5px;
        width: 100%; 
        padding: 15px; 
    }
    div.stButton > button:hover { 
        background-color: #FF0000 !important; 
        transform: scale(1.02); 
    }

    h1, h2, h3 { color: #333 !important; font-weight: 800; }

    /* KART TASARIMI */
    .bot-card {
        background-color: white;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #FF4B4B;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 10px;
    }
    [data-testid="stSidebarCollapseButton"] { display: none; }
</style>
""", unsafe_allow_html=True)

# --- 2. CONFIG ---
AY_LISTESI = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım",
              "Aralık"]
TARAF_SECENEKLERI = ["Sektör", "Mevduat-Kamu", "Mevduat-Yerli Özel", "Mevduat-Yabancı", "Katılım"]

VERI_KONFIGURASYONU = {
    "📌 Toplam Aktifler": {"tab": "tabloListesiItem-1", "row_text": "TOPLAM AKTİFLER", "col_id": "grdRapor_Toplam"},
    "📌 Toplam Özkaynaklar": {"tab": "tabloListesiItem-1", "row_text": "TOPLAM ÖZKAYNAKLAR",
                             "col_id": "grdRapor_Toplam"},
    "⚠️ Takipteki Alacaklar": {"tab": "tabloListesiItem-1", "row_text": "Takipteki Alacaklar",
                               "col_id": "grdRapor_Toplam"},
    "💰 Dönem Net Kârı": {"tab": "tabloListesiItem-2", "row_text": "DÖNEM NET KARI (ZARARI)",
                         "col_id": "grdRapor_Toplam"},
    "📊 Sermaye Yeterliliği Rasyosu": {"tab": "tabloListesiItem-12", "row_text": "Sermaye Yeterliliği Standart Rasyosu",
                                      "col_id": "grdRapor_Toplam"},
    "💳 Bireysel Kredi Kartları": {"tab": "tabloListesiItem-4", "row_text": "Bireysel Kredi Kartları (10+11)",
                                  "col_id": "grdRapor_Toplam"},
    "🏦 Toplam Krediler": {"tab": "tabloListesiItem-3", "row_text": "Toplam Krediler", "col_id": "grdRapor_Toplam"},
    "🏠 Tüketici Kredileri": {"tab": "tabloListesiItem-4", "row_text": "Tüketici Kredileri",
                             "col_id": "grdRapor_Toplam"},
    "🏭 KOBİ Kredileri": {"tab": "tabloListesiItem-6", "row_text": "Toplam KOBİ Kredileri",
                         "col_id": "grdRapor_NakdiKrediToplam"}
}


# --- 3. ULTRA HIZLI DRIVER ---
def get_driver():
    if sys.platform == "linux":
        options = FirefoxOptions()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        try:
            service = FirefoxService(GeckoDriverManager().install())
            return webdriver.Firefox(service=service, options=options)
        except:
            return None
    else:
        options = ChromeOptions()
        # --- HIZ AYARLARI ---
        options.add_argument("--headless=new")  # Arka planda çalış
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")  # Eklentileri kapat
        options.add_argument("--blink-settings=imagesEnabled=false")  # RESİMLERİ İNDİRME (Büyük Hız Kazancı)
        options.page_load_strategy = 'eager'  # SAYFANIN TAM YÜKLENMESİNİ BEKLEME (Sadece HTML yeter)

        try:
            service = ChromeService(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=options)
        except:
            st.error("Driver hatası.")
            return None


# --- 4. VERİ ÇEKME MOTORU (ATOMIC SPEED) ---
def scrape_bddk_data(bas_yil, bas_ay, bit_yil, bit_ay, secilen_taraflar, secilen_veriler, status_text_obj,
                     progress_bar_obj):
    driver = None
    data = []

    try:
        driver = get_driver()
        if not driver: return pd.DataFrame()

        # Sayfa yüklenirken timeout'a düşmesin ama hızlı geçsin
        driver.set_page_load_timeout(30)
        driver.get("https://www.bddk.org.tr/bultenaylik")

        # İlk yükleme için bekle
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.ID, "ddlYil")))

        bas_idx = AY_LISTESI.index(bas_ay)
        bit_idx = AY_LISTESI.index(bit_ay)
        total_steps = (bit_yil - bas_yil) * 12 + (bit_idx - bas_idx) + 1
        current_step = 0

        # Sekme optimizasyonu: Hangi veriler hangi sekmede?
        tabs_needed = {}
        for veri in secilen_veriler:
            tab_id = VERI_KONFIGURASYONU[veri]['tab']
            if tab_id not in tabs_needed: tabs_needed[tab_id] = []
            tabs_needed[tab_id].append(veri)

        for yil in range(bas_yil, bit_yil + 1):
            s_m = bas_idx if yil == bas_yil else 0
            e_m = bit_idx if yil == bit_yil else 11

            for ay_i in range(s_m, e_m + 1):
                ay_str = AY_LISTESI[ay_i]
                donem = f"{ay_str} {yil}"

                if status_text_obj: status_text_obj.text(f"🚀 Çekiliyor: {donem}")

                try:
                    # Yıl Değiştir
                    sel_yil = Select(driver.find_element(By.ID, "ddlYil"))
                    if sel_yil.first_selected_option.text != str(yil):
                        sel_yil.select_by_visible_text(str(yil))
                        # Eager load olduğu için elementin bayatlamasını beklemeliyiz
                        wait.until(EC.staleness_of(sel_yil.first_selected_option))
                        sel_yil = Select(driver.find_element(By.ID, "ddlYil"))  # Yeniden bul

                    # Ay Değiştir
                    sel_ay = Select(driver.find_element(By.ID, "ddlAy"))
                    if sel_ay.first_selected_option.text != ay_str:
                        sel_ay.select_by_visible_text(ay_str)
                        # BDDK'da ay değişince tablo yenilenir, bekle
                        wait.until(EC.presence_of_element_located((By.ID, "ddlTaraf")))

                    for taraf in secilen_taraflar:
                        # Taraf Değiştir
                        taraf_elem = driver.find_element(By.ID, "ddlTaraf")
                        select_taraf = Select(taraf_elem)
                        if taraf not in select_taraf.first_selected_option.text:
                            # Try-catch ile metni bulmaya çalış
                            try:
                                select_taraf.select_by_visible_text(taraf)
                            except:
                                for opt in select_taraf.options:
                                    if taraf in opt.text:
                                        select_taraf.select_by_visible_text(opt.text)
                                        break
                            # Taraf değişince update panel çalışır, kısa bir bekleme şart ama sleep yerine wait kullanıyoruz
                            # Ancak update panel ID'si karmaşık olduğu için minik bir sleep en güvenlisi burada
                            time.sleep(0.3)

                            # Gerekli Sekmeleri Gez
                        for tab_id, veriler_in_tab in tabs_needed.items():
                            try:
                                tab_btn = driver.find_element(By.ID, tab_id)
                                # Sadece aktif değilse tıkla
                                if "active" not in tab_btn.get_attribute("class"):
                                    driver.execute_script("arguments[0].click();", tab_btn)
                                    time.sleep(0.4)  # Tablo render süresi

                                # HTML Çek
                                soup = BeautifulSoup(driver.page_source, 'html.parser')

                                # Verileri Ayıkla
                                for veri_adi in veriler_in_tab:
                                    conf = VERI_KONFIGURASYONU[veri_adi]
                                    # Hızlı arama için
                                    rows = soup.find_all("tr")
                                    current_group = None

                                    for row in rows:
                                        # Grup kontrolü (Sektör/Kamu vs)
                                        cells = row.find_all("td")
                                        if not cells: continue

                                        if len(cells) > 0 and cells[0].has_attr("colspan"):
                                            txt = cells[0].get_text(strip=True)
                                            if "Sektör" in txt:
                                                current_group = "Sektör"
                                            elif "Kamu" in txt:
                                                current_group = "Kamu"
                                            continue

                                        # Veri satırı mı?
                                        # Hız için attribute kontrolü yerine text kontrolü deneyelim
                                        row_text = row.get_text(strip=True)
                                        if conf['row_text'] in row_text:
                                            # Bu satırı detaylı incele
                                            ad_cell = row.find("td", {"aria-describedby": "grdRapor_Ad"})
                                            val_cell = row.find("td", {"aria-describedby": conf['col_id']})

                                            if ad_cell and val_cell:
                                                row_taraf = current_group if current_group else taraf
                                                val_str = val_cell.get_text(strip=True).replace('.', '').replace(',',
                                                                                                                 '.')
                                                try:
                                                    val_flt = float(val_str)
                                                except:
                                                    val_flt = 0.0

                                                data.append({
                                                    "Dönem": donem,
                                                    "Taraf": row_taraf,
                                                    "Kalem": veri_adi,
                                                    "Değer": val_flt,
                                                    "TarihObj": pd.to_datetime(f"{yil}-{ay_i + 1}-01")
                                                })
                                                break  # Bulduk, diğer satırlara bakma
                            except:
                                pass  # Sekme hatası

                except:
                    pass  # Dönem hatası

                current_step += 1
                if progress_bar_obj: progress_bar_obj.progress(min(current_step / max(1, total_steps), 1.0))

    except:
        pass
    finally:
        if driver: driver.quit()

    return pd.DataFrame(data)


# --- ANA EKRAN ---
with st.sidebar:
    st.title("⚡ KONTROL PANELİ")
    st.caption("Ultra Hızlı Mod Aktif")
    c1, c2 = st.columns(2)
    bas_yil = c1.number_input("Başlangıç", 2022, 2030, 2025, key="sb_bas_yil")
    bas_ay = c1.selectbox("Başlangıç Ay", AY_LISTESI, index=0, key="sb_bas_ay")
    c3, c4 = st.columns(2)
    bit_yil = c3.number_input("Bitiş", 2022, 2030, 2025, key="sb_bit_yil")
    bit_ay = c4.selectbox("Bitiş Ay", AY_LISTESI, index=0, key="sb_bit_ay")
    secilen_taraflar = st.multiselect("Taraf:", TARAF_SECENEKLERI, default=["Sektör"], key="sb_taraflar")
    secilen_veriler = st.multiselect("Veri:", list(VERI_KONFIGURASYONU.keys()), default=["📌 Toplam Aktifler"],
                                     key="sb_veriler")

    st.markdown("###")
    btn = st.button("VERİLERİ GETİR", key="sb_btn_baslat")

st.title("⚡ BDDK Hızlı Analiz")

if 'df_sonuc' not in st.session_state:
    st.session_state['df_sonuc'] = None

if btn:
    if not secilen_taraflar or not secilen_veriler:
        st.warning("Eksik seçim.")
    else:
        status_txt = st.empty()
        my_bar = st.progress(0)
        df = scrape_bddk_data(bas_yil, bas_ay, bit_yil, bit_ay, secilen_taraflar, secilen_veriler, status_txt, my_bar)
        my_bar.empty()
        status_txt.empty()

        if not df.empty:
            st.session_state['df_sonuc'] = df
            st.success("✅ Tamamlandı!")
            time.sleep(0.5)
            st.rerun()
        else:
            st.error("Veri bulunamadı.")

# --- DASHBOARD ---
if st.session_state['df_sonuc'] is not None:
    df = st.session_state['df_sonuc']
    df = df.drop_duplicates(subset=["Dönem", "Taraf", "Kalem"]).sort_values("TarihObj")

    tab1, tab2, tab3, tab4 = st.tabs(["📉 Trend", "🏁 Yarış", "📑 Tablo", "🧠 Akıllı Bot"])

    with tab1:  # Trend
        k_sec = st.selectbox("Kalem:", df["Kalem"].unique())
        d_ch = df[df["Kalem"] == k_sec]
        fig = px.line(d_ch, x="Dönem", y="Değer", color="Taraf", markers=True, title=f"{k_sec} Trendi")
        fig.update_layout(hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

    with tab2:  # Yarış
        k_race = st.selectbox("Yarış:", df["Kalem"].unique(), key="race")
        d_race = df[df["Kalem"] == k_race].sort_values("TarihObj")
        fig_r = px.bar(d_race, x="Taraf", y="Değer", color="Taraf", animation_frame="Dönem",
                       range_y=[0, d_race["Değer"].max() * 1.1])
        st.plotly_chart(fig_r, use_container_width=True)

    with tab3:  # Tablo
        d_tbl = df[["Dönem", "Kalem", "Taraf", "Değer"]].sort_values(["Dönem", "Kalem"])
        d_tbl["Değer"] = d_tbl["Değer"].apply(lambda x: "{:,.0f}".format(x).replace(",", "."))
        st.dataframe(d_tbl, use_container_width=True)

        buf = io.BytesIO()
        with pd.ExcelWriter(buf) as w:
            for k in df["Kalem"].unique():
                df[df["Kalem"] == k].to_excel(w, index=False, sheet_name=k[:30].replace("/", ""))
        st.download_button("Excel İndir", buf.getvalue(), "bddk_hizli.xlsx")

    with tab4:  # Akıllı Bot
        b_kalem = st.selectbox("Analiz:", df["Kalem"].unique(), key="b_kalem")
        b_taraf = st.selectbox("Odak:", df["Taraf"].unique(), key="b_taraf")

        if st.button("Analiz Et"):
            d_b = df[(df["Kalem"] == b_kalem) & (df["Taraf"] == b_taraf)].sort_values("TarihObj")
            if not d_b.empty:
                son, ilk = d_b.iloc[-1]["Değer"], d_b.iloc[0]["Değer"]
                degisim = ((son - ilk) / ilk) * 100
                st.markdown(f"""
                <div class="bot-card">
                    <b>{b_taraf} - {b_kalem}</b><br>
                    <span style="font-size:24px">{'🚀' if degisim > 0 else '📉'} %{degisim:.1f}</span><br>
                    {ilk:,.0f} ➡️ {son:,.0f}
                </div>
                """, unsafe_allow_html=True)

                # Gelecek Tahmini
                avg_g = d_b["Değer"].pct_change().mean()
                next_val = son * (1 + avg_g)
                st.metric("Gelecek Ay Tahmini", f"{next_val:,.0f}", f"{(next_val - son):,.0f}")