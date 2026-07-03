import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import streamlit_authenticator as stauth
from supabase import create_client
from io import BytesIO

# Sayfa Ayarları
st.set_page_config(layout="wide", page_title="Şantiye Maliyet Yönetimi")

# 1. KULLANICI GİRİŞ PANELİ AYARLARI
credentials = st.secrets["credentials"].to_dict()
authenticator = stauth.Authenticate(credentials, "santiye_cookie", "santiye_key", cookie_expiry_days=30)
authenticator.login()

if st.session_state["authentication_status"] == False:
    st.error('Kullanıcı adı veya şifre yanlış.')
elif st.session_state["authentication_status"] == None:
    st.warning('Lütfen kullanıcı adı ve şifrenizi giriniz.')
elif st.session_state["authentication_status"]:
    kullanici_adi = st.session_state["name"]
    
    # 2. SUPABASE BAĞLANTI AYARI
    SUPABASE_URL = "https://ocxptzvwjivakkuygreq.supabase.co"
    SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9jeHB0enZ3aml2YWtrdXlncmVxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODMwNzM1MzksImV4cCI6MjA5ODY0OTUzOX0.n10TevnBUemDXPH6HYskIVV-JPY42IO_iQddmjN6xlw"
    
    supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

    st.sidebar.write(f"Hoş geldiniz, **{kullanici_adi}**")
    authenticator.logout('Güvenli Çıkış Yap', 'sidebar')

    KALEMLER = ["Su", "Elektrik", "Kırtasiye", "Araç Kirası", "Araç Bakımı", "Yakıt", "HGS", "İnternet", "LNG", "Yemek", "Fotokopi", "Mutfak Harcaması", "Güvenlik", "Yardımcı Personel", "Tamirat", "Genel Bakım", "Demirbaş", "Diğer"]

    st.title("🏗️ Şantiye İşletme Maliyeti")

    # Yan Menü: Veri Girişi
    st.sidebar.header("➕ Yeni Gider Ekle")
    secilen_tarih = st.sidebar.date_input("Tarih Seçin", datetime.date.today())
    secilen_kalem = st.sidebar.selectbox("Maliyet Kalemi", KALEMLER)
    girilen_tutar = st.sidebar.number_input("Tutar (TL)", min_value=0.0, step=100.0, format="%.2f")
    girilen_detay = st.sidebar.text_input("Detay/Açıklama (Örn: 34XYZ123 Plaka Haziran)")

    if st.sidebar.button("Gideri Buluta Kaydet"):
        if girilen_tutar > 0:
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
            df = df_raw.rename(columns={"id": "ID", "tarih": "Tarih", "yil_ay": "Yıl_Ay", "kalem": "Kalem", "tutar": "Tutar", "detay": "Detay", "created_at": "Kayıt Tarihi"})
            
            if "Tarih" in df.columns: df['Tarih'] = pd.to_datetime(df['Tarih'])
            if "Tutar" in df.columns: df['Tutar'] = df['Tutar'].astype(float)
            
            toplam_harcama = df["Tutar"].sum() if "Tutar" in df.columns else 0
            bu_ay = datetime.date.today().strftime("%Y-%m")
            bu_ay_harcama = df[df["Yıl_Ay"] == bu_ay]["Tutar"].sum() if "Yıl_Ay" in df.columns and "Tutar" in df.columns else 0

            col1, col2 = st.columns(2)
            col1.metric("📊 Toplam Proje Harcaması", f"{toplam_harcama:,.2f} TL")
            col2.metric("📅 Bu Ayki Toplam Harcama", f"{bu_ay_harcama:,.2f} TL")
            st.markdown("---")

            col3, col4 = st.columns(2)
            with col3:
                st.subheader("📊 Aylık Toplam Harcama Trendi")
                if "Tarih" in df.columns and "Tutar" in df.columns:
                    # Tarihten Ay isimlerini çekiyoruz (Ocak, Şubat...)
                    df['Ay_Adi'] = df['Tarih'].dt.strftime('%B')
                    
                    # 12 ayın kronolojik sırasını garanti altına alıyoruz
                    ay_siralamasi = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
                    turkce_aylar = {"January": "Ocak", "February": "Şubat", "March": "Mart", "April": "Nisan", "May": "Mayıs", "June": "Haziran", "July": "Temmuz", "August": "Ağustos", "September": "Eylül", "October": "Ekim", "November": "Kasım", "December": "Aralık"}
                    
                    # Gruplama ve sıralama işlemleri
                    aylik_grup = df.groupby('Ay_Adi')['Tutar'].sum().reset_index()
                    aylik_grup['Ay_Adi'] = pd.Categorical(aylik_grup['Ay_Adi'], categories=ay_siralamasi, ordered=True)
                    aylik_grup = aylik_grup.sort_values('Ay_Adi')
                    aylik_grup['Ay_Adi'] = aylik_grup['Ay_Adi'].map(turkce_aylar)
                    
                    # İstediğiniz dikey sütun (Bar) grafiği tasarımı
                    fig_bar = px.bar(aylik_grup, x="Ay_Adi", y="Tutar", text_auto='.2s', labels={"Ay_Adi": "Aylar", "Tutar": "Toplam Gider (TL)"})
                    fig_bar.update_traces(marker_color='#FF4B4B', textposition='outside')
                    st.plotly_chart(fig_bar, use_container_width=True)
                    
            with col4:
                st.subheader("🍕 Kalemlere Göre Dağılım (Genel)")
                if "Kalem" in df.columns and "Tutar" in df.columns:
                    st.plotly_chart(px.pie(df.groupby("Kalem")["Tutar"].sum().reset_index(), values="Tutar", names="Kalem", hole=0.3), use_container_width=True)

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

            if "Tarih" in filtreli_df.columns: filtreli_df = filtreli_df.sort_values(by="Tarih", ascending=False)

            col_pdf, _ = st.columns(2)
            with col_pdf:
                # Ay_Adi kolonunu çıktıya dahil etmemek için filtreliyoruz
                export_df = filtreli_df[["ID", "Tarih", "Yıl_Ay", "Kalem", "Tutar", "Detay", "Kayıt Tarihi"]].copy()
                csv_data = export_df.to_csv(index=False).encode('utf-8')
                st.download_button(label="📥 Filtrelenmiş Raporu CSV/Excel Olarak İndir", data=csv_data, file_name=f"santiye_raporu_{datetime.date.today()}.csv", mime="text/csv", use_container_width=True)

            # Ekranda temiz durması için geçici analiz kolonunu gizleyerek gösteriyoruz
            st.dataframe(filtreli_df[["ID", "Tarih", "Yıl_Ay", "Kalem", "Tutar", "Detay", "Kayıt Tarihi"]], use_container_width=True, column_config={"Tutar": st.column_config.NumberColumn("Tutar (TL)", format="%.2f TL")})

            # --- KAYIT SİLME PANELİ ---
            st.markdown("---")
            st.subheader("🗑️ Kayıt Silme İşlemi")
            silinecek_id_listesi = filtreli_df["ID"].tolist()
            
            col_sil_sec, col_sil_buton = st.columns(2)
            with col_sil_sec:
                secilen_sil_id = st.selectbox("Silinecek Kayıt ID'sini Seçin", silinecek_id_listesi)
                secilen_kayit_detay = filtreli_df[filtreli_df["ID"] == secilen_sil_id]
                
                if not secilen_kayit_detay.empty:
                    tutar_val = float(secilen_kayit_detay['Tutar'].iloc[0])
                    kalem_val = str(secilen_kayit_detay['Kalem'].iloc[0])
                    detay_val = str(secilen_kayit_detay['Detay'].iloc[0])
                    st.info(f"Seçilen Kayıt: **{kalem_val}** - **{tutar_val:,.2f} TL** ({detay_val})")

            with col_sil_buton:
                st.write(""); st.write("")
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
