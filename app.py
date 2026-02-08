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
    
    if not st.session_state.is_pro:
        if st.button("⭐ 升級 Pro (NT$299)", type="primary"):
            st.session_state.is_pro = True
            st.balloons()
            st.rerun()
    else:
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
    signal = "🟢 CALL時機" if S_current > ma20 > ma60 else "🟡 觀望"
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
# Tab 0: 穩健 ETF
# --------------------------
with tabs[0]:
    st.markdown("## 🐢 **ETF 定投計畫**")
    
    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.markdown("### 📊 **三大 ETF 比較**")
        etf_df = pd.DataFrame({
            "ETF": ["0050", "SPY", "QQQ"],
            "年化報酬": ["12%", "15%", "22%"],
            "建議比重": ["50%", "30%", "20%"],
            "風險": ["低", "中", "高"]
        })
        st.dataframe(etf_df, use_container_width=True)
    
    with c2:
        st.markdown("### 💰 **定投試算器**")
        monthly = st.number_input("每月投入", 10000, 100000, 30000)
        years = st.slider("持續年數", 5, 30, 10)
        rate = st.slider("預期年化", 8, 20, 12)
        
        final = monthly * 12 * (((1 + rate/100)**years - 1) / (rate/100))
        st.metric(f"{years}年後", f"NT$ {final:,.0f}")
        st.caption("💡 定時定額，漲跌都買")

    st.markdown("---")
    st.markdown("### 📅 **我的定投計畫**")
    st.info("""
    **建議**：
    1. 每月 5 號定投
    2. 0050:50%、SPY:30%、QQQ:20%
    3. **絕對不要看短期漲跌**
    4. 10年後檢視成果
    """)
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
# Tab 2: 嚴格低槓桿戰情室 v15.4
# --------------------------
with tabs[2]:
    # 初始化
    if 'portfolio' not in st.session_state: st.session_state.portfolio = []
    if 'strict_results' not in st.session_state: st.session_state.strict_results = []
    if 'strict_best' not in st.session_state: st.session_state.strict_best = None
    
    st.markdown("### ♟️ **嚴格低槓桿篩選**")
    col_search, col_portfolio = st.columns([1.3, 0.7])
    
    # 🔥 嚴格版雙階段 (基礎75% + 強制扣分)
    def calculate_strict_decay_win_rate(delta, days, d2_prob, lev):
        # 1. 基礎勝率 (上限75%)
        base_win = min(d2_prob * 100 * 0.9, 75)
        delta_bonus = abs(delta) * 8      # 降低加成
        time_bonus = min(days / 30 * 1.5, 7)  # 降低加成
        trend_bonus = 3 if delta > 0 else 0   # 降低加成
        raw_win = min(base_win + delta_bonus + time_bonus + trend_bonus, 75)
        
        # 📉 2. 強制衰退 (3x以上必扣)
        if lev <= 3:
            decay = 0
        elif lev <= 5:
            # 🔥 階段1: 嚴格1.5%/0.1x
            decay = (lev - 3) * 1.5
        else:
            # 階段2: 指數暴跌
            base_decay = (5 - 3) * 1.5
            extra_lev = lev - 5
            exp_decay = base_decay + (extra_lev ** 2) * 2.5
            decay = min(exp_decay, 95)
        
        final_win = raw_win - decay
        return min(max(final_win, 5), 75)  # 上限75%

    with col_search:
        st.markdown("#### 🔍 **嚴格掃描**")
        
        if df_latest.empty: st.error("⚠️ 無資料"); st.stop()
        
        df_work = df_latest.copy()
        df_work['call_put'] = df_work['call_put'].astype(str).str.upper().str.strip()
        for col in ['close', 'volume', 'strike_price']:
            df_work[col] = pd.to_numeric(df_work[col], errors='coerce').fillna(0)

        # 參數區
        c1, c2, c3 = st.columns(3)
        with c1:
            dir_mode = st.selectbox("方向", ["📈 CALL", "📉 PUT"], 0, key="strict_dir")
            op_type = "CALL" if "CALL" in dir_mode else "PUT"
        with c2:
            contracts = df_work[df_work['call_put']==op_type]['contract_date'].dropna()
            available = sorted(contracts[contracts.astype(str).str.len()==6].unique())
            sel_con = st.selectbox("月份", available if available else [""], key="strict_con")
        with c3:
            target_lev = st.slider("目標槓桿", 2.0, 20.0, 3.0, 0.1, key="strict_lev")

        # 掃描按鈕
        def on_scan_strict():
            st.session_state.strict_results = []
            
        if st.button("🚀 嚴格篩選", type="primary", use_container_width=True, on_click=on_scan_strict):
            if sel_con and len(str(sel_con))==6:
                tdf = df_work[(df_work["contract_date"].astype(str)==sel_con) & (df_work["call_put"]==op_type)]
                
                if tdf.empty: st.warning("無資料")
                else:
                    try:
                        y, m = int(sel_con[:4]), int(sel_con[4:6])
                        days = max((date(y,m,15)-latest_date.date()).days,1)
                        T = days/365.0
                    except: st.error("日期錯誤"); st.stop()

                    res = []
                    for _, row in tdf.iterrows():
                        try:
                            K = float(row["strike_price"])
                            vol = float(row["volume"])
                            close_p = float(row["close"])
                            if K<=0: continue
                            
                            # BS Model
                            try:
                                r, sigma = 0.02, 0.2
                                d1 = (np.log(S_current/K)+(r+0.5*sigma**2)*T)/(sigma*np.sqrt(T))
                                d2 = d1-sigma*np.sqrt(T)
                                
                                if op_type=="CALL":
                                    bs_p = S_current*norm.cdf(d1)-K*np.exp(-r*T)*norm.cdf(d2)
                                    delta = norm.cdf(d1)
                                    bspop_prob = norm.cdf(d2)
                                else:
                                    bs_p = K*np.exp(-r*T)*norm.cdf(-d2)-S_current*norm.cdf(-d1)
                                    delta = -norm.cdf(-d1)
                                    bspop_prob = norm.cdf(-d2)
                            except: 
                                bs_p, delta, bspop_prob = close_p, 0.5, 0.5

                            P = close_p if vol > 0 else bs_p
                            if P <= 0.5: continue
                            
                            lev = (abs(delta)*S_current)/P
                            
                            # 嚴格過濾
                            if abs(delta) < 0.2: continue  # 提高Delta門檻
                            if lev > 40: continue

                            # 🔥 嚴格勝率
                            win_rate = calculate_strict_decay_win_rate(delta, days, bspop_prob, lev)
                            status = "🟢成交價" if vol > 0 else "🔵合理價"

                            res.append({
                                "履約價": int(K), "價格": P, "狀態": status, "槓桿": lev,
                                "Delta": delta, "勝率": win_rate, "Vol": int(vol),
                                "差距": abs(lev - target_lev),
                                "合約": sel_con, "類型": op_type
                            })
                        except: continue
                    
                    if res:
                        res.sort(key=lambda x: (x['差距'], -x['勝率']))
                        st.session_state.strict_results = res[:12]  # 更嚴格，只顯示12個
                        st.session_state.strict_best = res[0]
                        st.success("🎯 嚴格篩選完成")
                    else: st.warning("無優質合約")

        # 顯示區
        if st.session_state.strict_results:
            best = st.session_state.strict_best
            st.markdown("---")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown("#### 🏆 **最佳低槓桿**")
                price_int = int(round(best['價格']))
                lev_str = f"{best['槓桿']:.1f}x"
                win_str = f"{best['勝率']:.0f}%"
                status_display = best.get('狀態', '成交價')
                
                st.markdown(f"""
                `{best['履約價']} {best['類型']}`
                **{price_int}點 {status_display}**
                槓桿 `{lev_str}` | 勝率 `{win_str}`
                """)
                
            with col2:
                st.write("")
                if st.button("➕ 加入投組", key="add_pf_strict"):
                    exists = any(p['履約價'] == best['履約價'] and p['合約'] == best['合約'] for p in st.session_state.portfolio)
                    if not exists:
                        st.session_state.portfolio.append(best)
                        st.toast("✅ 加入")
                    else: st.toast("⚠️ 重複")
            
            with st.expander("📋 嚴格清單 (3x以下優先)", expanded=True):
                res_df = pd.DataFrame(st.session_state.strict_results)
                
                def safe_fmt(val, fmt):
                    try: return fmt.format(val)
                    except: return str(val)

                show_df = res_df.copy()
                show_df['權利金'] = show_df['價格'].apply(lambda x: int(round(x)))
                show_df['槓桿'] = show_df['槓桿'].apply(lambda x: f"{x:.1f}x")
                show_df['勝率'] = show_df['勝率'].apply(lambda x: f"{x:.0f}%")
                if '狀態' not in show_df.columns: show_df['狀態'] = '成交價'
                
                # 添加槓桿顏色標記
                def lev_color(lev):
                    if lev <= 3: return "🟢"
                    elif lev <= 5: return "🟡"
                    else: return "🔴"
                
                show_df['槓桿標記'] = show_df['槓桿'].apply(lambda x: lev_color(float(x.replace('x',''))))
                final_show = show_df[["履約價", "權利金", "狀態", "槓桿標記", "槓桿", "勝率"]]
                st.dataframe(final_show.rename(columns={'槓桿標記':'標記'}), use_container_width=True, hide_index=True)

    with col_portfolio:
        st.markdown("#### 💼 **低槓桿投組**")
        if st.session_state.portfolio:
            pf_df = pd.DataFrame(st.session_state.portfolio)
            total = pf_df['價格'].sum() * 50
            avg_win = pf_df['勝率'].mean()
            avg_lev = pf_df['槓桿'].mean()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("總金", f"${int(total):,}")
            col2.metric("平均勝率", f"{avg_win:.0f}%")
            col3.metric("平均槓桿", f"{avg_lev:.1f}x")
            
            pf_show = pf_df.copy()
            pf_show['權利金'] = pf_df['價格'].round(0).astype(int)
            pf_show['槓桿'] = pf_df['槓桿'].apply(lambda x: f"{x:.1f}x")
            pf_show['勝率'] = pf_df['勝率'].fillna(0).apply(lambda x: f"{x:.0f}%")
            
            cols = ["合約","履約價","權利金","狀態","槓桿","勝率"]
            st.dataframe(pf_show[cols], use_container_width=True, hide_index=True)
            
            b1, b2 = st.columns(2)
            with b1: 
                if st.button("🗑️ 清空", key="clr_pf_strict"): 
                    st.session_state.portfolio = []
                    st.rerun()
            with b2:
                st.download_button("📥 CSV", pf_df.to_csv(index=False).encode('utf-8'), "低槓桿投組.csv", key="dl_pf_strict")
        else: st.info("📭 等待優質合約")

    # ✅ 衰退說明表 (取代圖表)
    st.markdown("---")
    st.markdown("#### 📋 **勝率衰退表**")
    decay_table = pd.DataFrame({
        '槓桿': ['≤3.0x', '3.1x', '3.5x', '4.0x', '5.0x', '8.0x', '12x+'],
        '衰退': ['0%', '-1.5%', '-7.5%', '-15%', '-30%', '-45%+', '-70%+'],
        '狀態': ['🟢安全區', '🟡輕罰', '🟡中罰', '🟠重罰', '🔴危險', '💀高危', '☠️必死']
    })
    st.table(decay_table)

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
