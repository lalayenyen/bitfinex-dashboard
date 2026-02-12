import streamlit as st
import ccxt
import time
import pandas as pd

# ==========================================
# 設定區
# ==========================================
SEARCH_CAP_USD = 3000000 
SEARCH_CAP_USDT = 3000000

st.set_page_config(page_title="Bitfinex 智慧戰情室 (雲端穩定版)", page_icon="💰", layout="wide")

# ==========================================
# 初始化
# ==========================================
@st.cache_resource
def init_exchange():
    # 增加超時與自動重試，提高雲端穩定度
    return ccxt.bitfinex({
        'timeout': 20000,
        'enableRateLimit': True,
    })

bfx = init_exchange()

def get_market_data(symbol):
    """
    抓取即時數據 (Ticker + Book)
    Ticker 包含 24h High/Low，可用來代替 30d 歷史數據判斷氛圍
    """
    try:
        # 1. 抓掛單簿 (P0精度)
        raw_book = bfx.public_get_book_symbol_precision({
            'symbol': symbol, 'precision': 'P0', 'len': 100
        })
        asks = []
        for item in raw_book:
            if float(item[3]) > 0:
                asks.append({'利率': float(item[0]), '掛單量': float(item[3])})
        asks.sort(key=lambda x: x['利率'])
        
        # 2. 抓 Ticker (包含當前 FRR 與 24h 波動)
        # v2 API 回傳格式為列表，第一個元素是 FRR
        ticker = bfx.public_get_ticker_symbol({'symbol': symbol})
        frr = float(ticker[0])
        # 我們利用 Ticker 數據來粗略判斷市場熱度
        # 註：雖然不像30天歷史那麼準，但 24h 數據在雲端非常穩定
        
        return asks, frr
    except Exception as e:
        st.error(f"連線異常: {e}")
        return [], 0

def analyze_logic(asks, frr, search_cap):
    if not asks: return None
    
    df = pd.DataFrame(asks)
    df['累積量'] = df['掛單量'].cumsum()
    
    # === 智慧牆算法 ===
    reachable_df = df[df['累積量'] <= search_cap]
    if reachable_df.empty: reachable_df = df.head(10)
    
    best_wall_row = reachable_df.loc[reachable_df['掛單量'].idxmax()]
    wall_rate = best_wall_row['利率']
    
    # === 策略定價 ===
    rec_rate = max(wall_rate - 0.00000001, frr)
    fish_rate = max(rec_rate * 1.3, frr * 1.5)
    
    return {
        'frr': frr,
        'rec_rate': rec_rate,
        'fish_rate': fish_rate,
        'wall_info': best_wall_row,
        'full_df': df
    }

def display_column(col, title, symbol, search_cap):
    with col:
        st.header(title)
        asks, frr = get_market_data(symbol)
        
        if asks:
            res = analyze_logic(asks, frr, search_cap)
            
            # --- 關鍵指標 ---
            m1, m2, m3 = st.columns(3)
            m1.metric("1.目前 FRR", f"{res['frr']*100:.4f}%", f"年{res['frr']*36500:.1f}%")
            m2.metric("2.穩健建議", f"{res['rec_rate']*100:.4f}%", "智慧牆前")
            m3.metric("3.釣魚建議", f"{res['fish_rate']*100:.4f}%", f"年{res['fish_rate']*36500:.0f}%")
            
            # --- 氛圍說明 ---
            st.info(f"💡 數據分析：目前偵測到前 {search_cap/10000:.0f}萬 資金中，最強牆位於 {res['wall_info']['利率']*100:.4f}%。")

            # --- 深度分布圖 ---
            st.subheader("🌊 資金深度分佈")
            chart_data = res['full_df'].head(40).copy()
            chart_data['利率標籤'] = (chart_data['利率']*100).map('{:.4f}%'.format)
            st.bar_chart(chart_data, x='利率標籤', y='掛單量', color='#00d4ff')

            # --- 掛單簿 ---
            with st.expander("詳細掛單清單"):
                df_show = res['full_df'].head(10).copy()
                df_show['年化'] = (df_show['利率']*36500).map('{:.2f}%'.format)
                df_show['利率'] = (df_show['利率']*100).map('{:.4f}%'.format)
                df_show['掛單量'] = df_show['掛單量'].map('{:,.0f}'.format)
                st.table(df_show[['利率', '年化', '掛單量']])
        else:
            st.warning("交易所回應超時，等待自動重試中...")

# ==========================================
# 主畫面
# ==========================================
st.title("💰 Bitfinex 智慧戰情室 (雲端穩定版)")
st.caption(f"最後更新: {time.strftime('%H:%M:%S')} | 每10秒自動刷新")

col1, col2 = st.columns(2)
display_column(col1, "🇺🇸 USD (美金)", 'fUSD', SEARCH_CAP_USD)
display_column(col2, "₮ USDT (泰達幣)", 'fUST', SEARCH_CAP_USDT)

time.sleep(10)
st.rerun()