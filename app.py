import streamlit as st
import requests
import time
import pandas as pd

# ==========================================
# V9.1 極簡直連版：捨棄 ccxt，改用原始 requests
# ==========================================
st.set_page_config(page_title="Bitfinex 智慧戰情室 V9.1", page_icon="💰", layout="wide")

def get_data_raw(symbol):
    try:
        # 使用原始 REST API 網址，這對伺服器負擔最小
        ticker_url = f"https://api-pub.bitfinex.com/v2/ticker/{symbol}"
        book_url = f"https://api-pub.bitfinex.com/v2/book/{symbol}/P0?len=50"
        
        t_res = requests.get(ticker_url, timeout=10).json()
        b_res = requests.get(book_url, timeout=10).json()
        
        # 解析 Ticker
        frr = abs(float(t_res[0]))
        h24_high = abs(float(t_res[8]))
        h24_low = abs(float(t_res[9]))
        h24_avg = (h24_high + h24_low) / 2
        
        # 解析 Book
        asks = [{'利率': float(item[0]), '掛單量': float(item[3])} for item in b_res if float(item[3]) > 0]
        asks.sort(key=lambda x: x['利率'])
        
        return asks, frr, h24_avg, h24_high
    except:
        return None, 0, 0, 0

def display_column(col, title, symbol):
    with col:
        st.header(title)
        asks, frr, h24_avg, h24_high = get_data_raw(symbol)
        
        if asks:
            # --- 邏輯計算 ---
            df = pd.DataFrame(asks)
            df['累積'] = df['掛單量'].cumsum()
            
            # 氛圍
            if frr >= h24_high * 0.95: sentiment, color = "🔥🔥 極度貪婪", "red"
            elif frr >= h24_avg * 1.05: sentiment, color = "🔥 市場火熱", "orange"
            else: sentiment, color = "☁️ 歲月靜好", "green"
            
            # 策略建議
            l1 = frr
            best_wall = df[df['利率'] >= frr].nlargest(1, '掛單量').iloc[0] if not df[df['利率'] >= frr].empty else df.iloc[0]
            l2 = max(best_wall['利率'], frr)
            l3 = max(h24_high, l2 * 1.3)

            # --- 顯示介面 ---
            st.success(f"{sentiment} | 基準: {h24_avg*100:.4f}% | 24H高: {h24_high*100:.4f}%")
            
            m1, m2, m3 = st.columns(3)
            m1.metric("1.保守", f"{l1*100:.4f}%")
            m2.metric("2.高勝率", f"{l2*100:.4f}%")
            m3.metric("3.智慧釣魚", f"{l3*100:.4f}%")

            st.info(f"💡 分析：最大阻力位在 **{best_wall['利率']*100:.4f}%**。")
            
            # 圖表
            chart_df = df.head(15).copy()
            chart_df['利率%'] = chart_df['利率'] * 100
            st.bar_chart(chart_df.set_index('利率%')['掛單量'])
            
            # 清單
            st.subheader("📊 詳細掛單")
            list_df = df.head(10).copy()
            list_df['利率%'] = (list_df['利率']*100).map('{:.4f}%'.format)
            list_df['年化'] = (list_df['利率']*36500).map('{:.1f}%'.format)
            st.table(list_df[['利率%', '年化', '掛單量']])
        else:
            st.error("API 連線失敗，請重整頁面或稍後再試。")

st.title("💰 Bitfinex 智慧戰情室 V9.1")
c1, c2 = st.columns(2)
display_column(c1, "🇺🇸 USD (美金)", 'fUSD')
display_column(c2, "₮ USDT (泰達幣)", 'fUST')
time.sleep(15); st.rerun()