import time
from dhanhq import dhanhq
from flask import Flask
from threading import Thread

# ====================================================
# SERVER KEEP-ALIVE CONFIGURATION (24/7 RUNNING)
# ====================================================
app = Flask('')

@app.route('/')
def home():
    return "🔥 धन ट्रेडिंग बॉट 24x7 सक्रिय और सुरक्षित रूप से चल रहा है!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# सर्वर को एक्टिव रखने के लिए इसे शुरू करें
keep_alive()

# ====================================================
# DHAN BOT MAIN CODE START
# ====================================================

# 1. अपनी धन (Dhan Sandbox) की चाबियां यहाँ भरें
CLIENT_ID = "2606182708"  # आपकी असली आईडी
ACCESS_TOKEN = "YOUR_DHAN_SANDBOX_ACCESS_TOKEN" # टोकन को अभी ऐसे ही रहने दें (सुरक्षा के लिए)

dhan = dhanhq(CLIENT_ID, ACCESS_TOKEN, env="sandbox")
print("🔥 परफेक्ट ट्रेलिंग रणनीति बॉट सक्रिय है... धन सैंडबॉक्स कनेक्टेड।")

# 2. कड़े नियम पैरामीटर्स (आपके इनपुट के अनुसार)
LOT_SIZE = 15           # बैंक निफ्टी का फिक्स लॉट साइज (15 क्वांटिटी)
INITIAL_SL_DIST = 100   # शुरुआत से फिक्स रहने वाली स्टॉप लॉस दूरी (100 पॉइंट)

# पोजीशन ट्रैकिंग वेरिएबल्स
position_active = False
position_type = "" # "CE" या "PE"
entry_price = 0
trailing_sl = 0
max_reached_price = 0
min_reached_price = 0
option_symbol = ""

# प्रति घंटा कंट्रोल वेरिएबल्स
hourly_trade_count = 0
current_hour_tag = ""

def get_monthly_itm_strike(spot_price, option_type):
    """100-190 पॉइंट दूर ITM स्ट्राइक निर्धारित करना"""
    base_strike = round(spot_price / 100) * 100
    if option_type == "CE":
        return base_strike - 100  # 100 पॉइंट इन-द-मनी (Call)
    else:
        return base_strike + 100  # 100 पॉइंट इन-द-मनी (Put)

# 3. मुख्य लाइव लूप (हर सेकंड भाव जाँचेगा)
while True:
    try:
        # बैंक निफ्टी स्पॉट का लाइव भाव (Security ID: 25)
        market_data = dhan.get_ltp_data(security_id="25", exchange_segment="NSE_INDEX")
        spot_price = market_data.get('data', {}).get('lastPrice', 0)
        
        if spot_price == 0:
            time.sleep(1)
            continue

        # --- ऐतिहासिक कैंडल डेटा सिमुलेशन ---
        prev_candle_type = "GREEN"
        prev_candle_high = 54100        
        prev_candle_low = 53800         
        
        current_candle_open = 54000 
        current_candle_high = 54020
        current_candle_low = 53950      
        minutes_since_candle_start = 15  
        this_hour_string = "10_AM"       

        # नए घंटे में ट्रेड काउंटर रीसेट करना
        if current_hour_tag != this_hour_string:
            current_hour_tag = this_hour_string
            hourly_trade_count = 0

        # ====================================================
        # भाग A: नई फ्रेश एंट्री ढूंढना (यदि कोई ट्रेड एक्टिव नहीं है)
        # ====================================================
        if not position_active and hourly_trade_count < 2:
            trigger_entry = False
            opt_type = "CE"

            # नियम 1: शुरुआती 50 मिनट के अंदर 'विक रिजेक्शन'
            if minutes_since_candle_start <= 50:
                if prev_candle_type == "GREEN":
                    opposite_move = current_candle_open - current_candle_low
                    if 30 <= opposite_move <= 90 and spot_price >= current_candle_open:
                        trigger_entry = True
                        opt_type = "CE"
                    elif opposite_move > 120 and spot_price >= (current_candle_open - 100):
                        trigger_entry = True
                        opt_type = "CE"
                elif prev_candle_type == "RED":
                    opposite_move = current_candle_high - current_candle_open
                    if 30 <= opposite_move <= 90 and spot_price <= current_candle_open:
                        trigger_entry = True
                        opt_type = "PE"
                    elif opposite_move > 120 and spot_price <= (current_candle_open + 100):
                        trigger_entry = True
                        opt_type = "PE"

            # नियम 2: 50 मिनट के बाद पिछली कैंडल का हाई/लो ब्रेकआउट
            else:
                if prev_candle_type == "GREEN" and spot_price > prev_candle_high:
                    trigger_entry = True
                    opt_type = "CE"
                elif prev_candle_type == "RED" and spot_price < prev_candle_low:
                    trigger_entry = True
                    opt_type = "PE"

            # आर्डर पंच करने का लॉजिक
            if trigger_entry:
                strike = get_monthly_itm_strike(spot_price, opt_type)
                option_symbol = f"BANKNIFTY MONTHLY {strike} {opt_type}"
                entry_price = spot_price
                position_type = opt_type
                position_active = True
                hourly_trade_count += 1
                
                if position_type == "CE":
                    trailing_sl = entry_price - INITIAL_SL_DIST
                    max_reached_price = entry_price
                else:
                    trailing_sl = entry_price + INITIAL_SL_DIST
                    min_reached_price = entry_price
                    
                print(f"🎯 नई एंट्री ट्रिगर: {option_symbol} | भाव: {entry_price}")

        # ====================================================
        # भाग B: एग्जिट और ट्रेलिंग स्टॉप लॉस लॉजिक (यदि पोजीशन एक्टिव है)
        # ====================================================
        elif position_active:
            if position_type == "CE":
                # ट्रेलिंग SL को ऊपर खिसकाना
                if spot_price > max_reached_price:
                    max_reached_price = spot_price
                    trailing_sl = max_reached_price - INITIAL_SL_DIST
                
                # SL हिट होने की जाँच
                if spot_price <= trailing_sl:
                    print(f"🛑 स्टॉप लॉस हिट (CE)! एग्जिट भाव: {spot_price}")
                    position_active = False

            elif position_type == "PE":
                # PE के लिए ट्रेलिंग SL को नीचे खिसकाना
                if spot_price < min_reached_price:
                    min_reached_price = spot_price
                    trailing_sl = min_reached_price + INITIAL_SL_DIST
                
                # SL हिट होने की जाँच
                if spot_price >= trailing_sl:
                    print(f"🛑 स्टॉप लॉस हिट (PE)! एग्जिट भाव: {spot_price}")
                    position_active = False

        time.sleep(1) # सर्वर लोड कम करने के लिए 1 सेकंड का ठहराव

    except Exception as e:
        print(f"❌ त्रुटि (Error) आई: {e}")
        time.sleep(5)
