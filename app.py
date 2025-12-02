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
from openai import OpenAI
import plotly.express as px
import plotly.graph_objects as go
import time
import sys
import io

# --- 1. AYARLAR VE TASARIM ---
st.set_page_config(page_title="BDDK Veri Analizi", layout="wide", page_icon="🏦", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stApp { background-color: #F9F9F9; }
    [data-testid="stSidebar"] { background-color: #FCB131; border-right: 1px solid #e0e0e0; }
    [data-testid="stSidebar"] * { color: #000000 !important; font-family: 'Segoe UI', sans-serif; }

    /* ANALİZİ BAŞLAT BUTONU: BEYAZ ZEMİN, SİYAH YAZI */
    div.stButton > button { 
        background-color: #FFFFFF !important; 
        color: #000000 !important; 
        font-weight: 900 !important; 
        border-radius: 8px; 
        border: 2px solid #000000 !important; 
        width: 100%; 
        padding: 15px; 
        font-size: 18px !important; 
        transition: all 0.3s ease; 
    }
    div.stButton > button:hover { 
        background-color: #000000 !important; 
        color: #FFFFFF !important; 
        border-color: #000000 !important; 
        transform: scale(1.02); 
    }

    [data-testid="stMetric"] { background-color: #FFFFFF; padding: 15px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-top: 5px solid #FCB131; }
    [data-testid="stMetricLabel"] { font-weight: bold; color: #555; }
    [data-testid="stMetricValue"] { color: #000000; font-weight: 800; font-size: 26px !important; }
    h1, h2, h3 { color: #d99000 !important; font-weight: 800; }
    .dataframe { font-size: 14px !important; }

    /* YAN PANELİ KAPATMA TUŞUNU GİZLE (SABİT KALSIN) */
    [data-testid="stSidebarCollapseButton"] { display: none; }
</style>
""", unsafe_allow_html=True)

# --- 2. CONFIG ---
AY_LISTESI = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım",
              "Aralık"]
TARAF_SECENEKLERI = ["Sektör", "Mevduat-Kamu", "Mevduat-Yerli Özel", "Mevduat-Yabancı", "Katılım"]

# DÜZELTME NOTU: Bazı satırlarda 'col_attr' yazmışsınız, kod aşağıda 'col_id' arıyor.
# Bu yüzden onları 'col_id' olarak düzelttim ki KeyError almayın.
VERI_KONFIGURASYONU = {
    "📌 Toplam Aktifler": {"tab": "tabloListesiItem-1", "row_text": "TOPLAM AKTİFLER", "col_id": "grdRapor_Toplam"},
    "📌 Toplam Özkaynaklar": {"tab": "tabloListesiItem-1", "row_text": "TOPLAM ÖZKAYNAKLAR", "col_id": "grdRapor_Toplam"},
    "⚠️ Takipteki Alacaklar": {"tab": "tabloListesiItem-1", "row_text": "Takipteki Alacaklar", "col_id": "grdRapor_Toplam"},
    "💰 Dönem Net Kârı": {"tab": "tabloListesiItem-2", "row_text": "DÖNEM NET KARI (ZARARI)", "col_id": "grdRapor_Toplam"},
    "📊 Sermaye Yeterliliği Rasyosu": {"tab": "tabloListesiItem-12", "row_text": "Sermaye Yeterliliği Standart Rasyosu", "col_id": "grdRapor_Toplam"},
    "💳 Bireysel Kredi Kartları": {"tab": "tabloListesiItem-4", "row_text": "Bireysel Kredi Kartları (10+11)", "col_id": "grdRapor_Toplam"},
    "🏦 Toplam Krediler": {"tab": "tabloListesiItem-3", "row_text": "Toplam Krediler", "col_id": "grdRapor_Toplam"},
    "🏠 Tüketici Kredileri": {"tab": "tabloListesiItem-4", "row_text": "Tüketici Kredileri", "col_id": "grdRapor_Toplam"},
    "🏭 KOBİ Kredileri": {"tab": "tabloListesiItem-6", "row_text": "Toplam KOBİ Kredileri", "col_id": "grdRapor_NakdiKrediToplam"}
}


# --- 3. DRIVER YÖNETİMİ ---
def get_driver():
    if sys.platform == "linux":
        options = FirefoxOptions()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        try:
            service = FirefoxService(GeckoDriverManager().install())
            return webdriver.Firefox(service=service, options=options)
        except Exception as e:
            st.error(f"Firefox Driver Başlatılamadı: {e}")
            return None
    else:
        options = ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        try:
            service = ChromeService(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=options)
        except Exception as e:
            st.error(f"Chrome Driver Başlatılamadı: {e}")
            return None


# --- 4. VERİ ÇEKME MOTORU ---
def scrape_bddk_data(bas_yil, bas_ay, bit_yil, bit_ay, secilen_taraflar, secilen_veriler, status_text_obj,
                     progress_bar_obj):
    driver = None
    data = []

    try:
        driver = get_driver()
        if not driver:
            return pd.DataFrame()

        driver.set_page_load_timeout(60)
        driver.get("https://www.bddk.org.tr/bultenaylik")

        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "ddlYil")))
        time.sleep(2)

        bas_idx = AY_LISTESI.index(bas_ay)
        bit_idx = AY_LISTESI.index(bit_ay)

        total_steps = (bit_yil - bas_yil) * 12 + (bit_idx - bas_idx) + 1
        current_step = 0

        for yil in range(bas_yil, bit_yil + 1):
            s_m = bas_idx if yil == bas_yil else 0
            e_m = bit_idx if yil == bit_yil else 11

            for ay_i in range(s_m, e_m + 1):
                ay_str = AY_LISTESI[ay_i]
                donem = f"{ay_str} {yil}"

                # Progress Bar Üstüne Anlık Bilgi Yaz
                if status_text_obj:
                    status_text_obj.info(f"⏳ **İşleniyor:** {donem}")

                try:
                    driver.execute_script("document.getElementById('ddlYil').style.display = 'block';")
                    sel_yil = Select(driver.find_element(By.ID, "ddlYil"))
                    sel_yil.select_by_visible_text(str(yil))
                    driver.execute_script("arguments[0].dispatchEvent(new Event('change'))",
                                          driver.find_element(By.ID, "ddlYil"))
                    time.sleep(1.5)

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
                                # Düzeltme: Burada kod col_id arıyor, config'de col_attr olursa hata verirdi.
                                toplam = row.find("td", {"aria-describedby": conf['col_id']})

                                if ad and toplam:
                                    row_taraf = current_group if current_group else taraf
                                    if conf['row_text'] in ad.get_text(strip=True):
                                        raw_text = toplam.get_text(strip=True)
                                        clean_text = raw_text.replace('.', '').replace(',', '.')
                                        try:
                                            found_val = float(clean_text)
                                        except:
                                            found_val = 0.0

                                        data.append({
                                            "Dönem": donem,
                                            "Taraf": row_taraf,
                                            "Kalem": veri,
                                            "Değer": found_val,
                                            "TarihObj": pd.to_datetime(f"{yil}-{ay_i + 1}-01")
                                        })
                except Exception as e:
                    pass

                current_step += 1
                if progress_bar_obj:
                    progress_bar_obj.progress(min(current_step / max(1, total_steps), 1.0))

    except Exception as e:
        pass
    finally:
        if driver: driver.quit()

    return pd.DataFrame(data)


# --- ANA EKRAN ---
with st.sidebar:
    st.title("🎛️ KONTROL PANELİ")
    st.markdown("---")

    c1, c2 = st.columns(2)
    bas_yil = c1.number_input("Başlangıç Yılı", 2024, 2030, 2024, key="sb_bas_yil")
    bas_ay = c1.selectbox("Başlangıç Ayı", AY_LISTESI, index=0, key="sb_bas_ay")
    c3, c4 = st.columns(2)
    bit_yil = c3.number_input("Bitiş Yılı", 2024, 2030, 2024, key="sb_bit_yil")
    bit_ay = c4.selectbox("Bitiş Ayı", AY_LISTESI, index=0, key="sb_bit_ay")
    st.markdown("---")
    secilen_taraflar = st.multiselect("Karşılaştır:", TARAF_SECENEKLERI, default=["Sektör"], key="sb_taraflar")
    # HATA BURADAYDI: default değeri sözlükteki anahtarla birebir (harf büyüklüğü dahil) aynı olmalı.
    secilen_veriler = st.multiselect("Veri:", list(VERI_KONFIGURASYONU.keys()), default=["📌 Toplam Aktifler"],
                                     key="sb_veriler")
    st.markdown("---")
    st.markdown("### 🚀 İŞLEM MERKEZİ")
    btn = st.button("ANALİZİ BAŞLAT", key="sb_btn_baslat")

st.title("🏦 BDDK Analiz Paneli")

if 'df_sonuc' not in st.session_state:
    st.session_state['df_sonuc'] = None

if btn:
    if not secilen_taraflar or not secilen_veriler:
        st.warning("Lütfen en az bir Taraf ve bir Veri kalemi seçin.")
    else:
        status_txt = st.empty()
        status_txt.info("🌐 BDDK'ya bağlanılıyor, lütfen bekleyiniz...")

        my_bar = st.progress(0)

        df = scrape_bddk_data(bas_yil, bas_ay, bit_yil, bit_ay, secilen_taraflar, secilen_veriler, status_txt, my_bar)

        my_bar.empty()
        status_txt.empty()

        if not df.empty:
            st.session_state['df_sonuc'] = df
            st.success("✅ Veriler Başarıyla Çekildi!")
            st.balloons()
            time.sleep(1)
            st.rerun()
        else:
            st.error("Veri bulunamadı veya bağlantı hatası oluştu.")

# --- DASHBOARD ---
if st.session_state['df_sonuc'] is not None:
    df = st.session_state['df_sonuc']
    df = df.drop_duplicates(subset=["Dönem", "Taraf", "Kalem"])
    df = df.sort_values("TarihObj")

    st.subheader("📊 Özet Performans (Son Dönem)")
    try:
        son_tarih = df["TarihObj"].max()
        df_son = df[df["TarihObj"] == son_tarih]

        cols = st.columns(4)
        for i, (idx, row) in enumerate(df_son.head(8).iterrows()):
            with cols[i % 4]:
                prev_val = 0
                df_prev = df[
                    (df["TarihObj"] < son_tarih) & (df["Kalem"] == row["Kalem"]) & (df["Taraf"] == row["Taraf"])]
                if not df_prev.empty:
                    prev_val = df_prev.iloc[-1]["Değer"]

                delta_val = row["Değer"] - prev_val
                delta_pct = (delta_val / prev_val * 100) if prev_val != 0 else 0
                val_fmt = f"{row['Değer']:,.0f}".replace(",", ".")

                label_text = f"{row['Taraf']} - {row['Kalem'][:10]}..."
                st.metric(label=label_text, value=f"{val_fmt}", delta=f"%{delta_pct:.1f}")
    except Exception as e:
        st.error(f"Metrik hatası: {e}")

    st.markdown("---")
    # Mevcut satırı bulun ve şununla değiştirin:
    tab1, tab2, tab3, tab4 = st.tabs(["📉 Trend Analizi", "🧪 Senaryo Simülasyonu", "📑 Detaylı Tablo", "🤖 AI Yorumu"])
    with tab1:
        kalem_sec = st.selectbox("Grafik Kalemi:", df["Kalem"].unique(), key="trend_select")
        df_chart = df[df["Kalem"] == kalem_sec].copy()
        df_chart = df_chart.sort_values("TarihObj")

        fig = px.line(df_chart, x="Dönem", y="Değer", color="Taraf", title=f"📅 {kalem_sec} Trendi",
                      markers=True,
                      color_discrete_sequence=["#FCB131", "#000000", "#555555"])

        fig.update_xaxes(categoryorder='array', categoryarray=df_chart["Dönem"].unique())
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", hovermode="x unified")
        fig.update_yaxes(tickformat=",")
        st.plotly_chart(fig, use_container_width=True, key="trend_chart")

    with tab2:
        st.markdown("#### 🧪 What-If (Senaryo) Analizi")
        st.info("Seçtiğiniz tarafın verilerini sanal olarak artırıp azaltarak sonucu simüle edin.")
        c_sim1, c_sim2 = st.columns([1, 2])
        with c_sim1:
            taraf_sim = st.selectbox("Simüle Edilecek Taraf:", df["Taraf"].unique(), key="sim_taraf")
            kalem_sim = st.selectbox("Simüle Edilecek Kalem:", df["Kalem"].unique(), key="sim_kalem")
            artis_orani = st.slider("Değişim Oranı (%)", min_value=-50, max_value=50, value=10, step=5,
                                    key="sim_slider")
        with c_sim2:
            base_row = df[
                (df["Taraf"] == taraf_sim) & (df["Kalem"] == kalem_sim) & (df["TarihObj"] == df["TarihObj"].max())]
            if not base_row.empty:
                mevcut_deger = base_row.iloc[0]["Değer"]
                yeni_deger = mevcut_deger * (1 + artis_orani / 100)
                fark = yeni_deger - mevcut_deger
                col_a, col_b = st.columns(2)
                with col_a: st.metric("Mevcut Durum", f"{mevcut_deger:,.0f}".replace(",", "."))
                with col_b: st.metric(f"Senaryo (%{artis_orani})", f"{yeni_deger:,.0f}".replace(",", "."),
                                      delta=f"{fark:,.0f}".replace(",", "."))
                sim_data = pd.DataFrame({"Durum": ["Mevcut", "Simülasyon"], "Tutar": [mevcut_deger, yeni_deger]})
                fig_sim = px.bar(sim_data, x="Durum", y="Tutar", color="Durum", text_auto='.2s',
                                 color_discrete_map={"Mevcut": "#000000", "Simülasyon": "#FCB131"})
                fig_sim.update_layout(height=300, showlegend=False)
                st.plotly_chart(fig_sim, use_container_width=True, key="sim_chart")

    with tab3:
        st.markdown("#### 📑 Ham Veri Tablosu")
        # Kalemi geri getirdik ve sıraya soktuk: Tarih -> Kalem -> Taraf
        df_display = df.sort_values(["TarihObj", "Kalem", "Taraf"])

        # Gösterilecek sütunları seç (TarihObj'yi at, Kalem'i tut)
        df_display = df_display[["Dönem", "Kalem", "Taraf", "Değer"]]

        # Ekran için formatlama (Noktalı)
        df_formatted_display = df_display.copy()
        df_formatted_display["Değer"] = df_formatted_display["Değer"].apply(
            lambda x: "{:,.0f}".format(x).replace(",", "."))

        st.dataframe(df_formatted_display, use_container_width=True)
        with tab4:
            st.markdown("#### 🤖 Yapay Zeka Destekli Finansal Yorum")
            st.info("Verileri analiz etmek için OpenAI (ChatGPT) API anahtarınızı giriniz. Anahtarınız kaydedilmez.")

            # API Key Giriş Alanı
            api_key = st.text_input("OpenAI API Key", type="password", placeholder="sk-...")

            if api_key:
                # Analiz Butonu
                if st.button("🚀 Verileri Yorumla"):
                    try:
                        client = OpenAI(api_key=api_key)

                        with st.spinner("Yapay zeka verileri inceliyor, finansal çıkarımlar yapıyor..."):
                            # --- 1. Veriyi Hazırla (Token tasarrufu için özetliyoruz) ---
                            # Sadece son 3 dönemi ve önemli değişimleri alalım
                            df_ai = df.sort_values("TarihObj", ascending=True)
                            son_donemler = df_ai["Dönem"].unique()[-3:]  # Son 3 dönem
                            df_ai_ozet = df_ai[df_ai["Dönem"].isin(son_donemler)]

                            # Veriyi metne çevir
                            csv_data = df_ai_ozet[["Dönem", "Taraf", "Kalem", "Değer"]].to_csv(index=False)

                            # --- 2. Prompt (Komut) Hazırla ---
                            prompt = f"""
                            Sen uzman bir bankacılık ve finans analistisin. 
                            Aşağıdaki CSV formatındaki verileri analiz et.

                            Veriler:
                            {csv_data}

                            Lütfen şunları yap:
                            1. Verilerdeki ana trendi belirle (Artış/Azalış).
                            2. Taraf bazında (Sektör vs Kamu vs Özel) dikkat çeken bir ayrışma varsa belirt.
                            3. Bu veriler bankacılık sektörü için bir risk mi yoksa fırsat mı oluşturuyor?
                            4. Finansal okuryazarlığı olan bir yöneticiye sunulacak profesyonel bir dille, Türkçe özetle.
                            5. Sayısal verileri kullanırken binlik ayrımlarına dikkat et.
                            """

                            # --- 3. API'ye Gönder ---
                            response = client.chat.completions.create(
                                model="gpt-4o",  # Veya gpt-3.5-turbo
                                messages=[
                                    {"role": "system", "content": "Sen kıdemli bir finansal danışmansın."},
                                    {"role": "user", "content": prompt}
                                ],
                                temperature=0.7
                            )

                            ai_reply = response.choices[0].message.content

                        # --- 4. Sonucu Yazdır ---
                        st.success("Analiz Tamamlandı!")
                        st.markdown("---")
                        st.markdown(ai_reply)

                    except Exception as e:
                        st.error(f"Hata oluştu: {e}. Lütfen API anahtarınızı ve bakiyenizi kontrol edin.")
            else:
                st.warning("Lütfen başlamak için API anahtarınızı girin.")
        with tab4:
            st.markdown("#### 🤖 Yapay Zeka Destekli Finansal Yorum")
            st.info("Verileri analiz etmek için OpenAI (ChatGPT) API anahtarınızı giriniz. Anahtarınız kaydedilmez.")

            # API Key Giriş Alanı
            api_key = st.text_input("OpenAI API Key", type="password", placeholder="sk-...")

            if api_key:
                # Analiz Butonu
                if st.button("🚀 Verileri Yorumla"):
                    try:
                        client = OpenAI(api_key=api_key)

                        with st.spinner("Yapay zeka verileri inceliyor, finansal çıkarımlar yapıyor..."):
                            # --- 1. Veriyi Hazırla (Token tasarrufu için özetliyoruz) ---
                            # Sadece son 3 dönemi ve önemli değişimleri alalım
                            df_ai = df.sort_values("TarihObj", ascending=True)
                            son_donemler = df_ai["Dönem"].unique()[-3:]  # Son 3 dönem
                            df_ai_ozet = df_ai[df_ai["Dönem"].isin(son_donemler)]

                            # Veriyi metne çevir
                            csv_data = df_ai_ozet[["Dönem", "Taraf", "Kalem", "Değer"]].to_csv(index=False)

                            # --- 2. Prompt (Komut) Hazırla ---
                            prompt = f"""
                            Sen uzman bir bankacılık ve finans analistisin. 
                            Aşağıdaki CSV formatındaki verileri analiz et.

                            Veriler:
                            {csv_data}

                            Lütfen şunları yap:
                            1. Verilerdeki ana trendi belirle (Artış/Azalış).
                            2. Taraf bazında (Sektör vs Kamu vs Özel) dikkat çeken bir ayrışma varsa belirt.
                            3. Bu veriler bankacılık sektörü için bir risk mi yoksa fırsat mı oluşturuyor?
                            4. Finansal okuryazarlığı olan bir yöneticiye sunulacak profesyonel bir dille, Türkçe özetle.
                            5. Sayısal verileri kullanırken binlik ayrımlarına dikkat et.
                            """

                            # --- 3. API'ye Gönder ---
                            response = client.chat.completions.create(
                                model="gpt-4o",  # Veya gpt-3.5-turbo
                                messages=[
                                    {"role": "system", "content": "Sen kıdemli bir finansal danışmansın."},
                                    {"role": "user", "content": prompt}
                                ],
                                temperature=0.7
                            )

                            ai_reply = response.choices[0].message.content

                        # --- 4. Sonucu Yazdır ---
                        st.success("Analiz Tamamlandı!")
                        st.markdown("---")
                        st.markdown(ai_reply)

                    except Exception as e:
                        st.error(f"Hata oluştu: {e}. Lütfen API anahtarınızı ve bakiyenizi kontrol edin.")
            else:
                st.warning("Lütfen başlamak için API anahtarınızı girin.")

        # --- EXCEL ÇIKTISI ---
        df_for_excel = df.copy().sort_values(["TarihObj", "Kalem", "Taraf"])
        df_for_excel["Değer"] = df_for_excel["Değer"].apply(lambda x: "{:,.0f}".format(x).replace(",", "."))

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer) as writer:
            unique_kalemler = df_for_excel["Kalem"].unique()
            for kalem_adi in unique_kalemler:
                sub_df = df_for_excel[df_for_excel["Kalem"] == kalem_adi].copy()
                # Sayfa adı zaten kalem adı, bu yüzden Excel içinden çıkarıyoruz
                sub_df = sub_df.drop(columns=["Kalem", "TarihObj"])

                sheet_name = kalem_adi[:30].replace("/", "-").replace("\\", "-")
                sub_df.to_excel(writer, index=False, sheet_name=sheet_name)

        st.download_button(
            label="💾 Excel İndir",
            data=buffer.getvalue(),
            file_name="bddk_analiz.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="btn_excel"
        )