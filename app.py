import streamlit as st
import ccxt
import time
import pandas as pd

# ==========================================
# V8.6 功能全回歸版
# ==========================================
st.set_page_config(page_title="Bitfinex 智慧戰情室 V8.6", page_icon="💰", layout="wide")

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
        # [FRR, BID, ..., 24H_HIGH, 24H_LOW]
        return asks, abs(float(ticker[0])), abs(float(ticker[8])), abs(float(ticker[9]))
    except:
        return [], 0, 0, 0

def analyze_logic(asks, frr, h24_low, h24_high):
    if not asks: return None
    df = pd.DataFrame(asks)
    df['累積量'] = df['掛單量'].cumsum()
    avg_vol = df['掛單量'].mean()
    h24_avg = (h24_high + h24_low) / 2
    
    # 1. 氛圍判斷修正：修正截圖中的矛盾，確保參考 24h 高低點
    if frr >= h24_high * 0.95: sentiment, color = "🔥🔥 極度貪婪 (暴利期)", "#ff4b4b"
    elif frr >= h24_avg * 1.1: sentiment, color = "🔥 市場火熱 (高於均價)", "#ffa500"
    elif frr <= h24_avg * 0.9: sentiment, color = "🧊 市場冷清 (低於均價)", "#1c83e1"
    else: sentiment, color = "☁️ 歲月靜好 (和平時期)", "#09ab3b"

    # 2. 三大牆與策略
    top_walls = df.nlargest(3, '掛單量').sort_values('利率')
    rate_a = next((x['利率'] for x in asks if x['掛單量'] > avg_vol * 5), asks[0]['利率'])
    rate_b = next((x['利率'] for x, c in zip(asks, df['累積量']) if c >= 3000000), asks[-1]['利率'])
    rate_c = next((x['利率'] for x in asks if abs(x['利率']*10000 - round(x['利率']*10000)) < 0.05), None)

    # 3. 階梯建議 (實戰導向)
    l1 = frr
    # 穩健單找 FRR 以上最強的牆
    valid_walls = df[df['利率'] >= frr]
    l2 = valid_walls.nlargest(1, '掛單量').iloc[0]['利率'] if not valid_walls.empty else frr
    l3 = max(h24_high, l2 * 1.3) # 釣魚單參考 24h 最高成交價
    
    return {
        'frr': frr, 'l1': l1, 'l2': l2, 'l3': l3,
        'sentiment': sentiment, 'color': color,
        'h24_avg': h24_avg, 'h24_high': h24_high, 'h24_low': h24_low,
        'top_walls': top_walls, 'full_df': df,
        'strats': {'動態平均': rate_a, '深度累積': rate_b, '心理關卡': rate_c}
    }

def display_column(col, title, symbol):
    with col:
        st.header(title)
        asks, frr, h24_low, h24_high = get_market_data(symbol)
        if asks:
            res = analyze_logic(asks, frr, h24_low, h24_high)
            
            # --- 功能 2 & 3: 市場氛圍 + 數據量化 ---
            st.markdown(f"""<div style="padding:15px; border-radius:10px; background-color:#f8f9fb; border-left: 5px solid {res['color']};">
                <h3 style="margin:0; color:{res['color']}">{res['sentiment']}</h3>
                <div style="display:flex; justify-content:space-between; margin-top:10px;">
                    <span>🕊️ <b>和平基準:</b> {res['h24_avg']*100:.4f}%</span>
                    <span>🌊 <b>24h波濤:</b> {res['h24_high']*100:.4f}%</span>
                </div>
            </div>""", unsafe_allow_html=True)
            
            # --- 功能 4: 智慧階梯指標 ---
            st.write("")
            m1, m2, m3 = st.columns(3)
            m1.metric("1.保守 (30%)", f"{res['l1']*100:.4f}%", "FRR")
            m2.metric("2.高勝率牆", f"{res['l2']*100:.4f}%", f"年{res['l2']*36500:.1f}%")
            m3.metric("3.智慧釣魚", f"{res['l3']*100:.4f}%", "參考24h高點")

            # --- 找回消失的分析區塊 ---
            st.info(f"💡 **高勝率分析**：在 FRR 以上發現最強阻力位在 **{res['l2']*100:.4f}%**，建議掛單於此，兼顧機率與利潤。")
            
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("🔍 策略分析")
                for k, v in res['strats'].items():
                    st.write(f"**{k}:** {v*100:.4f}%" if v else f"**{k}:** 無訊號")
            with c2:
                st.subheader("🧱 三大資金牆")
                for _, r in res['top_walls'].iterrows():
                    st.write(f"🚩 {r['利率']*100:.4f}% ({r['掛單量']/1000:.1f}K)")

            # --- 深度分布圖 ---
            st.subheader("🌊 資金深度分佈")
            chart_df = res['full_df'].head(20).copy()
            chart_df['利率(%)'] = chart_df['利率'] * 100
            st.bar_chart(chart_df.set_index('利率(%)')['掛單量'], color='#00d4ff')

            # --- 詳細階梯式掛單建議表格 ---
            st.subheader("📋 階梯式掛單執行方案")
            plan_df = pd.DataFrame([
                {"階段": "1. 保守", "分配": "30%", "利率": f"{res['l1']*100:.5f}%", "年化": f"{res['l1']*36500:.2f}%"},
                {"階段": "2. 穩健", "分配": "30%", "利率": f"{res['l2']*100:.5f}%", "年化": f"{res['l2']*36500:.2f}%"},
                {"階段": "3. 釣魚", "分配": "40%", "利率": f"{res['l3']*100:.5f}%", "年化": f"{res['l3']*36500:.2f}%"}
            ])
            st.table(plan_df)
            
        else:
            st.warning("等待 API 回傳...")

# ==========================================
# 主介面
# ==========================================
st.title("💰 Bitfinex 智慧戰情室 V8.6")
st.caption(f"最後更新: {time.strftime('%H:%M:%S')} | 功能完整回歸版")
col_a, col_b = st.columns(2)
display_column(col_a, "🇺🇸 USD (美金)", 'fUSD')
display_column(col_b, "₮ USDT (泰達幣)", 'fUST')
time.sleep(10); st.rerun()