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
        print("Aylık Telegram bildirimi gönderildi.")
    except Exception as e:
        print(f"Telegram mesajı gönderilirken hata: {e}")

# --- 2. TRADINGVIEW BİREBİR SKARADAG HESAPLAMASI ---
def calculate_tema(series, length=16):
    ema1 = series.ewm(span=length, adjust=False).mean()
    ema2 = ema1.ewm(span=length, adjust=False).mean()
    ema3 = ema2.ewm(span=length, adjust=False).mean()
    return 3 * (ema1 - ema2) + ema3

def calculate_skaradag(df, avg1=16, avg2=16):
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    tma1_1 = calculate_tema(typical_price, avg1)
    tma2_1 = calculate_tema(tma1_1, avg1)
    zl_cl = 2 * tma1_1 - tma2_1

    o = df['Open'].values
    h = df['High'].values
    l = df['Low'].values
    c = df['Close'].values
    n = len(df)

    ha_close = (o + h + l + c) / 4.0
    ha_open = np.zeros(n)
    ha_open[0] = (o[0] + c[0]) / 2.0

    for i in range(1, n):
        ha_open[i] = (ha_open[i-1] + ha_close[i-1]) / 2.0

    ha_high = np.maximum(h, np.maximum(ha_open, ha_close))
    ha_low = np.minimum(l, np.minimum(ha_open, ha_close))
    
    ha_c_series = pd.Series((ha_close + ha_open + ha_high + ha_low) / 4.0, index=df.index)

    tma1_2 = calculate_tema(ha_c_series, avg2)
    tma2_2 = calculate_tema(tma1_2, avg2)
    zl_ha = 2 * tma1_2 - tma2_2

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

# --- 4. TARAMA MOTORU (MÜKEMMEL TAZE KESİŞİM FİLTRESİ) ---
symbols = get_bist100_symbols()
al_listesi = []
sat_listesi = []

for symbol in symbols:
    try:
        df_daily = yf.download(symbol, period="5y", interval="1d", auto_adjust=False, progress=False)
        if len(df_daily) < 100:
            continue
            
        if isinstance(df_daily.columns, pd.MultiIndex):
            df_daily.columns = df_daily.columns.get_level_values(0)

        # Günlük veriyi Aylık (Month-End) barlara birleştiriyoruz
        data = df_daily.resample('ME').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()

        # Henüz tamamlanmamış içinde bulunduğumuz ayı dışarıda bırakıyoruz
        if len(data) > 1:
            data = data.iloc[:-1]

        if len(data) < 20:
            continue

        zl_cl, zl_ha = calculate_skaradag(data)

        # TAZE KESİŞİM MATEMATİĞİ (CROSSOVER / CROSSUNDER)
        # Önceki bar (t-1) ve Şimdiki bar (t)
        zl_cl_prev = zl_cl.shift(1)
        zl_ha_prev = zl_ha.shift(1)

        # Sadece son tamamlanan barda gerçekleşen taze kırılım
        buy_cross = (zl_cl_prev <= zl_ha_prev) & (zl_cl > zl_ha)
        sell_cross = (zl_cl_prev >= zl_ha_prev) & (zl_cl < zl_ha)

        clean_symbol = symbol.replace(".IS", "")

        if buy_cross.iloc[-1]:
            al_listesi.append(clean_symbol)
        elif sell_cross.iloc[-1]:
            sat_listesi.append(clean_symbol)

    except Exception as e:
        print(f"{symbol} hata: {e}")

# --- 5. TELEGRAM MESAJ FORMATI VE GÖNDERİMİ ---
al_str = ", ".join(al_listesi) if al_listesi else "Yok"
sat_str = ", ".join(sat_listesi) if sat_listesi else "Yok"

message = (
    "📅 *AYLIK SKARADAG BİST TARAMASI*\n"
    "_(Sadece Sinyalin Geldiği İlk Bar - Taze Kesişim)_\n\n"
    f"🟢 *AYLIK AL Verenler ({len(al_listesi)}):*\n`{al_str}`\n\n"
    f"🔴 *AYLIK SAT Verenler ({len(sat_listesi)}):*\n`{sat_str}`"
)

send_telegram_message(message)
