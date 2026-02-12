import streamlit as st
import ccxt
import time
import pandas as pd

# ==========================================
# V9.0 本地穩健版：包含所有實戰分析模塊
# ==========================================
st.set_page_config(page_title="Bitfinex 智慧戰情室 V9.0", page_icon="💰", layout="wide")

@st.cache_resource
def init_exchange():
    return ccxt.bitfinex({'timeout': 20000, 'enableRateLimit': True})

bfx = init_exchange()

# 本地執行不需快取太久，設定 5 秒更新一次即可
@st.cache_data(ttl=5)
def fetch_safe_data(symbol):
    try:
        # 1. 抓取標準化 Ticker
        ticker = bfx.fetch_ticker(symbol)
        
        # 強制校正單位函數：防止出現 94% 這種異常值
        def sanitize(val):
            if val is None: return 0.0
            temp_val = abs(float(val))
            # 如果日利率 > 0.5% (年化 180%)，通常是單位錯誤，自動縮放
            if temp_val > 0.005: return temp_val / 100
            return temp_val

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
    
    # 1. 市場氛圍分析
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
            
            # --- 1. 市場氛圍與量化指標 ---
            st.markdown(f"""<div style="padding:15px; border-radius:10px; background-color:#f8f9fb; border-left: 5px solid {res['color']};">
                <h3 style="margin:0; color:{res['color']}">{res['sentiment']}</h3>
                <div style="display:flex; justify-content:space-between; margin-top:10px; font-family:monospace;">
                    <span>🕊️ 和平基準: {res['h24_avg']*100:.4f}%</span>
                    <span>🌊 24H波濤: {res['h24_high']*100:.4f}%</span>
                </div>
            </div>""", unsafe_allow_html=True)
            
            # --- 2. 智慧階梯指標 ---
            st.write("")
            m1, m2, m3 = st.columns(3)
            m1.metric("1.保守 (30%)", f"{res['l1']*100:.4f}%", "FRR")
            m2.metric("2.高勝率牆", f"{res['l2']*100:.4f}%", f"年{res['l2']*36500:.1f}%")
            m3.metric("3.智慧釣魚", f"{res['l3']*100:.4f}%", "插針獲利")

            st.info(f"💡 **高勝率分析**：目前市場最強阻力位於 **{res['best_wall']['利率']*100:.4f}%**。建議掛單在此牆前一檔以確保成交。")
            
            # --- 3. 策略分析與三大牆並列 ---
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

            # --- 4. 資金深度分佈圖 ---
            st.subheader("🌊 資金深度分佈")
            chart_df = res['full_df'].head(20).copy()
            chart_df['利率(%)'] = chart_df['利率'] * 100
            st.bar_chart(chart_df.set_index('利率(%)')['掛單量'], color='#00d4ff')

            # --- 5. 執行方案建議表格 ---
            st.subheader("📋 階梯掛單建議方案")
            plan_df = pd.DataFrame([
                {"階段": "1. 保守", "分配": "30%", "利率": f"{res['l1']*100:.5f}%", "年化": f"{res['l1']*36500:.2f}%"},
                {"階段": "2. 穩健", "分配": "30%", "利率": f"{res['l2']*100:.5f}%", "年化": f"{res['l2']*36500:.2f}%"},
                {"階段": "3. 釣魚", "分配": "40%", "利率": f"{res['l3']*100:.5f}%", "年化": f"{res['l3']*36500:.2f}%"}
            ])
            st.table(plan_df)

            # --- 6. 詳細掛單清單 (Top 10) ---
            st.subheader("📊 詳細掛單清單")
            list_df = res['full_df'].head(10).copy()
            list_df['利率(%)'] = (list_df['利率']*100).map('{:.4f}%'.format)
            list_df['年化'] = (list_df['利率']*36500).map('{:.2f}%'.format)
            list_df['金額'] = list_df['掛單量'].map('{:,.0f}'.format)
            st.table(list_df[['利率(%)', '年化', '金額']])
            
        else:
            st.warning("正在嘗試連線至 Bitfinex...")

# ==========================================
# 主介面
# ==========================================
st.title("💰 Bitfinex 智慧戰情室 V9.0 (本地版)")
col_a, col_b = st.columns(2)
display_column(col_a, "🇺🇸 USD (美金)", 'fUSD')
display_column(col_b, "₮ USDT (泰達幣)", 'fUST')
time.sleep(5); st.rerun()