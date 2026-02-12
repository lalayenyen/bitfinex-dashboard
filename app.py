import streamlit as st
import ccxt
import time
import pandas as pd

# ==========================================
# 網頁設定
# ==========================================
st.set_page_config(
    page_title="Bitfinex 全能戰情室",
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
        # 抓掛單簿 (取前 100 檔以進行深度分析)
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

def analyze_full_strategy(asks, frr):
    if not asks: return None
    
    df = pd.DataFrame(asks)
    total_vol = df['掛單量'].sum()
    avg_vol = df['掛單量'].mean()
    
    # --- 1. 尋找前三大資金牆 ---
    # 依掛單量排序，取前三名
    top_walls = df.nlargest(3, '掛單量').sort_values('利率')
    
    # --- 2. 三大策略分析 (理論值) ---
    # A. 動態平均
    rate_a = None
    for index, row in df.iterrows():
        if row['掛單量'] > avg_vol * 5:
            rate_a = row['利率']
            break
            
    # B. 深度累積
    rate_b = None
    cum = 0
    for index, row in df.iterrows():
        cum += row['掛單量']
        if cum >= total_vol * 0.05:
            rate_b = row['利率']
            break
            
    # C. 心理關卡
    rate_c = None
    for index, row in df.iterrows():
        r_test = row['利率'] * 10000
        if abs(r_test - round(r_test)) < 0.05 and row['掛單量'] > avg_vol:
            rate_c = row['利率']
            break

    # --- 3. 階梯掛單 (實戰值) ---
    ladder_1 = frr
    
    # 穩健單：找最大的牆
    biggest_wall_rate = df.nlargest(1, '掛單量').iloc[0]['利率']
    if biggest_wall_rate > frr:
        ladder_2 = biggest_wall_rate - 0.00000001
    else:
        ladder_2 = frr * 1.1
        
    ladder_3 = max(ladder_2 * 1.3, frr * 1.5)
    
    return {
        'frr': frr,
        'top_asks': df.head(5),
        'top_walls': top_walls,
        'strategies': {
            'A.動態平均': rate_a,
            'B.深度累積': rate_b,
            'C.心理關卡': rate_c
        },
        'ladders': {
            '1.保守 (30%)': ladder_1,
            '2.穩健 (30%)': ladder_2,
            '3.釣魚 (40%)': ladder_3
        }
    }

def fmt_rate(r):
    """將小數轉成百分比字串"""
    if r is None: return "無訊號"
    return f"{r*100:.4f}%"

def display_currency_column(col, title, symbol):
    with col:
        st.header(title)
        asks, frr = get_data(symbol)
        
        if asks:
            res = analyze_full_strategy(asks, frr)
            ladders = res['ladders']
            
            # --- 1. 關鍵指標 (階梯建議) ---
            m1, m2, m3 = st.columns(3)
            
            # 顯示階梯式掛單建議
            r1 = ladders['1.保守 (30%)']
            r2 = ladders['2.穩健 (30%)']
            r3 = ladders['3.釣魚 (40%)']
            
            m1.metric("1.保守 (FRR)", f"{r1*100:.4f}%", f"年化 {r1*36500:.1f}%")
            m2.metric("2.穩健 (推薦)", f"{r2*100:.4f}%", f"年化 {r2*36500:.1f}%")
            m3.metric("3.釣魚 (暴擊)", f"{r3*100:.4f}%", f"年化 {r3*36500:.1f}%")
            
            st.divider()
            
            # --- 2. 市場分析三策略 ---
            st.subheader("🔍 市場分析 (支撐位)")
            strat_df = pd.DataFrame([
                {"策略": k, "理論利率": fmt_rate(v), "狀態": "低於 FRR" if v and v < frr else "有效支撐"} 
                for k, v in res['strategies'].items()
            ])
            st.dataframe(strat_df, use_container_width=True, hide_index=True)
            
            # --- 3. 前三大資金牆 ---
            st.subheader("🧱 前三大資金牆")
            walls_df = res['top_walls'].copy()
            walls_df['利率'] = walls_df['利率'].apply(fmt_rate)
            walls_df['掛單量'] = walls_df['掛單量'].apply(lambda x: f"{x:,.0f}")
            walls_df = walls_df[['利率', '掛單量']]
            st.dataframe(walls_df, use_container_width=True, hide_index=True)

            # --- 4. 掛單簿表格 ---
            st.subheader("📊 掛單簿 Top 5")
            display_df = res['top_asks'].copy()
            display_df['年化報酬'] = (display_df['利率'] * 36500).map('{:.2f}%'.format)
            display_df['利率'] = (display_df['利率'] * 100).map('{:.4f}%'.format)
            display_df['掛單量'] = (display_df['掛單量']).map('{:,.0f}'.format)
            st.table(display_df[['利率', '年化報酬', '掛單量']])
            
        else:
            st.error("讀取失敗")

# ==========================================
# 主畫面
# ==========================================
st.title("💰 Bitfinex 全能戰情室 V6")
st.caption(f"最後更新: {time.strftime('%H:%M:%S')} (每10秒刷新)")

col1, col2 = st.columns(2)
display_currency_column(col1, "🇺🇸 USD (美金)", 'fUSD')
display_currency_column(col2, "₮ USDT (泰達幣)", 'fUST')

time.sleep(10)
st.rerun()