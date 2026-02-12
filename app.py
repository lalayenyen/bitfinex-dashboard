import streamlit as st
import ccxt
import time
import pandas as pd

# ==========================================
# V10.0 結構重組版：捨棄 24h 高點以換取 100% 連線
# ==========================================
st.set_page_config(page_title="Bitfinex 智慧戰情室 V10.0", page_icon="💰", layout="wide")

@st.cache_resource
def init_exchange():
    return ccxt.bitfinex({'timeout': 30000, 'enableRateLimit': True})

bfx = init_exchange()

def get_stable_data(symbol):
    asks, frr = [], 0
    try:
        # 只抓最穩定的掛單簿與基本 Ticker，捨棄導致卡死的 24h 高點分析
        raw_book = bfx.public_get_book_symbol_precision({'symbol': symbol, 'precision': 'P0', 'len': 100})
        raw_df = pd.DataFrame(raw_book, columns=['rate', 'period', 'count', 'amount'])
        raw_df = raw_df[raw_df['amount'] > 0].astype(float)
        
        # 彙整相同利率，對齊圖表大柱子
        grouped = raw_df.groupby('rate')['amount'].sum().reset_index()
        asks = [{'利率': r, '掛單量': a} for r, a in zip(grouped['rate'], grouped['amount'])]
        asks.sort(key=lambda x: x['利率'])
        
        # 隊頭利率作為 FRR 參考
        frr = asks[0]['利率'] if asks else 0
    except: pass
    return asks, frr

def display_column(col, title, symbol):
    with col:
        st.header(title)
        asks, frr = get_stable_data(symbol)
        
        if asks:
            df = pd.DataFrame(asks)
            df['累積量'] = df['掛單量'].cumsum()
            avg_vol = df['掛單量'].mean()

            # 1. 市場狀態方塊
            st.markdown(f"""<div style="padding:15px; border-radius:10px; background-color:#f8f9fb; border-left: 5px solid #00d4ff;">
                <h3 style="margin:0; color:#333">市場即時分析</h3>
                <code style="color:#666">隊頭利率: {frr*100:.4f}% | 年化基準: {frr*36500:.1f}%</code>
            </div>""", unsafe_allow_html=True)

            # 2. 智慧指標
            valid_walls = df[df['利率'] >= frr]
            best_wall = valid_walls.loc[valid_walls['掛單量'].idxmax()] if not valid_walls.empty else df.iloc[0]
            
            m1, m2, m3 = st.columns(3)
            m1.metric("1.保守 (隊頭)", f"{frr*100:.4f}%")
            m2.metric("2.高勝率牆", f"{best_wall['利率']*100:.4f}%")
            # 改用掛單簿最高位作為釣魚參考
            fishing_rate = df['利率'].max() 
            m3.metric("3.智慧釣魚", f"{fishing_rate*100:.4f}%")

            st.info(f"💡 **穩健分析**：真正大牆在 **{best_wall['利率']*100:.4f}%** (總額 {best_wall['掛單量']:,.0f})。")

            # 3. 資金深度圖表
            st.subheader("🌊 資金深度分佈")
            chart_df = df.head(30).copy()
            chart_df['利率標籤'] = (chart_df['利率']*100).map('{:.4f}%'.format)
            st.bar_chart(chart_df.set_index('利率標籤')['掛單量'], color='#00d4ff')
            
            # 4. 詳細清單
            st.subheader("📊 詳細清單 (Top 10)")
            list_df = df.head(10).copy()
            list_df['利率%'] = (list_df['利率']*100).map('{:.4f}%'.format)
            list_df['金額'] = list_df['掛單量'].map('{:,.0f}'.format)
            st.table(list_df[['利率%', '金額']])

            # 5. 置底區塊：策略分析與三大牆 (解決不顯示問題)
            st.markdown("---")
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("🔍 策略分析")
                rate_a = next((x['利率'] for x in asks if x['掛單量'] > avg_vol * 3), asks[0]['利率'])
                rate_b = next((x['利率'] for x, c in zip(asks, df['累積量']) if c >= 2000000), asks[-1]['利率'])
                st.write(f"📈 **動態平均:** {rate_a*100:.4f}% (年{rate_a*36500:.1f}%)")
                st.write(f"⚖️ **深度累積:** {rate_b*100:.4f}% (年{rate_b*36500:.1f}%)")
            
            with c2:
                st.subheader("🧱 三大資金牆")
                top_3 = df.nlargest(3, '掛單量').sort_values('利率')
                for _, r in top_3.iterrows():
                    st.write(f"🚩 {r['利率']*100:.4f}% | {r['掛單量']/1000:.1f}K")
        else:
            st.warning("數據讀取中...")

# --- 主畫面佈局 ---
st.title("💰 Bitfinex 智慧戰情室 V10.0")
col_a, col_b = st.columns(2)
display_column(col_a, "🇺🇸 USD (美金)", 'fUSD')
display_column(col_b, "₮ USDT (泰達幣)", 'fUST')

time.sleep(15)
st.rerun()