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
        print("Haftalık Telegram bildirimi gönderildi.")
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

# --- 4. TARAMA MOTORU (CANLI HAFTALIK TARAMA) ---
symbols = get_bist100_symbols()
al_listesi = []
sat_listesi = []

for symbol in symbols:
    try:
        # Günlük veriyi çekip Cuma günü ile biten haftalık barlara birleştiriyoruz
        df_daily = yf.download(symbol, period="2y", interval="1d", auto_adjust=False, progress=False)
        if len(df_daily) < 40:
            continue
            
        if isinstance(df_daily.columns, pd.MultiIndex):
            df_daily.columns = df_daily.columns.get_level_values(0)

        data = df_daily.resample('W-FRI').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()

        if len(data) < 20:
            continue

        zl_cl, zl_ha = calculate_skaradag(data)

        # prev: Geçen haftanın kapanmış barı
        # curr: İçinde bulunduğumuz haftanın anlık gün sonu kapanış değeri
        prev_cl = float(zl_cl.iloc[-2])
        curr_cl = float(zl_cl.iloc[-1])
        prev_ha = float(zl_ha.iloc[-2])
        curr_ha = float(zl_ha.iloc[-1])

        clean_symbol = symbol.replace(".IS", "")

        diff_prev = prev_cl - prev_ha
        diff_curr = curr_cl - curr_ha

        # CANLI HAFTA İÇİNDE İLK DEFA TAZE KESİŞİM YAPANLAR
        is_new_buy = (diff_prev <= 0) and (diff_curr > 0)
        is_new_sell = (diff_prev >= 0) and (diff_curr < 0)

        if is_new_buy:
            al_listesi.append(clean_symbol)
        elif is_new_sell:
            sat_listesi.append(clean_symbol)

    except Exception as e:
        print(f"{symbol} hata: {e}")

# --- 5. TELEGRAM MESAJ FORMATI VE GÖNDERİMİ ---
al_str = ", ".join(al_listesi) if al_listesi else "Yok"
sat_str = ", ".join(sat_listesi) if sat_listesi else "Yok"

message = (
    "📊 *CANLI HAFTALIK SKARADAG BİST TARAMASI (18:45)*\n"
    "_(Bugün İtibarıyla Haftalık Kesişim Verenler)_\n\n"
    f"🟢 *HAFTALIK AL Verenler ({len(al_listesi)}):*\n`{al_str}`\n\n"
    f"🔴 *HAFTALIK SAT Verenler ({len(sat_listesi)}):*\n`{sat_str}`"
)

send_telegram_message(message)
