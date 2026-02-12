import streamlit as st
import ccxt
import time
import pandas as pd

# ==========================================
# V10.3 最終穩定版：全功能對齊 + 極限連線優化
# ==========================================
st.set_page_config(page_title="Bitfinex 智慧戰情室 V10.3", page_icon="💰", layout="wide")

@st.cache_resource
def init_exchange():
    return ccxt.bitfinex({'timeout': 40000, 'enableRateLimit': True})

bfx = init_exchange()

def get_pure_book_data(symbol):
    try:
        # 只讀取最穩定的 P0 精度掛單簿
        raw_book = bfx.public_get_book_symbol_precision({'symbol': symbol, 'precision': 'P0', 'len': 50})
        raw_df = pd.DataFrame(raw_book, columns=['rate', 'period', 'count', 'amount'])
        raw_df = raw_df[raw_df['amount'].astype(float) > 0]
        
        # 彙整加總相同利率，解決判定與圖表柱子不一致問題
        grouped = raw_df.groupby('rate')['amount'].sum().reset_index()
        asks = [{'利率': float(r), '掛單量': float(a)} for r, a in zip(grouped['rate'], grouped['amount'])]
        asks.sort(key=lambda x: x['利率'])
        return asks
    except:
        return None

def display_column(col, title, symbol):
    with col:
        st.header(title)
        asks = get_pure_book_data(symbol)
        
        if asks:
            df = pd.DataFrame(asks)
            df['累積量'] = df['掛單量'].cumsum()
            avg_vol = df['掛單量'].mean()
            frr_sim = asks[0]['利率'] # 隊頭基準

            # 1. 市場狀態方塊
            st.markdown(f"""<div style="padding:15px; border-radius:10px; background-color:#f8f9fb; border-left: 5px solid #00d4ff;">
                <h3 style="margin:0; color:#333">市場即時數據</h3>
                <code style="color:#666">隊頭基準: {frr_sim*100:.4f}% | 年化: {frr_sim*36500:.1f}%</code>
            </div>""", unsafe_allow_html=True)

            # 2. 智慧指標卡片
            best_wall = df.loc[df['掛單量'].idxmax()] # 真正的大柱子
            m1, m2, m3 = st.columns(3)
            m1.metric("1.隊頭 (保守)", f"{frr_sim*100:.4f}%")
            m2.metric("2.最大阻力牆", f"{best_wall['利率']*100:.4f}%")
            m3.metric("3.插針預期", f"{df['利率'].max()*100:.4f}%")

            # 3. 穩健分析文字
            st.info(f"💡 **穩健分析**：真正大牆位於 **{best_wall['利率']*100:.4f}%** (總量 {best_wall['掛單量']:,.0f})，建議掛在此牆前一檔。")

            # 4. 資金深度分佈圖
            st.subheader("🌊 資金深度分佈")
            chart_df = df.head(30).copy()
            chart_df['標籤'] = (chart_df['利率']*100).map('{:.4f}%'.format)
            st.bar_chart(chart_df.set_index('標籤')['掛單量'], color='#00d4ff')
            
            # 5. 詳細清單
            st.subheader("📊 詳細清單 (Top 10)")
            list_df = df.head(10).copy()
            list_df['利率%'] = (list_df['利率']*100).map('{:.4f}%'.format)
            list_df['金額'] = list_df['掛單量'].map('{:,.0f}'.format)
            st.table(list_df[['利率%', '金額']])

            # 6. 置底功能區：策略分析 & 三大資金牆
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
            st.warning("🔄 數據連線恢復中，請確保已更換至手機熱點網路...")

# --- 主佈局 ---
st.title("💰 Bitfinex 智慧戰情室 V10.3")
col_a, col_b = st.columns(2)
display_column(col_a, "🇺🇸 USD (美金)", 'fUSD')
display_column(col_b, "₮ USDT (泰達幣)", 'fUST')

time.sleep(30)
st.rerun()