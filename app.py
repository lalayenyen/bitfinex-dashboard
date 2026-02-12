import streamlit as st
import ccxt
import time
import pandas as pd

# ==========================================
# 設定區
# ==========================================
SEARCH_CAP = 3000000 
st.set_page_config(page_title="Bitfinex 智慧戰情室 V8.3", page_icon="💰", layout="wide")

@st.cache_resource
def init_exchange():
    return ccxt.bitfinex({'timeout': 20000, 'enableRateLimit': True})

bfx = init_exchange()

def get_market_data(symbol):
    try:
        # 1. 抓掛單簿
        raw_book = bfx.public_get_book_symbol_precision({'symbol': symbol, 'precision': 'P0', 'len': 100})
        asks = [{'利率': float(item[0]), '掛單量': float(item[3])} for item in raw_book if float(item[3]) > 0]
        asks.sort(key=lambda x: x['利率'])
        
        # 2. 抓 Ticker (修正負值與顯示倍數問題)
        ticker = bfx.public_get_ticker_symbol({'symbol': symbol})
        # Bitfinex v2 Ticker: [FRR, BID, ..., 24H_HIGH, 24H_LOW]
        # 注意：Bitfinex 原始數據是小數點格式 (如 0.0004)，不需要在抓取時乘 100
        frr = abs(float(ticker[0]))
        h24_high = abs(float(ticker[8]))
        h24_low = abs(float(ticker[9]))
        h24_avg = (h24_high + h24_low) / 2
        
        return asks, frr, h24_avg, h24_high
    except Exception as e:
        return [], 0, 0, 0

def analyze_logic(asks, frr, h24_avg, h24_high):
    if not asks: return None
    df = pd.DataFrame(asks)
    df['累積量'] = df['掛單量'].cumsum()
    avg_vol = df['掛單量'].mean()
    
    # 氛圍判斷
    if frr > h24_high * 0.9: sentiment, color = "🔥🔥 極度貪婪 (暴利期)", "#ff4b4b"
    elif frr > h24_avg * 1.1: sentiment, color = "🔥 市場火熱 (高於均價)", "#ffa500"
    elif frr < h24_avg * 0.9: sentiment, color = "🧊 市場冷清 (低於均價)", "#1c83e1"
    else: sentiment, color = "☁️ 歲月靜好 (和平時期)", "#09ab3b"

    # 策略計算
    top_walls = df.nlargest(3, '掛單量').sort_values('利率')
    rate_a = next((x['利率'] for x in asks if x['掛單量'] > avg_vol * 5), asks[0]['利率'])
    rate_b = next((x['利率'] for x, c in zip(asks, df['累積量']) if c >= SEARCH_CAP), asks[-1]['利率'])
    rate_c = next((x['利率'] for x in asks if abs(x['利率']*10000 - round(x['利率']*10000)) < 0.05), None)

    # 階梯建議
    l1 = frr
    l2 = max(top_walls.iloc[0]['利率'] - 0.00000001, frr)
    l3 = max(h24_high, l2 * 1.3)
    
    return {
        'frr': frr, 'l1': l1, 'l2': l2, 'l3': l3,
        'sentiment': sentiment, 'color': color,
        'h24_avg': h24_avg, 'h24_high': h24_high,
        'top_walls': top_walls, 'full_df': df,
        'strats': {'動態平均': rate_a, '深度累積': rate_b, '心理關卡': rate_c}
    }

def display_column(col, title, symbol):
    with col:
        st.header(title)
        asks, frr, h24_avg, h24_high = get_market_data(symbol)
        if asks:
            res = analyze_logic(asks, frr, h24_avg, h24_high)
            
            # 1. 氛圍與指標 (修正顯示倍數)
            st.markdown(f"""<div style="padding:15px; border-radius:10px; background-color:#f8f9fb; border-left: 5px solid {res['color']}; margin-bottom:20px;">
                <h3 style="margin:0; color:{res['color']}">{res['sentiment']}</h3>
                <code style="color:#666">和平基準: {res['h24_avg']*100:.4f}% | 24h最高: {res['h24_high']*100:.4f}%</code>
            </div>""", unsafe_allow_html=True)
            
            m1, m2, m3 = st.columns(3)
            m1.metric("1.保守 (30%)", f"{res['l1']*100:.4f}%", "FRR")
            m2.metric("2.穩健 (30%)", f"{res['l2']*100:.4f}%", f"年{res['l2']*36500:.1f}%")
            m3.metric("3.釣魚 (40%)", f"{res['l3']*100:.4f}%", "暴擊")

            # 2. 分析與牆
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("🔍 策略分析")
                for k, v in res['strats'].items():
                    st.write(f"**{k}:** {v*100:.4f}%" if v else f"**{k}:** 無訊號")
            with c2:
                st.subheader("🧱 三大資金牆")
                for _, r in res['top_walls'].iterrows():
                    st.write(f"🚩 {r['利率']*100:.4f}% ({r['掛單量']/1000:.1f}K)")

            # 3. 圖表 (修正畫法，避免 TypeError)
            st.subheader("🌊 資金深度分佈")
            chart_df = res['full_df'].head(20).copy()
            # 建立一個乾淨的繪圖用 DataFrame
            plot_data = pd.DataFrame({
                '利率(%)': chart_df['利率'] * 100,
                '掛單量': chart_df['掛單量']
            }).set_index('利率(%)')
            st.bar_chart(plot_data, color='#00d4ff')

            # 4. 詳細清單
            st.subheader("📊 詳細掛單清單 (Top 10)")
            list_df = res['full_df'].head(10).copy()
            list_df['年化'] = (list_df['利率']*36500).map('{:.2f}%'.format)
            list_df['利率(%)'] = (list_df['利率']*100).map('{:.4f}%'.format)
            list_df['金額'] = list_df['掛單量'].map('{:,.0f}'.format)
            st.table(list_df[['利率(%)', '年化', '金額']])
        else:
            st.warning("等待 API 回傳數據...")

# ==========================================
# 主介面
# ==========================================
st.title("💰 Bitfinex 智慧戰情室 V8.3")
st.caption(f"最後更新: {time.strftime('%H:%M:%S')} | 修復畫圖錯誤與負值")
col_a, col_b = st.columns(2)
display_column(col_a, "🇺🇸 USD (美金)", 'fUSD')
display_column(col_b, "₮ USDT (泰達幣)", 'fUST')
time.sleep(10); st.rerun()