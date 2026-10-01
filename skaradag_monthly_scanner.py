# --- 4. TARAMA MOTORU ---
symbols = get_bist100_symbols()
al_listesi = []
sat_listesi = []

first_day_of_current_month = pd.Timestamp(datetime.now().year, datetime.now().month, 1)

for symbol in symbols:
    try:
        data = yf.download(symbol, period="10y", interval="1mo", auto_adjust=False, progress=False)
        if len(data) < 30:
            continue
        
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        # Sadece bu aydan önce kapanmış olan tamamlanmış ayları alıyoruz
        data = data[data.index < first_day_of_current_month]

        if len(data) < 20:
            continue

        zl_cl, zl_ha = calculate_skaradag(data)

        prev_cl, curr_cl = zl_cl.iloc[-2], zl_cl.iloc[-1]
        prev_ha, curr_ha = zl_ha.iloc[-2], zl_ha.iloc[-1]

        clean_symbol = symbol.replace(".IS", "")

        # MİKRON DÜZEYDEKİ TEĞET GEÇİŞLERİ VE KÜSURAT SAPMALARINI ELENEN KESİN KESİŞİM
        # %0.1'lik (0.001) net kırılım marjı eklenmiştir
        diff_prev = prev_cl - prev_ha
        diff_curr = curr_cl - curr_ha

        # Önceki ay net aşağıda/yukarıda iken son ay net olarak üzerine çıkanlar
        is_new_buy = (diff_prev < -0.01) and (diff_curr > 0.01)
        is_new_sell = (diff_prev > 0.01) and (diff_curr < -0.01)

        if is_new_buy:
            al_listesi.append(clean_symbol)
        elif is_new_sell:
            sat_listesi.append(clean_symbol)

    except Exception as e:
        print(f"{symbol} hata: {e}")
