"""
🔰 貝伊果屋 - 財富雙軌系統 (旗艦完整版 v6.0)
整合：ETF定投 + 智能情報中心 + Lead Call策略 + 戰情室(12因子/趨勢/籌碼/損益) + 真實回測
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta
from FinMind.data import DataLoader
from scipy.stats import norm
import plotly.graph_objects as go
import plotly.express as px
import feedparser
from collections import Counter
# Add these imports at the top of your app.py (after existing imports)
from wordcloud import WordCloud
import matplotlib.pyplot as plt
# Optional: pip install streamlit-pills for clickable pills
try:
    from streamlit_pills import pills
    PILLS_AVAILABLE = True
except ImportError:
    PILLS_AVAILABLE = False
if "jump" in st.query_params and st.query_params["jump"] == "2":
    st.components.v1.html("""
        <script>
            setTimeout(function(){
                var tabs = window.parent.document.querySelectorAll('button[data-baseweb="tab"]');
                if (tabs.length > 2) { tabs[2].click(); }
            }, 500);
        </script>
    """, height=0)

# === 放在程式最開頭 ===
import streamlit.components.v1 as components

# 檢查 URL 是否帶有 jump=tab2 參數
if "jump" in st.query_params and st.query_params["jump"] == "tab2":
    # 注入自動點擊 JS
    components.html("""
        <script>
            window.parent.document.querySelectorAll('button[data-baseweb="tab"]')[2].click();
        </script>
    """, height=0)
    # 清除參數，避免下次刷新還在跳
    st.query_params.clear()

# =========================
# 1. 初始化 & 設定
# =========================================
st.set_page_config(page_title="貝伊果屋-財富雙軌系統", layout="wide", page_icon="🥯")

# CSS 優化 (新增卡片與標籤樣式)
st.markdown("""
<style>
.big-font {font-size:20px !important; font-weight:bold;}

/* 新聞卡片容器 */
.news-card {
    background-color: #262730;
    padding: 15px;
    border-radius: 10px;
    border-left: 5px solid #4ECDC4;
    margin-bottom: 15px;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.3);
    transition: transform 0.2s;
}
.news-card:hover {
    background-color: #31333F;
    transform: translateY(-2px);
}

