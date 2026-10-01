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
        print("ADX Telegram bildirimi gönderildi.")
    except Exception as e:
        print(f"Telegram mesajı gönderilirken hata: {e}")

# --- 2. TRADINGVIEW BİREBİR ADX VE DMI HESAPLAMASI ---
def calculate_adx(df, length=14, adx_smoothing=14):
    high = df['High']
    low = df['Low']
    close = df['Close']

    up = high.diff()
    down = -low.diff()

    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    tr_smooth = tr.ewm(alpha=1/length, adjust=False).mean()
    plus_di = 100 * (pd.Series(plus_dm, index=df.index).ewm(alpha=1/length, adjust=False).mean() / tr_smooth)
    minus_di = 100 * (pd.Series(minus_dm, index=df.index).ewm(alpha=1/length, adjust=False).mean() / tr_smooth)

    sum_di = plus_di + minus_di
    sum_di = np.where(sum_di == 0, 1, sum_di)
    dx = 100 * (plus_di - minus_di).abs() / sum_di

    adx = pd.Series(dx, index=df.index).ewm(alpha=1/adx_smoothing, adjust=False).mean()
    return adx, plus_di, minus_di

# --- 3. BIST SYMBOLS ---
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

# --- 4. TARAMA MOTORU (GÜNLÜK ADX ERKEN PATLAMA & DOYUM) ---
symbols = get_bist100_symbols()
adx_patlama_listesi = []
adx_doyum_listesi = []

for symbol in symbols:
    try:
        data = yf.download(symbol, period="1y", interval="1d", auto_adjust=False, progress=False)
        if len(data) < 40:
            continue
            
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        adx, plus_di, minus_di = calculate_adx(data)

        prev_adx = float(adx.iloc[-2])
        curr_adx = float(adx.iloc[-1])
        curr_plus = float(plus_di.iloc[-1])
        curr_minus = float(minus_di.iloc[-1])

        clean_symbol = symbol.replace(".IS", "")

        # ADX Erken Patlama (ADX 20 seviyesini yukarı taze kestiğinde ve DI+ > DI- iken)
        is_adx_breakout = (prev_adx <= 20) and (curr_adx > 20) and (curr_plus > curr_minus)
        
        # ADX Doyum / Aşırı Trend (ADX 45 seviyesinin üzerine çıktığında)
        is_adx_extreme = (prev_adx <= 45) and (curr_adx > 45)

        if is_adx_breakout:
            adx_patlama_listesi.append(clean_symbol)
        if is_adx_extreme:
            adx_doyum_listesi.append(clean_symbol)

    except Exception as e:
        print(f"{symbol} hata: {e}")

al_str = ", ".join(adx_patlama_listesi) if adx_patlama_listesi else "Yok"
doyum_str = ", ".join(adx_doyum_listesi) if adx_doyum_listesi else "Yok"

message = (
    "🚀 *GÜNLÜK ADX STRATEJİ TARAMASI (18:45)*\n"
    "_(Erken Patlama ve Doyum Sinyalleri)_\n\n"
    f"🔥 *ADX Erken Patlama Verenler (20 Üstü - {len(adx_patlama_listesi)}):*\n`{al_str}`\n\n"
    f"⚠️ *ADX Doyum Noktasındakiler (45 Üstü - {len(adx_doyum_listesi)}):*\n`{doyum_str}`"
)

send_telegram_message(message)
