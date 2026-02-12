import streamlit as st
import ccxt
import time
import pandas as pd

# ==========================================
# 網頁設定
# ==========================================
st.set_page_config(
    page_title="Bitfinex 戰情室",
    page_icon="💰",
    layout="wide"
)

# ==========================================
# 初始化與工具函式
# ==========================================
@st.cache_resource
def init_exchange():
    return ccxt.bitfinex()

bfx = init_exchange()

def get_data(symbol):
    try:
        # 抓掛單簿 (取前 25 檔)
        raw_book = bfx.public_get_book_symbol_precision({
            'symbol': symbol, 'precision': 'P0', 'len': 25
        })
        asks = []
        for item in raw_book:
            # item[3] > 0 代表是放貸方 (Asks)
            if float(item[3]) > 0:
                asks.append({'利率': float(item[0]), '掛單量': float(item[3])})
        asks.sort(key=lambda x: x['利率'])
        
        # 抓 FRR
        raw_ticker = bfx.public_get_ticker_symbol({'symbol': symbol})
        frr = float(raw_ticker[0])
        
        return asks, frr
    except:
        return [], 0

def analyze_strategy(asks, frr):
    if not asks: return None
    
    df = pd.DataFrame(asks)
    
    # 策略計算
    # 1. 穩健 (最大牆前一檔)
    max_vol_idx = df['掛單量'].idxmax()
    wall_rate = df.iloc[max_vol_idx]['利率']
    
    if wall_rate > frr:
        rec_rate = wall_rate - 0.00000001
    else:
        rec_rate = frr * 1.0001 # 稍微高一點點
        
    # 2. 釣魚
    fish_rate = max(rec_rate * 1.3, frr * 1.5)
    
    return {
        'frr': frr,
        'rec_rate': rec_rate,
        'fish_rate': fish_rate,
        'top_asks': df.head(5) # 取前5檔顯示
    }

def display_currency_column(col, title, symbol):
    """ 顯示單一幣種的欄位邏輯 (封裝起來讓程式碼更乾淨) """
    with col:
        st.header(title)
        asks, frr = get_data(symbol)
        
        if asks:
            res = analyze_strategy(asks, frr)
            
            # --- 1. 顯示關鍵指標 (加入年化顯示) ---
            m1, m2, m3 = st.columns(3)
            
            # FRR
            frr_daily = res['frr'] * 100
            frr_year = res['frr'] * 365 * 100
            m1.metric("基準 FRR", f"{frr_daily:.4f}%", f"年化 {frr_year:.1f}%")
            
            # 穩健掛單
            rec_daily = res['rec_rate'] * 100
            rec_year = res['rec_rate'] * 365 * 100
            m2.metric("穩健掛單 (推薦)", f"{rec_daily:.4f}%", f"年化 {rec_year:.1f}%")
            
            # 釣魚掛單
            fish_daily = res['fish_rate'] * 100
            fish_year = res['fish_rate'] * 365 * 100
            m3.metric("釣魚掛單 (暴擊)", f"{fish_daily:.4f}%", f"年化 {fish_year:.1f}%")
            
            st.divider()
            
            # --- 2. 顯示掛單簿表格 (加入年化欄位) ---
            st.subheader("📊 市場掛單簿 (Top 5)")
            
            # 複製一份資料來做格式化，不影響原始計算
            display_df = res['top_asks'].copy()
            
            # 新增「年化報酬」欄位 (日利率 * 365)
            display_df['年化報酬'] = display_df['利率'] * 365
            
            # 格式化顯示 (轉成漂亮的字串)
            # 利率: 0.0123%
            display_df['利率 (日)'] = (display_df['利率'] * 100).map('{:.4f}%'.format)
            
            # 年化: 4.50%
            display_df['年化報酬'] = (display_df['年化報酬'] * 100).map('{:.2f}%'.format)
            
            # 掛單量: 1,234
            display_df['掛單量 (USD)'] = (display_df['掛單量']).map('{:,.0f}'.format)
            
            # 選取要顯示的欄位並排序
            final_table = display_df[['利率 (日)', '年化報酬', '掛單量 (USD)']]
            
            # 顯示表格 (use_container_width=True 讓表格填滿欄位)
            st.table(final_table)
            
        else:
            st.error("讀取失敗，請檢查網路連線")

# ==========================================
# 主畫面顯示
# ==========================================
st.title("💰 Bitfinex 資金戰情室 (Web版)")
st.caption(f"最後更新時間: {time.strftime('%H:%M:%S')} (每10秒自動刷新)")

# 建立左右兩欄
col1, col2 = st.columns(2)

# 左欄顯示 USD
display_currency_column(col1, "🇺🇸 USD (美金)", 'fUSD')

# 右欄顯示 USDT
display_currency_column(col2, "₮ USDT (泰達幣)", 'fUST')

# ==========================================
# 自動刷新機制
# ==========================================
time.sleep(10)
st.rerun()