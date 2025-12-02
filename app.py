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
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import plotly.express as px
import plotly.graph_objects as go
import time
import sys

# --- 1. AYARLAR VE TASARIM ---
st.set_page_config(page_title="Finansal Analiz Pro", layout="wide", page_icon="🏦")

st.markdown("""
<style>
    .stApp { background-color: #F9F9F9; }
    [data-testid="stSidebar"] { background-color: #FCB131; border-right: 1px solid #e0e0e0; }
    [data-testid="stSidebar"] * { color: #000000 !important; font-family: 'Segoe UI', sans-serif; }
    div.stButton > button { 
        background-color: #000000 !important; color: #FFFFFF !important; font-weight: 900 !important; 
        border-radius: 8px; border: 2px solid #FFFFFF; width: 100%; padding: 15px; font-size: 18px !important; 
        transition: all 0.3s ease; 
    }
    div.stButton > button:hover { background-color: #333333 !important; color: #FCB131 !important; border-color: #FCB131 !important; transform: scale(1.02); }
    [data-testid="stMetric"] { background-color: #FFFFFF; padding: 15px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-top: 5px solid #FCB131; }
    [data-testid="stMetricLabel"] { font-weight: bold; color: #555; }
    [data-testid="stMetricValue"] { color: #000000; font-weight: 800; font-size: 26px !important; }
    h1, h2, h3 { color: #d99000 !important; font-weight: 800; }
    .dataframe { font-size: 14px !important; }
</style>
""", unsafe_allow_html=True)

# --- 2. CONFIG ---
AY_LISTESI = ["Ocak","Şubat","Mart","Nisan","Mayıs","Haziran","Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"]
TARAF_SECENEKLERI = ["Sektör", "Mevduat-Kamu", "Mevduat-Yerli Özel", "Mevduat-Yabancı", "Katılım"]

VERI_KONFIGURASYONU = {
    "📌 TOPLAM AKTİFLER": {"tab": "tabloListesiItem-1", "row_text": "TOPLAM AKTİFLER", "col_id": "grdRapor_Toplam"},
    "📌 TOPLAM ÖZKAYNAKLAR": {"tab": "tabloListesiItem-1", "row_text": "TOPLAM ÖZKAYNAKLAR", "col_id": "grdRapor_Toplam"},
    "⚠️ Takipteki Alacaklar": {"tab": "tabloListesiItem-1", "row_text": "Takipteki Alacaklar", "col_id": "grdRapor_Toplam"},
    "💰 DÖNEM NET KARI": {"tab": "tabloListesiItem-2", "row_text": "DÖNEM NET KARI (ZARARI)", "col_id": "grdRapor_Toplam"},
    "🏦 Toplam Krediler": {"tab": "tabloListesiItem-3", "row_text": "Toplam Krediler", "col_id": "grdRapor_Toplam"},
    "🏠 Tüketici Kredileri": {"tab": "tabloListesiItem-4", "row_text": "Tüketici Kredileri", "col_id": "grdRapor_Toplam"},
    "🏭 KOBİ Kredileri": {"tab": "tabloListesiItem-6", "row_text": "Toplam KOBİ Kredileri", "col_id": "grdRapor_NakdiKrediToplam"}
}

# --- 3. DRIVER YÖNETİMİ ---
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
        service = ChromeService(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)

