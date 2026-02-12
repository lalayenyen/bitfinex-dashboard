import streamlit as st
import ccxt
import time
import pandas as pd
import numpy as np

# ==========================================
# 設定區
# ==========================================
SEARCH_CAP_USD = 3000000 
SEARCH_CAP_USDT = 3000000

st.set_page_config(page_title="Bitfinex 歷史氛圍戰情室", page_icon="📈", layout="wide")

# ==========================================
# 初始化
# ==========================================
@st.cache_resource
def init_exchange():
    return ccxt.bitfinex()

bfx = init_exchange()

def get_history_data(symbol):
    """抓取過去 30 天的歷史 K 線數據 (日線)"""
    try:
        # timeframe='1D' 代表日線, limit=30 代表過去30天
        # Bitfinex 的 funding candle: [timestamp, open, high, low, close, volume]
        # 這裡的 close 代表當天平均收盤利率
        candles = bfx.fetch_ohlcv(symbol, timeframe='1D', limit=30)
        
        df = pd.DataFrame(candles, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        df['date'] = pd.to_datetime(df['ts'], unit='ms')
        
        # 計算統計數據
        avg_30d = df['close'].mean()
        max_30d = df['high'].max()
        min_30d = df['low'].min()
        
        return df, avg_30d, max_30d, min_30d
    except:
        return pd.DataFrame(), 0, 0, 0

def get_current_book(symbol):
    try:
        raw_book = bfx.public_get_book_symbol_precision({
            'symbol': symbol, 'precision': 'P0', 'len': 100
        })
        asks = []
        for item in raw_book:
            if float(item[3]) > 0:
                asks.append({'利率': float(item[0]), '掛單量': float(item[3])})
        asks.sort(key=lambda x: x['利率'])
        
        raw_ticker = bfx.public_get_ticker_symbol({'symbol': symbol})
        frr = float(raw_ticker[0])
        
        return asks, frr
    except:
        return [], 0

def analyze_market_sentiment(asks, frr, search_cap, avg_30d, max_30d):
    if not asks: return None
    
    df = pd.DataFrame(asks)
    df['累積量'] = df['掛單量'].cumsum()
    
    # === 1. 判斷市場氛圍 (Sentiment) ===
    # 比較 當前FRR vs 30天平均
    if frr > max_30d * 0.9:
        sentiment = "🔥🔥 極度貪婪 (暴利期)"
        color = "red"
    elif frr > avg_30d * 1.2:
        sentiment = "🔥 市場火熱 (高於平均)"
        color = "orange"
    elif frr < avg_30d * 0.8:
        sentiment = "🧊 市場冷清 (低於平均)"
        color = "blue"
    else:
        sentiment = "☁️ 歲月靜好 (和平時期)"
        color = "green"

    # === 2. 智慧射程牆 ===
    reachable_df = df[df['累積量'] <= search_cap]
    if reachable_df.empty: reachable_df = df.head(10)
    
    best_wall_idx = reachable_df['掛單量'].idxmax()
    wall_info = reachable_df.loc[best_wall_idx]
    wall_rate = wall_info['利率']
    
    # === 3. 策略定價 ===
    if wall_rate > frr:
        rec_rate = wall_rate - 0.00000001
    else:
        rec_rate = frr 
        
    # 釣魚單：如果現在很冷，就掛歷史平均；如果現在很熱，就掛歷史最高
    # 這樣可以確保你在冷的時候守住底線，熱的時候吃到暴利
    fish_rate = max(max_30d, rec_rate * 1.3)
    
    return {
        'frr': frr,
        'rec_rate': rec_rate,
        'fish_rate': fish_rate,
        'sentiment': sentiment,
        'sentiment_color': color,
        'avg_30d': avg_30d,
        'max_30d': max_30d,
        'full_df': df
    }

def display_panel(col, title, symbol, search_cap):
    with col:
        st.header(title)
        
        # 1. 先抓歷史數據
        hist_df, avg_30d, max_30d, min_30d = get_history_data(symbol)
        
        # 2. 再抓即時數據
        asks, frr = get_current_book(symbol)
        
        if asks and not hist_df.empty:
            res = analyze_market_sentiment(asks, frr, search_cap, avg_30d, max_30d)
            
            # --- A. 市場氛圍卡片 ---
            st.markdown(f"""
            <div style="padding:10px; border-radius:10px; background-color:#f0f2f6; border-left: 5px solid {res['sentiment_color']}">
                <h3 style="margin:0; color:{res['sentiment_color']}">{res['sentiment']}</h3>
                <small>目前 FRR: {res['frr']*100:.4f}% | 30日平均: {res['avg_30d']*100:.4f}%</small>
            </div>
            """, unsafe_allow_html=True)
            
            st.write("") # 空行

            # --- B. 關鍵指標 (加入歷史比較) ---
            m1, m2, m3 = st.columns(3)
            
            # 顯示這比平常高還是低
            delta_val = (res['frr'] - res['avg_30d']) * 100
            m1.metric("1.目前市價 (FRR)", f"{res['frr']*100:.4f}%", f"{delta_val:.4f}% (vs 平均)", delta_color="normal")
            
            m2.metric("2.穩健掛單", f"{res['rec_rate']*100:.4f}%", "推薦")
            
            # 釣魚單現在參考「歷史最高」
            m3.metric("3.釣魚 (歷史高點)", f"{res['fish_rate']*100:.4f}%", f"目標 {res['fish_rate']*36500:.0f}% 年化")

            # --- C. 歷史趨勢圖 (新功能!) ---
            st.subheader("📅 過去 30 天利率走勢")
            
            # 整理圖表數據
            chart_df = hist_df[['date', 'close', 'high']].copy()
            chart_df['平均利率'] = chart_df['close'] * 100
            chart_df['最高利率'] = chart_df['high'] * 100
            chart_df = chart_df.set_index('date')
            
            st.line_chart(chart_df[['平均利率', '最高利率']])
            st.caption(f"藍線: 每日平均 (和平基準) | 紅線: 每日最高 (波濤起伏)")
            
            # 顯示統計數據
            c1, c2 = st.columns(2)
            c1.info(f"🕊️ **和平時刻 (30日均價)**: \n {avg_30d*100:.4f}% (年化 {avg_30d*36500:.1f}%)")
            c2.error(f"🌊 **波濤起伏 (30日最高)**: \n {max_30d*100:.4f}% (年化 {max_30d*36500:.1f}%)")

            st.divider()

        else:
            st.error("讀取失敗，請檢查網路")

# ==========================================
# 主畫面
# ==========================================
st.title("📈 Bitfinex 歷史氛圍戰情室 V8")
st.caption(f"最後更新: {time.strftime('%H:%M:%S')} | 數據來源: 過去30天日線")

col1, col2 = st.columns(2)
display_panel(col1, "🇺🇸 USD (美金)", 'fUSD', SEARCH_CAP_USD)
display_panel(col2, "₮ USDT (泰達幣)", 'fUST', SEARCH_CAP_USDT)

time.sleep(15) # 稍微延長刷新時間，因為要抓歷史數據
st.rerun()