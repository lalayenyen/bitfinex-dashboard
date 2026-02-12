import streamlit as st
import ccxt
import time
import pandas as pd

# ==========================================
# V9.0 終極校正版：修復百分比異常與數據偏移
# ==========================================
st.set_page_config(page_title="Bitfinex 智慧戰情室 V9.0", page_icon="💰", layout="wide")

@st.cache_resource
def init_exchange():
    return ccxt.bitfinex({'timeout': 20000, 'enableRateLimit': True})

bfx = init_exchange()

# 使用快取減少 API 請求壓力，解決「數據讀取中」問題
@st.cache_data(ttl=10)
def fetch_safe_data(symbol):
    try:
        # 1. 抓取標準化 Ticker
        ticker = bfx.fetch_ticker(symbol)
        
        # 強制校正單位函數
        def sanitize(val):
            if val is None: return 0.0
            # 如果抓到的數字大於 1 (例如 94)，通常是 API 回傳單位與預期不符，強制校正
            if val > 1: return val / 10000
            return val

        frr = sanitize(ticker['last'])
        h24_high = sanitize(ticker['high'])
        h24_low = sanitize(ticker['low'])
        h24_avg = (h24_high + h24_low) / 2

        # 2. 抓取掛單簿
        raw_book = bfx.public_get_book_symbol_precision({'symbol': symbol, 'precision': 'P0', 'len': 50})
        asks = [{'利率': float(item[0]), '掛單量': float(item[3])} for item in raw_book if float(item[3]) > 0]
        asks.sort(key=lambda x: x['利率'])
        
        return asks, frr, h24_avg, h24_high
    except Exception as e:
        return None, 0, 0, 0

def analyze_logic(asks, frr, h24_avg, h24_high):
    df = pd.DataFrame(asks)
    df['累積量'] = df['掛單量'].cumsum()
    avg_vol = df['掛單量'].mean()
    
    # 1. 氛圍判斷 (基準錨點修正)
    if frr >= h24_high * 0.98: sentiment, color = "🔥🔥 極度貪婪 (暴利期)", "#ff4b4b"
    elif frr >= h24_avg * 1.05: sentiment, color = "🔥 市場火熱 (高於均價)", "#ffa500"
    elif frr <= h24_avg * 0.95: sentiment, color = "🧊 市場冷清 (低於均價)", "#1c83e1"
    else: sentiment, color = "☁️ 歲月靜好 (和平時期)", "#09ab3b"

    # 2. 三大策略理論值
    rate_a = next((x['利率'] for x in asks if x['掛單量'] > avg_vol * 5), asks[0]['利率'])
    rate_b = next((x['利率'] for x, c in zip(asks, df['累積量']) if c >= 3000000), asks[-1]['利率'])
    rate_c = next((x['利率'] for x in asks if abs(x['利率']*10000 - round(x['利率']*10000)) < 0.05), None)

    # 3. 高勝率牆與階梯建議
    valid_walls = df[df['利率'] >= frr]
    best_wall = valid_walls.loc[valid_walls['掛單量'].idxmax()] if not valid_walls.empty else df.iloc[0]
    
    l1 = frr
    l2 = max(best_wall['利率'] - 0.00000001, frr)
    l3 = max(h24_high, l2 * 1.3)

    return {
        'frr': frr, 'l1': l1, 'l2': l2, 'l3': l3,
        'sentiment': sentiment, 'color': color,
        'h24_avg': h24_avg, 'h24_high': h24_high,
        'best_wall': best_wall, 'full_df': df,
        'strats': {'動態平均': rate_a, '深度累積': rate_b, '心理關卡': rate_c}
    }

def display_column(col, title, symbol):
    with col:
        st.header(title)
        asks, frr, h24_avg, h24_high = fetch_safe_data(symbol)
        
        if asks:
            res = analyze_logic(asks, frr, h24_avg, h24_high)
            
            # --- 1. 市場氛圍 ---
            st.markdown(f"""<div style="padding:15px; border-radius:10px; background-color:#f8f9fb; border-left: 5px solid {res['color']};">
                <h3 style="margin:0; color:{res['color']}">{res['sentiment']}</h3>
                <div style="display:flex; justify-content:space-between; margin-top:10px; font-family:monospace;">
                    <span>🕊️ 基準: {res['h24_avg']*100:.4f}%</span>
                    <span>🌊 24H高: {res['h24_high']*100:.4f}%</span>
                </div>
            </div>""", unsafe_allow_html=True)
            
            # --- 2. 核心指標 ---
            st.write("")
            m1, m2, m3 = st.columns(3)
            m1.metric("1.保守 (30%)", f"{res['l1']*100:.4f}%", "FRR")
            m2.metric("2.高勝率牆", f"{res['l2']*100:.4f}%", f"年{res['l2']*36500:.1f}%")
            m3.metric("3.智慧釣魚", f"{res['l3']*100:.4f}%", "插針目標")

            # --- 3. 智慧分析文字 ---
            st.info(f"💡 **高勝率分析**：目前市場最強牆位於 **{res['best_wall']['利率']*100:.4f}%**。已過濾低於基準利率之無效阻力。")
            
            # --- 4. 策略與資金牆並列 ---
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("🔍 策略分析")
                for k, v in res['strats'].items():
                    st.write(f"**{k}:** {v*100:.4f}%" if v else f"**{k}:** 無訊號")
            with c2:
                st.subheader("🧱 三大資金牆")
                top_3 = res['full_df'].nlargest(3, '掛單量').sort_values('利率')
                for _, r in top_3.iterrows():
                    st.write(f"🚩 {r['利率']*100:.4f}% ({r['掛單量']/1000:.1f}K)")

            # --- 5. 深度分佈圖 ---
            st.subheader("🌊 資金深度分佈")
            chart_df = res['full_df'].head(20).copy()
            chart_df['利率(%)'] = chart_df['利率'] * 100
            st.bar_chart(chart_df.set_index('利率(%)')['掛單量'], color='#00d4ff')

            # --- 6. 掛單建議表格 ---
            st.subheader("📋 執行建議方案")
            plan_df = pd.DataFrame([
                {"階段": "1. 保守", "分配": "30%", "利率": f"{res['l1']*100:.5f}%", "年化": f"{res['l1']*36500:.2f}%"},
                {"階段": "2. 穩健", "分配": "30%", "利率": f"{res['l2']*100:.5f}%", "年化": f"{res['l2']*36500:.2f}%"},
                {"階段": "3. 釣魚", "分配": "40%", "利率": f"{res['l3']*100:.5f}%", "年化": f"{res['l3']*36500:.2f}%"}
            ])
            st.table(plan_df)

            # --- 7. 詳細清單 (Top 10) ---
            st.subheader("📊 詳細掛單清單")
            list_df = res['full_df'].head(10).copy()
            list_df['利率(%)'] = (list_df['利率']*100).map('{:.4f}%'.format)
            list_df['年化'] = (list_df['利率']*36500).map('{:.2f}%'.format)
            list_df['金額'] = list_df['掛單量'].map('{:,.0f}'.format)
            st.table(list_df[['利率(%)', '年化', '金額']])
            
        else:
            st.warning("數據連接中...")

# ==========================================
# 主介面
# ==========================================
st.title("💰 Bitfinex 智慧戰情室 V9.0")
col_a, col_b = st.columns(2)
display_column(col_a, "🇺🇸 USD (美金)", 'fUSD')
display_column(col_b, "₮ USDT (泰達幣)", 'fUST')
time.sleep(10); st.rerun()