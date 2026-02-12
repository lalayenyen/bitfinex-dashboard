import streamlit as st
import ccxt
import time
import pandas as pd

# ==========================================
# V8.5 高勝率分析邏輯 (避開 K 線封鎖)
# ==========================================
SEARCH_CAP = 5000000 # 擴大掃描深度至 500 萬，尋找更具規模的牆
st.set_page_config(page_title="Bitfinex 智慧戰情室 V8.5", page_icon="💰", layout="wide")

@st.cache_resource
def init_exchange():
    return ccxt.bitfinex({'timeout': 20000, 'enableRateLimit': True})

bfx = init_exchange()

def get_market_data(symbol):
    try:
        raw_book = bfx.public_get_book_symbol_precision({'symbol': symbol, 'precision': 'P0', 'len': 100})
        asks = [{'利率': float(item[0]), '掛單量': float(item[3])} for item in raw_book if float(item[3]) > 0]
        asks.sort(key=lambda x: x['利率'])
        ticker = bfx.public_get_ticker_symbol({'symbol': symbol})
        return asks, abs(float(ticker[0])), abs(float(ticker[8])), abs(float(ticker[9]))
    except:
        return [], 0, 0, 0

def analyze_logic(asks, frr, h24_avg, h24_high):
    if not asks: return None
    df = pd.DataFrame(asks)
    df['累積量'] = df['掛單量'].cumsum()
    
    # 核心算法優化：只在 FRR 以上尋找具規模的「高勝率牆」
    # 如果全市場掛單都在 FRR 以下，則回退到 FRR
    valid_walls = df[df['利率'] >= frr].head(20) # 找 FRR 以上的前 20 檔
    if valid_walls.empty:
        best_wall = df.iloc[0] # 保底
    else:
        best_wall = valid_walls.loc[valid_walls['掛單量'].idxmax()]

    # 氛圍判斷
    if frr > h24_high * 0.9: sentiment, color = "🔥🔥 極度貪婪 (暴利期)", "#ff4b4b"
    elif frr > h24_avg * 1.1: sentiment, color = "🔥 市場火熱 (高於均價)", "#ffa500"
    else: sentiment, color = "☁️ 歲月靜好 (和平時期)", "#09ab3b"

    # 階梯建議 (加入高勝率修正)
    l1 = frr
    l2 = max(best_wall['利率'] - 0.00000001, frr) # 確保穩健單不低於 FRR
    l3 = max(h24_high, l2 * 1.3)
    
    return {
        'frr': frr, 'l1': l1, 'l2': l2, 'l3': l3,
        'sentiment': sentiment, 'color': color,
        'h24_avg': h24_avg, 'h24_high': h24_high,
        'best_wall': best_wall, 'full_df': df
    }

def display_column(col, title, symbol):
    with col:
        st.header(title)
        asks, frr, h24_avg, h24_high = get_market_data(symbol)
        if asks:
            res = analyze_logic(asks, frr, h24_avg, h24_high)
            
            # 1. 氛圍與指標
            st.markdown(f"""<div style="padding:15px; border-radius:10px; background-color:#f8f9fb; border-left: 5px solid {res['color']}; margin-bottom:20px;">
                <h3 style="margin:0; color:{res['color']}">{res['sentiment']}</h3>
                <code style="color:#666">FRR: {res['frr']*100:.4f}% | 24h高: {res['h24_high']*100:.4f}%</code>
            </div>""", unsafe_allow_html=True)
            
            m1, m2, m3 = st.columns(3)
            m1.metric("1.保守 (FRR)", f"{res['l1']*100:.4f}%", "成交率高")
            m2.metric("2.高勝率牆", f"{res['l2']*100:.4f}%", f"年{res['l2']*36500:.1f}%")
            m3.metric("3.釣魚暴擊", f"{res['l3']*100:.4f}%", "等待插針")

            # 2. 智慧分析文字 (修正邏輯)
            st.info(f"💡 **高勝率分析**：在 FRR 以上掃描發現，最大阻力位在 **{res['best_wall']['利率']*100:.4f}%**。若市場熱度上升，此價位成交機率最高。")

            # 3. 圖表 (修正 TypeError)
            st.subheader("🌊 資金深度分佈")
            chart_df = res['full_df'].head(20).copy()
            chart_df['利率(%)'] = chart_df['利率'] * 100
            # 確保使用 Series 傳遞，避免 DataFrame 欄位衝突
            st.bar_chart(chart_df.set_index('利率(%)')['掛單量'], color='#00d4ff')

            # 4. 詳細清單
            st.table(res['full_df'].head(8).assign(
                年化=lambda x: (x['利率']*36500).map('{:.2f}%'.format),
                利率=lambda x: (x['利率']*100).map('{:.4f}%'.format),
                金額=lambda x: x['掛單量'].map('{:,.0f}'.format)
            )[['利率', '年化', '金額']])
        else:
            st.warning("數據讀取中...")

# ==========================================
# 主介面 (解決對齊)
# ==========================================
st.title("💰 Bitfinex 智慧戰情室 V8.5")
c1, c2 = st.columns(2)
display_column(c1, "🇺🇸 USD (美金)", 'fUSD')
display_column(c2, "₮ USDT (泰達幣)", 'fUST')
time.sleep(10); st.rerun()