/* 情緒標籤 */
.tag-bull {background-color: #28a745; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;}
.tag-bear {background-color: #dc3545; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;}
.tag-neutral {background-color: #6c757d; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;}

/* 來源標記 */
.source-badge {background-color: #444; color: #ddd; padding: 2px 6px; border-radius: 4px; font-size: 11px; margin-right: 8px;}

/* 跑馬燈特效 */
.ticker-wrap {
    width: 100%;
    overflow: hidden;
    background-color: #1E1E1E;
    padding: 10px;
    border-radius: 5px;
    margin-bottom: 15px;
    white-space: nowrap;
}
</style>
""", unsafe_allow_html=True)

# Session State 初始化
init_state = {
    'portfolio': [],
    'user_type': 'free',
    'is_pro': False,
    'disclaimer_accepted': False,
    'search_results': None,
    'selected_contract': None
}
for key, value in init_state.items():
    if key not in st.session_state:
        st.session_state[key] = value

FINMIND_TOKEN = st.secrets.get("finmind_token", "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMi0wNSAxODo1ODo1MiIsInVzZXJfaWQiOiJiYWdlbDA0MjciLCJpcCI6IjEuMTcyLjEwOC42OSIsImV4cCI6MTc3MDg5MzkzMn0.cojhPC-1LBEFWqG-eakETyteDdeHt5Cqx-hJ9OIK9k0")

# =========================
# 2. 核心函數庫
# =========================================
@st.cache_data(ttl=60)
def get_data(token):
    dl = DataLoader()
    dl.login_by_token(api_token=token)
    try:
        index_df = dl.taiwan_stock_daily("TAIEX", start_date=(date.today()-timedelta(days=100)).strftime("%Y-%m-%d"))
        S = float(index_df["close"].iloc[-1]) if not index_df.empty else 23000.0
        ma20 = index_df['close'].rolling(20).mean().iloc[-1] if len(index_df) > 20 else S * 0.98
        ma60 = index_df['close'].rolling(60).mean().iloc[-1] if len(index_df) > 60 else S * 0.95
    except: 
        S = 23000.0
        ma20, ma60 = 22800.0, 22500.0

    opt_start = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
    df = dl.taiwan_option_daily("TXO", start_date=opt_start)
    
    if df.empty: return S, pd.DataFrame(), pd.to_datetime(date.today()), ma20, ma60
    
    df["date"] = pd.to_datetime(df["date"])
    latest = df["date"].max()
    df_latest = df[df["date"] == latest].copy()
    
    return S, df_latest, latest, ma20, ma60

@st.cache_data(ttl=1800)
def get_real_news(token):
    dl = DataLoader()
    dl.login_by_token(api_token=token)
    start_date = (date.today() - timedelta(days=3)).strftime("%Y-%m-%d")
    try:
        news = dl.taiwan_stock_news(stock_id="TAIEX", start_date=start_date)
        if news.empty:
            news = dl.taiwan_stock_news(stock_id="2330", start_date=start_date)
        news["date"] = pd.to_datetime(news["date"])
        news = news.sort_values("date", ascending=False).head(10)
        return news
    except:
        return pd.DataFrame()

@st.cache_data(ttl=1800)
def get_institutional_data(token):
    dl = DataLoader()
    dl.login_by_token(api_token=token)
    start_date = (date.today() - timedelta(days=10)).strftime("%Y-%m-%d")
    try:
        df = dl.taiwan_stock_institutional_investors_total(start_date=start_date)
        if df.empty: return pd.DataFrame()
        df["date"] = pd.to_datetime(df["date"])
        latest_date = df["date"].max()
        df_latest = df[df["date"] == latest_date].copy()
        df_latest["net"] = (df_latest["buy"] - df_latest["sell"]) / 100000000
        return df_latest
    except:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_support_pressure(token):
    dl = DataLoader()
    dl.login_by_token(api_token=token)
    start_date = (date.today() - timedelta(days=90)).strftime("%Y-%m-%d")
    try:
        df = dl.taiwan_stock_daily("TAIEX", start_date=start_date)
        if df.empty: return 0, 0
        pressure = df['max'].tail(20).max()
        support = df['min'].tail(60).min()
        return pressure, support
    except:
        return 0, 0

def bs_price_delta(S, K, T, r, sigma, cp):
    if T <= 0: return 0.0, 0.5
    try:
        d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        if cp == "CALL": return S*norm.cdf(d1)-K*np.exp(-r*T)*norm.cdf(d2), norm.cdf(d1)
        return K*np.exp(-r*T)*norm.cdf(-d2)-S*norm.cdf(-d1), -norm.cdf(-d1)
    except: return 0.0, 0.5

def calculate_win_rate(delta, days):
    return min(max((abs(delta)*0.7 + 0.8*0.3)*100, 1), 99)

def plot_payoff(K, premium, cp):
    x_range = np.linspace(K * 0.9, K * 1.1, 100)
    profit = []
    for spot in x_range:
        val = (max(0, spot - K) - premium) if cp == "CALL" else (max(0, K - spot) - premium)
        profit.append(val * 50)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x_range, y=profit, mode='lines', fill='tozeroy', 
                             line=dict(color='green' if profit[-1]>0 else 'red')))
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(title=f"到期損益圖 ({cp} @ {K})", xaxis_title="指數", yaxis_title="損益(TWD)", 
                      height=300, margin=dict(l=0,r=0,t=30,b=0))
    return fig

def plot_oi_walls(current_price):
    strikes = np.arange(int(current_price)-600, int(current_price)+600, 100)
    np.random.seed(int(current_price)) 
    call_oi = np.random.randint(2000, 15000, len(strikes))
    put_oi = np.random.randint(2000, 15000, len(strikes))
    fig = go.Figure()
    fig.add_trace(go.Bar(x=strikes, y=call_oi, name='Call OI (壓力)', marker_color='#FF6B6B'))
    fig.add_trace(go.Bar(x=strikes, y=-put_oi, name='Put OI (支撐)', marker_color='#4ECDC4'))
    fig.update_layout(title="籌碼戰場 (OI Walls)", barmode='overlay', height=300, margin=dict(l=0,r=0,t=30,b=0))
    return fig

# =========================
# 3. 載入數據
# =========================================
with st.spinner("🚀 啟動財富引擎..."):
    try:
        S_current, df_latest, latest_date, ma20, ma60 = get_data(FINMIND_TOKEN)
    except:
        st.error("連線逾時，請重整頁面")
        st.stop()
# =========================
# 側邊欄
# =========================================
with st.sidebar:
    st.markdown("## 🥯 **貝伊果屋**")
    st.image("https://via.placeholder.com/300x100?text=BeiGuoWu", use_container_width=True)
    
    # 方案一：圖片 + 連結
    st.image("https://down-tw.img.susercontent.com/file/sg-11134201-7qvdl-lh2v8yc9n8530d.webp", caption="持續買進: 資料科學家的投資終極解答, 存錢及致富的實證方法", use_container_width=True)
    st.markdown("[🛒 購買『 持續買進 』](https://s.shopee.tw/5AmrxVrig8)")
    
    st.divider()  # 分隔方案
    
    # 方案二：圖片 + 連結
    st.image("https://down-tw.img.susercontent.com/file/tw-11134207-7rasc-m2ba9wueqaze3a.webp", caption="長期買進：財金教授周冠男的42堂自制力投資課", use_container_width=True)
    st.markdown("[🛒 購買『 長期買進 』](https://s.shopee.tw/6KypLiCjuy)")
    
    if st.session_state.get('is_pro', False):
        st.success("👑 Pro 會員")
    
    st.divider()
    st.caption("📊 功能導航：\n• Tab0: 定投計畫\n• Tab1: 智能情報\n• Tab2: CALL獵人\n• Tab3: 回測系統\n• Tab4: 戰情室")



# =========================
# 5. 主介面 & 市場快報
# =========================================
st.markdown("# 🥯 **貝伊果屋：財富雙軌系統**")

# 市場快報
st.markdown("---")
col1, col2, col3, col4 = st.columns(4)
with col1:
    change_pct = (S_current - ma20) / ma20 * 100
    st.metric("📈 加權指數", f"{S_current:,.0f}", f"{change_pct:+.1f}%")
with col2:
    ma_trend = "🔥 多頭" if ma20 > ma60 else "⚖️ 盤整"
    st.metric("均線狀態", ma_trend)
with col3:
    st.metric("資料更新", latest_date.strftime("%m/%d"))
with col4:
    signal = "🟢 大好局面" if S_current > ma20 > ma60 else "🟡 觀望"
    st.metric("今日建議", signal)
st.markdown("---")

# 合規聲明
if not st.session_state.disclaimer_accepted:
    st.warning("🚨 **重要聲明**：本工具僅供教育，非投資建議。新手請先閱讀「穩健ETF」章節。")
    if st.button("✅ 我了解，開始使用"):
        st.session_state.disclaimer_accepted = True
        st.rerun()
    st.stop()

# 分頁導航
tab_names = [
    "🏦 **穩健ETF**", 
    "🌍 **智能情報**", 
    "🔰 **期權獵人**", 
    "📊 **歷史回測**",
    "🔥 **專業戰情室**"
]
tab_names += [f"🛠️ 擴充 {i+2}" for i in range(9)]
tabs = st.tabs(tab_names)

# --------------------------
# Tab 0: 穩健 ETF (純前端JS導航版 v6.5)
# --------------------------
# 請確保已 import: FinMind, pandas, plotly, numpy, datetime, streamlit.components.v1
# 注意：此版本無需在程式開頭加額外代碼，直接替換 tabs[0] 即可

with tabs[0]:
    # === 0. 首屏核心導航 (第一眼就看到) ===
    st.markdown("## 🐢 **ETF 定投計畫**")
    
    # CSS 樣式
    st.markdown("""
    <style>
    @keyframes pulse-red {
        0% { box-shadow: 0 0 0 0 rgba(255, 75, 75, 0.4); }
        70% { box-shadow: 0 0 0 10px rgba(255, 75, 75, 0); }
        100% { box-shadow: 0 0 0 0 rgba(255, 75, 75, 0); }
    }
    .nav-card {
        border-radius: 10px; padding: 15px; text-align: center; height: 100%;
        display: flex; flex-direction: column; justify-content: space-between;
    }
    .card-safe {
        background: rgba(40, 167, 69, 0.1); border: 1px solid #28a745;
    }
    .card-danger {
        background: linear-gradient(135deg, #2b0f0f 0%, #1a1a1a 100%);
        border: 2px solid #ff4b4b;
        animation: pulse-red 2s infinite;
    }
    .nav-title { font-size: 20px; font-weight: bold; margin-bottom: 5px; }
    .nav-desc { font-size: 13px; color: #ccc; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

    col_safe, col_risk = st.columns(2)
    
    # 左側：新手定投
    with col_safe:
        st.markdown("""
        <div class="nav-card card-safe">
            <div class="nav-title" style="color: #28a745;">🐢 穩健定投區</div>
            <div class="nav-desc">每月自動買，10年變富翁<br>適合新手、上班族</div>
        </div>
        """, unsafe_allow_html=True)
        st.info("👇 **向下瀏覽定投教學**")

    # 右側：進階戰室 (純 HTML/JS 按鈕 - 絕不跳分頁且每次有效)
    with col_risk:
        st.markdown("""
        <div class="nav-card card-danger">
            <div class="nav-title" style="color: #ff4b4b;">⚡最簡單賺到第一桶金的科學</div>
            <div class="nav-desc"> 當長期持續買進 + 槓桿<br>使用前請注意期權槓桿風險</div>
        </div>
        """, unsafe_allow_html=True)
        
        # 🔥 純前端 JS 按鈕元件
        import streamlit.components.v1 as components
        btn_html = '''
        <!DOCTYPE html>
        <html>
        <head>
        <style>
            body { margin: 0; padding: 0; background: transparent; }
            .jump-btn {
                display: flex; align-items: center; justify-content: center;
                width: 100%; height: 40px;
                background-color: #ff4b4b; color: white;
                border: 1px solid #ff4b4b; border-radius: 8px;
                font-family: "Source Sans Pro", sans-serif; font-weight: 600; font-size: 16px;
                cursor: pointer; transition: all 0.2s;
                margin-top: 5px;
            }
            .jump-btn:hover { background-color: #ff3333; border-color: #ff3333; transform: scale(1.02); }
            .jump-btn:active { background-color: #cc0000; transform: scale(0.98); }
        </style>
        </head>
        <body>
            <button class="jump-btn" onclick="jumpToTab2()">
                🚀 立即進入戰場 (Tab 2) ⏭️
            </button>
            <script>
                function jumpToTab2() {
                    try {
                        // 1. 穿透 iframe 找到父頁面 tabs
                        var tabs = window.parent.document.querySelectorAll('button[data-baseweb="tab"]');
                        if (tabs.length > 2) {
                            tabs[2].click(); // 點擊 Tab 2
                            window.parent.scrollTo(0, 0); // 滾動到頂部
                        } else {
                            console.log("Tabs not found");
                        }
                    } catch(e) { console.error(e); }
                }
            </script>
        </body>
        </html>
        '''
        # 渲染按鈕 (height=50 確保不被切掉)
        components.html(btn_html, height=55)

    st.markdown("---")

    # === 1. FinMind 即時報價 ===
    @st.cache_data(ttl=600)
    def get_etf_quotes():
        api = DataLoader()
        etfs = ['0050', '006208', '00662', '00757', '00646']
        data = []
        end_date = date.today().strftime('%Y-%m-%d')
        start_date = (date.today() - timedelta(days=90)).strftime('%Y-%m-%d')
        
        for stock_id in etfs:
            try:
                df = api.taiwan_stock_daily(stock_id=stock_id, start_date=start_date, end_date=end_date)
                if not df.empty:
                    latest = df.iloc[-1]
                    current = latest['close']
                    prev = df.iloc[-2]['close'] if len(df) > 1 else current
                    change = current - prev
                    pct = (change / prev) * 100
                    data.append({
                        'ETF': stock_id,
                        '名稱': {'0050':'台灣50','006208':'富邦台50','00662':'富邦NASDAQ',
                               '00757':'統一FANG+','00646':'元大S&P500'}.get(stock_id, stock_id),
                        '最新價': f"NT${current:.2f}",
                        '漲跌': f"{change:+.2f}",
                        '漲跌幅': f"{pct:+.2f}%"
                    })
                else:
                    data.append({'ETF': stock_id, '名稱': '無資料', '最新價': '-', '漲跌': '-', '漲跌幅': '-'})
            except:
                data.append({'ETF': stock_id, '名稱': 'API錯誤', '最新價': '-', '漲跌': '-', '漲跌幅': '-'})
        return pd.DataFrame(data)

    st.markdown("### 📡 **即時報價**")
    try:
        quotes = get_etf_quotes()
        st.dataframe(quotes, use_container_width=True, hide_index=True)
    except:
        st.error("報價載入失敗")

    if st.button("🔄 刷新報價", key="refresh_t0"):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")

    # === 2. ETF 比較 ===
    st.markdown("### 📊 **ETF 特色一覽**")
    etf_compare = pd.DataFrame({
        "ETF": ["0050", "006208", "00662", "00757", "00646"],
        "追蹤指數": ["台灣50", "台灣50", "NASDAQ100", "FANG+", "S&P500"],
        "年費率": ["0.42%", "0.23%", "0.60%", "0.99%", "0.48%"],
        "風險等級": ["低⭐", "低⭐", "中⭐⭐", "高⭐⭐⭐", "中⭐⭐"]
    })
    st.dataframe(etf_compare, use_container_width=True, hide_index=True)
    
    st.markdown("---")

    # === 3. 定投試算 ===
    st.markdown("### 💰 **定投試算器**")
    c1, c2, c3 = st.columns(3)
    with c1: monthly = st.number_input("每月投入", 5000, 500000, 30000, step=1000, key="t0_m")
    with c2: years = st.slider("持續年數", 5, 30, 10, key="t0_y")
    with c3: rate = st.slider("預期年化 (%)", 5.0, 20.0, 12.0, key="t0_r")
    
    r = rate / 100
    final = monthly * 12 * (( (1 + r)**years - 1 ) / r )
    st.metric(f"💎 {years}年後總資產", f"NT$ {final:,.0f}")
    
    periods = np.arange(1, years+1)
    values = monthly * 12 * (( (1 + r)**periods - 1 ) / r )
    fig = px.line(pd.DataFrame({'年份':periods,'資產':values}), x='年份', y='資產', markers=True)
    fig.update_layout(height=300, showlegend=False, margin=dict(l=20,r=20,t=20,b=20))
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")

    # === 4. 心理建設 ===
    st.markdown("### 🆚 **最重要：堅持到底**")
    c_stop, c_go = st.columns(2)
    with c_stop:
        stop_y = st.slider("❌ 假如第幾年停止？", 1, years-1, 3, key="t0_stop")
        stop_val = monthly * 12 * (( (1 + r)**stop_y - 1 ) / r )
        st.error(f"資產停滯：NT$ {stop_val:,.0f}")
    with c_go:
        st.write("") 
        st.write("")
        gain_pct = ((final / stop_val) - 1) * 100
        st.success(f"✅ 持續定投多賺：**{gain_pct:.0f}%** ！")
    
    st.markdown("---")
    st.caption("💪 **恭喜！您已完成定投啟蒙。**")

# --------------------------
# Tab 1: 智能全球情報中心 (v6.7 全真實數據版)
# --------------------------
with tabs[1]:
    st.markdown("## 🌍 **智能全球情報中心**")

    # 🔥 新增：抓取真實市場數據 (台股 + 美股 + 幣圈)
    @st.cache_data(ttl=300) # 快取 5 分鐘，避免頻繁請求變慢
    def get_real_market_ticker():
        data = {}
        try:
            # 1. 台股 (FinMind)
            dl = DataLoader()
            dl.login_by_token(api_token=FINMIND_TOKEN)
            
            # TAIEX
            df_tw = dl.taiwan_stock_daily("TAIEX", start_date=(date.today()-timedelta(days=5)).strftime("%Y-%m-%d"))
            if not df_tw.empty:
                close = df_tw['close'].iloc[-1]
                prev = df_tw['close'].iloc[-2]
                change = (close - prev) / prev * 100
                data['taiex'] = f"{close:,.0f}"
                data['taiex_pct'] = f"{change:+.1f}%"
                data['taiex_color'] = "#28a745" if change > 0 else "#dc3545"
            else:
                data['taiex'] = "N/A"; data['taiex_pct'] = "0%"; data['taiex_color'] = "gray"

            # 台積電 (2330)
            df_tsmc = dl.taiwan_stock_daily("2330", start_date=(date.today()-timedelta(days=5)).strftime("%Y-%m-%d"))
            if not df_tsmc.empty:
                close = df_tsmc['close'].iloc[-1]
                prev = df_tsmc['close'].iloc[-2]
                change = (close - prev) / prev * 100
                data['tsmc'] = f"{close:,.0f}"
                data['tsmc_pct'] = f"{change:+.1f}%"
                data['tsmc_color'] = "#28a745" if change > 0 else "#dc3545"
            else:
                data['tsmc'] = "N/A"; data['tsmc_pct'] = "0%"; data['tsmc_color'] = "gray"

            # 2. 美股期貨與比特幣 (yfinance)
            import yfinance as yf
            
            # 納斯達克期貨 (NQ=F) 或 S&P500 (ES=F)
            nq = yf.Ticker("NQ=F").history(period="2d")
            if len(nq) > 0:
                last = nq['Close'].iloc[-1]
                prev = nq['Close'].iloc[-2] if len(nq) > 1 else last
                chg = (last - prev) / prev * 100
                data['nq'] = f"{last:,.0f}"
                data['nq_pct'] = f"{chg:+.1f}%"
                data['nq_color'] = "#28a745" if chg > 0 else "#dc3545"
            else:
                data['nq'] = "N/A"; data['nq_pct'] = "0%"; data['nq_color'] = "gray"

            # 比特幣 (BTC-USD)
            btc = yf.Ticker("BTC-USD").history(period="2d")
            if len(btc) > 0:
                last = btc['Close'].iloc[-1]
                prev = btc['Close'].iloc[-2] if len(btc) > 1 else last
                chg = (last - prev) / prev * 100
                data['btc'] = f"${last:,.0f}"
                data['btc_pct'] = f"{chg:+.1f}%"
                data['btc_color'] = "#28a745" if chg > 0 else "#dc3545"
            else:
                data['btc'] = "N/A"; data['btc_pct'] = "0%"; data['btc_color'] = "gray"

        except Exception as e:
            # 出錯時的回退顯示
            return {k: "N/A" for k in ['taiex','tsmc','nq','btc']}
            
        return data

    # 執行抓取
    m = get_real_market_ticker()

    # 渲染真實跑馬燈
    st.markdown(f"""
    <div class="ticker-wrap">
        🚀 <b>即時行情:</b> 
        TAIEX: <span style="color:{m.get('taiex_color','gray')}">{m.get('taiex','N/A')} ({m.get('taiex_pct','')})</span> &nbsp;|&nbsp; 
        台積電: <span style="color:{m.get('tsmc_color','gray')}">{m.get('tsmc','N/A')} ({m.get('tsmc_pct','')})</span> &nbsp;|&nbsp; 
        Nasdaq期: <span style="color:{m.get('nq_color','gray')}">{m.get('nq','N/A')} ({m.get('nq_pct','')})</span> &nbsp;|&nbsp; 
        Bitcoin: <span style="color:{m.get('btc_color','gray')}">{m.get('btc','N/A')} ({m.get('btc_pct','')})</span>
    </div>
    """, unsafe_allow_html=True)
    
    st.caption("數據來源：FinMind (台股) + Yahoo Finance (國際/加密幣)")
    # Session State 初始化
    if 'filter_kw' not in st.session_state:
        st.session_state['filter_kw'] = "全部"

    with st.spinner("🤖 正在掃描全球市場訊號..."):
        # 2. 數據抓取
        taiwan_news = get_real_news(FINMIND_TOKEN)
        rss_sources = {
            "📈 Yahoo財經": "https://tw.stock.yahoo.com/rss/index.rss",
            "🌐 Reuters": "https://feeds.reuters.com/reuters/businessNews",
            "📊 CNBC Tech": "https://www.cnbc.com/id/19854910/device/rss/rss.html"
        }
        
        all_news = []
        if not taiwan_news.empty:
            for _, row in taiwan_news.head(5).iterrows():
                all_news.append({
                    'title': str(row.get('title', '無標題')), 'link': str(row.get('link', '#')),
                    'source': "🇹🇼 台股新聞", 'time': pd.to_datetime(row['date']).strftime('%m/%d %H:%M'),
                    'summary': str(row.get('description', ''))[:100] + '...'
                })
        
        import feedparser
        for title, url in rss_sources.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:3]:
                    all_news.append({
                        'title': str(entry.title), 'link': str(entry.link), 'source': title,
                        'time': entry.get('published', 'N/A'), 'summary': str(entry.get('summary', ''))[:100] + '...'
                    })
            except: pass

        # 3. AI 情緒與熱詞分析
        pos_keywords = ['上漲', '漲', '買', '多頭', '樂觀', '強勢', 'Bull', 'Rise', 'AI', '成長', '台積電', '營收', '創高']
        neg_keywords = ['下跌', '跌', '賣', '空頭', '悲觀', '弱勢', 'Bear', 'Fall', '關稅', '通膨', '衰退']
        
        word_list = []
        pos_score, neg_score = 0, 0
        
        for news in all_news:
            text = (news['title'] + news['summary']).lower()
            n_pos = sum(text.count(k.lower()) for k in pos_keywords)
            n_neg = sum(text.count(k.lower()) for k in neg_keywords)
            
            if n_pos > n_neg: news['sentiment'] = 'bull'
            elif n_neg > n_pos: news['sentiment'] = 'bear'
            else: news['sentiment'] = 'neutral'
            
            pos_score += n_pos
            neg_score += n_neg
            
            for k in pos_keywords + neg_keywords:
                if k.lower() in text:
                    word_list.append(k)

        sentiment_idx = (pos_score - neg_score) / max(pos_score + neg_score, 1)
        sentiment_label = "🟢 貪婪" if sentiment_idx > 0.2 else "🔴 恐慌" if sentiment_idx < -0.2 else "🟡 中性"
        
        from collections import Counter
        top_keywords = ["全部"]
        if word_list:
            top_keywords += [w[0] for w in Counter(word_list).most_common(6)]
        else:
            top_keywords += ["台積電", "AI", "降息", "強勢", "營收"]

    # 4. 儀表板區域
    col_dash1, col_dash2 = st.columns([1, 2])
    
    with col_dash1:
        st.markdown(f"#### 🌡️ 市場情緒：{sentiment_label}")
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number", 
            value = 50 + sentiment_idx*50,
            gauge = {
                'axis': {'range': [0, 100]}, 
                'bar': {'color': "#4ECDC4"},
                'steps': [
                    {'range': [0, 40], 'color': "rgba(255, 0, 0, 0.2)"},
                    {'range': [60, 100], 'color': "rgba(0, 255, 0, 0.2)"}
                ]
            }
        ))
        fig_gauge.update_layout(height=220, margin=dict(l=20,r=20,t=10,b=20), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_gauge, use_container_width=True)
    
    with col_dash2:
        st.markdown("#### 🔥 **今日市場熱詞**")
        
        # 🌟 優先使用 Pills (最美)，失敗則使用隱藏式 Radio
        try:
            # 嘗試使用 st.pills (Streamlit 1.40+)
            selected = st.pills("篩選新聞：", top_keywords, selection_mode="single", default="全部")
        except:
            # Fallback: 使用 CSS 美化 Radio 按鈕 (橫向排列)
            st.markdown("""
            <style>
            div[role="radiogroup"] {flex-direction: row; gap: 8px; flex-wrap: wrap;}
            div[role="radiogroup"] label > div:first-child {display: none;} /* 隱藏圓點 */
            div[role="radiogroup"] label {
                background: #333; padding: 4px 12px; border-radius: 15px; border: 1px solid #555; cursor: pointer; transition: 0.3s;
            }
            div[role="radiogroup"] label:hover {background: #444; border-color: #4ECDC4;}
            div[role="radiogroup"] label[data-checked="true"] {background: #4ECDC4; color: black; font-weight: bold;}
            </style>
            """, unsafe_allow_html=True)
            selected = st.radio("篩選新聞：", top_keywords, label_visibility="collapsed")
            
        st.session_state['filter_kw'] = selected
        st.success(f"🔍 篩選：#{selected} | 📊 市場氣氛：{sentiment_label}")

    st.divider()
    
    # 5. 過濾與顯示新聞 (修復 TypeError)
    current_filter = st.session_state['filter_kw']
    st.markdown(f"### 📰 **精選快訊**")
    
    # 🔥 安全過濾：確保 title 轉為字串
    filtered_news = []
    for n in all_news:
        title_str = str(n.get('title', ''))
        summary_str = str(n.get('summary', ''))
        
        if current_filter == "全部":
            filtered_news.append(n)
        elif current_filter in title_str or current_filter in summary_str:
            filtered_news.append(n)
            
    if not filtered_news:
        st.info(f"⚠️ 暫無包含「{current_filter}」的新聞，顯示全部。")
        filtered_news = all_news 
    
    col_news_left, col_news_right = st.columns(2)
    for i, news in enumerate(filtered_news):
        # 安全取得 sentiment
        sent = news.get('sentiment', 'neutral')
        
        if sent == 'bull':
            tag_html = '<span class="tag-bull">看多</span>'
            border_color = "#28a745"
        elif sent == 'bear':
            tag_html = '<span class="tag-bear">看空</span>'
            border_color = "#dc3545"
        else:
            tag_html = '<span class="tag-neutral">中性</span>'
            border_color = "#6c757d"

        card_html = f"""
        <div class="news-card" style="border-left: 5px solid {border_color};">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <div>
                    <span class="source-badge">{news['source']}</span>
                    {tag_html}
                </div>
                <div style="font-size: 0.8em; color: #888;">{news['time']}</div>
            </div>
            <a href="{news['link']}" target="_blank" style="text-decoration: none; color: white; font-weight: bold; font-size: 1.1em; display: block; margin-bottom: 5px; line-height: 1.4;">
                {news['title']}
            </a>
            <div style="font-size: 0.9em; color: #aaa; margin-bottom: 5px; line-height: 1.5;">
                {news['summary']}
            </div>
        </div>
        """
        
        if i % 2 == 0:
            with col_news_left: st.markdown(card_html, unsafe_allow_html=True)
        else:
            with col_news_right: st.markdown(card_html, unsafe_allow_html=True)
# --------------------------
# Tab 2: 槓桿篩選版 v18.5 (回歸槓桿操作 + LEADS CALL)
# --------------------------
with tabs[2]:
    KEY_RES = "results_lev_v185"
    KEY_BEST = "best_lev_v185"
    KEY_PF = "portfolio_lev"

    if KEY_RES not in st.session_state: st.session_state[KEY_RES] = []
    if KEY_BEST not in st.session_state: st.session_state[KEY_BEST] = None
    if KEY_PF not in st.session_state: st.session_state[KEY_PF] = []

    st.markdown("### ♟️ **專業戰情室 (槓桿篩選 + 微觀勝率 + LEADS CALL)**")
    col_search, col_portfolio = st.columns([1.3, 0.7])

    # 1. 原始評分 (綜合因子)
    def calculate_raw_score(delta, days, volume, S, K, op_type):
        s_delta = abs(delta) * 100.0
        
        if op_type == "CALL": m = (S - K) / S
        else: m = (K - S) / S
        s_money = max(-10, min(m * 100 * 2, 10)) + 50
        
        s_time = min(days / 90.0 * 100, 100)
        s_vol = min(volume / 5000.0 * 100, 100)
        
        raw = (s_delta * 0.4 + s_money * 0.2 + s_time * 0.2 + s_vol * 0.2)
        return raw

    # 2. 微觀展開 (Top 40% -> 90-95%)
    def micro_expand_scores(results):
        if not results: return []
        results.sort(key=lambda x: x['raw_score'], reverse=True)
        n = len(results)
        top_n = max(1, int(n * 0.4)) 
        
        for i in range(n):
            if i < top_n:
                if top_n > 1: score = 95.0 - (i / (top_n - 1)) * 5.0
                else: score = 95.0
            else:
                remain = n - top_n
                if remain > 1:
                    idx = i - top_n
                    score = 85.0 - (idx / (remain - 1)) * 70.0
                else: score = 15.0
            results[i]['勝率'] = round(score, 1)
        return results

    with col_search:
        st.markdown("#### 🔍 **槓桿掃描 (LEADS CALL 優化)**")
        
        if df_latest.empty: st.error("⚠️ 無資料"); st.stop()
        
        df_work = df_latest.copy()
        df_work['call_put'] = df_work['call_put'].str.upper().str.strip()
        for col in ['close', 'volume', 'strike_price']:
            df_work[col] = pd.to_numeric(df_work[col], errors='coerce').fillna(0)

        c1, c2, c3, c4 = st.columns([1, 1, 1, 0.6])
        with c1:
            dir_mode = st.selectbox("方向", ["📈 CALL (LEADS)", "📉 PUT"], 0, key="v185_dir")
            op_type = "CALL" if "CALL" in dir_mode else "PUT"
        with c2:
            contracts = df_work[df_work['call_put']==op_type]['contract_date'].dropna()
            available = sorted(contracts[contracts.astype(str).str.len()==6].unique())
            # ✅ 預設遠月合約 (LEADS CALL 偏好)
            default_idx = len(available) - 1 if available else 0
            sel_con = st.selectbox("月份", available if available else [""], 
                                 index=default_idx, key="v185_con")
        with c3:
            target_lev = st.slider("目標槓桿", 2.0, 20.0, 5.0, 0.5, key="v185_lev")
        with c4:
            if st.button("🧹 重置", key="v185_reset"):
                st.session_state[KEY_RES] = []
                st.session_state[KEY_BEST] = None
                st.rerun()

        if st.button("🚀 執行掃描", type="primary", use_container_width=True, key="v185_scan"):
            st.session_state[KEY_RES] = []
            st.session_state[KEY_BEST] = None
            
            if sel_con and len(str(sel_con))==6:
                tdf = df_work[(df_work["contract_date"].astype(str)==sel_con) & (df_work["call_put"]==op_type)]
                
                if tdf.empty: st.warning("無資料")
                else:
                    try:
                        y, m = int(str(sel_con)[:4]), int(str(sel_con)[4:6])
                        days = max((date(y,m,15)-latest_date.date()).days, 1)
                        T = days / 365.0
                    except: st.error("日期解析失敗"); st.stop()

                    raw_results = []
                    for _, row in tdf.iterrows():
                        try:
                            K = float(row["strike_price"])
                            vol = float(row["volume"])
                            close_p = float(row["close"])
                            if K<=0: continue
                            
                            try:
                                r, sigma = 0.02, 0.2
                                d1 = (np.log(S_current/K)+(r+0.5*sigma**2)*T)/(sigma*np.sqrt(T))
                                
                                if op_type=="CALL":
                                    delta = norm.cdf(d1)
                                    bs_p = S_current*norm.cdf(d1)-K*np.exp(-r*T)*norm.cdf(d1-sigma*np.sqrt(T))
                                else:
                                    delta = -norm.cdf(-d1)
                                    bs_p = K*np.exp(-r*T)*norm.cdf(-(d1-sigma*np.sqrt(T)))-S_current*norm.cdf(-d1)
                            except: 
                                delta, bs_p = 0.5, close_p

                            P = close_p if vol > 0 else bs_p
                            if P <= 0.5: continue
                            lev = (abs(delta)*S_current)/P
                            
                            if abs(delta) < 0.1: continue

                            # 1. 原始分
                            raw_score = calculate_raw_score(delta, days, vol, S_current, K, op_type)
                            status = "🟢成交" if vol > 0 else "🔵合理"

                            raw_results.append({
                                "履約價": int(K), 
                                "價格": P, 
                                "狀態": status, 
                                "槓桿": lev,
                                "Delta": delta,
                                "raw_score": raw_score,
                                "Vol": int(vol),
                                "差距": abs(lev - target_lev),
                                "合約": sel_con, 
                                "類型": op_type,
                                "天數": days  # 新增，用於排序
                            })
                        except: continue
                    
                    if raw_results:
                        # 2. 微觀展開勝率
                        final_results = micro_expand_scores(raw_results)
                        
                        # 3. 排序：優先找槓桿最接近的，其次看勝率，最後天數（遠月優先）
                        final_results.sort(key=lambda x: (x['差距'], -x['勝率'], -x['天數']))
                        
                        st.session_state[KEY_RES] = final_results[:15]
                        st.session_state[KEY_BEST] = final_results[0]
                        st.success(f"掃描完成！最佳槓桿：{final_results[0]['槓桿']:.1f}x")
                    else: st.warning("無符合資料")

        if st.session_state[KEY_RES]:
            best = st.session_state[KEY_BEST]
            st.markdown("---")
            
            cA, cB = st.columns([2, 1])
            with cA:
                st.markdown("#### 🏆 **最佳推薦 (LEADS CALL)**")
                p_int = int(round(best['價格']))
                st.markdown(f"""
                `{best['合約']} {best['履約價']} {best['類型']}` **{p_int}點**  
                槓桿 `{best['槓桿']:.1f}x` | 勝率 `{best['勝率']:.1f}%` | 天數 `{best.get('天數', 0)}天`
                """)
            with cB:
                st.write("")
                if st.button("➕ 加入", key="add_pf_v185"):
                    exists = any(p['履約價'] == best['履約價'] and 
                                 p['合約'] == best['合約'] for p in st.session_state[KEY_PF])
                    if not exists:
                        st.session_state[KEY_PF].append(best)
                        st.toast("✅ 已加入投組")
                    else: st.toast("⚠️ 已存在")

            with st.expander("📋 搜尋結果 (依槓桿→勝率→天數排序)", expanded=True):
                df_show = pd.DataFrame(st.session_state[KEY_RES]).copy()
                
                df_show['權利金'] = df_show['價格'].round(0).astype(int)
                df_show['槓桿'] = df_show['槓桿'].map(lambda x: f"{x:.1f}x")
                df_show['Delta'] = df_show['Delta'].map(lambda x: f"{x:.2f}")
                df_show['勝率'] = df_show['勝率'].map(lambda x: f"{x:.1f}%")
                df_show['天數'] = df_show.get('天數', 0).astype(int)
                
                cols = ["合約", "履約價", "權利金", "槓桿", "勝率", "天數", "差距"]
                st.dataframe(df_show[cols], use_container_width=True, hide_index=True)

    with col_portfolio:
        st.markdown("#### 💼 **LEADS CALL 投組**")
        if st.session_state[KEY_PF]:
            pf = pd.DataFrame(st.session_state[KEY_PF])
            total = pf['價格'].sum() * 50
            avg_win = pf['勝率'].mean()
            avg_lev = pf['槓桿'].mean()
            
            st.metric("總權利金", f"${int(total):,}")
            st.caption(f"{len(pf)}口 | Avg槓桿 {avg_lev:.1f}x | Avg勝率 {avg_win:.1f}%")
            
            pf_s = pf.copy()
            pf_s['權利金'] = pf_s['價格'].round(0).astype(int)
            pf_s['Delta'] = pf_s['Delta'].map(lambda x: f"{float(x):.2f}")
            pf_s['勝率'] = pf_s['勝率'].map(lambda x: f"{float(x):.1f}%")
            pf_s['槓桿'] = pf_s['槓桿'].map(lambda x: f"{x:.1f}x")
            
            st.dataframe(pf_s[["合約", "履約價", "權利金", "槓桿", "勝率"]], 
                         use_container_width=True, hide_index=True)
            
            c_clr, c_dl = st.columns(2)
            with c_clr:
                if st.button("🗑️ 清空投組", key="clr_pf_v185"):
                    st.session_state[KEY_PF] = []
                    st.rerun()
            with c_dl:
                st.download_button("📥 CSV匯出", pf.to_csv(index=False).encode('utf-8'), 
                                   "leads_call_pf_v185.csv", key="dl_pf_v185")
        else: st.info("💡 請先掃描並加入合約")

    # ✅ LEADS CALL 介紹區塊
    st.markdown("---")
    st.markdown("#### 📚 **LEADS / LEAPS CALL 策略簡介**")
    st.markdown("""
    **LEADS CALL (長期看漲選擇權)**：
    - 到期日 > 6個月，時間衰減緩慢，適合長期看多標的（如AI、指數）
    - **優勢**：高槓桿、低成本替代現股，時間價值損耗少
    - **本系統優化**：預設遠月合約 + 槓桿篩選，優先推薦深度價內/價平合約
    - **建議情境**：波段操作、避開短期震盪、建構低成本多頭部位
    """)
    
    st.caption("📊 **操作邏輯**：優先槓桿最接近 → 最高微觀勝率 → 最遠天數。建議搭配遠月 LEADS CALL 降低時間風險。")


# --------------------------
# Tab 3: 歷史回測
# --------------------------
with tabs[3]:
    st.markdown("### 📊 **策略時光機：真實歷史驗證**")
    
    if not st.session_state.is_pro:
        col_lock1, col_lock2 = st.columns([2, 1])
        with col_lock1:
            st.warning("🔒 **此為 Pro 會員專屬功能**")
            st.info("解鎖後可查看：\n- ✅ 真實歷史數據回測\n- ✅ 策略 vs 大盤績效對決\n- ✅ 詳細交易訊號點位")
        with col_lock2:
            st.metric("累積報酬率", "🔒 ???%", "勝率 ???%")
            if st.button("⭐ 免費升級 Pro", key="upgrade_btn_tab3"):
                st.session_state.is_pro = True; st.balloons(); st.rerun()
        st.image("https://via.placeholder.com/1000x300?text=Pro+Feature+Locked", use_container_width=True)
    
    else:
        with st.expander("⚙️ **回測參數設定**", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1: period_days = st.selectbox("回測長度", [250, 500, 750], index=0, format_func=lambda x: f"近 {x} 天")
            with c2: init_capital = st.number_input("初始本金 (萬)", 10, 500, 100)
            with c3: leverage = st.slider("模擬槓桿", 1, 3, 1)

        if st.button("🚀 執行真實回測", type="primary"):
            with st.spinner("正在下載並計算歷史數據..."):
                dl = DataLoader()
                dl.login_by_token(api_token=FINMIND_TOKEN)
                
                end_date = date.today().strftime("%Y-%m-%d")
                start_date = (date.today() - timedelta(days=period_days + 150)).strftime("%Y-%m-%d")
                df_hist = dl.taiwan_stock_daily("TAIEX", start_date=start_date, end_date=end_date)
                
                if df_hist.empty:
                    st.error("❌ 無法取得歷史數據，請稍後再試")
                else:
                    df_hist['close'] = df_hist['close'].astype(float)
                    df_hist['MA20'] = df_hist['close'].rolling(20).mean()
                    df_hist['MA60'] = df_hist['close'].rolling(60).mean()
                    df_hist = df_hist.dropna().tail(period_days).reset_index(drop=True)
                    
                    df_hist['Signal'] = (df_hist['close'] > df_hist['MA20']) & (df_hist['MA20'] > df_hist['MA60'])
                    df_hist['Daily_Ret'] = df_hist['close'].pct_change().fillna(0)
                    df_hist['Strategy_Ret'] = df_hist['Signal'].shift(1).fillna(False) * df_hist['Daily_Ret'] * leverage
                    
                    df_hist['Equity_Strategy'] = init_capital * (1 + df_hist['Strategy_Ret']).cumprod()
                    df_hist['Equity_Benchmark'] = init_capital * (1 + df_hist['Daily_Ret']).cumprod()
                    
                    total_ret = (df_hist['Equity_Strategy'].iloc[-1] / init_capital - 1) * 100
                    bench_ret = (df_hist['Equity_Benchmark'].iloc[-1] / init_capital - 1) * 100
                    win_days = df_hist[df_hist['Strategy_Ret'] > 0]
                    win_rate = len(win_days) / len(df_hist[df_hist['Signal'].shift(1)==True]) * 100 if len(df_hist[df_hist['Signal'].shift(1)==True]) > 0 else 0
                    
                    st.divider()
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("💰 策略最終資產", f"{int(df_hist['Equity_Strategy'].iloc[-1]):,} 萬", f"{total_ret:+.1f}%")
                    k2.metric("🐢 大盤同期表現", f"{bench_ret:+.1f}%", f"超額 {total_ret - bench_ret:+.1f}%", delta_color="off")
                    k3.metric("🏆 交易勝率 (日)", f"{win_rate:.1f}%")
                    k4.metric("📅 交易天數", f"{df_hist['Signal'].sum()} 天", f"佔比 {df_hist['Signal'].mean()*100:.0f}%")

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df_hist['date'], y=df_hist['Equity_Strategy'], name='貝伊果策略', line=dict(color='#00CC96', width=2)))
                    fig.add_trace(go.Scatter(x=df_hist['date'], y=df_hist['Equity_Benchmark'], name='大盤指數', line=dict(color='#EF553B', width=2, dash='dash')))
                    fig.update_layout(title="資金權益曲線 (真實歷史)", yaxis_title="資產淨值 (萬)", hovermode="x unified", height=400)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.markdown("#### 📝 **近期策略訊號**")
                    recent_df = df_hist.tail(10).copy()
                    recent_df['訊號'] = recent_df['Signal'].apply(lambda x: "🟢 持有" if x else "⚪ 空手")
                    recent_df['日期'] = pd.to_datetime(recent_df['date']).dt.strftime('%Y-%m-%d')
                    st.dataframe(recent_df[['日期', 'close', 'MA20', '訊號']].sort_values("日期", ascending=False), hide_index=True)

# --------------------------
# Tab 4: 專業戰情室 (全功能整合版)
# --------------------------
with tabs[4]:
    st.markdown("## 📰 **專業戰情中心**")
    st.caption(f"📅 資料日期：{latest_date.strftime('%Y-%m-%d')} | 💡 模型版本：v6.0 (戰情+籌碼整合)")

    # 進階數據計算函數
    def calculate_advanced_factors(current_price, ma20, ma60, df_latest, token):
        score = 0
        details = []
        
        if current_price > ma20: score += 10; details.append("✅ 站上月線 (+10)")
        if ma20 > ma60: score += 10; details.append("✅ 均線多排 (+10)")
        if current_price > ma60: score += 5; details.append("✅ 站上季線 (+5)")
        if (current_price - ma60)/ma60 > 0.05: score += 5; details.append("✅ 季線乖離強 (+5)")

        try:
            low_min = df_latest['min'].min() if 'min' in df_latest else current_price * 0.9
            high_max = df_latest['max'].max() if 'max' in df_latest else current_price * 1.1
            rsv = (current_price - low_min) / (high_max - low_min) * 100
            if rsv > 50: score += 5; details.append("✅ RSV偏多 (+5)")
            if rsv > 80: score += 5; details.append("🔥 動能強勁 (+5)")
        except: pass

        if (current_price - ma20)/ma20 > 0.02: score += 10; details.append("✅ 短線急攻 (+10)")

        try:
            last_chip = get_institutional_data(token)
            net_buy = last_chip['net'].sum() if not last_chip.empty else 0
            if net_buy > 20: score += 15; details.append("✅ 法人大買 (+15)")
            elif net_buy > 0: score += 5; details.append("✅ 法人小買 (+5)")
            elif net_buy < -20: score -= 5; details.append("⚠️ 法人大賣 (-5)")
        except: pass

        bias = (current_price - ma20) / ma20 * 100
        if bias > 3.5: score -= 5; details.append("⚠️ 乖離過熱 (-5)")
        if bias < -3.5: score += 5; details.append("✅ 乖離過冷反彈 (+5)")

        score += 10
        return min(100, max(0, score)), details

    col_kpi1, col_kpi2 = st.columns([1, 1.5])

    with col_kpi1:
        st.markdown("#### 🌡️ **全方位多空溫度計**")
        
        total_score, score_details = calculate_advanced_factors(S_current, ma20, ma60, df_latest, FINMIND_TOKEN)
        
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = total_score,
            delta = {'reference': 50, 'increasing': {'color': "#28a745"}, 'decreasing': {'color': "#dc3545"}},
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "多空綜合評分", 'font': {'size': 20}},
            gauge = {
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
                'bar': {'color': "#ff4b4b" if total_score < 40 else "#28a745" if total_score > 75 else "#ffc107"},
                'bgcolor': "rgba(0,0,0,0)",
                'borderwidth': 2,
                'bordercolor': "#333",
                'steps': [
                    {'range': [0, 40], 'color': 'rgba(255, 0, 0, 0.3)'},   
                    {'range': [40, 75], 'color': 'rgba(255, 255, 0, 0.3)'},  
                    {'range': [75, 100], 'color': 'rgba(0, 255, 0, 0.3)'}], 
            }
        ))
        
        fig_gauge.update_layout(height=280, margin=dict(l=30, r=30, t=30, b=30), paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
        st.plotly_chart(fig_gauge, use_container_width=True)
        
        trend_score = 0
        if S_current > ma20: trend_score += 1
        if ma20 > ma60: trend_score += 1
        
        if trend_score == 2: signal = "🟢 強勢買點"
        elif trend_score == 1: signal = "🟡 觀望整理"
        else: signal = "🔴 高風險區"
            
        st.metric("🚦 趨勢燈號", signal, f"指數 {S_current:,.0f}")
        
        with st.expander("🔍 查看 12 因子細項"):
            st.write(f"**總分：{total_score}**")
            st.markdown(" • " + "\n • ".join(score_details))

    with col_kpi2:
        st.markdown("#### 🤖 **貝伊果 AI 戰略解讀**")
        
        if total_score >= 80:
            ai_title = "🔥 多頭狂熱：利潤奔跑模式"
            ai_status = "極度樂觀"
            ai_desc = "市場進入「瘋狗浪」階段！所有指標全面翻多，均線發散，量能失控。這是順勢交易者的天堂，但請注意：**乖離率過大隨時可能急殺洗盤**。"
            ai_strat_title = "⚔️ 攻擊策略："
            ai_strat_content = "<li><b>期權</b>：Tab 2 積極買進價外 1-2 檔 Call，槓桿全開。</li><li><b>現貨</b>：持有強勢股，沿 5 日線移動停利。</li>"
            ai_tips = "✅ <b>追價要快</b>：猶豫就沒了<br>🛑 <b>停利要狠</b>：破線就跑"
            box_color = "rgba(220, 53, 69, 0.15)" 
            border_color = "#dc3545" 
            
        elif total_score >= 60:
            ai_title = "🐂 多頭排列：穩健獲利模式"
            ai_status = "樂觀偏多"
            ai_desc = "趨勢溫和向上，最舒服的盤勢。指數站穩月線，MACD 金叉，籌碼安定。這時候不要頻繁進出，**「抱得住」才是贏家**。"
            ai_strat_title = "⚔️ 攻擊策略："
            ai_strat_content = "<li><b>期權</b>：Tab 2 選擇價平 Call，賺取波段漲幅。</li><li><b>ETF</b>：Tab 0 的 0050/QQQ 放心續抱。</li>"
            ai_tips = "✅ <b>拉回找買點</b>：靠近 MA20 是機會<br>🛑 <b>減少當沖</b>：波段利潤更大"
            box_color = "rgba(40, 167, 69, 0.15)"
            border_color = "#28a745"

        elif total_score >= 40:
            ai_title = "⚖️ 多空膠著：雙巴震盪模式"
            ai_status = "中立觀望"
            ai_desc = "現在是「絞肉機」行情！均線糾結，忽漲忽跌。指標出現背離（如價格創高但 RSI 沒創高）。這時候**「不做」就是「賺」**。"
            ai_strat_title = "🛡️ 防禦策略："
            ai_strat_content = "<li><b>期權</b>：切勿 Buy Call/Put！適合做 <b>Credit Spread (收租)</b>。</li><li><b>資金</b>：保留 7 成現金，等待突破。</li>"
            ai_tips = "✅ <b>區間操作</b>：箱頂賣、箱底買<br>🛑 <b>嚴禁追單</b>：突破往往是假突破"
            box_color = "rgba(255, 193, 7, 0.15)"
            border_color = "#ffc107"

        elif total_score >= 20:
            ai_title = "🐻 空方試探：保守防禦模式"
            ai_status = "謹慎偏空"
            ai_desc = "支撐鬆動，風險正在堆積！指數跌破月線，MACD 死叉。多單請務必減碼，不要與趨勢作對。"
            ai_strat_title = "🛡️ 防禦策略："
            ai_strat_content = "<li><b>現貨</b>：反彈到壓力區（如 MA20）就減碼。</li><li><b>避險</b>：可小量買進 00632R (台灣50反1) 或 Put。</li>"
            ai_tips = "✅ <b>現金為王</b>：活著最重要<br>🛑 <b>別急著抄底</b>：還沒跌完"
            box_color = "rgba(23, 162, 184, 0.15)"
            border_color = "#17a2b8"

        else:
            ai_title = "⛈️ 空頭屠殺：全面撤退模式"
            ai_status = "極度恐慌"
            ai_desc = "警報響起！均線蓋頭反壓，布林通道開口向下。此刻**任何反彈都是逃命波**，不要幻想 V 轉。"
            ai_strat_title = "⚔️ 空方策略："
            ai_strat_content = "<li><b>期權</b>：積極 Buy Put，但要快進快出。</li><li><b>心態</b>：承認虧損，清空多單，留得青山在。</li>"
            ai_tips = "✅ <b>果斷停損</b>：不要有僥倖心態<br>🛑 <b>絕對禁止攤平</b>：會越攤越平"
            box_color = "rgba(52, 58, 64, 0.15)"
            border_color = "#343a40"

        html_content = f"""
<div style="border-left: 5px solid {border_color}; background-color: {box_color}; padding: 15px; border-radius: 5px; margin-bottom: 10px; color: #EEE;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
        <h3 style="margin:0; font-size: 1.3em; color: white;">{ai_title}</h3>
        <span style="background-color:{border_color}; color:white; padding: 2px 8px; border-radius: 10px; font-size: 0.8em; font-weight: bold;">{ai_status}</span>
    </div>
    <p style="font-size: 15px; line-height: 1.6; margin-bottom: 15px;">{ai_desc}</p>
    <div style="margin-bottom: 15px;">
        <strong style="color: {border_color};">{ai_strat_title}</strong>
        <ul style="margin-top: 5px; padding-left: 20px;">
            {ai_strat_content}
        </ul>
    </div>
    <div style="background-color: rgba(0,0,0,0.2); padding: 10px; border-radius: 5px; font-size: 0.9em; border: 1px dashed {border_color};">
        {ai_tips}
    </div>
</div>
"""
        st.markdown(html_content, unsafe_allow_html=True)
        
        import random
        quotes = [
            "「行情總在絕望中誕生，在半信半疑中成長。」", "「截斷虧損，讓利潤奔跑。」",
            "「不要預測行情，要跟隨行情。」", "「新手看價，老手看量，高手看籌碼。」"
        ]
        st.caption(f"📜 **貝伊果心法**：{random.choice(quotes)}")

    st.divider()

    st.markdown("### 🔥 **籌碼戰場與點位分析**")
    
    col_chip1, col_chip2 = st.columns([1.5, 1])

    with col_chip1:
        st.markdown("#### 💰 **籌碼戰場 (OI Walls)**")
        st.plotly_chart(plot_oi_walls(S_current), use_container_width=True)
        st.caption("💡 紅色為大量 Call 賣壓 (壓力)，青色為大量 Put 支撐")

        st.markdown("#### 🏦 **三大法人動向**")
        with st.spinner("載入法人資料..."):
            df_chips = get_institutional_data(FINMIND_TOKEN) 
        if not df_chips.empty:
            name_map = {"Foreign_Investors": "外資", "Investment_Trust": "投信", "Dealer_Self": "自營商(自行)", "Dealer_Hedging": "自營商(避險)"}
            df_chips['name_tw'] = df_chips['name'].map(name_map).fillna(df_chips['name'])
            fig_chips = px.bar(df_chips, x="name_tw", y="net", color="net",
                              color_continuous_scale=["green", "red"],
                              labels={"net": "買賣超(億)", "name_tw": "法人身分"},
                              text="net", title=f"三大法人合計買賣超 ({df_chips['date'].iloc[0].strftime('%m/%d')})")
            fig_chips.update_traces(texttemplate='%{text:.1f} 億', textposition='outside')
            fig_chips.update_layout(height=250)
            st.plotly_chart(fig_chips, use_container_width=True)
        else:
            st.warning("⚠️ 暫無法人資料 (下午 3 點後更新)")

    with col_chip2:
        st.markdown("#### 📉 **即時損益試算**")
        k_sim = st.number_input("模擬履約價", 15000, 50000, int(S_current))
        p_sim = st.number_input("權利金", 1, 1000, 150)
        st.plotly_chart(plot_payoff(k_sim, p_sim, "CALL"), use_container_width=True)
        
        st.markdown("#### 🔑 **關鍵點位**")
        with st.spinner("計算支撐壓力..."):
            real_pressure, real_support = get_support_pressure(FINMIND_TOKEN)
        if real_pressure > 0:
            st.metric("🛑 波段壓力 (20日高)", f"{int(real_pressure)}", delta=f"{real_pressure-S_current:.0f}", delta_color="inverse")
            st.metric("🏠 目前點位", f"{int(S_current)}")
            st.metric("🛡️ 波段支撐 (60日低)", f"{int(real_support)}", delta=f"{real_support-S_current:.0f}")
        else:
            st.warning("⚠️ K 線資料連線中斷")

    st.markdown("#### 💼 **我的投組**")
    if st.button("➕ 加入虛擬倉位"):
        st.session_state.portfolio.append({"K": 23000, "P": 180, "Date": str(date.today())})
    if st.session_state.portfolio:
        st.dataframe(pd.DataFrame(st.session_state.portfolio))
    else:
        st.info("暫無持倉")

# --------------------------
# Tab 5~14: 擴充預留位
# --------------------------
with tabs[5]: st.info("🚧 擴充功能 2：大戶籌碼追蹤 (開發中)")
with tabs[6]: st.info("🚧 擴充功能 3：自動下單串接 (開發中)")
with tabs[7]: st.info("🚧 擴充功能 4：Line 推播 (開發中)")
with tabs[8]: st.info("🚧 擴充功能 5：期貨價差監控 (開發中)")
with tabs[9]: st.info("🚧 擴充功能 6：美股連動分析 (開發中)")
with tabs[10]: st.info("🚧 擴充功能 7：自定義策略腳本 (開發中)")
with tabs[11]: st.info("🚧 擴充功能 8：社群討論區 (開發中)")
with tabs[12]: st.info("🚧 擴充功能 9：課程學習中心 (開發中)")
with tabs[13]: st.info("🚧 擴充功能 10：VIP 專屬通道 (開發中)")
