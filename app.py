import streamlit as st
import ccxt
import time
import pandas as pd

# ==========================================
# 設定區
# ==========================================
# 有效射程：我們只看前 300 萬美金的掛單 (這是大戶通常會掃單的範圍)
SEARCH_CAP_USD = 3000000 
SEARCH_CAP_USDT = 3000000

st.set_page_config(page_title="Bitfinex 智慧戰情室", page_icon="💰", layout="wide")

# ==========================================
# 初始化
# ==========================================
@st.cache_resource
def init_exchange():
    return ccxt.bitfinex()

bfx = init_exchange()

def get_data(symbol):
    try:
        # 抓取掛單簿 (取前 100 檔，保證數據夠深)
        raw_book = bfx.public_get_book_symbol_precision({
            'symbol': symbol, 'precision': 'P0', 'len': 100
        })
        asks = []
        for item in raw_book:
            if float(item[3]) > 0:
                asks.append({'利率': float(item[0]), '掛單量': float(item[3])})
        asks.sort(key=lambda x: x['利率'])
        
        # 抓 FRR
        raw_ticker = bfx.public_get_ticker_symbol({'symbol': symbol})
        frr = float(raw_ticker[0])
        
        return asks, frr
    except:
        return [], 0

def analyze_smart_strategy(asks, frr, search_cap):
    if not asks: return None
    
    df = pd.DataFrame(asks)
    
    # 1. 計算「累積掛單量」 (Cumulative Sum)
    df['累積量'] = df['掛單量'].cumsum()
    
    # 2. 計算年化報酬 (方便顯示)
    df['年化'] = df['利率'] * 365
    
    # === 核心算法：尋找有效射程內的最佳牆 ===
    # 篩選出累積量在「射程範圍 (Search Cap)」內的單
    # 例如：只看前 300萬 USD，因為太遠的單通常吃不到
    reachable_df = df[df['累積量'] <= search_cap]
    
    # 如果射程內沒單 (市場太淺)，就退而求其次用全部
    if reachable_df.empty:
        reachable_df = df.head(10)
        
    # 在這個「吃得到的範圍」內，找最大的一根柱子
    best_wall_idx = reachable_df['掛單量'].idxmax()
    best_wall_row = reachable_df.loc[best_wall_idx]
    
    wall_rate = best_wall_row['利率']
    
    # 3. 設定策略價格
    # 穩健單：掛在牆的前面一點點
    if wall_rate > frr:
        rec_rate = wall_rate - 0.00000001
    else:
        rec_rate = frr # 如果牆比 FRR 還低，就掛 FRR 保護自己
        
    # 釣魚單：射程外的高價區 (假設市場暴衝)
    fish_rate = max(rec_rate * 1.3, frr * 1.5)
    
    return {
        'frr': frr,
        'rec_rate': rec_rate,
        'fish_rate': fish_rate,
        'wall_info': best_wall_row, # 記錄那道牆的資訊
        'full_df': df, # 為了畫圖用
        'reachable_df': reachable_df # 為了畫圖標示射程
    }

def display_panel(col, title, symbol, search_cap):
    with col:
        st.header(title)
        asks, frr = get_data(symbol)
        
        if asks:
            res = analyze_smart_strategy(asks, frr, search_cap)
            
            # --- 1. 關鍵指標 ---
            m1, m2, m3 = st.columns(3)
            r1 = res['frr']
            r2 = res['rec_rate']
            r3 = res['fish_rate']
            
            m1.metric("1.保守 (FRR)", f"{r1*100:.4f}%", f"年化 {r1*36500:.1f}%")
            m2.metric("2.穩健 (智慧牆)", f"{r2*100:.4f}%", f"年化 {r2*36500:.1f}%")
            m3.metric("3.釣魚 (暴擊)", f"{r3*100:.4f}%", f"年化 {r3*36500:.1f}%")
            
            st.info(f"💡 穩健策略分析：我們掃描了市場前 **{search_cap/10000:.0f}萬 USD** 的資金，發現最大阻力位在 **{res['wall_info']['利率']*100:.4f}%** (量體 {res['wall_info']['掛單量']:,.0f})，建議掛在它前面。")

            st.divider()
            
            # --- 2. 資金深度圖 (視覺化) ---
            st.subheader("🌊 資金深度分佈圖")
            
            chart_data = res['full_df'].head(40).copy() # 只畫前40檔，不然太密
            
            # 為了讓圖表好讀，我們把利率當 X 軸 (字串化避免被當數值縮放)，掛單量當 Y 軸
            # 並標記出哪一根是我們的「智慧牆」
            chart_data['利率標籤'] = (chart_data['利率']*100).map('{:.4f}%'.format)
            
            # 使用 Streamlit 原生 Bar Chart
            st.bar_chart(chart_data, x='利率標籤', y='掛單量', color='#00ff00')
            st.caption("X軸: 利率 (低->高) | Y軸: 該價位的掛單量 (越高代表牆越厚)")

            # --- 3. 掛單簿表格 ---
            with st.expander("查看詳細掛單簿數據"):
                display_df = res['full_df'].head(10).copy()
                display_df['年化'] = display_df['年化'].map('{:.2f}%'.format)
                display_df['利率'] = (display_df['利率']*100).map('{:.4f}%'.format)
                display_df['掛單量'] = display_df['掛單量'].map('{:,.0f}'.format)
                display_df['累積量'] = display_df['累積量'].map('{:,.0f}'.format)
                st.table(display_df[['利率', '年化', '掛單量', '累積量']])
            
        else:
            st.error("讀取失敗")

# ==========================================
# 主畫面
# ==========================================
st.title("💰 Bitfinex 智慧戰情室 V7 (射程分析版)")
st.caption(f"最後更新: {time.strftime('%H:%M:%S')} | 射程設定: 300萬 USD")

col1, col2 = st.columns(2)
display_panel(col1, "🇺🇸 USD (美金)", 'fUSD', SEARCH_CAP_USD)
display_panel(col2, "₮ USDT (泰達幣)", 'fUST', SEARCH_CAP_USDT)

time.sleep(10)
st.rerun()