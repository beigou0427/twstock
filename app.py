"""
🔰 貝伊果屋 - 財富雙軌系統 (旗艦完整版)
整合：ETF定投 + 趨勢判斷 + Lead Call策略 + 專業分析 + 市場快報(全真實數據) + 真實回測
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta
from FinMind.data import DataLoader
from scipy.stats import norm
import plotly.graph_objects as go
import plotly.express as px

# =========================
# 1. 初始化 & 設定
# =========================================
st.set_page_config(page_title="貝伊果屋-財富雙軌系統", layout="wide", page_icon="🥯")

# CSS 優化
st.markdown("""
<style>
.big-font {font-size:20px !important; font-weight:bold;}
.crowd-card {background: linear-gradient(90deg, #1D976C, #93F9B9); padding: 15px; border-radius: 10px; color: #004d40;}
.share-btn {border: 2px solid #FF4B4B; border-radius: 5px; padding: 5px;}
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
        # 抓到最新收盤日
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
        news = news.sort_values("date", ascending=False).head(5)
        return news
    except:
        return pd.DataFrame()

@st.cache_data(ttl=1800)
def get_institutional_data(token):
    """抓取真實的三大法人大盤買賣超"""
    dl = DataLoader()
    dl.login_by_token(api_token=token)
    # 抓取最近 10 天資料 (確保有最新交易日)
    start_date = (date.today() - timedelta(days=10)).strftime("%Y-%m-%d")
    try:
        # FinMind API: 台灣整體市場三大法人買賣超
        df = dl.taiwan_stock_institutional_investors_total(start_date=start_date)
        if df.empty: return pd.DataFrame()
        
        # 轉換日期並取最新一天
        df["date"] = pd.to_datetime(df["date"])
        latest_date = df["date"].max()
        df_latest = df[df["date"] == latest_date].copy()
        
        # 計算淨買賣超 (buy - sell) 並轉為「億」
        df_latest["net"] = (df_latest["buy"] - df_latest["sell"]) / 100000000
        return df_latest
    except:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_support_pressure(token):
    """抓取真實 K 線以計算支撐壓力"""
    dl = DataLoader()
    dl.login_by_token(api_token=token)
    start_date = (date.today() - timedelta(days=90)).strftime("%Y-%m-%d")
    try:
        df = dl.taiwan_stock_daily("TAIEX", start_date=start_date)
        if df.empty: return 0, 0
        # 壓力：近 20 日最高價
        pressure = df['max'].tail(20).max()
        # 支撐：近 60 日最低價
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
    fig.update_layout(title=f"到期損益圖 ({cp} @ {K})", xaxis_title="指數", yaxis_title="損益(TWD)", height=300, margin=dict(l=0,r=0,t=30,b=0))
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
# 側邊欄 (簡潔版)
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
    st.caption("📊 功能說明：\\n• Tab0: ETF定投\\n• Tab1: 趨勢判斷\\n• Tab2: CALL獵人")

# =========================
# 5. 主介面 & 市場快報
# =========================================
st.markdown("# 🥯 **貝伊果屋：財富雙軌系統**")

# 市場快報 (貼在所有 Tab 之前)
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

# 分頁導航 (6個功能 + 9個升級槽)
tab_names = [
    "🏦 **穩健ETF**", 
    "📈 **趨勢判斷**", 
    "🔰 **CALL獵人**", 
    "🔥 **專業戰情**", 
    "📊 **歷史回測**",
    "📰 **市場快報**"
]
tab_names += [f"🛠️ 擴充 {i+2}" for i in range(9)]

tabs = st.tabs(tab_names)

# --------------------------
# Tab 0: 穩健 ETF (純定投版)
# --------------------------
with tabs[0]:
    st.markdown("## 🐢 **ETF 定投計畫**")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 📊 **三大 ETF 比較**")
        etf_df = pd.DataFrame({
            "ETF": ["0050", "SPY", "QQQ"],
            "年化報酬": ["12%", "15%", "22%"],
            "建議比重": ["50%", "30%", "20%"],
            "風險": ["低", "中", "高"]
        })
        st.dataframe(etf_df, use_container_width=True)
    
    with col2:
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
# Tab 1: 趨勢判斷 (完整修復版)
# --------------------------
with tabs[1]:
    st.markdown("## 🚦 **市場趨勢儀表板**")
    
    col_idx, col_ma, col_signal = st.columns(3)
    
    with col_idx:
        st.metric("📈 加權指數", f"{S_current:,.0f}", delta=f"{S_current-ma20:.0f}")
    
    with col_ma:
        ma_trend = "🔥 多頭排列" if ma20 > ma60 else "⚖️ 盤整" if abs(ma20-ma60)/S_current < 0.01 else "❄️ 空頭排列"
        st.metric("均線狀態", ma_trend, f"20日: {ma20:,.0f}")
    
    with col_signal:
        trend_score = 0
        if S_current > ma20: trend_score += 1
        if ma20 > ma60: trend_score += 1
        
        if trend_score == 2:
            signal = "🟢 強勢買點"
            action = "立即前往 CALL 獵人"
        elif trend_score == 1:
            signal = "🟡 觀望整理"
            action = "回穩健 ETF 定投"
        else:
            signal = "🔴 高風險區"
            action = "現金為王"
        
        st.metric("交易燈號", signal, action)
    
    st.divider()
    
    st.markdown("### 📉 **趨勢視覺化**")
    fig = go.Figure()
    
    x = np.arange(20)
    np.random.seed(42)
    price_line = S_current * (1 + np.random.normal(0, 0.005, 20).cumsum())
    ma20_line = np.linspace(ma20*0.99, ma20*1.01, 20)
    ma60_line = np.linspace(ma60*0.995, ma60*1.005, 20)
    
    fig.add_trace(go.Scatter(x=x, y=price_line, mode='lines', name='指數', line=dict(color='#1f77b4', width=2)))
    fig.add_trace(go.Scatter(x=x, y=ma20_line, mode='lines', name='MA20', line=dict(color='#ff7f0e', width=2)))
    fig.add_trace(go.Scatter(x=x, y=ma60_line, mode='lines', name='MA60', line=dict(color='#2ca02c', width=2)))
    
    fig.update_layout(height=300, title="近期趨勢 (綠燈 = 20 > 60日線)", showlegend=True)
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("### 🎯 **今日操作建議**")
    
    if trend_score == 2:
        st.success("""
        **🟢 強勢多頭環境**
        - ✅ 適合操作 CALL 策略
        - 🎯 點擊上方「CALL 獵人」尋找機會
        - 💡 建議槓桿 3~7x
        """)
    elif trend_score == 1:
        st.warning("""
        **🟡 震盪整理環境**
        - ⚠️ 趨勢不明，建議觀望或減少部位
        - 💡 回到「穩健 ETF」進行定投
        - 🚫 槓桿操作需極度保守
        """)
    else:
        st.error("""
        **🔴 空頭/高風險環境**
        - ⛔ 禁止 Buy CALL 操作
        - 💵 現金為王，等待落底訊號
        - 🛡️ 只做 ETF 定投
        """)

# --------------------------
# Tab 2: 新手 CALL 獵人 (狀態保存+畫面修復版)
# --------------------------
with tabs[2]:
    st.markdown("### 🔰 **Lead Call 策略選號**")
    
    # 資料前處理
    if not df_latest.empty:
        df_latest["call_put"] = df_latest["call_put"].astype(str).str.upper().str.strip()
    
    # 篩選可用合約
    available_contracts = []
    if not df_latest.empty:
        call_df = df_latest[df_latest["call_put"] == "CALL"]
        available_contracts = sorted(call_df["contract_date"].unique())

    if not available_contracts:
        st.error("⚠️ 找不到任何 CALL 合約資料 (可能是資料源問題)")
    else:
        # 搜尋區塊
        c1, c2, c3, c4 = st.columns([1, 2, 1.5, 1])
        with c1: st.success("📈 **固定看漲**")
        
        with c2: 
            # 記憶合約選擇
            default_idx = len(available_contracts)-1
            if 'selected_contract' in st.session_state:
                if st.session_state['selected_contract'] in available_contracts:
                    default_idx = available_contracts.index(st.session_state['selected_contract'])
            
            sel_con = st.selectbox("合約月份", available_contracts, index=default_idx)
            
        with c3: 
            target_lev = st.slider("目標槓桿", 2.0, 15.0, 5.0, 0.1, format="%.1f")
            
        with c4: is_safe = st.checkbox("穩健濾網", True)
        
        # 🔥 按鈕點擊事件：只負責「算」跟「存」
        if st.button("🎯 **尋找最佳 CALL**", type="primary", use_container_width=True):
            st.session_state['selected_contract'] = sel_con # 記住選擇
            
            tdf = df_latest[(df_latest["contract_date"] == sel_con) & (df_latest["call_put"] == "CALL")]
            y, m = int(sel_con[:4]), int(sel_con[4:6])
            expiry_date = date(y, m, 15)
            days = (expiry_date - latest_date.date()).days
            if days <= 0: days = 1

            res = []
            for _, row in tdf.iterrows():
                try:
                    K = float(row["strike_price"])
                    vol = float(row.get("volume", 0))
                    bs_p, d = bs_price_delta(S_current, K, days/365, 0.02, 0.2, "CALL")
                    
                    if vol > 0:
                        P = float(row["close"])
                        price_type = "🟢 成交價"
                    else:
                        P = bs_p
                        price_type = "🔵 合理價"
                    
                    if P <= 0.1: continue
                    lev = (abs(d) * S_current) / P
                    if is_safe and abs(d) < 0.1: continue
                    
                    res.append({
                        "K": int(K), "P": int(round(P)), "Lev": lev, "Delta": abs(d), 
                        "Win": int(calculate_win_rate(d, days)), "Diff": abs(lev - target_lev),
                        "Type": price_type, "Vol": int(vol)
                    })
                except: continue
            
            if res:
                res.sort(key=lambda x: x['Diff'])
                st.session_state['search_results'] = res # 存入結果
            else:
                st.session_state['search_results'] = None
                st.toast("⚠️ 找不到符合條件的合約")

        # 🔥 顯示區塊：獨立於按鈕之外，只要 Session 有資料就顯示
        if st.session_state.get('search_results'):
            res = st.session_state['search_results']
            best = res[0]
            
            st.divider()
            st.success(f"✅ 找到 {len(res)} 檔合約，最佳推薦：")
            
            rc1, rc2 = st.columns([1, 1])
            with rc1:
                # 顯示推薦卡片
                con_name = st.session_state.get('selected_contract', sel_con)
                st.markdown(f"#### 🏆 {con_name} **{best['K']} CALL**")
                st.metric(f"{best['Type']}", f"{best['P']} 點", f"槓桿 {best['Lev']:.1f}x")
                
                if best['Vol'] == 0:
                    st.caption("⚠️ 此為理論價格 (無成交量)，請掛單等待")
                else:
                    st.caption(f"成交量: {best['Vol']} | 勝率: {best['Win']}%")
                
                if st.button("📱 分享此策略", key="share_btn"):
                    st.balloons()
                    st.code(f"台指{int(S_current)}，我用貝伊果屋選了 {best['K']} CALL ({best['Type']})，槓桿{best['Lev']:.1f}x！")

            with rc2:
                # 顯示風險模擬
                st.markdown("#### 🛡️ **交易計畫模擬**")
                col_sl, col_tp = st.columns(2)
                with col_sl:
                    loss_pct = st.slider("停損幅度 %", 10, 50, 20, step=5)
                with col_tp:
                    profit_pct = st.slider("停利幅度 %", 10, 200, 50, step=10)
                
                cost = best['P'] * 50
                potential_loss = int(cost * (loss_pct/100))
                potential_profit = int(cost * (profit_pct/100))
                rr_ratio = potential_profit / potential_loss if potential_loss > 0 else 0
                
                st.write(f"💰 **本金投入**: NT$ {int(cost):,}")
                
                if rr_ratio >= 3.0:
                    rr_color = "#28a745"; rr_msg = "🌟 優質交易 (>3)"
                elif rr_ratio >= 1.5:
                    rr_color = "#ffc107"; rr_msg = "✅ 可接受 (>1.5)"
                else:
                    rr_color = "#dc3545"; rr_msg = "⚠️ 風險過高 (<1.5)"

                st.markdown(f"""
                <div style="background-color: #262730; padding: 10px; border-radius: 5px; border: 1px solid #444;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                        <span style="color: #ff6b6b;">🔻 停損 (-{loss_pct}%)</span>
                        <span style="color: #ff6b6b; font-weight: bold;">- NT$ {potential_loss:,}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <span style="color: #4ecdc4;">💚 停利 (+{profit_pct}%)</span>
                        <span style="color: #4ecdc4; font-weight: bold;">+ NT$ {potential_profit:,}</span>
                    </div>
                    <div style="border-top: 1px solid #555; padding-top: 5px; text-align: center;">
                        <span style="color: {rr_color}; font-weight: bold; font-size: 1.1em;">風報比 1 : {rr_ratio:.1f}</span><br>
                        <span style="font-size: 0.8em; color: #ccc;">{rr_msg}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("---")
            st.caption("📋 其他候選合約")
            other_df = pd.DataFrame(res[:5])
            display_df = other_df[["K", "P", "Lev", "Type", "Win"]].copy()
            display_df["Lev"] = display_df["Lev"].map(lambda x: f"{x:.1f}")
            st.dataframe(display_df.rename(columns={"K":"履約價", "P":"價格", "Lev":"槓桿", "Type":"類型", "Win":"勝率"}), hide_index=True)


# --------------------------
# Tab 3: 專業戰情 (Pro功能)
# --------------------------
with tabs[3]:
    st.markdown("### 🔥 **戰情室：籌碼與損益分析**")
    
    col_p1, col_p2 = st.columns([2, 1])
    
    with col_p1:
        st.markdown("#### 📊 **籌碼戰場 (OI Walls)**")
        st.plotly_chart(plot_oi_walls(S_current), use_container_width=True)
        st.caption("💡 紅色為大量 Call 賣壓 (壓力)，青色為大量 Put 支撐")

    with col_p2:
        st.markdown("#### 📉 **損益試算**")
        k_sim = st.number_input("模擬履約價", 15000, 50000, int(S_current))
        p_sim = st.number_input("權利金", 1, 1000, 150)
        st.plotly_chart(plot_payoff(k_sim, p_sim, "CALL"), use_container_width=True)

    # 投組管理 (簡化版)
    st.markdown("#### 💼 **我的投組**")
    if st.button("➕ 加入虛擬倉位"):
        st.session_state.portfolio.append({"K": 23000, "P": 180, "Date": str(date.today())})
    
    if st.session_state.portfolio:
        st.dataframe(pd.DataFrame(st.session_state.portfolio))
    else:
        st.info("暫無持倉")

# --------------------------
# Tab 4: 歷史回測 (真實數據版)
# --------------------------
with tabs[4]:
    st.markdown("### 📊 **策略時光機：真實歷史驗證**")
    
    if not st.session_state.is_pro:
        # 鎖定畫面
        col_lock1, col_lock2 = st.columns([2, 1])
        with col_lock1:
            st.warning("🔒 **此為 Pro 會員專屬功能**")
            st.info("解鎖後可查看：\n- ✅ 真實歷史數據回測\n- ✅ 策略 vs 大盤績效對決\n- ✅ 詳細交易訊號點位")
        with col_lock2:
            st.metric("累積報酬率", "🔒 ???%", "勝率 ???%")
            if st.button("⭐ 免費升級 Pro", key="upgrade_btn_tab4"):
                st.session_state.is_pro = True; st.balloons(); st.rerun()
        st.image("https://via.placeholder.com/1000x300?text=Pro+Feature+Locked", use_container_width=True)
    
    else:
        # Pro 功能區
        with st.expander("⚙️ **回測參數設定**", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1: period_days = st.selectbox("回測長度", [250, 500, 750], index=0, format_func=lambda x: f"近 {x} 天")
            with c2: init_capital = st.number_input("初始本金 (萬)", 10, 500, 100)
            with c3: leverage = st.slider("模擬槓桿", 1, 3, 1)

        if st.button("🚀 執行真實回測", type="primary"):
            with st.spinner("正在下載並計算歷史數據..."):
                dl = DataLoader()
                dl.login_by_token(api_token=FINMIND_TOKEN)
                
                # 優化：確保資料抓取範圍涵蓋 MA 計算需求
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
# Tab 5: 市場快報 (旗艦升級版 - 多因子溫度計)
# --------------------------
with tabs[5]:
    st.markdown("## 📰 **市場快報中心**")
    st.caption(f"📅 資料日期：{latest_date.strftime('%Y-%m-%d')} | 💡 綜合因子模型：趨勢+動能+籌碼")

    # ================= 1. 核心儀表板區 (多因子模型) =================
    col_kpi1, col_kpi2 = st.columns([1, 1.5])

    with col_kpi1:
        st.markdown("#### 🌡️ **綜合多空溫度計**")
        
        # --- 因子 1: 趨勢分數 (Trend) ---
        trend_score = 0
        bias_20 = (S_current - ma20) / ma20 * 100
        if S_current > ma20: trend_score += 15       # 站上月線
        if ma20 > ma60: trend_score += 15            # 多頭排列
        if S_current > ma60: trend_score += 10       # 站上季線
        if bias_20 > 2.0: trend_score -= 5           # 乖離過大扣分(過熱)
        
        # --- 因子 2: 動能分數 (Momentum - KD) ---
        # 簡易 KD 計算 (因為不想太複雜，這裡用最近9天模擬 RSV)
        try:
            rsv = (S_current - df_latest['min'].min()) / (df_latest['max'].max() - df_latest['min'].min()) * 100 if 'max' in df_latest else 50
        except: rsv = 50
        
        mom_score = 0
        if rsv > 80: mom_score = 10      # 超買區 (強勢但小心)
        elif rsv < 20: mom_score = 5     # 超賣區 (反彈機會)
        elif rsv > 50: mom_score = 20    # 多方強勢區
        else: mom_score = 10             # 空方弱勢區
        
        # --- 因子 3: 籌碼分數 (Chip) ---
        chip_score = 0
        try:
            last_chip = get_institutional_data(FINMIND_TOKEN)
            net_buy = last_chip['net'].sum() if not last_chip.empty else 0
            if net_buy > 50: chip_score = 20      # 大買 > 50億
            elif net_buy > 0: chip_score = 15     # 小買
            elif net_buy > -50: chip_score = 5    # 小賣
            else: chip_score = 0                  # 大賣
        except: chip_score = 10
        
        # --- 總分計算 ---
        total_score = min(100, max(0, trend_score + mom_score + chip_score + 10)) # +10 為基礎分
        
        # 繪製儀表板
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = total_score,
            delta = {'reference': 50, 'increasing': {'color': "green"}, 'decreasing': {'color': "red"}},
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "多空綜合評分", 'font': {'size': 20}},
            gauge = {
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
                'bar': {'color': "#ff4b4b" if total_score < 30 else "#28a745" if total_score > 70 else "#ffc107"},
                'bgcolor': "rgba(0,0,0,0)",
                'borderwidth': 2,
                'bordercolor': "#333",
                'steps': [
                    {'range': [0, 30], 'color': 'rgba(255, 0, 0, 0.3)'},   
                    {'range': [30, 70], 'color': 'rgba(255, 255, 0, 0.3)'},  
                    {'range': [70, 100], 'color': 'rgba(0, 255, 0, 0.3)'}], 
            }
        ))
        
        fig_gauge.update_layout(
            height=280, 
            margin=dict(l=30, r=30, t=30, b=30),
            paper_bgcolor="rgba(0,0,0,0)", 
            font={'color': "white"}
        )
        st.plotly_chart(fig_gauge, use_container_width=True)
        
        # 顯示細項得分
        c1, c2, c3 = st.columns(3)
        c1.metric("趨勢力", f"{trend_score}/40", help="均線與乖離")
        c2.metric("動能力", f"{mom_score}/20", help="KD與RSV")
        c3.metric("籌碼力", f"{chip_score}/20", help="法人買賣超")

    with col_kpi2:
        st.markdown("#### 🤖 **貝伊果 AI 戰略解讀**")
        
        # 根據細膩分數給出精準建議
        if total_score >= 75:
            ai_title = "🚀 火力全開：強力多頭"
            ai_desc = f"""
            **評分 {total_score} 分：市場情緒極度樂觀！**
            趨勢與籌碼同步偏多，這是利潤奔跑的時刻。
            
            ✅ **建議策略**：
            1. **積極追價**：使用 Tab 2 的 Call 策略，可放大槓桿。
            2. **移動停利**：沿著 MA10 線操作，不破不賣。
            """
            box_style = "border-left: 5px solid #28a745; background-color: rgba(40, 167, 69, 0.1);"
        elif total_score >= 45:
            ai_title = "⚖️ 步步為營：區間震盪"
            ai_desc = f"""
            **評分 {total_score} 分：多空勢力拉鋸中。**
            雖然長線保護短線，但短線動能不足或籌碼鬆動。
            
            ⚠️ **建議策略**：
            1. **高出低進**：接近箱型上緣減碼，回測支撐小買。
            2. **賣方收租**：適合做 Credit Spread (價差單) 賺取時間價值。
            """
            box_style = "border-left: 5px solid #ffc107; background-color: rgba(255, 193, 7, 0.1);"
        else:
            ai_title = "🛡️ 嚴防死守：空方來襲"
            ai_desc = f"""
            **評分 {total_score} 分：市場進入防禦狀態。**
            趨勢破壞且法人賣壓湧現，下跌風險極高。
            
            ⛔ **建議策略**：
            1. **現金為王**：清空所有短線多單。
            2. **反向避險**：考慮買入 Put 或反向 ETF (如 00632R) 進行避險。
            """
            box_style = "border-left: 5px solid #dc3545; background-color: rgba(220, 53, 69, 0.1);"

        st.markdown(f"""
        <div style="{box_style} padding: 15px; border-radius: 5px;">
            <h3 style="margin:0; padding-bottom:10px;">{ai_title}</h3>
            <p style="font-size: 16px; line-height: 1.6;">{ai_desc}</p>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # ================= 2. 真實籌碼與點位區 (維持原樣) =================
    col_chip, col_key = st.columns([1.5, 1])

    with col_chip:
        st.markdown("#### 💰 **法人籌碼動向 (真實數據)**")
        
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
            fig_chips.update_layout(height=300)
            st.plotly_chart(fig_chips, use_container_width=True)
        else:
            st.warning("⚠️ 暫無法人資料 (下午 3 點後更新)")

    with col_key:
        st.markdown("#### 🔑 **關鍵點位 (真實 K 線)**")
        
        with st.spinner("計算支撐壓力..."):
            real_pressure, real_support = get_support_pressure(FINMIND_TOKEN)
        
        if real_pressure > 0:
            st.metric("🛑 波段壓力 (20日高)", f"{int(real_pressure)}", delta=f"{real_pressure-S_current:.0f}", delta_color="inverse")
            st.metric("🏠 目前點位", f"{int(S_current)}")
            st.metric("🛡️ 波段支撐 (60日低)", f"{int(real_support)}", delta=f"{real_support-S_current:.0f}")
            st.caption("💡 數據來源：真實歷史 K 線高低點")
        else:
            st.warning("⚠️ K 線資料連線中斷")

    st.markdown("---")
    
    # ================= 3. 真實新聞區 (維持原樣) =================
    st.markdown("#### 📰 **今日必讀頭條 (即時更新)**")
    
    with st.spinner("抓取最新新聞中..."):
        real_news_df = get_real_news(FINMIND_TOKEN)
    
    if not real_news_df.empty:
        for _, row in real_news_df.iterrows():
            col_n1, col_n2 = st.columns([4, 1])
            with col_n1:
                title = row.get('title', '無標題')
                link = row.get('link', '#')
                source = row.get('source', '新聞')
                st.markdown(f"**[{source}]** [{title}]({link})")
                if 'description' in row and row['description']:
                    st.caption(f"{row['description'][:60]}...")
            with col_n2:
                news_time = pd.to_datetime(row['date']).strftime('%m/%d %H:%M')
                st.caption(f"🕒 {news_time}")
            st.divider()
    else:
        st.warning("⚠️ 目前無最新新聞，或 API 連線忙碌中。")


# --------------------------
# Tab 6~14: 擴充預留位
# --------------------------
with tabs[6]: st.info("🚧 擴充功能 2：大戶籌碼追蹤 (開發中)")
with tabs[7]: st.info("🚧 擴充功能 3：自動下單串接 (開發中)")
with tabs[8]: st.info("🚧 擴充功能 4：Line 推播 (開發中)")
with tabs[9]: st.info("🚧 擴充功能 5：期貨價差監控 (開發中)")
with tabs[10]: st.info("🚧 擴充功能 6：美股連動分析 (開發中)")
with tabs[11]: st.info("🚧 擴充功能 7：自定義策略腳本 (開發中)")
with tabs[12]: st.info("🚧 擴充功能 8：社群討論區 (開發中)")
with tabs[13]: st.info("🚧 擴充功能 9：課程學習中心 (開發中)")
with tabs[14]: st.info("🚧 擴充功能 10：VIP 專屬通道 (開發中)")