# --- 4. VERİ ÇEKME MOTORU ---
def scrape_bddk(bas_yil, bas_ay, bit_yil, bit_ay, secilen_taraflar, secilen_veriler, status_container):
    driver = None
    data = []
    try:
        driver = get_driver()
        driver.set_page_load_timeout(60)
        status_container.info("🌐 BDDK sistemine bağlanılıyor...")
        driver.get("https://www.bddk.org.tr/bultenaylik")
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "ddlYil")))
        time.sleep(2)

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
                    sel_yil = Select(driver.find_element(By.ID, "ddlYil"))
                    sel_yil.select_by_visible_text(str(yil))
                    driver.execute_script("arguments[0].dispatchEvent(new Event('change'))", driver.find_element(By.ID, "ddlYil"))
                    time.sleep(1)

                    driver.execute_script("document.getElementById('ddlAy').style.display = 'block';")
                    sel_ay_elem = driver.find_element(By.ID, "ddlAy")
                    sel_ay = Select(sel_ay_elem)
                    sel_ay.select_by_visible_text(ay_str)
                    driver.execute_script("arguments[0].dispatchEvent(new Event('change'))", sel_ay_elem)
                    time.sleep(2)

                    for taraf in secilen_taraflar:
                        driver.execute_script("document.getElementById('ddlTaraf').style.display = 'block';")
                        taraf_elem = driver.find_element(By.ID, "ddlTaraf")
                        select_taraf = Select(taraf_elem)
                        try:
                            select_taraf.select_by_visible_text(taraf)
                        except:
                            for opt in select_taraf.options:
                                if taraf in opt.text:
                                    select_taraf.select_by_visible_text(opt.text)
                                    break
                        driver.execute_script("arguments[0].dispatchEvent(new Event('change'))", taraf_elem)
                        time.sleep(1.5)

                        soup = BeautifulSoup(driver.page_source, 'html.parser')

                        for veri in secilen_veriler:
                            conf = VERI_KONFIGURASYONU[veri]

                            try:
                                WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, conf['tab'])))
                                driver.execute_script(f"document.getElementById('{conf['tab']}').click();")
                                time.sleep(1.5)
                                soup = BeautifulSoup(driver.page_source, 'html.parser')
                            except:
                                pass

                            current_group = None
                            for row in soup.find_all("tr"):
                                group_cell = row.find("td", colspan=True)
                                if group_cell:
                                    text = group_cell.get_text(strip=True)
                                    if "Sektör" in text:
                                        current_group = "Sektör"
                                    elif "Kamu" in text:
                                        current_group = "Kamu"
                                    continue

                                ad = row.find("td", {"aria-describedby": "grdRapor_Ad"})
                                toplam = row.find("td", {"aria-describedby": conf['col_id']})
                                if ad and toplam and current_group:
                                    raw_text = toplam.get_text(strip=True)
                                    clean_text = raw_text.replace('.', '').replace(',', '.')
                                    try:
                                        found_val = float(clean_text)
                                    except:
                                        found_val = 0.0
                                    data.append({
                                        "Dönem": donem,
                                        "Taraf": current_group,
                                        "Kalem": ad.get_text(strip=True),
                                        "Değer": found_val,
                                        "TarihObj": pd.to_datetime(f"{yil}-{ay_i+1}-01")
                                    })
                except:
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

