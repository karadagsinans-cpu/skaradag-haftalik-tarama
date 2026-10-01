import os
import yfinance as yf
import pandas as pd
import numpy as np
import requests

# --- 1. TELEGRAM BİLDİRİM FONKSİYONU ---
def send_telegram_message(message):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        print("Telegram kimlik bilgileri bulunamadı, mesaj gönderilmedi.")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
        print("Aylık Telegram bildirimi başarıyla gönderildi.")
    except Exception as e:
        print(f"Telegram mesajı gönderilirken hata oluştu: {e}")

# --- 2. SKARADAG MATEMATİKSEL FONKSİYONLARI ---
def calculate_tema(series, length=16):
    ema1 = series.ewm(span=length, adjust=False).mean()
    ema2 = ema1.ewm(span=length, adjust=False).mean()
    ema3 = ema2.ewm(span=length, adjust=False).mean()
    return 3 * (ema1 - ema2) + ema3

def calculate_skaradag(df, avg1=16, avg2=16):
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    tma1_1 = calculate_tema(typical_price, avg1)
    tma2_1 = calculate_tema(tma1_1, avg1)
    diff1 = tma1_1 - tma2_1
    zl_cl = tma1_1 + diff1 

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

# --- 3. XU100 VE ENDEKS LİSTESİ ---
def get_bist100_symbols():
    try:
        url = "https://tr.wikipedia.org/wiki/BIST_100"
        tables = pd.read_html(url)
        df_bist = None
        for table in tables:
            if 'Kod' in table.columns or 'Simge' in table.columns:
                df_bist = table
                break
        col_name = 'Kod' if 'Kod' in df_bist.columns else 'Simge'
        symbols = [str(code).strip() + ".IS" for code in df_bist[col_name].dropna().tolist()]
    except Exception as e:
        symbols = ["THYAO.IS", "ASELS.IS", "GARAN.IS", "AKBNK.IS", "EREGL.IS", "TUPRS.IS", "BIMAS.IS", "KCHOL.IS", "SISE.IS", "SAHOL.IS"]

    endeksler = ["XU100.IS", "XU030.IS"]
    return endeksler + [s for s in symbols if s not in endeksler]

# --- 4. TARAMA MOTORU (AYLIK PERİYOT) ---
symbols = get_bist100_symbols()
al_listesi = []
sat_listesi = []

for symbol in symbols:
    try:
        # Periyot AYLIK (1mo) ve 5 Yıllık Veri Çekme
        data = yf.download(symbol, period="5y", interval="1mo", progress=False)
        if len(data) < 20:
            continue
        
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        zl_cl, zl_ha = calculate_skaradag(data)

        prev_cl, curr_cl = zl_cl.iloc[-2], zl_cl.iloc[-1]
        prev_ha, curr_ha = zl_ha.iloc[-2], zl_ha.iloc[-1]

        clean_symbol = symbol.replace(".IS", "")

        if prev_cl <= prev_ha and curr_cl > curr_ha:
            al_listesi.append(clean_symbol)
        elif prev_cl >= prev_ha and curr_cl < curr_ha:
            sat_listesi.append(clean_symbol)

    except Exception as e:
        print(f"{symbol} hata: {e}")

# --- 5. TELEGRAM MESAJ FORMATI VE GÖNDERİMİ ---
al_str = ", ".join(al_listesi) if al_listesi else "Yok"
sat_str = ", ".join(sat_listesi) if sat_listesi else "Yok"

message = (
    "📅 *AYLIK SKARADAG BİST TARAMASI*\n"
    "_(Her Ayın 1'i Otomatik Raporu)_\n\n"
    f"🟢 *AYLIK AL Verenler ({len(al_listesi)}):*\n`{al_str}`\n\n"
    f"🔴 *AYLIK SAT Verenler ({len(sat_listesi)}):*\n`{sat_str}`"
)

send_telegram_message(message)
