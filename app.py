import streamlit as st
import ccxt
import time
import pandas as pd

# ==========================================
# 設定區
# ==========================================
SEARCH_CAP_USD = 3000000 
SEARCH_CAP_USDT = 3000000

st.set_page_config(page_title="Bitfinex 智慧戰情室 (全功能穩定版)", page_icon="💰", layout="wide")

# ==========================================
# 初始化
# ==========================================
@st.cache_resource
def init_exchange():
    return ccxt.bitfinex({'timeout': 20000, 'enableRateLimit': True})

bfx = init_exchange()

def get_market_data(symbol):
    try:
        # 1. 抓掛單簿
        raw_book = bfx.public_get_book_symbol_precision({'symbol': symbol, 'precision': 'P0', 'len': 100})
        asks = []
        for item in raw_book:
            if float(item[3]) > 0:
                asks.append({'利率': float(item[0]), '掛單量': float(item[3])})
        asks.sort(key=lambda x: x['利率'])
        
        # 2. 抓 Ticker (包含當前 FRR 與 24h 數據)
        # v2 Ticker: [FRR, BID, ..., 24H_HIGH, 24H_LOW, ...]
        ticker = bfx.public_get_ticker_symbol({'symbol': symbol})
        frr = float(ticker[0])
        h24_high = float(ticker[8]) # 24h 最高
        h24_low = float(ticker[9])  # 24h 最低
        h24_avg = (h24_high + h24_low) / 2 # 模擬和平基準
        
        return asks, frr, h24_avg, h24_high
    except Exception as e:
        return [], 0, 0, 0

def analyze_logic(asks, frr, search_cap, h24_avg, h24_high):
    if not asks: return None
    
    df = pd.DataFrame(asks)
    df['累積量'] = df['掛單量'].cumsum()
    avg_vol = df['掛單量'].mean()
    
    # --- A. 市場氛圍 ---
    if frr > h24_high * 0.95:
        sentiment, color = "🔥🔥 極度貪婪 (暴利期)", "red"
    elif frr > h24_avg * 1.1:
        sentiment, color = "🔥 市場火熱 (高於均價)", "orange"
    elif frr < h24_avg * 0.9:
        sentiment, color = "🧊 市場冷清 (低於均價)", "blue"
    else:
        sentiment, color = "☁️ 歲月靜好 (和平時期)", "green"

    # --- B. 前三大資金牆 ---
    top_walls = df.nlargest(3, '掛單量').sort_values('利率')

    # --- C. 三大策略 (理論) ---
    rate_a = next((x['利率'] for x in asks if x['掛單量'] > avg_vol * 5), None)
    rate_b = next((x['利率'] for x, c in zip(asks, df['累積量']) if c >= df['掛單量'].sum() * 0.05), None)
    rate_c = next((x['利率'] for x in asks if abs(x['利率']*10000 - round(x['利率']*10000)) < 0.05), None)

    # --- D. 階梯建議 (實戰) ---
    l1 = frr
    biggest_wall_rate = df.nlargest(1, '掛單量').iloc[0]['利率']
    l2 = max(biggest_wall_rate - 0.00000001, frr)
    l3 = max(h24_high, l2 * 1.3) # 聰明釣魚：參考 24h 最高價
    
    return {
        'frr': frr, 'l1': l1, 'l2': l2, 'l3': l3,
        'sentiment': sentiment, 'color': color,
        'h24_avg': h24_avg, 'h24_high': h24_high,
        'top_walls': top_walls, 'full_df': df,
        'strats': {'動態平均': rate_a, '深度累積': rate_b, '心理關卡': rate_c}
    }

def display_column(col, title, symbol, search_cap):
    with col:
        st.header(title)
        asks, frr, h24_avg, h24_high = get_market_data(symbol)
        
        if asks:
            res = analyze_logic(asks, frr, search_cap, h24_avg, h24_high)
            
            # 1. 氛圍儀表板
            st.markdown(f"""<div style="padding:10px; border-radius:10px; background-color:#f0f2f6; border-left: 5px solid {res['color']}">
                <h3 style="margin:0; color:{res['color']}">{res['sentiment']}</h3>
                <small>和平基準: {res['h24_avg']*100:.4f}% | 24h最高: {res['h24_high']*100:.4f}%</small>
            </div>""", unsafe_allow_html=True)
            
            # 2. 階梯建議
            st.write("")
            m1, m2, m3 = st.columns(3)
            m1.metric("1.保守 (30%)", f"{res['l1']*100:.4f}%", "FRR")
            m2.metric("2.穩健 (30%)", f"{res['l2']*100:.4f}%", f"年{res['l2']*36500:.1f}%")
            m3.metric("3.釣魚 (40%)", f"{res['l3']*100:.4f}%", "暴擊")

            # 3. 三大策略與資金牆 (並排)
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("🔍 策略分析")
                for k, v in res['strats'].items():
                    st.write(f"**{k}:** {v*100:.4f}%" if v else f"**{k}:** 無訊號")
            with c2:
                st.subheader("🧱 三大資金牆")
                for _, r in res['top_walls'].iterrows():
                    st.write(f"🚩 {r['利率']*100:.4f}% ({r['掛單量']/1000:.1f}K)")

            # 4. 深度分布圖
            st.subheader("🌊 資金深度分佈")
            chart_data = res['full_df'].head(30).copy()
            chart_data['利率標籤'] = (chart_data['利率']*100).map('{:.4f}%'.format)
            st.bar_chart(chart_data, x='利率標籤', y='掛單量', color='#00d4ff')
        else:
            st.warning("數據讀取中...")

# ==========================================
# 主介面
# ==========================================
st.title("💰 Bitfinex 智慧戰情室 V8.1 (全功能穩定版)")
c1, col2 = st.columns(2)
display_column(c1, "🇺🇸 USD (美金)", 'fUSD', SEARCH_CAP_USD)
display_column(col2, "₮ USDT (泰達幣)", 'fUST', SEARCH_CAP_USDT)
time.sleep(10); st.rerun()