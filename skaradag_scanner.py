import yfinance as yf
import pandas as pd
import numpy as np
import requests

# --- 1. SKARADAG MATEMATİKSEL FONKSİYONLARI ---
def calculate_tema(series, length=16):
    ema1 = series.ewm(span=length, adjust=False).mean()
    ema2 = ema1.ewm(span=length, adjust=False).mean()
    ema3 = ema2.ewm(span=length, adjust=False).mean()
    return 3 * (ema1 - ema2) + ema3

def calculate_skaradag(df, avg1=16, avg2=16):
    # Skaradag1 (Typical Price Tabanlı Zero-Lag TEMA)
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    tma1_1 = calculate_tema(typical_price, avg1)
    tma2_1 = calculate_tema(tma1_1, avg1)
    diff1 = tma1_1 - tma2_1
    zl_cl = tma1_1 + diff1 

    # Skaradag2 (Heikin Ashi Tabanlı Zero-Lag TEMA)
    ha_open = pd.Series(index=df.index, dtype=float)
    ha_open.iloc[0] = (df['Open'].iloc[0] + df['High'].iloc[0] + df['Low'].iloc[0] + df['Close'].iloc[0]) / 4
    
    for i in range(1, len(df)):
        ha_open.iloc[i] = (ha_open.iloc[i-1] + ((df['Open'].iloc[i] + df['High'].iloc[i] + df['Low'].iloc[i] + df['Close'].iloc[i]) / 4)) / 2
        
    ha_c = ((df['Open'] + df['High'] + df['Low'] + df['Close']) / 4 + 
            ha_open + 
            np.maximum(df['High'], ha_open) + 
            np.minimum(df['Low'], ha_open)) / 4

    tma1_2 = calculate_tema(ha_c, avg2)
    tma2_2 = calculate_tema(tma1_2, avg2)
    diff2 = tma1_2 - tma2_2
    zl_ha = tma1_2 + diff2

    return zl_cl, zl_ha

# --- 2. XU100 HİSSE LİSTESİNİ OTOMATİK ÇEKME VE ENDEKSLERİ EKLEME ---
def get_bist100_symbols():
    try:
        url = "https://tr.wikipedia.org/wiki/BIST_100"
        tables = pd.read_html(url)
        
        # Wikipedia tablosundan sembolleri ayıklama
        df_bist = None
        for table in tables:
            if 'Kod' in table.columns or 'Simge' in table.columns:
                df_bist = table
                break
        
        col_name = 'Kod' if 'Kod' in df_bist.columns else 'Simge'
        symbols = [str(code).strip() + ".IS" for code in df_bist[col_name].dropna().tolist()]
    except Exception as e:
        print(f"Canlı BIST100 listesi çekilemedi, varsayılan liste kullanılıyor: {e}")
        symbols = ["THYAO.IS", "ASELS.IS", "GARAN.IS", "AKBNK.IS", "EREGL.IS", "TUPRS.IS", "BIMAS.IS", "KCHOL.IS", "SISE.IS", "SAHOL.IS"]

    # Endeksleri listenin başına ekliyoruz
    endeksler = ["XU100.IS", "XU030.IS"]
    all_symbols = endeksler + [s for s in symbols if s not in endeksler]
    return all_symbols

# --- 3. TARAMA MOTORU ---
symbols = get_bist100_symbols()
al_listesi = []
sat_listesi = []

print(f"Toplam {len(symbols)} sembol için Haftalık Skaradag Taraması Başlatılıyor...\n")

for symbol in symbols:
    try:
        data = yf.download(symbol, period="2y", interval="1wk", progress=False)
        if len(data) < 30:
            continue
        
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        zl_cl, zl_ha = calculate_skaradag(data)

        prev_cl, curr_cl = zl_cl.iloc[-2], zl_cl.iloc[-1]
        prev_ha, curr_ha = zl_ha.iloc[-2], zl_ha.iloc[-1]

        clean_symbol = symbol.replace(".IS", "")

        # AL Şartı: Skaradag1 (ZlCl) Skaradag2'yi (ZlHa) YUKARI KESTİ
        if prev_cl <= prev_ha and curr_cl > curr_ha:
            al_listesi.append(clean_symbol)

        # SAT Şartı: Skaradag1 (ZlCl) Skaradag2'yi (ZlHa) AŞAĞI KESTİ
        elif prev_cl >= prev_ha and curr_cl < curr_ha:
            sat_listesi.append(clean_symbol)

    except Exception as e:
        print(f"{symbol} taranırken hata: {e}")

# --- 4. SONUÇ RAPORU ---
print("="*50)
print(f"HAFTALIK AL VERENLER ({len(al_listesi)} Adet):")
print(", ".join(al_listesi) if al_listesi else "Yok")
print("="*50)
print(f"HAFTALIK SAT VERENLER ({len(sat_listesi)} Adet):")
print(", ".join(sat_listesi) if sat_listesi else "Yok")
print("="*50)
