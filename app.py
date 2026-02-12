import streamlit as st
import ccxt
import time
import pandas as pd

# ==========================================
# V9.4 視覺強化版：確保資金深度圖回歸
# ==========================================
st.set_page_config(page_title="Bitfinex 戰情室 V9.4", page_icon="💰", layout="wide")

@st.cache_resource
def init_exchange():
    return ccxt.bitfinex({'timeout': 30000, 'enableRateLimit': True})

bfx = init_exchange()

def get_data_only_book(symbol):
    try:
        # 只抓掛單簿 P0 精度，這對雲端 IP 最友善
        raw_book = bfx.public_get_book_symbol_precision({
            'symbol': symbol, 'precision': 'P0', 'len': 100
        })
        asks = [{'利率': float(item[0]), '掛單量': float(item[3])} for item in raw_book if float(item[3]) > 0]
        asks.sort(key=lambda x: x['利率'])
        
        simulated_frr = asks[0]['利率'] if asks else 0
        return asks, simulated_frr
    except:
        return None, 0

def analyze_by_book(asks, frr):
    if not asks: return None
    df = pd.DataFrame(asks)
    df['累積量'] = df['掛單量'].cumsum()
    avg_vol = df['掛單量'].mean()
    
    # 1. 氛圍判斷
    if frr > 0.0006: sentiment, color = "🔥 市場火熱", "#ffa500"
    elif len(df[df['利率'] < 0.0002]) > 40: sentiment, color = "🧊 市場冷清", "#1c83e1"
    else: sentiment, color = "☁️ 歲月靜好", "#09ab3b"

    # 2. 資金牆與策略 (核心功能)
    top_walls = df.nlargest(3, '掛單量').sort_values('利率')
    rate_a = next((x['利率'] for x in asks if x['掛單量'] > avg_vol * 5), asks[0]['利率'])
    rate_b = next((x['利率'] for x, c in zip(asks, df['累積量']) if c >= 3000000), asks[-1]['利率'])
    
    # 3. 階梯建議
    l1 = frr
    search_df = df[df['累積量'] <= 3000000]
    best_wall = search_df.loc[search_df['掛單量'].idxmax()] if not search_df.empty else df.iloc[0]
    l2 = best_wall['利率']
    l3 = l2 * 1.5 
    
    return {
        'frr': frr, 'l1': l1, 'l2': l2, 'l3': l3,
        'sentiment': sentiment, 'color': color,
        'top_walls': top_walls, 'full_df': df,
        'strats': {'動態平均': rate_a, '深度累積': rate_b}
    }

def display_column(col, title, symbol):
    with col:
        st.header(title)
        asks, frr = get_data_only_book(symbol)
        if asks:
            res = analyze_by_book(asks, frr)
            
            # --- 1. 氛圍儀表板 ---
            st.markdown(f"""<div style="padding:15px; border-radius:10px; background-color:#f8f9fb; border-left: 5px solid {res['color']}; margin-bottom:10px;">
                <h3 style="margin:0; color:{res['color']}">{res['sentiment']}</h3>
                <small>目前隊頭利率: {res['frr']*100:.4f}%</small>
            </div>""", unsafe_allow_html=True)
            
            # --- 2. 核心指標 ---
            m1, m2, m3 = st.columns(3)
            m1.metric("1.保守", f"{res['l1']*100:.4f}%")
            m2.metric("2.穩健 (牆前)", f"{res['l2']*100:.4f}%")
            m3.metric("3.智慧釣魚", f"{res['l3']*100:.4f}%")

            # --- 3. 策略與牆 ---
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("🔍 策略分析")
                for k, v in res['strats'].items():
                    st.write(f"**{k}:** {v*100:.4f}%")
            with c2:
                st.subheader("🧱 三大資金牆")
                for _, r in res['top_walls'].iterrows():
                    st.write(f"🚩 {r['利率']*100:.4f}% ({r['掛單量']/1000:.1f}K)")

            # --- 4. 重新回歸：資金深度分佈圖 ---
            st.subheader("🌊 資金深度分佈")
            chart_df = res['full_df'].head(20).copy()
            # 建立乾淨的繪圖數據，確保 Streamlit 不會報錯
            chart_df['利率標籤'] = (chart_df['利率']*100).map('{:.4f}%'.format)
            st.bar_chart(chart_df.set_index('利率標籤')['掛單量'], color='#00d4ff')

            # --- 5. 詳細清單 ---
            st.subheader("📊 詳細掛單清單 (Top 10)")
            list_df = res['full_df'].head(10).copy()
            list_df['日利率(%)'] = (list_df['利率']*100).map('{:.4f}%'.format)
            list_df['年化'] = (list_df['利率']*36500).map('{:.2f}%'.format)
            st.table(list_df[['日利率(%)', '年化', '掛單量']])
        else:
            st.warning("Bitfinex 連線繁忙，每 15 秒重試...")

st.title("💰 Bitfinex 智慧戰情室 V9.4")
c1, c2 = st.columns(2)
display_column(c1, "🇺🇸 USD (美金)", 'fUSD')
display_column(c2, "₮ USDT (泰達幣)", 'fUST')
time.sleep(15); st.rerun()