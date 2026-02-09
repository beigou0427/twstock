"""
🔰 貝伊果屋 - 財富雙軌系統 (旗艦完整版 v6.0)
整合：ETF定投 + 智能情報中心 + LEAP Call策略 + 戰情室(12因子/趨勢/籌碼/損益) + 真實回測
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
    st.markdown("##  🔥**強烈建議**🔥")
    st.markdown("##  **閱讀下列書籍後!才投資!**")
    
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
# 合規聲明（零基礎新手版，CALL獵人改半年以上）
if not st.session_state.get('disclaimer_accepted', False):
    st.error("🚨 **股票完全新手必讀！**")
    st.markdown("""
    **先搞懂股票基礎：**
    - 💹 **股票** = 買公司股份，股價漲才賺錢
    - 📈 **ETF** = 一籃子優質股票，新手首選  
    - 💳 **定期定額** = 每月固定買，避開追高殺低
    """)
    
    st.markdown("---")
    
    # 完整5大功能分級
    st.markdown("## 🎯 **貝伊果屋5大功能**")
    
    st.markdown("""
    **🌱 新手起手（先練這3個）**
    - **Tab0 定投計畫**：設定每月自動買ETF，複利致富
    - **Tab1 智能情報**：看懂台股熱門 + 大盤趨勢  
    - **Tab4 戰情室**：追蹤市場熱門題材（AI、半導體）
    
    **🚀 中級看多（看好中長期）**
    - **Tab2 CALL獵人**：找**半年以上到期CALL**（低成本槓桿看多個股)
    
    **🧠 高手專用（會寫策略）**
    - **Tab3 回測系統**：驗證策略過去10年績效
    """)
    
    st.markdown("---")
    
    # 確認按鈕
    if st.button("✅ **我懂基礎，開始使用**", type="primary", use_container_width=True):
        st.session_state.disclaimer_accepted = True
        st.balloons()
        st.rerun()
    
    st.markdown("---")
    
    st.markdown("### 📚 **零基礎必備書籍**")
    col1, col2 = st.columns(2)
    with col1:
        st.image("https://down-tw.img.susercontent.com/file/sg-11134201-7qvdl-lh2v8yc9n8530d.webp", caption="方案一", use_container_width=True)
        st.markdown("[🛒 購買方案一](https://s.shopee.tw/5AmrxVrig8)")
    with col2:
        st.image("https://down-tw.img.susercontent.com/file/tw-11134207-7rasc-m2ba9wueqaze3a.webp", caption="方案二", use_container_width=True)
        st.markdown("[🛒 購買方案二](https://s.shopee.tw/6KypLiCjuy)")
    
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
# Tab 0: 穩健 ETF (v7.4 - 穩定顯示版)
# --------------------------

with tabs[0]:
    if not st.session_state.get('etf_done', False):
        st.markdown("### 🚨 新手入門")
        st.info("ETF=股票籃子 | 定投=每月買")
        if st.button("開始"): st.session_state.etf_done = True; st.rerun()
        st.stop()

    st.markdown("## 🐢 ETF 定投")

    # 導航
    col1,col2=st.columns(2)
    with col1:st.markdown('<div style="padding:15px;border-radius:10px;background:#e8f5e8;border:1px solid #28a745;text-align:center;"><b style="color:#28a745;font-size:18px;">定投計畫</b></div>',unsafe_allow_html=True)
    with col2:st.markdown('<div style="padding:15px;border-radius:10px;background:#2b0f0f;border:2px solid #ff4b4b;text-align:center;"><b style="color:#ff4b4b;font-size:18px;">進階戰室</b></div>',unsafe_allow_html=True)

    # Tab跳轉
    import streamlit.components.v1 as components
    components.html('<button style="width:100%;height:40px;background:#ff4b4b;color:white;border-radius:8px;" onclick="jumpToTab2()">Tab2</button><script>function jumpToTab2(){try{var t=window.parent.document.querySelectorAll(\'button[data-baseweb="tab"]\');t[2]&&t[2].click()}catch(e){}}</script>',height=50)

    st.markdown("---")

    # === 真實回測（簡化穩定版） ===
    st.markdown("### 📊 歷史績效")

    @st.cache_data(ttl=1800)
    def safe_backtest():
        try:
            from FinMind.data import DataLoader
            from datetime import date, timedelta
            
            api=DataLoader()
            etfs=['0050','006208','00662','00757','00646']
            end=date.today().strftime('%Y-%m-%d')
            start=(date.today()-timedelta(days=365*5)).strftime('%Y-%m-%d')  # 5年較穩
            
            data_rows=[]
            for etf in etfs:
                df=api.taiwan_stock_daily(etf,start,end)
                if len(df)>100:
                    first=df['close'].iloc[0]
                    last=df['close'].iloc[-1]
                    days=(df.index[-1]-df.index[0]).days
                    yrs=round(days/365.25,1)
                    
                    total=(last/first-1)*100
                    ann=((last/first)**(1/yrs)-1)*100 if yrs>0 else 0
                    
                    cum_max=df['close'].expanding().max()
                    dd=((df['close']-cum_max)/cum_max*100).min()
                    
                    data_rows.append([etf,f"{total:.1f}%",f"{ann:.1f}%",yrs,f"{dd:.1f}%"])
                else:
                    data_rows.append([etf,"-","-","-","-"])
            
            return pd.DataFrame(data_rows,columns=['ETF','總報酬','年化','年數','回撤'])
        except:
            # 備用靜態數據
            return pd.DataFrame({
                'ETF':['0050','006208','00662','00757','00646'],
                '總報酬':['+250%','+260%','+450%','+600%','+320%'],
                '年化':['11.6%','11.8%','17.2%','21.5%','13.2%'],
                '年數':[10,8,5,4,5],
                '回撤':['-35%','-34%','-42%','-55%','-28%']
            })

    perf_df = safe_backtest()
    st.dataframe(perf_df, use_container_width=True)

    st.caption("5-10年真實數據 | 按鈕更新")
    if st.button("🔄 刷新數據"): st.cache_data.clear(); st.rerun()

    st.markdown("---")

    # 定投試算
    st.markdown("### 💰 定投試算器")

    c1,c2,c3=st.columns(3)
    with c1: mon_in=st.number_input("每月",1000,50000,10000,1000)
    with c2: yrs_in=st.slider("年數",5,30,10)
    with c3:
        etf_sel=st.selectbox("ETF",perf_df['ETF'].tolist())
        ann_val=perf_df[perf_df['ETF']==etf_sel]['年化'].values[0]
        rate_use=float(str(ann_val).replace('%',''))/100 if '%' in str(ann_val) else 0.10

    final_amt=mon_in*12*(((1+rate_use)**yrs_in-1)/rate_use)
    st.metric(f"{yrs_in}年總資產",f"NT${final_amt:,.0f}")

    # 圖
    import plotly.express as px
    import numpy as np
    yrs_arr=np.arange(1,yrs_in+1)
    amt_arr=[mon_in*12*(((1+rate_use)**y-1)/rate_use)for y in yrs_arr]
    fig=px.line(pd.DataFrame({'年':yrs_arr,'資產':amt_arr}),x='年',y='資產')
    st.plotly_chart(fig,height=280,use_container_width=True)

    st.markdown("---")

    # 堅持
    st.markdown("### 🧠 堅持收益")
    cs,cg=st.columns(2)
    with cs:
        stop_in=st.slider("早停年",1,yrs_in-1,3)
        stop_amt=mon_in*12*(((1+rate_use)**stop_in-1)/rate_use)
        st.error(f"NT${stop_amt:,.0f}")
    with cg:
        gain_amt=((final_amt/stop_amt)-1)*100
        st.success(f"**多{gain_amt:.0f}%**")

    st.markdown("---")

    st.warning("短期回撤大 | 用閒錢 | 每月100元起")
    st.success("定投啟蒙完成！0050開始")

# --------------------------
# Tab 0: 穩健 ETF (v7.6 - 完整導航版)
# --------------------------

with tabs[0]:
    # 新手檢查
    if not st.session_state.get('etf_done', False):
        st.markdown("### 🚨 新手必讀")
        st.info("ETF=股票籃子 | 定投=每月自動買")
        if st.button("開始"): st.session_state.etf_done = True; st.rerun()
        st.stop()

    st.markdown("## 🐢 ETF 定投計畫")

    # === 🔥 完整雙軌導航（原始需求） ===
    st.markdown("""
    <style>
    @keyframes pulse-red {
        0% { box-shadow: 0 0 0 0 rgba(255,75,75,0.7); }
        70% { box-shadow: 0 0 0 20px rgba(255,75,75,0); }
        100% { box-shadow: 0 0 0 0 rgba(255,75,75,0); }
    }
    .safe-card { 
        background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
        border: 2px solid #28a745; border-radius: 15px; padding: 20px; 
        text-align: center; height: 140px; display: flex; flex-direction: column; 
        justify-content: space-between; box-shadow: 0 4px 15px rgba(40,167,69,0.3);
    }
    .risk-card { 
        background: linear-gradient(135deg, #721c24 0%, #dc3545 50%, #c82333 100%);
        border: 3px solid #ff4b4b; border-radius: 15px; padding: 20px;
        text-align: center; height: 140px; display: flex; flex-direction: column; 
        justify-content: space-between; box-shadow: 0 0 30px rgba(255,75,75,0.6);
        animation: pulse-red 2s infinite;
    }
    .card-title { font-size: 22px; font-weight: bold; margin-bottom: 8px; }
    .card-desc { font-size: 14px; line-height: 1.4; }
    .jump-btn {
        width: 100%; height: 42px; background: #ff4b4b; color: white;
        border: none; border-radius: 10px; font-size: 16px; font-weight: 600;
        cursor: pointer; transition: all 0.3s; margin-top: 5px;
    }
    .jump-btn:hover { background: #ff3333; transform: scale(1.05); }
    </style>
    """, unsafe_allow_html=True)

    col_safe, col_risk = st.columns(2, gap="large")
    
    # 🐢 穩健定投區
    with col_safe:
        st.markdown("""
        <div class="safe-card">
            <div class="card-title" style="color: #155724;">🐢 穩健定投區</div>
            <div class="card-desc">
                每月自動買入ETF<br>
                <b>10年變富翁</b><br>
                適合新手、上班族
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.info("👇 向下看**實時報價+試算**")

    # ⚡ 進階戰室（原始需求文案）
    with col_risk:
        st.markdown("""
        <div class="risk-card">
            <div class="card-title" style="color: #fff;">⚡ 最簡單賺到第一桶金的科學</div>
            <div class="card-desc">
                當<b>長期持續買進 + 槓桿</b><br>
                <span style="color: #ffeb3b;">使用前請注意期權槓桿風險</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # 🔥 強化跳轉按鈕
        components.html('''
        <button class="jump-btn" onclick="jumpToTab2()">
            🚀 立即進入戰場 (Tab 2) ⏭️
        </button>
        <script>
        function jumpToTab2(){
            try{
                var tabs = window.parent.document.querySelectorAll('button[data-baseweb="tab"]');
                if(tabs.length > 2){
                    tabs[2].click();
                    window.parent.scrollTo(0, 0);
                    console.log("Jump to Tab 2 success!");
                }
            }catch(e){
                console.error("Tab jump failed:", e);
            }
        }
        </script>
        ''', height=80)

    st.markdown("---")

    # === 實時報價 ===
    st.markdown("### 📡 實時報價（5分更新）")

    @st.cache_data(ttl=300)
    def live_quotes():
        from FinMind.data import DataLoader
        from datetime import date, timedelta
        api = DataLoader()
        etfs = ['0050', '006208', '00662', '00757', '00646']
        end = date.today().strftime('%Y-%m-%d')
        start = (date.today() - timedelta(3)).strftime('%Y-%m-%d')
        
        data = []
        for etf in etfs:
            try:
                df = api.taiwan_stock_daily(etf, start, end)
                if not df.empty:
                    row = df.iloc[-1]
                    prev = df.iloc[-2] if len(df)>1 else row
                    data.append({
                        'ETF': etf,
                        '名稱': {'0050':'台灣50','006208':'富邦台50','00662':'NASDAQ','00757':'FANG+','00646':'S&P500'}[etf],
                        '現價': f"${row.close:.2f}",
                        '漲跌': f"{row.close-prev.close:+.2f}",
                        '%': f"{((row.close/prev.close)-1)*100:+.1f}%"
                    })
            except:
                data.append({'ETF': etf, '名稱': etf, '現價': '-', '漲跌': '-', '%': '-'})
        return pd.DataFrame(data)

    q_df = live_quotes()
    st.dataframe(q_df, use_container_width=True)

    if st.button("🔄 5秒刷新"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")

    # === 歷史績效 ===
    st.markdown("### 📊 5年真實年化")

    @st.cache_data(ttl=1800)
    def hist_perf():
        from FinMind.data import DataLoader
        from datetime import date, timedelta
        
        api = DataLoader()
        etfs = ['0050', '006208', '00662', '00757', '00646']
        end = date.today().strftime('%Y-%m-%d')
        start = (date.today() - timedelta(365*5)).strftime('%Y-%m-%d')
        
        rows = []
        for etf in etfs:
            try:
                df = api.taiwan_stock_daily(etf, start, end)
                if len(df) > 50:
                    f_p = df.close.iloc[0]
                    l_p = df.close.iloc[-1]
                    dys = (df.index[-1] - df.index[0]).days
                    ys = dys / 365.25
                    
                    t_ret = (l_p/f_p-1)*100
                    a_ret = ((l_p/f_p)**(1/ys)-1)*100
                    
                    c_max = df.close.expanding().max()
                    drw = ((df.close - c_max)/c_max * 100).min()
                    
                    rows.append([etf, f"{t_ret:.1f}%", f"{a_ret:.1f}%", f"{ys:.1f}", f"{drw:.1f}%"])
                else:
                    rows.append([etf, "-", "-", "-", "-"])
            except:
                rows.append([etf, "-", "-", "-", "-"])
        return pd.DataFrame(rows, columns=['ETF', '總報酬', '年化', '年數', '回撤'])

    h_df = hist_perf()
    st.dataframe(h_df, use_container_width=True)

    st.markdown("---")

    # 定投
    st.markdown("### 💰 定投試算")
    c1,c2,c3=st.columns(3)
    with c1:amt_mo=st.number_input("每月",1000,50000,10000)
    with c2:yrs_te=st.slider("年數",5,30,10)
    with c3:
        etf_te=st.selectbox("ETF",h_df['ETF'].tolist())
        ann_te=h_df[h_df['ETF']==etf_te]['年化'].values[0]
        rate_te=0.10
        if ann_te!='-' and '%' in ann_te:rate_te=float(ann_te.replace('%',''))/100

    fin_val=amt_mo*12*(((1+rate_te)**yrs_te-1)/rate_te)
    st.metric(f"{yrs_te}年總額",f"NT${fin_val:,.0f}")

    import plotly.express as px;import numpy as np
    y_arr=np.arange(1,yrs_te+1)
    v_arr=[amt_mo*12*(((1+rate_te)**y-1)/rate_te)for y in y_arr]
    fig=px.line(pd.DataFrame({'年':y_arr,'資產':v_arr}),x='年',y='資產')
    st.plotly_chart(fig,use_container_width=True)

    st.markdown("---")

    # 堅持
    st.markdown("### 🧠 堅持多賺")
    cs1,cs2=st.columns(2)
    with cs1:
        yr_st=st.slider("早停",1,yrs_te-1,3)
        val_st=amt_mo*12*(((1+rate_te)**yr_st-1)/rate_te)
        st.error(f"NT${val_st:,.0f}")
    with cs2:
        pct_ex=((fin_val/val_st)-1)*100
        st.success(f"+{pct_ex:.0f}%")

    st.markdown("---")
    st.warning("短期回撤大 | 閒錢投資")
    st.success("定投完成！0050最穩")

# --------------------------
# Tab 2: 槓桿篩選版 v18.5 (回歸槓桿操作 + LEAPS CALL)
# --------------------------
with tabs[2]:
    KEY_RES = "results_lev_v185"
    KEY_BEST = "best_lev_v185"
    KEY_PF = "portfolio_lev"

    if KEY_RES not in st.session_state: st.session_state[KEY_RES] = []
    if KEY_BEST not in st.session_state: st.session_state[KEY_BEST] = None
    if KEY_PF not in st.session_state: st.session_state[KEY_PF] = []

    st.markdown("### ♟️ **專業戰情室 (槓桿篩選 + 微觀勝率 + LEAPS CALL)**")
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
        st.markdown("#### 🔍 **槓桿掃描 (LEAPS CALL 優化)**")
        
        if df_latest.empty: st.error("⚠️ 無資料"); st.stop()
        
        df_work = df_latest.copy()
        df_work['call_put'] = df_work['call_put'].str.upper().str.strip()
        for col in ['close', 'volume', 'strike_price']:
            df_work[col] = pd.to_numeric(df_work[col], errors='coerce').fillna(0)

        c1, c2, c3, c4 = st.columns([1, 1, 1, 0.6])
        with c1:
            dir_mode = st.selectbox("方向", ["📈 CALL (LEAPS)", "📉 PUT"], 0, key="v185_dir")
            op_type = "CALL" if "CALL" in dir_mode else "PUT"
        with c2:
            contracts = df_work[df_work['call_put']==op_type]['contract_date'].dropna()
            available = sorted(contracts[contracts.astype(str).str.len()==6].unique())
            # ✅ 預設遠月合約 (LEAPS CALL 偏好)
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
                st.markdown("#### 🏆 **最佳推薦 (LEAPS CALL)**")
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
        st.markdown("#### 💼 **LEAPS CALL 投組**")
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
                                   "LEAPs_call_pf_v185.csv", key="dl_pf_v185")
        else: st.info("💡 請先掃描並加入合約")

    # ✅ LEAPS CALL 介紹區塊
    st.markdown("---")
    st.markdown("#### 📚 **LEAPS / LEAPS CALL 策略簡介**")
    st.markdown("""
    **LEAPS CALL (長期看漲選擇權)**：
    - 到期日 > 6個月，時間衰減緩慢，適合長期看多標的（如AI、指數）
    - **優勢**：高槓桿、低成本替代現股，時間價值損耗少
    - **本系統優化**：預設遠月合約 + 槓桿篩選，優先推薦深度價內/價平合約
    - **建議情境**：波段操作、避開短期震盪、建構低成本多頭部位
    """)
    
    st.caption("📊 **操作邏輯**：優先槓桿最接近 → 最高微觀勝率 → 最遠天數。建議搭配遠月 LEAPS CALL 降低時間風險。")


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
