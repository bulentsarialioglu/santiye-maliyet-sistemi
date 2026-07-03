import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import streamlit_authenticator as stauth
from supabase import create_client
from io import BytesIO

# Sayfa Ayarları
st.set_page_config(layout="wide", page_title="Şantiye Maliyet Yönetimi")

# Başlık üzerindeki gereksiz boşluğu azaltmak için CSS
st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1.5rem;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# TÜRKÇE SAYI FORMATLAMA (12500.50 -> 12.500,50) - TL EKİ OLMADAN
def tr_number_str(deger):
    try:
        return f"{deger:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0,00"

# TÜRKÇE SAYI FORMATLAMA FONKSİYONU (12500.50 -> 12.500,50 TL)
def tr_format(deger):
    return tr_number_str(deger) + " TL"

# TÜRKÇE FORMATTAN SAYIYA ÇEVİRME FONKSİYONU ("1.234,56" -> 1234.56)
def tr_to_float(metin):
    if metin is None:
        return None
    metin = str(metin).strip()
    if metin == "":
        return None
    try:
        # Binlik ayıracı (.) kaldır, ondalık ayıracı (,) noktaya çevir
        temiz_metin = metin.replace(".", "").replace(",", ".")
        return float(temiz_metin)
    except ValueError:
        return None

# 1. KULLANICI GİRİŞ PANELİ AYARLARI
credentials = st.secrets["credentials"].to_dict()
authenticator = stauth.Authenticate(credentials, "santiye_cookie", "santiye_key", cookie_expiry_days=30)
authenticator.login()

if st.session_state["authentication_status"] == False:
    st.error('Kullanıcı adı veya şifre yanlış.')
elif st.session_state["authentication_status"] is None:
    st.warning('Lütfen kullanıcı adı ve şifrenizi giriniz.')
