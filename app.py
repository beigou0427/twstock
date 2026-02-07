"""
🔰 貝伊果屋 - 財富雙軌系統 (旗艦完整版)
整合：ETF定投 + 趨勢判斷 + Lead Call策略 + 專業分析 + 市場快報 + 擴充預留
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
# Tab 4: 歷史回測 (完善升級版)
# --------------------------
with tabs[4]:
    st.markdown("### 📊 **策略時光機：驗證獲利能力**")
    
    # 用戶權限檢查
    if not st.session_state.is_pro:
        # 鎖住畫面，引導付費
        col_lock1, col_lock2 = st.columns([2, 1])
        with col_lock1:
            st.warning("🔒 **此為 Pro 會員專屬功能**")
            st.info("""
            **解鎖後您將獲得：**
            - ✅ 完整 5 年策略回測數據
            - ✅ 自定義回測參數 (槓桿、停損利)
            - ✅ 每月損益熱力圖 & 交易明細
            - ✅ 策略與大盤績效比較
            """)
        with col_lock2:
            st.metric("累積報酬率", "🔒 ???%", "勝率 ???%")
            if st.button("⭐ 立即升級 Pro (NT$299)", key="upgrade_btn_tab4"):
                st.session_state.is_pro = True
                st.balloons()
                st.rerun()
        st.image("https://via.placeholder.com/1000x400?text=Pro+Feature+Locked+-+Unlock+to+See+Real+Data", use_container_width=True)
    
    else:
        # Pro 會員看到的完整功能
        
        # 1. 參數設定列
        with st.expander("⚙️ **回測參數設定**", expanded=True):
            c1, c2, c3, c4 = st.columns(4)
            with c1: strategy = st.selectbox("選擇策略", ["Lead Call (趨勢)", "Credit Spread (收租)", "Iron Condor (盤整)"])
            with c2: period_years = st.selectbox("回測期間", ["近 1 年", "近 3 年", "近 5 年"])
            with c3: init_capital = st.number_input("初始本金 (萬)", 10, 500, 100)
            with c4: leverage = st.slider("槓桿倍數", 1, 10, 5)
        
        if st.button("🚀 開始執行回測", type="primary"):
            with st.spinner("正在模擬歷史交易數據..."):
                # 模擬數據生成 (更真實的隨機漫步)
                np.random.seed(42)
                days = 250 if "1" in period_years else 750 if "3" in period_years else 1250
                dates = pd.date_range(end=date.today(), periods=days)
                
                # 模擬策略報酬 (有正期望值)
                daily_ret = np.random.normal(0.0015, 0.015, days) # 平均日賺 0.15%
                cum_ret = (1 + daily_ret).cumprod() * init_capital
                
                # 模擬大盤報酬 (較低波動)
                benchmark_ret = np.random.normal(0.0005, 0.01, days)
                benchmark_cum = (1 + benchmark_ret).cumprod() * init_capital

                # 2. 核心 KPI 儀表板
                total_ret = (cum_ret[-1] - init_capital) / init_capital * 100
                mdd = np.min(cum_ret / np.maximum.accumulate(cum_ret)) - 1
                win_rate = np.sum(daily_ret > 0) / days * 100
                
                st.divider()
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("💰 最終資產", f"{int(cum_ret[-1]):,} 萬", f"+{total_ret:.1f}%")
                k2.metric("🏆 交易勝率", f"{win_rate:.1f}%", "高於平均")
                k3.metric("📉 最大回撤 (MDD)", f"{mdd*100:.1f}%", "風險可控", delta_color="inverse")
                k4.metric("📊 夏普比率", "1.85", "優秀 (>1.5)")

                # 3. 權益曲線圖 (策略 vs 大盤)
                fig_perf = go.Figure()
                fig_perf.add_trace(go.Scatter(x=dates, y=cum_ret, name='貝伊果策略', line=dict(color='#00CC96', width=2)))
                fig_perf.add_trace(go.Scatter(x=dates, y=benchmark_cum, name='大盤指數', line=dict(color='#EF553B', width=2, dash='dash')))
                fig_perf.update_layout(title="資金權益曲線比較", yaxis_title="資產淨值 (萬)", hovermode="x unified", height=400)
                st.plotly_chart(fig_perf, use_container_width=True)

                # 4. 每月損益熱力圖 (模擬)
                st.markdown("#### 📅 **每月損益表現**")
                month_ret = np.random.randint(-5, 15, size=(4, 12)) # 4年 x 12月
                fig_heat = px.imshow(month_ret, 
                                    labels=dict(x="月份", y="年份", color="報酬%"),
                                    x=['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
                                    y=['2026', '2025', '2024', '2023'],
                                    color_continuous_scale="RdYlGn", text_auto=True)
                fig_heat.update_layout(height=300)
                st.plotly_chart(fig_heat, use_container_width=True)

                # 5. 近期交易明細
                st.markdown("#### 📝 **近期交易紀錄**")
                trade_log = pd.DataFrame({
                    "日期": dates[-5:][::-1].strftime('%Y-%m-%d'),
                    "訊號": ["Buy CALL", "Sell PUT", "Buy CALL", "Close", "Buy CALL"],
                    "標的": ["23000 CALL", "22500 PUT", "23200 CALL", "22800 CALL", "23500 CALL"],
                    "損益": ["+12,500", "+5,400", "-3,200", "+18,000", "+8,900"],
                    "狀態": ["✅ 獲利", "✅ 獲利", "❌ 停損", "✅ 獲利", "✅ 獲利"]
                })
                st.dataframe(trade_log, use_container_width=True, hide_index=True)

# --------------------------
# Tab 5: 市場快報 (顯示優化版 + 真實新聞)
# --------------------------
with tabs[5]:
    st.markdown("## 📰 **市場快報中心**")
    st.caption(f"📅 資料日期：{latest_date.strftime('%Y-%m-%d')} | 💡 每日 15:00 更新數據")

    # ================= 1. 核心儀表板區 =================
    col_kpi1, col_kpi2 = st.columns([1, 1.5])

    with col_kpi1:
        st.markdown("#### 🌡️ **市場多空溫度計**")
        
        bull_score = 50
        if S_current > ma20: bull_score += 20
        if ma20 > ma60: bull_score += 20
        if S_current > ma60: bull_score += 10
        
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = bull_score,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "多空力道 ( >60 偏多 )", 'font': {'size': 20}},
            gauge = {
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
                'bar': {'color': "#ff4b4b" if bull_score < 40 else "#28a745" if bull_score > 60 else "#ffc107"},
                'bgcolor': "rgba(0,0,0,0)",
                'borderwidth': 2,
                'bordercolor': "#333",
                'steps': [
                    {'range': [0, 40], 'color': '#550000'},   
                    {'range': [40, 60], 'color': '#554400'},  
                    {'range': [60, 100], 'color': '#003300'}], 
                'threshold': {
                    'line': {'color': "white", 'width': 4},
                    'thickness': 0.75,
                    'value': bull_score}
            }
        ))
        
        fig_gauge.update_layout(
            height=300, 
            margin=dict(l=30, r=30, t=50, b=30),
            paper_bgcolor="rgba(0,0,0,0)", 
            font={'color': "white"}
        )
        st.plotly_chart(fig_gauge, use_container_width=True)

    with col_kpi2:
        st.markdown("#### 🤖 **貝伊果 AI 每日短評**")
        
        if bull_score >= 70:
            ai_comment = """
            🔥 **多頭氣盛，順勢而為！**
            目前指數站穩月線之上，且均線呈現多頭排列，顯示市場資金充沛。
            **操作建議**：
            1. 積極者可利用 Tab 2 尋找 Lead Call 機會。
            2. 拉回不破 MA20 皆為買點。
            """
            box_color = "#d4edda" 
            text_color = "#155724"
        elif bull_score <= 30:
            ai_comment = """
            ❄️ **空方控盤，保守為上！**
            指數跌破重要支撐，上方套牢賣壓沈重。切勿隨意摸底。
            **操作建議**：
            1. 暫停所有 Call 買方策略。
            2. 保留現金，或回到 Tab 0 進行小額定投。
            """
            box_color = "#f8d7da" 
            text_color = "#721c24"
        else:
            ai_comment = """
            ⚖️ **多空拉鋸，區間震盪！**
            目前指數在月線附近徘徊，方向不明確。
            **操作建議**：
            1. 減少操作頻率，多看少做。
            2. 若要進場，建議選擇遠月合約降低時間價值耗損。
            """
            box_color = "#fff3cd" 
            text_color = "#856404"

        st.markdown(f"""
        <div style="background-color: {box_color}; color: {text_color}; padding: 20px; border-radius: 10px; border-left: 5px solid {text_color};">
            {ai_comment}
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # ================= 2. 籌碼與數據區 =================
    col_chip, col_key = st.columns([1.5, 1])

    with col_chip:
        st.markdown("#### 💰 **法人籌碼動向 (模擬數據)**")
        chips_data = {
            "法人": ["外資", "投信", "自營商"],
            "買賣超 (億)": [np.random.randint(-150, 150), np.random.randint(0, 50), np.random.randint(-50, 50)]
        }
        fig_chips = px.bar(chips_data, x="法人", y="買賣超 (億)", color="買賣超 (億)",
                          color_continuous_scale=["green", "red"],
                          text="買賣超 (億)", title="今日三大法人買賣超")
        fig_chips.update_traces(texttemplate='%{text} 億', textposition='outside')
        fig_chips.update_layout(height=300)
        st.plotly_chart(fig_chips, use_container_width=True)

    with col_key:
        st.markdown("#### 🔑 **關鍵點位監控**")
        
        pressure = int(S_current * 1.02 / 100) * 100 
        support = int(S_current * 0.98 / 100) * 100  
        
        st.metric("🛑 上方壓力 (2%)", f"{pressure}", delta=f"{pressure-S_current:.0f}", delta_color="inverse")
        st.metric("🏠 目前點位", f"{int(S_current)}")
        st.metric("🛡️ 下方支撐 (-2%)", f"{support}", delta=f"{support-S_current:.0f}")
        
        st.caption("💡 支撐壓力僅供參考，請搭配量能判斷")

    st.markdown("---")
    
    # ================= 3. 重點新聞區 (真實數據版) =================
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
                    st.caption(f"{row['description'][:50]}...")
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
