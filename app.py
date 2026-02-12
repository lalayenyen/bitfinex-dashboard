import streamlit as st
import ccxt
import time
import pandas as pd

# ==========================================
# V9.7 修正版：徹底校正單位 + 強制渲染完整模塊
# ==========================================
st.set_page_config(page_title="Bitfinex 智慧戰情室 V9.7", page_icon="💰", layout="wide")

@st.cache_resource
def init_exchange():
    return ccxt.bitfinex({'timeout': 20000, 'enableRateLimit': True})

bfx = init_exchange()

def get_hybrid_data(symbol):
    asks, frr, h24_avg, h24_high = [], 0, 0, 0
    try:
        # 使用原始 API 獲取 Ticker
        ticker = bfx.public_get_ticker_symbol({'symbol': symbol})
        
        # 強效校正單位防呆
        def fix_unit(val):
            v = abs(float(val))
            # 若數值 > 0.005 (日利率 0.5%)，通常是單位偏移或抓到成交量，自動縮放
            while v > 0.005: v /= 100 
            return v

        frr = fix_unit(ticker[0])
        h24_high = fix_unit(ticker[8])
        h24_low = fix_unit(ticker[9])
        h24_avg = (h24_high + h24_low) / 2
    except: pass

    try:
        # 抓取掛單簿數據
        raw_book = bfx.public_get_book_symbol_precision({'symbol': symbol, 'precision': 'P0', 'len': 100})
        asks = [{'利率': float(item[0]), '掛單量': float(item[3])} for item in raw_book if float(item[3]) > 0]
        asks.sort(key=lambda x: x['利率'])
        if frr == 0 and asks: frr = asks[0]['利率']
    except: pass
    return asks, frr, h24_avg, h24_high

def display_column(col, title, symbol):
    with col:
        st.header(title)
        asks, frr, h24_avg, h24_high = get_hybrid_data(symbol)
        if asks:
            df = pd.DataFrame(asks)
            df['累積量'] = df['掛單量'].cumsum()
            
            # --- 1. 市場氛圍 ---
            color = "#09ab3b" if frr < h24_avg else "#ffa500"
            st.markdown(f"""<div style="padding:15px; border-radius:10px; background-color:#f8f9fb; border-left: 5px solid {color};">
                <h3 style="margin:0; color:{color}">市場狀態分析</h3>
                <code style="color:#666">FRR: {frr*100:.4f}% (年{frr*36500:.1f}%) | 24h高: {h24_high*100:.4f}% (年{h24_high*36500:.1f}%)</code>
            </div>""", unsafe_allow_html=True)
            
            # --- 2. 智慧指標 ---
            valid_walls = df[df['利率'] >= frr]
            best_wall = valid_walls.loc[valid_walls['掛單量'].idxmax()] if not valid_walls.empty else df.iloc[0]
            
            m1, m2, m3 = st.columns(3)
            m1.metric("1.保守 (FRR)", f"{frr*100:.4f}%", f"年{frr*36500:.1f}%")
            m2.metric("2.高勝率牆", f"{best_wall['利率']*100:.4f}%", f"年{best_wall['利率']*36500:.1f}%")
            m3.metric("3.智慧釣魚", f"{max(h24_high, best_wall['利率']*1.3)*100:.4f}%", "插針獲利")

            # --- 3. 穩健分析文字 ---
            st.info(f"💡 **穩健分析**：最大阻力位在 **{best_wall['利率']*100:.4f}%**，建議掛單在此牆前一檔。")

            # --- 4. 資金深度圖 ---
            st.subheader("🌊 資金深度分佈")
            chart_df = df.head(30).copy()
            chart_df['利率標籤'] = (chart_df['利率']*100).map('{:.4f}%'.format)
            st.bar_chart(chart_df.set_index('利率標籤')['掛單量'], color='#00d4ff')

            # --- 5. 詳細掛單清單 ---
            st.subheader("📊 詳細掛單清單 (Top 10)")
            list_df = df.head(10).copy()
            list_df['利率(%)'] = (list_df['利率']*100).map('{:.4f}%'.format)
            list_df['年化'] = (list_df['利率']*36500).map('{:.2f}%'.format)
            list_df['金額'] = list_df['掛單量'].map('{:,.0f}'.format)
            st.table(list_df[['利率(%)', '年化', '金額']])
        else:
            st.warning("數據讀取中...")

# --- 主畫面佈局 ---
st.title("💰 Bitfinex 智慧戰情室 V9.7")
c1, c2 = st.columns(2)
display_column(c1, "🇺🇸 USD (美金)", 'fUSD')
display_column(c2, "₮ USDT (泰達幣)", 'fUST') # 修正參數調用錯誤

time.sleep(20)
st.rerun()