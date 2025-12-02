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
import numpy as np  # Hesaplamalar için eklendi

# --- 1. AYARLAR VE TASARIM ---
st.set_page_config(page_title="Finansal Analiz Pro", layout="wide", page_icon="🏦")

# VAKIFBANK TEMASI VE ŞIK GÖRÜNÜM
st.markdown("""
<style>
    /* Genel Arka Plan */
    .stApp { background-color: #F4F4F4; }

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
        padding: 12px;
        transition: all 0.3s ease;
        box-shadow: 0 4px 6px rgba(0,0,0,0.2);
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
        border-radius: 12px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        border-left: 6px solid #FCB131;
    }
    [data-testid="stMetricLabel"] { font-size: 14px; font-weight: bold; color: #666; }
    [data-testid="stMetricValue"] { color: #000000; font-size: 24px; font-weight: 800; }

    /* Başlıklar */
    h1, h2, h3 { color: #BF8000 !important; font-weight: 800; }

    /* Tablo Header */
    thead tr th:first-child {display:none}
    tbody th {display:none}
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
        options.add_argument("--headless")  # Arka planda çalışması için
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
        time.sleep(2)

        bas_idx = AY_LISTESI.index(bas_ay)
        bit_idx = AY_LISTESI.index(bit_ay)

        # Basit bir döngü mantığı
        start_date = pd.Timestamp(year=bas_yil, month=bas_idx + 1, day=1)
        end_date = pd.Timestamp(year=bit_yil, month=bit_idx + 1, day=1)

        current_date = start_date
        total_months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month) + 1
        processed_count = 0
        progress_bar = st.progress(0)

        while current_date <= end_date:
            yil = current_date.year
            ay_str = AY_LISTESI[current_date.month - 1]
            donem = f"{ay_str} {yil}"

            status_container.markdown(f"⏳ **{donem}** verileri işleniyor...")

            try:
                # 1. YIL SEÇİMİ
                driver.execute_script("document.getElementById('ddlYil').style.display = 'block';")
                select_yil = Select(driver.find_element(By.ID, "ddlYil"))
                select_yil.select_by_visible_text(str(yil))
                time.sleep(1.5)

                # 2. AY SEÇİMİ
                driver.execute_script("document.getElementById('ddlAy').style.display = 'block';")
                select_ay = Select(driver.find_element(By.ID, "ddlAy"))
                select_ay.select_by_visible_text(ay_str)
                time.sleep(2)

                # 3. TARAF SEÇİMİ
                for taraf in secilen_taraflar:
                    driver.execute_script("document.getElementById('ddlTaraf').style.display = 'block';")
                    select_taraf = Select(driver.find_element(By.ID, "ddlTaraf"))

                    found_taraf = False
                    for opt in select_taraf.options:
                        if taraf in opt.text:
                            select_taraf.select_by_visible_text(opt.text)
                            found_taraf = True
                            break

                    if not found_taraf: continue
                    time.sleep(2)

                    # HTML ÇEKME
                    soup = BeautifulSoup(driver.page_source, 'html.parser')

                    for veri in secilen_veriler:
                        conf = VERI_KONFIGURASYONU[veri]

                        # Sekme Tıklama (Gerekirse)
                        try:
                            # Eğer mevcut sayfa zaten doğru tabloyu içermiyorsa tıkla
                            if conf['tab'] not in driver.page_source:
                                driver.execute_script(f"document.getElementById('{conf['tab']}').click();")
                                time.sleep(1)
                                soup = BeautifulSoup(driver.page_source, 'html.parser')
                        except:
                            pass

                        # Veri Arama
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
                                        "Dönem": donem,
                                        "Taraf": taraf,
                                        "Kalem": veri,
                                        "Değer": found_val,
                                        "TarihObj": current_date
                                    })
                                break

            except Exception as step_e:
                print(f"Hata ({donem}): {step_e}")

            # Bir sonraki aya geç
            if current_date.month == 12:
                current_date = pd.Timestamp(year=current_date.year + 1, month=1, day=1)
            else:
                current_date = pd.Timestamp(year=current_date.year, month=current_date.month + 1, day=1)

            processed_count += 1
            progress_bar.progress(min(processed_count / total_months, 1.0))

    except Exception as e:
        st.error(f"Kritik Hata: {e}")
    finally:
        # Driver'ı kapatma, cache kullanıyorsak açık kalabilir ama manuel temizlik daha iyi
        if driver: driver.quit()

    return pd.DataFrame(data)


# --- ANA EKRAN ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/e/e0/Vak%C4%B1fBank_logo.svg", width=200)
    st.title("🎛️ ANALİZ PANELİ")
    st.markdown("---")
    c1, c2 = st.columns(2)
    bas_yil = c1.number_input("Başlangıç Yılı", 2020, 2030, 2024)
    bas_ay = c1.selectbox("Başlangıç Ayı", AY_LISTESI, index=0)
    c3, c4 = st.columns(2)
    bit_yil = c3.number_input("Bitiş Yılı", 2020, 2030, 2024)
    bit_ay = c4.selectbox("Bitiş Ayı", AY_LISTESI, index=AY_LISTESI.index("Mayıs"))
    st.markdown("---")
    secilen_taraflar = st.multiselect("Karşılaştır:", TARAF_SECENEKLERI, default=["Sektör"])
    secilen_veriler = st.multiselect("Veri Kalemleri:", list(VERI_KONFIGURASYONU.keys()),
                                     default=["📌 TOPLAM AKTİFLER", "💰 DÖNEM NET KARI"])
    st.markdown("---")
    btn = st.button("🚀 ANALİZİ BAŞLAT")

    if st.button("🗑️ Önbelleği Temizle"):
        st.session_state.clear()
        st.rerun()

st.title("🏦 BDDK Finansal Zeka ve Simülasyonu")

if 'df_sonuc' not in st.session_state:
    st.session_state['df_sonuc'] = None

if btn:
    status = st.empty()
    st.session_state['df_sonuc'] = None
    df = scrape_bddk(bas_yil, bas_ay, bit_yil, bit_ay, secilen_taraflar, secilen_veriler, status)

    if not df.empty:
        # --- VERİ TİPİ DÜZELTME (HAYATİ ÖNEMLİ) ---
        df["Değer"] = pd.to_numeric(df["Değer"], errors='coerce')
        df = df.sort_values("TarihObj")  # Tarih sırasını garantiye alıyoruz
        st.session_state['df_sonuc'] = df
        status.success("✅ Veriler Analize Hazır!")
        time.sleep(0.5)
        st.rerun()
    else:
        status.error("Veri çekilemedi. Parametreleri kontrol edip tekrar deneyiniz.")

# --- DASHBOARD ---
if st.session_state['df_sonuc'] is not None:
    df = st.session_state['df_sonuc']

    # 1. KPI KARTLARI (EN SON DURUM)
    st.markdown("### 📊 Anlık Piyasa Durumu")

    # En son tarihi bul
    son_tarih = df["TarihObj"].max()
    df_son = df[df["TarihObj"] == son_tarih]

    # KPI'ları oluştur
    cols = st.columns(4)
    col_idx = 0

    for idx, row in df_son.iterrows():
        # Önceki ay verisini bul
        prev_date = son_tarih - pd.DateOffset(months=1)
        # Yaklaşık önceki ay kontrolü (tam gün tutmayabilir, ay/yıl kontrolü daha güvenli)
        df_prev = df[(df["TarihObj"].dt.year == prev_date.year) &
                     (df["TarihObj"].dt.month == prev_date.month) &
                     (df["Kalem"] == row["Kalem"]) &
                     (df["Taraf"] == row["Taraf"])]

        prev_val = df_prev.iloc[0]["Değer"] if not df_prev.empty else row["Değer"]

        delta = row["Değer"] - prev_val
        delta_pct = (delta / prev_val * 100) if prev_val != 0 else 0

        with cols[col_idx % 4]:
            st.metric(
                label=f"{row['Kalem'].replace('📌', '').replace('💰', '').strip()}",
                value=f"{row['Değer']:,.0f}",
                delta=f"%{delta_pct:.2f}"
            )
        col_idx += 1

    st.markdown("---")

    # 2. SEKMELİ ANALİZ YAPISI
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📈 Trend & Büyüme", "🔮 Gelecek Simülasyonu", "🌡️ Isı Haritası (Heatmap)", "📑 Ham Veri"])

    # --- TAB 1: KLASİK VE GELİŞMİŞ GRAFİKLER ---
    with tab1:
        col_g1, col_g2 = st.columns([3, 1])
        with col_g2:
            secilen_kalem_grafik = st.selectbox("Grafik Kalemi:", df["Kalem"].unique())

        df_chart = df[df["Kalem"] == secilen_kalem_grafik].copy()
        df_chart = df_chart.sort_values("TarihObj")

        # GRAFİK 1: AREA CHART (DOLGUN)
        fig_area = px.area(df_chart, x="TarihObj", y="Değer", color="Taraf",
                           title=f"📅 {secilen_kalem_grafik} - Zaman Serisi",
                           labels={"TarihObj": "Dönem", "Değer": "Tutar (Milyon TL)"},
                           color_discrete_sequence=["#FCB131", "#333333", "#A6A6A6", "#E5E5E5"])
        fig_area.update_layout(hovermode="x unified", legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig_area, use_container_width=True)

        st.markdown("#### 🚀 Aylık Büyüme Performansı (%)")

        # BÜYÜME HESAPLAMA
        df_chart['Onceki'] = df_chart.groupby('Taraf')['Değer'].shift(1)
        df_chart['Degisim_Yuzde'] = ((df_chart['Değer'] - df_chart['Onceki']) / df_chart['Onceki']) * 100
        df_chart['Renk'] = df_chart['Degisim_Yuzde'].apply(lambda x: 'Pozitif' if x > 0 else 'Negatif')

        fig_bar = px.bar(df_chart.dropna(), x="TarihObj", y="Degisim_Yuzde", color="Renk",
                         facet_col="Taraf",
                         color_discrete_map={'Pozitif': '#2ecc71', 'Negatif': '#e74c3c'},
                         title="Aylık % Değişim (MoM)")
        fig_bar.update_layout(showlegend=False)
        st.plotly_chart(fig_bar, use_container_width=True)

    # --- TAB 2: SİMÜLASYON (ŞOV KISMI) ---
    with tab2:
        st.info(
            "💡 **Simülasyon Modu:** Aşağıdaki ayarları değiştirerek 'Eğer aylık %X büyürsek, 6 ay sonra nerede oluruz?' sorusuna yanıt bulabilirsiniz.")

        col_sim1, col_sim2 = st.columns([1, 3])

        with col_sim1:
            st.markdown("#### 🎚️ Parametreler")
            secilen_sim_kalem = st.selectbox("Simüle Edilecek Kalem:", df["Kalem"].unique(), key="sim_k")
            buyume_orani = st.slider("Hedef Aylık Büyüme (%)", -5.0, 10.0, 2.5, 0.1)
            sim_ay_sayisi = st.slider("Kaç Ay İleri?", 3, 24, 6)

        with col_sim2:
            # Simülasyon Verisi Hazırlama
            df_sim_base = df[df["Kalem"] == secilen_sim_kalem].copy()
            taraflar = df_sim_base["Taraf"].unique()

            sim_data = []

            for taraf in taraflar:
                # Mevcut verileri al
                current_rows = df_sim_base[df_sim_base["Taraf"] == taraf].sort_values("TarihObj")
                last_val = current_rows.iloc[-1]["Değer"]
                last_date = current_rows.iloc[-1]["TarihObj"]

                # Mevcut veriyi ekle
                for _, row in current_rows.iterrows():
                    sim_data.append(
                        {"Tarih": row["TarihObj"], "Değer": row["Değer"], "Tip": "Gerçekleşen", "Taraf": taraf})

                # Geleceği üret
                curr_val = last_val
                curr_date = last_date

                for i in range(sim_ay_sayisi):
                    curr_date = curr_date + pd.DateOffset(months=1)
                    curr_val = curr_val * (1 + buyume_orani / 100)
                    sim_data.append({"Tarih": curr_date, "Değer": curr_val, "Tip": "Simülasyon", "Taraf": taraf})

            df_sim = pd.DataFrame(sim_data)

            fig_sim = px.line(df_sim, x="Tarih", y="Değer", color="Taraf", line_dash="Tip",
                              title=f"🔮 Gelecek Projeksiyonu (Aylık %{buyume_orani} Büyüme ile)",
                              color_discrete_sequence=["#FCB131", "#000000"])

            # Simülasyon bölgesini işaretle
            fig_sim.add_vrect(x0=son_tarih, x1=df_sim["Tarih"].max(),
                              fillcolor="green", opacity=0.1,
                              annotation_text="Tahmin Bölgesi", annotation_position="top left")

            st.plotly_chart(fig_sim, use_container_width=True)

    # --- TAB 3: HEATMAP ---
    with tab3:
        st.markdown("#### 🌡️ Dönemsel Yoğunluk Haritası")
        secilen_hm_kalem = st.selectbox("Heatmap Kalemi:", df["Kalem"].unique(), key="hm_k")

        df_hm = df[df["Kalem"] == secilen_hm_kalem].copy()
        df_hm["Ay"] = df_hm["TarihObj"].dt.strftime('%Y-%m')

        pivot_hm = df_hm.pivot(index="Taraf", columns="Ay", values="Değer")

        fig_hm = px.imshow(pivot_hm, text_auto=".2s", aspect="auto",
                           color_continuous_scale="Viridis",
                           title=f"{secilen_hm_kalem} - Taraf Bazlı Isı Haritası")
        st.plotly_chart(fig_hm, use_container_width=True)

    # --- TAB 4: VERİ İNDİRME ---
    with tab4:
        st.dataframe(df.style.format({"Değer": "{:,.2f}"}), use_container_width=True)

        # Excel İndirme
        import io

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Ham_Veri", index=False)

        st.download_button(
            label="📥 Excel Olarak İndir",
            data=buffer.getvalue(),
            file_name="BDDK_Analiz_Pro.xlsx",
            mime="application/vnd.ms-excel"
        )