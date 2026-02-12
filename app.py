import streamlit as st
import ccxt
import time
import pandas as pd

# ==========================================
# V9.6 APY 強化版：所有利率後方自動計算年化
# ==========================================
st.set_page_config(page_title="Bitfinex 智慧戰情室 V9.6", page_icon="💰", layout="wide")

@st.cache_resource
def init_exchange():
    return ccxt.bitfinex({'timeout': 20000, 'enableRateLimit': True})

bfx = init_exchange()

def get_hybrid_data(symbol):
    """嘗試抓取數據，並確保日利率與 APY 單位正確"""
    asks, frr, h24_avg, h24_high = [], 0, 0, 0
    try:
        ticker = bfx.public_get_ticker_symbol({'symbol': symbol})
        frr = abs(float(ticker[0]))
        h24_high = abs(float(ticker[8]))
        h24_low = abs(float(ticker[9]))
        h24_avg = (h24_high + h24_low) / 2
    except:
        pass

    try:
        raw_book = bfx.public_get_book_symbol_precision({'symbol': symbol, 'precision': 'P0', 'len': 100})
        asks = [{'利率': float(item[0]), '掛單量': float(item[3])} for item in raw_book if float(item[3]) > 0]
        asks.sort(key=lambda x: x['利率'])
        if frr == 0 and asks: frr = asks[0]['利率']
    except:
        pass
    return asks, frr, h24_avg, h24_high

def analyze_logic(asks, frr, h24_avg, h24_high):
    if not asks: return None
    df = pd.DataFrame(asks)
    df['累積量'] = df['掛單量'].cumsum()
    avg_vol = df['掛單量'].mean()
    
    # 1. 氛圍判斷
    if h24_high > 0:
        if frr >= h24_high * 0.95: sentiment, color = "🔥🔥 極度貪婪 (暴利期)", "#ff4b4b"
        elif frr >= h24_avg * 1.05: sentiment, color = "🔥 市場火熱 (高於均價)", "#ffa500"
        else: sentiment, color = "☁️ 歲月靜好 (和平時期)", "#09ab3b"
    else:
        sentiment, color = "📊 即時掛單簿模式", "#666"

    # 2. 核心指標計算
    valid_walls = df[df['利率'] >= frr]
    best_wall = valid_walls.loc[valid_walls['掛單量'].idxmax()] if not valid_walls.empty else df.iloc[0]
    l1 = frr
    l2 = max(best_wall['利率'] - 0.00000001, frr)
    l3 = h24_high if h24_high > 0 else l2 * 1.5
    
    # 策略分析數據
    rate_a = next((x['利率'] for x in asks if x['掛單量'] > avg_vol * 5), asks[0]['利率'])
    rate_b = next((x['利率'] for x, c in zip(asks, df['累積量']) if c >= 3000000), asks[-1]['利率'])

    return {
        'frr': frr, 'l1': l1, 'l2': l2, 'l3': l3,
        'sentiment': sentiment, 'color': color,
        'best_wall': best_wall, 'full_df': df,
        'h24_avg': h24_avg, 'h24_high': h24_high,
        'strats': {'動態平均': rate_a, '深度累積': rate_b}
    }

def display_column(col, title, symbol):
    with col:
        st.header(title)
        asks, frr, h24_avg, h24_high = get_hybrid_data(symbol)
        if asks:
            res = analyze_logic(asks, frr, h24_avg, h24_high)
            
            # --- 1. 氛圍方塊 (加入 APY 顯示) ---
            st.markdown(f"""<div style="padding:15px; border-radius:10px; background-color:#f8f9fb; border-left: 5px solid {res['color']}; margin-bottom:10px;">
                <h3 style="margin:0; color:{res['color']}">{res['sentiment']}</h3>
                <div style="display:flex; justify-content:space-between; margin-top:5px; font-family:monospace;">
                    <span><b>FRR:</b> {res['frr']*100:.4f}% (年{res['frr']*36500:.1f}%)</span>
                    <span>🌊 24h高: {res['h24_high']*100:.4f}% (年{res['h24_high']*36500:.1f}%)</span>
                </div>
            </div>""", unsafe_allow_html=True)
            
            # --- 2. 階梯指標 ---
            m1, m2, m3 = st.columns(3)
            m1.metric("1.保守 (FRR)", f"{res['l1']*100:.4f}%", f"年{res['l1']*36500:.1f}%")
            m2.metric("2.穩健 (牆前)", f"{res['l2']*100:.4f}%", f"年{res['l2']*36500:.1f}%")
            m3.metric("3.智慧釣魚", f"{res['l3']*100:.4f}%", f"年{res['l3']*36500:.1f}%")

            # --- 3. 智慧分析文字 ---
            st.info(f"💡 **穩健策略分析**：最大阻力位在 **{res['best_wall']['利率']*100:.4f}% (年{res['best_wall']['利率']*36500:.1f}%)**，建議掛單在此牆前一檔。")

            # --- 4. 策略分析與三大牆 ---
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("🔍 策略分析")
                for k, v in res['strats'].items():
                    st.write(f"**{k}:** {v*100:.4f}% (年{v*36500:.1f}%)")
            with c2:
                st.subheader("🧱 三大資金牆")
                top_walls = res['full_df'].nlargest(3, '掛單量').sort_values('利率')
                for _, r in top_walls.iterrows():
                    st.write(f"🚩 {r['利率']*100:.4f}% (年{r['利率']*36500:.1f}%) | {r['掛單量']/1000:.1f}K")

            # --- 5. 資金深度圖 ---
            st.subheader("🌊 資金深度分佈")
            chart_df = res['full_df'].head(20).copy()
            chart_df['利率標籤'] = (chart_df['利率']*100).map('{:.4f}%'.format)
            st.bar_chart(chart_df.set_index('利率標籤')['掛單量'], color='#00d4ff')

            # --- 6. 完整建議表格 ---
            st.subheader("📋 執行建議方案")
            plan_df = pd.DataFrame([
                {"階段": "1. 保守", "利率": f"{res['l1']*100:.5f}%", "年化(APY)": f"{res['l1']*36500:.2f}%"},
                {"階段": "2. 穩健", "利率": f"{res['l2']*100:.5f}%", "年化(APY)": f"{res['l2']*36500:.2f}%"},
                {"階段": "3. 釣魚", "利率": f"{res['l3']*100:.5f}%", "年化(APY)": f"{res['l3']*36500:.2f}%"}
            ])
            st.table(plan_df)
        else:
            st.warning("數據連接中...")

st.title("💰 Bitfinex 智慧戰情室 V9.6 (APY 強化版)")
col_a, col_b = st.columns(2)
display_column(col_a, "🇺🇸 USD (美金)", 'fUSD')
display_column(col_b, "₮ USDT (泰達幣)", 'fUST')
time.sleep(20); st.rerun()