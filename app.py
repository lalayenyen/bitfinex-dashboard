import streamlit as st
import ccxt
import time
import pandas as pd

# ==========================================
# V10.1 穩定版：完全跳過 Ticker，只靠掛單簿驅動全功能
# ==========================================
st.set_page_config(page_title="Bitfinex 智慧戰情室 V10.1", page_icon="💰", layout="wide")

@st.cache_resource
def init_exchange():
    return ccxt.bitfinex({'timeout': 20000, 'enableRateLimit': True})

bfx = init_exchange()

def get_data_from_book_only(symbol):
    try:
        # P0 精度掛單簿是目前最穩定、最不會被擋的接口
        raw_book = bfx.public_get_book_symbol_precision({'symbol': symbol, 'precision': 'P0', 'len': 100})
        raw_df = pd.DataFrame(raw_book, columns=['rate', 'period', 'count', 'amount'])
        raw_df = raw_df[raw_df['amount'] > 0].astype(float)
        
        # 核心：彙整相同利率，讓判定與柱狀圖同步
        grouped = raw_df.groupby('rate')['amount'].sum().reset_index()
        asks = [{'利率': r, '掛單量': a} for r, a in zip(grouped['rate'], grouped['amount'])]
        asks.sort(key=lambda x: x['利率'])
        
        return asks
    except:
        return None

def display_column(col, title, symbol):
    with col:
        st.header(title)
        asks = get_data_from_book_only(symbol)
        
        if asks:
            df = pd.DataFrame(asks)
            df['累積量'] = df['掛單量'].cumsum()
            avg_vol = df['掛單量'].mean()
            frr_sim = asks[0]['利率'] # 以隊頭模擬基準

            # 1. 市場方塊 (跳過 24H，改用深度判斷)
            color = "#09ab3b" if len(df) > 50 else "#ffa500"
            st.markdown(f"""<div style="padding:15px; border-radius:10px; background-color:#f8f9fb; border-left: 5px solid {color};">
                <h3 style="margin:0; color:{color}">市場即時監控 (掛單簿模式)</h3>
                <code>隊頭參考: {frr_sim*100:.4f}% | 年化: {frr_sim*36500:.1f}%</code>
            </div>""", unsafe_allow_html=True)

            # 2. 智慧指標
            best_wall = df.loc[df['掛單量'].idxmax()]
            m1, m2, m3 = st.columns(3)
            m1.metric("1.保守 (隊頭)", f"{frr_sim*100:.4f}%")
            m2.metric("2.高勝率牆", f"{best_wall['利率']*100:.4f}%")
            m3.metric("3.智慧釣魚", f"{df['利率'].max()*100:.4f}%")

            # 3. 穩健分析 (文字回歸)
            st.info(f"💡 **穩健分析**：真正大牆位於 **{best_wall['利率']*100:.4f}%** (總量 {best_wall['掛單量']:,.0f})，建議掛在此牆前。")

            # 4. 資金深度圖表 (對齊大牆)
            st.subheader("🌊 資金深度分佈")
            chart_df = df.head(30).copy()
            chart_df['標籤'] = (chart_df['利率']*100).map('{:.4f}%'.format)
            st.bar_chart(chart_df.set_index('標籤')['掛單量'], color='#00d4ff')
            
            # 5. 詳細清單
            st.subheader("📊 詳細清單")
            list_df = df.head(10).copy()
            list_df['利率%'] = (list_df['利率']*100).map('{:.4f}%'.format)
            list_df['金額'] = list_df['金額'] = list_df['掛單量'].map('{:,.0f}'.format)
            st.table(list_df[['利率%', '金額']])

            # 6. 置底：策略分析與三大牆 (位置調整)
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
            st.error("連線中斷，請確認網路或嘗試更換 IP (例如手機熱點)。")

# --- 主佈局 ---
st.title("💰 Bitfinex 智慧戰情室 V10.1")
col_a, col_b = st.columns(2)
display_column(col_a, "🇺🇸 USD (美金)", 'fUSD')
display_column(col_b, "₮ USDT (泰達幣)", 'fUST')

time.sleep(15)
st.rerun()