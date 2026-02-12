import streamlit as st
import ccxt
import time
import pandas as pd

# ==========================================
# V9.3 掛單簿驅動版 (最強連線容錯)
# ==========================================
st.set_page_config(page_title="Bitfinex 戰情室 V9.3", page_icon="💰", layout="wide")

@st.cache_resource
def init_exchange():
    return ccxt.bitfinex({'timeout': 30000, 'enableRateLimit': True})

bfx = init_exchange()

def get_data_only_book(symbol):
    try:
        # 只抓掛單簿 (P0精度)，這是目前對 API 壓力最低的抓法
        raw_book = bfx.public_get_book_symbol_precision({
            'symbol': symbol, 'precision': 'P0', 'len': 100
        })
        # 排除負值與異常數據
        asks = [{'利率': float(item[0]), '掛單量': float(item[3])} for item in raw_book if float(item[3]) > 0]
        asks.sort(key=lambda x: x['利率'])
        
        # 使用掛單簿第一檔 (隊頭) 作為模擬 FRR
        simulated_frr = asks[0]['利率'] if asks else 0
        return asks, simulated_frr
    except:
        return None, 0

def analyze_by_book(asks, frr):
    if not asks: return None
    df = pd.DataFrame(asks)
    df['累積量'] = df['掛單量'].cumsum()
    avg_vol = df['掛單量'].mean()
    
    # --- 1. 市場氛圍儀表板 (改由資金深度判斷) ---
    # 若掛單集中在低利率，代表冷清；若高利率區間有大量掛單被消化，代表火熱
    if len(df[df['利率'] < 0.0002]) > 50: # 假設大量極低利掛單堆積
        sentiment, color = "🧊 市場冷清 (低利堆積)", "#1c83e1"
    elif frr > 0.0005: # 日利率高於 0.05%
        sentiment, color = "🔥 市場火熱", "#ffa500"
    else:
        sentiment, color = "☁️ 歲月靜好 (和平時期)", "#09ab3b"

    # --- 2. 三大資金牆 (核心功能回歸) ---
    top_walls = df.nlargest(3, '掛單量').sort_values('利率')
    
    # --- 3. 策略分析 ---
    rate_a = next((x['利率'] for x in asks if x['掛單量'] > avg_vol * 5), asks[0]['利率']) # 動態平均
    rate_b = next((x['利率'] for x, c in zip(asks, df['累積量']) if c >= 3000000), asks[-1]['利率']) # 深度累積
    
    # --- 4. 階梯建議方案 ---
    l1 = frr # 保守單掛隊頭
    # 穩健單找 300 萬深度內最強的牆
    search_df = df[df['累積量'] <= 3000000]
    best_wall = search_df.loc[search_df['掛單量'].idxmax()] if not search_df.empty else df.iloc[0]
    l2 = best_wall['利率']
    l3 = l2 * 1.5 # 釣魚單改用倍率模擬
    
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
            
            # 1. 氛圍儀表板
            st.markdown(f"""<div style="padding:15px; border-radius:10px; background-color:#f8f9fb; border-left: 5px solid {res['color']};">
                <h3 style="margin:0; color:{res['color']}">{res['sentiment']}</h3>
                <small>目前隊頭利率: {res['frr']*100:.4f}%</small>
            </div>""", unsafe_allow_html=True)
            
            # 2. 階梯建議
            m1, m2, m3 = st.columns(3)
            m1.metric("1.保守", f"{res['l1']*100:.4f}%")
            m2.metric("2.穩健 (高勝率)", f"{res['l2']*100:.4f}%")
            m3.metric("3.智慧釣魚", f"{res['l3']*100:.4f}%")

            # 3. 策略與牆
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("🔍 策略分析")
                for k, v in res['strats'].items():
                    st.write(f"**{k}:** {v*100:.4f}%")
            with c2:
                st.subheader("🧱 三大資金牆")
                for _, r in res['top_walls'].iterrows():
                    st.write(f"🚩 {r['利率']*100:.4f}% ({r['掛單量']/1000:.1f}K)")

            # 4. 詳細清單
            st.subheader("📊 詳細掛單清單 (Top 10)")
            list_df = res['full_df'].head(10).copy()
            list_df['年化'] = (list_df['利率']*36500).map('{:.2f}%'.format)
            list_df['日利率(%)'] = (list_df['利率']*100).map('{:.4f}%'.format)
            st.table(list_df[['日利率(%)', '年化', '掛單量']])
        else:
            st.warning("Bitfinex 連線繁忙，每 15 秒重試...")

st.title("💰 Bitfinex 智慧戰情室 V9.3 (純掛單簿版)")
c1, c2 = st.columns(2)
display_column(c1, "🇺🇸 USD (美金)", 'fUSD')
display_column(c2, "₮ USDT (泰達幣)", 'fUST')
time.sleep(15); st.rerun()