elif st.session_state["authentication_status"]:
    kullanici_adi = st.session_state["name"]

    # 2. SUPABASE BAĞLANTI AYARI
    SUPABASE_URL = "https://ocxptzvwjivakkuygreq.supabase.co"
    SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9jeHB0enZ3aml2YWtrdXlncmVxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODMwNzM1MzksImV4cCI6MjA5ODY0OTUzOX0.n10TevnBUemDXPH6HYskIVV-JPY42IO_iQddmjN6xlw"

    supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

    st.sidebar.write(f"Hoş geldiniz, **{kullanici_adi}**")
    authenticator.logout('Güvenli Çıkış Yap', 'sidebar')

    KALEMLER = ["Su", "Elektrik", "Kırtasiye", "Araç Kirası", "Araç Bakımı", "Yakıt", "HGS", "İnternet", "LNG", "Yemek", "Fotokopi", "Mutfak Harcaması", "Güvenlik", "Yardımcı Personel", "Temizlik Malzemesi", "Genel Bakım", "GSM", "Vidanjör", "Diğer"]

    st.title("🏗️ Şantiye İşletme Maliyeti")

    # Yan Menü: Veri Girişi
    st.sidebar.header("➕ Yeni Gider Ekle")
    secilen_tarih = st.sidebar.date_input("Tarih Seçin", datetime.date.today())
    secilen_kalem = st.sidebar.selectbox("Maliyet Kalemi", KALEMLER)
    girilen_tutar_str = st.sidebar.text_input("Tutar (TL)", placeholder="Örn: 1.250,50")
    girilen_detay = st.sidebar.text_input("Detay/Açıklama (Örn: 34XYZ123 Plaka Haziran)")

    if st.sidebar.button("Gideri Buluta Kaydet"):
        girilen_tutar = tr_to_float(girilen_tutar_str)
        if girilen_tutar is None:
            st.sidebar.error("Lütfen tutarı '1.250,50' formatında (nokta=binlik, virgül=ondalık) girin.")
        elif girilen_tutar > 0:
            yil_ay = secilen_tarih.strftime("%Y-%m")
            try:
                supabase_client.table("santiye_maliyetleri").insert({
                    "tarih": str(secilen_tarih),
                    "yil_ay": yil_ay,
                    "kalem": secilen_kalem,
                    "tutar": girilen_tutar,
                    "detay": girilen_detay
                }).execute()
                st.sidebar.success("Veri güvenli bir şekilde buluta kaydedildi!")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Veri yüklenirken hata oluştu: {e}")
        else:
            st.sidebar.error("Lütfen sıfırdan büyük bir tutar girin.")

    # 3. VERİLERİ BULUTTAN ÇEKME VE DASHBOARD
    try:
        response = supabase_client.table("santiye_maliyetleri").select("*").execute()

        if response.data:
            df_raw = pd.DataFrame(response.data)

            kolon_haritasi = {
                "id": "ID",
                "tarih": "Tarih",
                "yil_ay": "Yıl_Ay",
                "kalem": "Kalem",
                "tutar": "Tutar",
                "detay": "Detay",
                "created_at": "Kayıt Tarihi"
            }
            df = df_raw.rename(columns={k: v for k, v in kolon_haritasi.items() if k in df_raw.columns})

            if "Tarih" in df.columns:
                df['Tarih'] = pd.to_datetime(df['Tarih'])
            if "Tutar" in df.columns:
                df['Tutar'] = df['Tutar'].astype(float)

            toplam_harcama = df["Tutar"].sum() if "Tutar" in df.columns else 0
            bu_ay = datetime.date.today().strftime("%Y-%m")
            bu_ay_harcama = df[df["Yıl_Ay"] == bu_ay]["Tutar"].sum() if "Yıl_Ay" in df.columns and "Tutar" in df.columns else 0

            # 📌 Bu ayki harcamanın, diğer ayların ortalamasına göre %15'ten fazla
            # yüksek olup olmadığını kontrol et (uyarı ünlemi için)
            uyari_goster = False
            fark_yuzde = 0
            if "Yıl_Ay" in df.columns and "Tutar" in df.columns:
                aylik_toplamlar = df.groupby("Yıl_Ay")["Tutar"].sum()
                diger_aylar = aylik_toplamlar.drop(labels=[bu_ay], errors="ignore")
                if len(diger_aylar) > 0:
                    ortalama_aylik_harcama = diger_aylar.mean()
                    if ortalama_aylik_harcama > 0 and bu_ay_harcama > ortalama_aylik_harcama * 1.15:
                        uyari_goster = True
                        fark_yuzde = ((bu_ay_harcama / ortalama_aylik_harcama) - 1) * 100

            # 📌 KPI Metrikleri Türkçe Formatına Güncellendi
            col1, col2 = st.columns(2)
            col1.metric("📊 Toplam Proje Harcaması", tr_format(toplam_harcama))
            if uyari_goster:
                col2.metric(
                    "📅 Bu Ayki Toplam Harcama ❗",
                    tr_format(bu_ay_harcama),
                    help=f"Bu ayki harcama, diğer ayların ortalamasının %{fark_yuzde:.0f} üzerinde!"
                )
            else:
                col2.metric("📅 Bu Ayki Toplam Harcama", tr_format(bu_ay_harcama))

            if uyari_goster:
                col2.markdown(
                    f"<span style='color:#D32F2F; font-weight:700;'>❗ Ortalamanın %{fark_yuzde:.0f} üzerinde harcama yapıldı!</span>",
                    unsafe_allow_html=True
                )

            st.markdown("---")

            col3, col4 = st.columns(2)
            with col3:
                st.subheader("📊 Aylık Toplam Harcama Trendi")
                if "Tarih" in df.columns and "Tutar" in df.columns:
                    df['Ay_Adi'] = df['Tarih'].dt.strftime('%B')

                    ay_siralamasi = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
                    turkce_aylar = {"January": "Ocak", "February": "Şubat", "March": "Mart", "April": "Nisan", "May": "Mayıs", "June": "Haziran", "July": "Temmuz", "August": "Ağustos", "September": "Eylül", "October": "Ekim", "November": "Kasım", "December": "Aralık"}

                    aylik_grup = df.groupby('Ay_Adi', as_index=False)['Tutar'].sum()
                    aylik_grup['Ay_Adi'] = pd.Categorical(aylik_grup['Ay_Adi'], categories=ay_siralamasi, ordered=True)
                    aylik_grup = aylik_grup.sort_values('Ay_Adi')
                    aylik_grup['Ay_Adi'] = aylik_grup['Ay_Adi'].map(turkce_aylar)

                    fig_bar = px.bar(aylik_grup, x="Ay_Adi", y="Tutar", labels={"Ay_Adi": "Aylar", "Tutar": "Toplam Gider (TL)"})
                    fig_bar.update_traces(marker_color='#800020', textposition='outside')

                    # 📌 Grafik Sayı Ayracı Türkçe Yapıldı
                    fig_bar.update_layout(
                        separators=".,",
                        yaxis=dict(tickformat=",.2f")
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)

            with col4:
                st.subheader("🍕 Kalemlere Göre Dağılım (Genel)")
                if "Kalem" in df.columns and "Tutar" in df.columns:
                    fig_pie = px.pie(df.groupby("Kalem", as_index=False)["Tutar"].sum(), values="Tutar", names="Kalem", hole=0.3)
                    # 📌 Pasta Grafiği Ayracı Türkçe Yapıldı
                    fig_pie.update_layout(separators=".,")
                    st.plotly_chart(fig_pie, use_container_width=True)

            st.markdown("---")
            st.subheader("🔍 Detaylı Veri İnceleme & Filtreleme")
            arama_kelimesi = st.text_input("Açıklama içinde ara")

            mevcut_aylar = sorted(df["Yıl_Ay"].dropna().unique()) if "Yıl_Ay" in df.columns else []
            mevcut_kalemler = sorted(df["Kalem"].dropna().unique()) if "Kalem" in df.columns else []
            secilen_ay_filtresi = st.multiselect("Aylara Göre Filtrele", mevcut_aylar)
            secilen_kalem_filtresi = st.multiselect("Kalemlere Göre Filtrele", mevcut_kalemler)

            filtreli_df = df.copy()
            if arama_kelimesi and "Detay" in filtreli_df.columns:
                filtreli_df = filtreli_df[filtreli_df["Detay"].str.contains(arama_kelimesi, case=False, na=False)]
            if secilen_ay_filtresi and "Yıl_Ay" in filtreli_df.columns:
                filtreli_df = filtreli_df[filtreli_df["Yıl_Ay"].isin(secilen_ay_filtresi)]
            if secilen_kalem_filtresi and "Kalem" in filtreli_df.columns:
                filtreli_df = filtreli_df[filtreli_df["Kalem"].isin(secilen_kalem_filtresi)]

            if "Tarih" in filtreli_df.columns:
                filtreli_df = filtreli_df.sort_values(by="Tarih", ascending=False)

            gosterilecek_kolonlar = [c for c in ["ID", "Tarih", "Yıl_Ay", "Kalem", "Tutar", "Detay", "Kayıt Tarihi"] if c in filtreli_df.columns]

            col_pdf, _ = st.columns(2)
            with col_pdf:
                export_df = filtreli_df[gosterilecek_kolonlar].copy()
                # 📌 Excel Çıktısı Türkçe Bölge Ayarlarına Uyarlandı (sep=';' ve ondalık virgül)
                csv_data = export_df.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
                st.download_button(label="📥 Filtrelenmiş Raporu CSV/Excel Olarak İndir", data=csv_data, file_name=f"santiye_raporu_{datetime.date.today()}.csv", mime="text/csv", use_container_width=True)

            # 📌 Tablodaki Sayı Gösterimi Türkçe Yapıldı
            st.dataframe(
                filtreli_df[gosterilecek_kolonlar],
                use_container_width=True,
                column_config={
                    "Tutar": st.column_config.NumberColumn("Tutar (TL)", format="%.2f")
                }
            )

            # --- YAN YANA VERİ DÜZENLEME VE SİLME PANELLERİ ---
            st.markdown("---")
            col_duzenle_sol, col_sil_sag = st.columns(2)
            genel_id_listesi = filtreli_df["ID"].tolist()

            if genel_id_listesi:
                # 🛠️ GÜNCELLEME / DÜZENLEME ALANI (SOL SÜTUN)
                with col_duzenle_sol:
                    st.subheader("📝 Kayıt Düzenleme İşlemi")
                    st.caption("Güncellemek istediğiniz kaydın ID'sini seçip yeni değerlerini girin.")

                    secilen_duzenle_id = st.selectbox("Düzenlenecek Kayıt ID'sini Seçin", genel_id_listesi, key="duzenle_id_select")
                    secilen_d_kayit = filtreli_df[filtreli_df["ID"] == secilen_duzenle_id]

                    if not secilen_d_kayit.empty:
                        mevcut_tarih = pd.to_datetime(secilen_d_kayit['Tarih'].iloc[0]).date()
                        mevcut_kalem_deger = secilen_d_kayit['Kalem'].iloc[0]
                        mevcut_kalem_idx = KALEMLER.index(mevcut_kalem_deger) if mevcut_kalem_deger in KALEMLER else 0
                        mevcut_tutar = float(secilen_d_kayit['Tutar'].iloc[0])
                        mevcut_detay = str(secilen_d_kayit['Detay'].iloc[0])

                        yeni_tarih = st.date_input("Yeni Tarih", mevcut_tarih, key="y_tarih")
                        yeni_kalem = st.selectbox("Yeni Maliyet Kalemi", KALEMLER, index=mevcut_kalem_idx, key="y_kalem")
                        yeni_tutar_str = st.text_input("Yeni Tutar (TL)", value=tr_number_str(mevcut_tutar), key="y_tutar")
                        yeni_detay = st.text_input("Yeni Detay/Açıklama", mevcut_detay, key="y_detay")

                        if st.button("🔵 Değişiklikleri Bulutta Güncelle", use_container_width=True):
                            yeni_tutar = tr_to_float(yeni_tutar_str)
                            if yeni_tutar is None:
                                st.error("Lütfen tutarı '1.250,50' formatında (nokta=binlik, virgül=ondalık) girin.")
                            elif yeni_tutar <= 0:
                                st.error("Lütfen sıfırdan büyük bir tutar girin.")
                            else:
                                try:
                                    supabase_client.table("santiye_maliyetleri").update({
                                        "tarih": str(yeni_tarih),
                                        "yil_ay": yeni_tarih.strftime("%Y-%m"),
                                        "kalem": yeni_kalem,
                                        "tutar": yeni_tutar,
                                        "detay": yeni_detay
                                    }).eq("id", int(secilen_duzenle_id)).execute()
                                    st.success("Kayıt başarıyla güncellendi!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Güncelleme hatası: {e}")

                # 🗑️ SİLME ALANI (SAĞ SÜTUN)
                with col_sil_sag:
                    st.subheader("🗑️ Kayıt Silme İşlemi")
                    st.caption("Seçtiğiniz benzersiz ID numarasına sahip harcamayı buluttan tamamen temizler.")

                    secilen_sil_id = st.selectbox("Silinecek Kayıt ID'sini Seçin", genel_id_listesi, key="sil_id_select")
                    secilen_kayit_detay = filtreli_df[filtreli_df["ID"] == secilen_sil_id]

                    if not secilen_kayit_detay.empty:
                        tutar_val = float(secilen_kayit_detay['Tutar'].iloc[0])
                        kalem_val = str(secilen_kayit_detay['Kalem'].iloc[0])
                        detay_val = str(secilen_kayit_detay['Detay'].iloc[0])
                        st.info(f"Seçilecek Silme Onayı:\n\n**{kalem_val}** - {tr_format(tutar_val)}\n\n({detay_val})")

                    st.write("")
                    st.write("")
                    st.write("")
                    st.write("")
                    if st.button("🔴 Seçili Kaydı Kalıcı Sil", use_container_width=True):
                        try:
                            supabase_client.table("santiye_maliyetleri").delete().eq("id", int(secilen_sil_id)).execute()
                            st.success("Kayıt başarıyla silindi!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Silme hatası: {e}")
        else:
            st.info("Bulut veritabanında henüz kayıtlı veri yok. Sol menüden ilk eklemeyi yapın.")
    except Exception as e:
        st.error(f"Buluttan veri çekilirken hata oluştu: {e}")
