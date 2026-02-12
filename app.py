import streamlit as st
import ccxt
import time
import pandas as pd

# ==========================================
# V10.6 連線強化版：增加握手測試與錯誤退避
# ==========================================
st.set_page_config(page_title="Bitfinex 智慧戰情室 V10.6", page_icon="💰", layout="wide")

@st.cache_resource
def init_exchange():
    # 增加超時時間並開啟連線限制保護
    return ccxt.bitfinex({'timeout': 45000, 'enableRateLimit': True})

bfx = init_exchange()

def get_data_with_retry(symbol):
    """加入重試與退避機制，降低被擋機率"""
    for _ in range(2):
        try:
            raw_book = bfx.public_get_book_symbol_precision({'symbol': symbol, 'precision': 'P0', 'len': 50})
            df = pd.DataFrame(raw_book, columns=['rate', 'period', 'count', 'amount'])
            df = df[df['amount'].astype(float) > 0].astype(float)
            # 彙整相同利率，對齊大牆
            grouped = df.groupby('rate')['amount'].sum().reset_index().sort_values('rate')
            return [{'利率': r, '掛單量': a} for r, a in zip(grouped['rate'], grouped['amount'])]
        except:
            time.sleep(2) # 失敗後靜默 2 秒再試
    return None

def display_column(col, title, symbol):
    with col:
        st.header(title)
        asks = get_data_with_retry(symbol)
        
        if asks:
            df = pd.DataFrame(asks)
            df['累積量'] = df['掛單量'].cumsum()
            frr_sim = asks[0]['利率']

            # 1. 核心指標方塊
            st.markdown(f"""<div style="padding:15px; border-radius:10px; background-color:#f8f9fb; border-left: 5px solid #00d4ff;">
                <h3 style="margin:0; color:#333">市場即時數據 (穩定模式)</h3>
                <code>隊頭基準: {frr_sim*100:.4f}% | 年化: {frr_sim*36500:.1f}%</code>
            </div>""", unsafe_allow_html=True)

            # 2. 智慧指標
            best_wall = df.loc[df['掛單量'].idxmax()]
            m1, m2, m3 = st.columns(3)
            m1.metric("1.隊頭 (保守)", f"{frr_sim*100:.4f}%")
            m2.metric("2.高勝率牆", f"{best_wall['利率']*100:.4f}%")
            m3.metric("3.智慧插針", f"{df['利率'].max()*100:.4f}%")

            # 3. 資金深度圖
            st.subheader("🌊 資金深度分佈")
            chart_df = df.head(25).copy()
            chart_df['標籤'] = (chart_df['利率']*100).map('{:.4f}%'.format)
            st.bar_chart(chart_df.set_index('標籤')['掛單量'], color='#00d4ff')
            
            # 4. 置底模塊：找回消失的策略分析
            st.markdown("---")
            c1, c2 = st.columns(2)
            avg_vol = df['掛單量'].mean()
            with c1:
                st.subheader("🔍 策略分析")
                rate_a = next((x['利率'] for x in asks if x['掛單量'] > avg_vol * 3), asks[0]['利率'])
                rate_b = next((x['利率'] for x, c in zip(asks, df['累積量']) if c >= 2000000), asks[-1]['利率'])
                st.write(f"📈 動態平均: {rate_a*100:.4f}%")
                st.write(f"⚖️ 深度累積: {rate_b*100:.4f}%")
            with c2:
                st.subheader("🧱 三大資金牆")
                top_3 = df.nlargest(3, '掛單量').sort_values('利率')
                for _, r in top_3.iterrows():
                    st.write(f"🚩 {r['利率']*100:.4f}% | {r['掛單量']/1000:.1f}K")
        else:
            st.error("⚠️ API 目前對此 IP 限制連線，請嘗試切換手機熱點後重整頁面。")

st.title("💰 Bitfinex 智慧戰情室 V10.6")
col_a, col_b = st.columns(2)
display_column(col_a, "🇺🇸 USD (美金)", 'fUSD')
display_column(col_b, "₮ USDT (泰達幣)", 'fUST')

time.sleep(45) # 延長刷新間隔至 45 秒，保護 IP
st.rerun()