# --- DASHBOARD ---
if st.session_state['df_sonuc'] is not None:
    df = st.session_state['df_sonuc']
    df = df.sort_values("TarihObj")

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
                st.metric(label=f"{row['Taraf']}", value=f"{val_fmt}", delta=f"%{delta_pct:.1f}")
    except:
        pass

    st.markdown("---")
    tab1, tab2, tab3, tab4 = st.tabs(["📉 Trend Analizi", "🧪 Senaryo Simülasyonu", "📊 Pazar Payı", "📑 Detaylı Tablo"])

    with tab1:
        kalem_sec = st.selectbox("Grafik Kalemi:", df["Kalem"].unique())
        df_chart = df[df["Kalem"] == kalem_sec].copy()
        df_chart["Değer"] = df_chart["Değer"].astype(float)
        sirali_donemler = df_chart["Dönem"].unique()
        fig = px.line(df_chart, x="Dönem", y="Değer", color="Taraf", title=f"📅 {kalem_sec} Trendi",
                      markers=True, category_orders={"Dönem": sirali_donemler},
                      color_discrete_sequence=["#FCB131","#000000","#555555"])
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", hovermode="x unified")
        fig.update_yaxes(tickformat=",")
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.markdown("#### 🧪 What-If (Senaryo) Analizi")
        st.info("Seçtiğiniz tarafın verilerini sanal olarak artırıp azaltarak sonucu simüle edin.")
        c_sim1, c_sim2 = st.columns([1,2])
        with c_sim1:
            taraf_sim = st.selectbox("Simüle Edilecek Taraf:", df["Taraf"].unique())
            kalem_sim = st.selectbox("Simüle Edilecek Kalem:", df["Kalem"].unique())
            artis_orani = st.slider("Değişim Oranı (%)", min_value=-50, max_value=50, value=10, step=5)
        with c_sim2:
            base_row = df[(df["Taraf"]==taraf_sim) & (df["Kalem"]==kalem_sim) & (df["TarihObj"]==df["TarihObj"].max())]
            if not base_row.empty:
                mevcut_deger = base_row.iloc[0]["Değer"]
                yeni_deger = mevcut_deger*(1+artis_orani/100)
                fark = yeni_deger-mevcut_deger
                col_a, col_b = st.columns(2)
                with col_a: st.metric("Mevcut Durum", f"{mevcut_deger:,.0f}".replace(",", "."))
                with col_b: st.metric(f"Senaryo (%{artis_orani})", f"{yeni_deger:,.0f}".replace(",", "."), delta=f"{fark:,.0f}".replace(",", "."))
                sim_data = pd.DataFrame({"Durum":["Mevcut","Simülasyon"],"Tutar":[mevcut_deger,yeni_deger]})
                fig_sim = px.bar(sim_data,x="Durum",y="Tutar",color="Durum",text_auto='.2s',
                                 color_discrete_map={"Mevcut":"#000000","Simülasyon":"#FCB131"})
                fig_sim.update_layout(height=300, showlegend=False)
                st.plotly_chart(fig_sim,use_container_width=True)

    with tab3:
        st.markdown("#### 📊 Pazar Payı Analizi")
        if "Sektör" in df["Taraf"].unique() and len(df["Taraf"].unique())>1:
            kalem_pie = st.selectbox("Payı İncelenecek Kalem:", df["Kalem"].unique(), key="share_select")
            df_last = df[(df["TarihObj"]==df["TarihObj"].max()) & (df["Kalem"]==kalem_pie)]
            sektor_row = df_last[df_last["Taraf"]=="Sektör"]
            if not sektor_row.empty:
                sektor_val = sektor_row.iloc[0]["Değer"]
                other_rows = df_last[df_last["Taraf"]!="Sektör"]
                cols_g = st.columns(len(other_rows))
                for idx, (i,r) in enumerate(other_rows.iterrows()):
                    share_pct = (r["Değer"]/sektor_val)*100
                    with cols_g[idx]:
                        fig_g = go.Figure(go.Indicator(mode="gauge+number", value=share_pct, title={'text':f"{r['Taraf']} Payı"},
                                                       gauge={'axis':{'range':[0,100]},'bar':{'color':"#FCB131"}}))
                        fig_g.update_layout(height=300, margin=dict(l=20,r=20,t=50,b=20))
                        st.plotly_chart(fig_g,use_container_width=True)
            else:
                st.warning("Sektör verisi yok.")
        else:
            kalem_pie = st.selectbox("Dağılım Kalemi:", df["Kalem"].unique(), key="pie_simple")
            df_pie = df[(df["TarihObj"]==df["TarihObj"].max()) & (df["Kalem"]==kalem_pie)]
            fig_pie = px.pie(df_pie, values="Değer", names="Taraf", color_discrete_sequence=px.colors.sequential.Oranges)
            st.plotly_chart(fig_pie,use_container_width=True)

    with tab4:
        st.markdown("#### 📑 Ham Veri Tablosu")
        st.dataframe(df.sort_values(["TarihObj","Taraf","Kalem"]),use_container_width=True)
        st.download_button("💾 Excel İndir", df.sort_values(["TarihObj","Taraf","Kalem"]).to_excel(index=False),file_name="bddk_analiz.xlsx")
