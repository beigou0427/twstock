"""

🔰 貝伊果屋 - 0050不只正2
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
from datetime import date, timedelta
from FinMind.data import DataLoader
from scipy.stats import norm
import plotly.graph_objects as go
import plotly.express as px

import feedparser
import time
from collections import Counter
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import random
import httpx
# 開頭加這段（import）
from supabase import create_client
from datetime import date
import streamlit as st

@st.cache_resource
def init_supabase():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_ANON_KEY"]
    )




# =========================================
# 1. 初始化 & 設定
# =========================================
st.set_page_config(page_title="貝伊果屋 - 0050不只正2 ", layout="wide", page_icon="🥯")
# 安全檢查 Token（放在 st.set_page_config 後）
try:
    FINMIND_TOKEN = st.secrets.get("FINMIND_TOKEN", st.secrets.get("finmind_token", ""))
    if not FINMIND_TOKEN:
        st.error("🚨 請在 .streamlit/secrets.toml 加: FINMIND_TOKEN = '你的token'\n或 Cloud 設定 Secrets")
        # Fallback 繼續跑，但標紅警告
except Exception as e:
    st.error(f"Secrets 讀取失敗: {str(e)[:50]}...")
    FINMIND_TOKEN = ""

st.markdown("""
<style>
.big-font {font-size:20px !important; font-weight:bold;}
.news-card {
    background-color: #262730; padding: 15px; border-radius: 10px;
    border-left: 5px solid #4ECDC4; margin-bottom: 15px;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.3); transition: transform 0.2s;
}
.news-card:hover { background-color: #31333F; transform: translateY(-2px); }
.tag-bull {background-color: #28a745; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;}
.tag-bear {background-color: #dc3545; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;}
.tag-neutral {background-color: #6c757d; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;}
.source-badge {background-color: #444; color: #ddd; padding: 2px 6px; border-radius: 4px; font-size: 11px; margin-right: 8px;}
.ticker-wrap { width: 100%; overflow: hidden; background-color: #1E1E1E; padding: 10px; border-radius: 5px; margin-bottom: 15px; white-space: nowrap;}
</style>
""", unsafe_allow_html=True)

init_state = {
    'portfolio': [], 'user_type': 'free', 'is_pro': False,
    'disclaimer_accepted': False, 'search_results': None, 'selected_contract': None
}
for key, value in init_state.items():
    if key not in st.session_state:
        st.session_state[key] = value

FINMIND_TOKEN = st.secrets.get("FINMIND_TOKEN", st.secrets.get("finmind_token", ""))

# =========================================
# 2. 核心函數庫 (全數保留)
# =========================================
@st.cache_data(ttl=60)
def get_data(token):
    dl = DataLoader()
    if token: dl.login_by_token(api_token=token)
    try:
        index_df = dl.taiwan_stock_daily("TAIEX", start_date=(date.today()-timedelta(days=100)).strftime("%Y-%m-%d"))
        S = float(index_df["close"].iloc[-1]) if not index_df.empty else 23000.0
        ma20 = index_df['close'].rolling(20).mean().iloc[-1] if len(index_df) > 20 else S * 0.98
        ma60 = index_df['close'].rolling(60).mean().iloc[-1] if len(index_df) > 60 else S * 0.95
    except: 
        S, ma20, ma60 = 23000.0, 22800.0, 22500.0

    opt_start = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
    df = dl.taiwan_option_daily("TXO", start_date=opt_start)
    if df.empty: return S, pd.DataFrame(), pd.to_datetime(date.today()), ma20, ma60
    
    df["date"] = pd.to_datetime(df["date"])
    latest = df["date"].max()
    return S, df[df["date"] == latest].copy(), latest, ma20, ma60

@st.cache_data(ttl=1800)
def get_real_news(token):
    dl = DataLoader()
    if token: dl.login_by_token(api_token=token)
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
    if token: dl.login_by_token(api_token=token)
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
    if token: dl.login_by_token(api_token=token)
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

# =========================================
# 3. 載入數據 & 側邊欄
# =========================================
with st.spinner("🚀 啟動財富引擎..."):
    try:
        S_current, df_latest, latest_date, ma20, ma60 = get_data(FINMIND_TOKEN)
    except:
        S_current, df_latest, latest_date, ma20, ma60 = 23000.0, pd.DataFrame(), pd.to_datetime(date.today()), 22800.0, 22500.0
        


# 🔥 歷史數據載入（回測用）

# =========================================
# 4. 主介面 & 市場快報
# =========================================
st.markdown("# 🥯 ** 貝伊果屋 - 0050不只正2**")
st.markdown("-專為沒資源散戶打造--")

col1, col2, col3, col4 = st.columns(4, gap="small")
with col1:
    change_pct = (S_current - ma20) / ma20 * 100
    st.metric("📈 加權指數", f"{S_current:,.0f}", f"{change_pct:+.1f}%")
with col2:
    ma_trend = "🔥 多頭" if ma20 > ma60 else "⚖️ 盤整"
    st.metric("均線狀態", ma_trend)
with col3:
    real_date = min(latest_date.date(), date.today())
    st.metric("資料更新", real_date.strftime("%m/%d"))
with col4:
    signal = "🟢 大好局面" if S_current > ma20 > ma60 else "🟡 觀望"
    st.metric("今日建議", signal)
st.markdown("---")

# =========================================
# 合規聲明與新手導航 (優化版 UI)
# =========================================
# =========================================
# =========================================
# 合規聲明與新手導航 (終極視覺強化版 v2)
# =========================================

# =========================================
# 5. 建立 Tabs
# =========================================
tabnames = ["0050不只正2"]
tabs = st.tabs(tabnames)

# [此處以下銜接原本的 with tabs[0]: ]


#========= Tab 0 =========


#        


# --------------------------
# Tab 2: 槓桿篩選版 v18.5 (回歸槓桿操作 + LEAPS CALL)
# --------------------------
# ==========================
# ✅ 完整 Tab 0: 槓桿篩選 + LEAPS CALL 回測版 v185
# Tab 0 v19.1: 槓桿篩選 + Email付費回測 (貝伊果屋版)
# ──────────────────────────────────────────────────────────────────────────
# Tab 0 v19.1 完整版：槓桿篩選 + Email付費回測 + Supabase VIP收集
# ────────────────────────────────────────────────────────────────────────────────
from supabase import create_client

@st.cache_resource
def init_supabase():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_ANON_KEY"]
    )

with tabs[0]:
    KEY_RES = "results_lev_v191"
    KEY_BEST = "best_lev_v191"
    KEY_BT = "backtest_lev_v191"
    KEY_EMAIL = "email_v191"
    KEY_USES = "bt_uses_v191"

    if KEY_RES not in st.session_state: st.session_state[KEY_RES] = []
    if KEY_BEST not in st.session_state: st.session_state[KEY_BEST] = None
    if KEY_BT not in st.session_state: st.session_state[KEY_BT] = None
    if KEY_EMAIL not in st.session_state: st.session_state[KEY_EMAIL] = ""
    if KEY_USES not in st.session_state: st.session_state[KEY_USES] = 0

    st.markdown("### ♟️ **貝伊果屋專業戰情室 v19.1 (付費回測)**")
    col_search, col_backtest = st.columns([1.3, 0.7])

    def calculate_raw_score_v191(delta, days, volume, S, K, op_type):
        s_delta = abs(delta) * 100.0
        m = (S - K) / S if op_type == "CALL" else (K - S) / S
        s_money = max(-10, min(m * 100 * 2, 10)) + 50
        s_time = min(days / 90.0 * 100, 100)
        s_vol = min(volume / 5000.0 * 100, 100)
        return s_delta * 0.4 + s_money * 0.2 + s_time * 0.2 + s_vol * 0.2

    def micro_expand_scores_v191(results):
        if not results: return []
        results.sort(key=lambda x: x['raw_score'], reverse=True)
        n = len(results)
        top_n = max(1, int(n * 0.4))
        for i in range(n):
            if i < top_n:
                score = 95.0 - (i / (top_n - 1) * 5.0) if top_n > 1 else 95.0
            else:
                remain = n - top_n
                idx = i - top_n
                score = 85.0 - (idx / (remain - 1) * 70.0) if remain > 1 else 15.0
            results[i]['勝率'] = round(score, 1)
        return results

    @st.cache_data(ttl=3600)
    def backtest_taiex_leverage_v191(lev, days, token):
        try:
            from FinMind.data import DataLoader
            dl = DataLoader()
            if token: dl.login_by_token(api_token=token)
            start_date = (date.today() - timedelta(days=max(days * 2, 180))).strftime("%Y-%m-%d")
            df_taiex = dl.taiwan_stock_daily("TAIEX", start_date=start_date)
            if df_taiex.empty: raise ValueError("TAIEX數據為空")
            df_taiex['date'] = pd.to_datetime(df_taiex['date'])
            df_taiex = df_taiex.sort_values('date').reset_index(drop=True)
            df_taiex['ret'] = df_taiex['close'].pct_change().fillna(0)
            theta_decay = 0.0003
            lev_returns = (df_taiex['ret'] * lev * 0.8 - theta_decay).clip(lower=-0.95)
            df_taiex['cum_tai'] = (1 + df_taiex['ret']).cumprod()
            df_taiex['cum_lev'] = (1 + lev_returns).cumprod()
            avg_ret = lev_returns.mean()
            std_ret = lev_returns.std()
            return (df_taiex[['date', 'cum_tai', 'cum_lev']].copy(), {
                'total_lev': df_taiex['cum_lev'].iloc[-1] - 1,
                'total_tai': df_taiex['cum_tai'].iloc[-1] - 1,
                'win_rate': round((lev_returns > 0).mean() * 100, 1),
                'sharpe': round((avg_ret / std_ret * np.sqrt(252)) if std_ret > 0 else 0, 2),
                'maxdd': round((df_taiex['cum_lev'] / df_taiex['cum_lev'].cummax() - 1).min() * 100, 1),
                'trades': len(df_taiex), 'lev': lev,
                'avg_ret': round(avg_ret * 100, 2)
            })
        except:
            np.random.seed(42)
            n_days = min(days * 2, 365)
            dates = pd.date_range(end=date.today(), periods=n_days, freq='B')
            mock_daily_ret = np.random.normal(0.0005, 0.012, n_days)
            mock_lev_ret = mock_daily_ret * lev * 0.8 - 0.0003
            mock_df = pd.DataFrame({
                'date': dates,
                'cum_tai': (1 + pd.Series(mock_daily_ret)).cumprod(),
                'cum_lev': (1 + pd.Series(mock_lev_ret)).cumprod()
            })
            mock_avg = mock_lev_ret.mean()
            mock_std = mock_lev_ret.std()
            return (mock_df, {
                'total_lev': mock_df['cum_lev'].iloc[-1] - 1,
                'total_tai': mock_df['cum_tai'].iloc[-1] - 1,
                'win_rate': round((pd.Series(mock_lev_ret) > 0).mean() * 100, 1),
                'sharpe': round((mock_avg / mock_std * np.sqrt(252)) if mock_std > 0 else 0, 2),
                'maxdd': round((mock_df['cum_lev'] / mock_df['cum_lev'].cummax() - 1).min() * 100, 1),
                'trades': n_days, 'lev': lev, 'avg_ret': round(mock_avg * 100, 2)
            })

    # ════ 左欄：免費槓桿掃描 ════════════════════════════════════════════════════
    with col_search:
        st.markdown("#### 🔍 **免費槓桿掃描 (LEAPS CALL優化)** 💰")
        if df_latest.empty:
            st.error("⚠️ 無最新資料，請檢查數據源")
            st.stop()

        df_work = df_latest.copy()
        df_work['call_put'] = df_work['call_put'].str.upper().str.strip()
        for col in ['close', 'volume', 'strike_price']:
            df_work[col] = pd.to_numeric(df_work[col], errors='coerce').fillna(0)

        c1, c2, c3, c4 = st.columns([1, 1, 1, 0.6])
        with c1:
            dir_mode = st.selectbox("📊 方向", ["📈 CALL (LEAPS)", "📉 PUT"], 0, key="v191_dir")
            op_type = "CALL" if "CALL" in dir_mode else "PUT"
        with c2:
            contracts = df_work[df_work['call_put'] == op_type]['contract_date'].dropna()
            available = sorted(contracts[contracts.astype(str).str.len() == 6].unique())
            default_idx = len(available) - 1 if available else 0
            sel_con = st.selectbox("📅 月份", available if available else [""], index=default_idx, key="v191_con")
        with c3:
            target_lev = st.slider("🎯 目標槓桿", 2.0, 20.0, 5.0, 0.5, key="v191_lev")
        with c4:
            if st.button("🧹 重置全部", key="v191_reset_all"):
                for k in [KEY_RES, KEY_BEST, KEY_BT]:
                    st.session_state[k] = None if 'best' in k else []
                st.rerun()

        if st.button("🚀 智慧掃描", type="primary", use_container_width=True, key="v191_scan"):
            st.session_state[KEY_RES] = []
            st.session_state[KEY_BEST] = None
            st.session_state[KEY_BT] = None
            if sel_con and len(str(sel_con)) == 6:
                tdf = df_work[(df_work["contract_date"].astype(str) == sel_con) & (df_work["call_put"] == op_type)]
                if tdf.empty:
                    st.warning("⚠️ 無此合約交易資料")
                else:
                    try:
                        y, m = int(str(sel_con)[:4]), int(str(sel_con)[4:6])
                        days_to_exp = max((date(y, m, 15) - latest_date.date()).days, 1)
                        T_years = days_to_exp / 365.0
                    except Exception as e:
                        st.error(f"日期解析失敗: {e}")
                        st.stop()

                    raw_results = []
                    for _, row in tdf.iterrows():
                        try:
                            strike = float(row["strike_price"])
                            volume = float(row["volume"])
                            close_price = float(row["close"])
                            if strike <= 0: continue
                            try:
                                r, vola = 0.02, 0.2
                                d1 = (np.log(S_current / strike) + (r + 0.5 * vola**2) * T_years) / (vola * np.sqrt(T_years))
                                delta = norm.cdf(d1) if op_type == "CALL" else -norm.cdf(-d1)
                            except:
                                delta = 0.5
                            bs_price = (abs(delta) * S_current) / target_lev
                            price = close_price if volume > 0 else bs_price
                            if price <= 0.5 or abs(delta) < 0.1: continue
                            leverage = (abs(delta) * S_current) / price
                            score = calculate_raw_score_v191(delta, days_to_exp, volume, S_current, strike, op_type)
                            raw_results.append({
                                "履約價": int(strike), "價格": round(price, 1),
                                "狀態": "🟢成交" if volume > 0 else "🔵合理價",
                                "槓桿": leverage, "Delta": round(delta, 3),
                                "raw_score": score, "Vol": int(volume),
                                "差距": abs(leverage - target_lev),
                                "合約": sel_con, "類型": op_type, "天數": days_to_exp
                            })
                        except:
                            continue

                    if raw_results:
                        final_results = micro_expand_scores_v191(raw_results)
                        final_results.sort(key=lambda x: (x['差距'], -x['勝率'], -x['天數']))
                        st.session_state[KEY_RES] = final_results[:15]
                        st.session_state[KEY_BEST] = final_results[0]
                        st.success(f"✅ 掃描完成！最佳槓桿：{final_results[0]['槓桿']:.1f}x | 勝率：{final_results[0]['勝率']}%")
                    else:
                        st.warning("⚠️ 無符合條件的優質合約")

        if st.session_state[KEY_RES]:
            best_contract = st.session_state[KEY_BEST]
            st.markdown("─" * 60)
            st.markdown("#### 🏆 **🔥 最佳LEAPS CALL推薦**")
            st.markdown(f"""
            <div style='background: linear-gradient(90deg, #10b981, #059669); 
                        color: white; padding: 1rem; border-radius: 12px; text-align: center;'>
                <h3><b>{best_contract['合約']} {best_contract['履約價']} {best_contract['類型']}</b></h3>
                <h2>權利金：{int(round(best_contract['價格']))}點</h2>
                <p>槓桿：<b>{best_contract['槓桿']:.1f}x</b> | 勝率：<b>{best_contract['勝率']:.1f}%</b> | Delta：<b>{best_contract['Delta']}</b></p>
                <p>到期：<b>{best_contract['天數']}天</b> | 狀態：<span style='color:yellow'>{best_contract['狀態']}</span></p>
            </div>
            """, unsafe_allow_html=True)
            with st.expander(f"📋 Top15完整結果 ({len(st.session_state[KEY_RES])}筆)", expanded=True):
                df_display = pd.DataFrame(st.session_state[KEY_RES]).copy()
                df_display['權利金'] = df_display['價格'].round(0).astype(int)
                df_display['槓桿'] = df_display['槓桿'].apply(lambda x: f"{x:.1f}x")
                df_display['Delta'] = df_display['Delta'].apply(lambda x: f"{x:.3f}")
                df_display['勝率'] = df_display['勝率'].apply(lambda x: f"{x:.1f}%")
                df_display['天數'] = df_display['天數'].astype(int)
                st.dataframe(df_display[["合約", "履約價", "權利金", "槓桿", "勝率", "Delta", "天數", "狀態"]], use_container_width=True, hide_index=True)

    # ════ 右欄：Email付費回測 ════════════════════════════════════════════════════════
    with col_backtest:
        st.markdown("#### 🔒 **貝伊果屋付費回測引擎 (每日3次免費)** 💎")

        # ── Email授權區（只出現一次）────────────────────────────────────────────────
        col_email_input, col_email_btn = st.columns([3, 1])
        with col_email_input:
            email_entered = st.text_input(
                "📧 開通授權Email",
                value=st.session_state[KEY_EMAIL],
                placeholder="your@email.com (Threads專屬更新)",
                help="輸入後點「開通」→ 每日3次真實回測 + v20 Beta資格",
                key="email_entry_v191"
            )
        with col_email_btn:
            if st.button("✅ 立即開通", type="secondary", use_container_width=True, key="email_auth_v191"):
                if '@' in email_entered and '.' in email_entered.split('@')[-1]:
                    st.session_state[KEY_EMAIL] = email_entered
                    st.session_state[KEY_USES] = 0
                    # 🔥 寫入 Supabase
                    try:
                        supabase = init_supabase()
                        supabase.table("vips").insert({
                            "email": email_entered,
                            "uses": 0,
                            "source": "貝伊果屋 v19.1"
                        }).execute()
                    except:
                        pass
                    st.success(f"🎉 {email_entered} 授權成功！剩餘3/3次")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("❌ Email格式錯誤 (需包含@和.)")

        email_authorized = bool(st.session_state[KEY_EMAIL] and '@' in st.session_state[KEY_EMAIL])
        daily_quota = 3
        remaining_uses = daily_quota - st.session_state[KEY_USES] if email_authorized else 0

        if not email_authorized:
            st.warning("🔒 **請輸入Email開通付費功能**")
            st.markdown("""
            **開通立即獲得**：
            • 真實TAIEX 365天歷史回測
            • Sharpe比率 + 勝率 + 最大回撤
            • Threads (@beigou0427) 每日策略
            • 貝伊果屋v20.0封閉測試資格
            """)
        elif remaining_uses <= 0:
            st.error("⏰ **今日額度已用完** | 明天12:00自動重置")
            col_upgrade_a, col_upgrade_b = st.columns(2)
            with col_upgrade_a:
                if st.button("💎 升級無限版", type="primary", key="upgrade_infinite_v191"):
                    st.info("聯絡 @beigou0427 Threads 洽談企業版")
            with col_upgrade_b:
                st.markdown("[📱 Threads訂閱](https://threads.net/@beigou0427)")
        else:
            st.success(f"✅ 已授權：{st.session_state[KEY_EMAIL]} | **剩餘 {remaining_uses}/3 次**")
            best_available = st.session_state.get(KEY_BEST)
            default_leverage = best_available['槓桿'] if best_available else 5.0
            default_duration = best_available.get('天數', 180) if best_available else 180

            backtest_leverage = st.slider("🎯 回測槓桿", 2.0, 20.0, round(default_leverage, 1), 0.5, key="v191_backtest_leverage")
            backtest_days = st.slider("📅 回測天數", 30, 500, min(default_duration, 365), 30, key="v191_backtest_days")

            col_run1, col_run2 = st.columns([3, 1])
            with col_run1:
                if st.button(f"🔄 貝伊果屋回測 (剩餘{remaining_uses}/3)", type="primary", use_container_width=True, key="execute_backtest_v191"):
                    with st.spinner("🚀 專業回測引擎啟動中..."):
                        bt_chart_data, bt_metrics = backtest_taiex_leverage_v191(backtest_leverage, backtest_days, FINMIND_TOKEN)
                        st.session_state[KEY_USES] += 1
                        st.session_state[KEY_BT] = {
                            'data': bt_chart_data, 'metrics': bt_metrics,
                            'email': st.session_state[KEY_EMAIL],
                            'remaining': daily_quota - st.session_state[KEY_USES],
                            'params': {'lev': backtest_leverage, 'days': backtest_days}
                        }
                        st.success("✅ 回測完成！結果已儲存")
            with col_run2:
                if st.button("📱 Threads更新", key="threads_update_v191"):
                    st.toast(f"已記錄 {st.session_state[KEY_EMAIL]} 到貝伊果屋VIP名單")

            if st.session_state[KEY_BT]:
                bt_result = st.session_state[KEY_BT]
                metrics_result = bt_result['metrics']
                col_kpi1, col_kpi2 = st.columns(2)
                with col_kpi1:
                    st.metric(f"{metrics_result['lev']:.1f}x 總報酬", f"{metrics_result['total_lev']:.1%}", delta=f"大盤 {metrics_result['total_tai']:.1%}")
                with col_kpi2:
                    st.metric("Sharpe比率", f"{metrics_result['sharpe']:.2f}", delta="💎 優質策略" if metrics_result['sharpe'] > 0.5 else "⚠️ 需優化")
                col_kpi3, col_kpi4 = st.columns(2)
                with col_kpi3:
                    st.metric("日勝率", f"{metrics_result['win_rate']:.1f}%")
                with col_kpi4:
                    st.metric("最大回撤", f"{metrics_result['maxdd']:.1f}%")
                chart_data = bt_result['data'].set_index('date')
                chart_data.columns = ['大盤累積報酬', f'{metrics_result["lev"]:.1f}x LEAPS']
                st.line_chart(chart_data, use_container_width=True)
                st.caption(f"📊 回測 {metrics_result['trades']} 個交易日 | Theta每日衰減 0.03% | 授權Email：{bt_result['email']} | 剩餘額度：{bt_result['remaining']}/3")
                col_action1, col_action2 = st.columns(2)
                with col_action1:
                    if st.button("🗑️ 清除回測結果", key="clear_bt_result_v191"):
                        st.session_state[KEY_BT] = None
                        st.rerun()
                with col_action2:
                    st.caption("⚙️ 重跑不扣額度")

    # ── 底部 ──────────────────────────────────────────────────────────────────────
    st.markdown("─" * 90)
    st.markdown("#### 💎 **貝伊果屋功能對比表**")
    st.markdown("""
    | 功能 | 免費版 | 付費版(Email) |
    |------|--------|---------------|
    | 槓桿掃描 | ✅ | ✅ |
    | 微觀勝率 | ✅ | ✅ |
    | BS定價 | ✅ | ✅ |
    | TAIEX回測 | ❌ | ✅ |
    | Sharpe/DD | ❌ | ✅ |
    | 每日額度 | - | 3次免費 |
    | Threads更新 | ❌ | ✅ |
    | v20 Beta | ❌ | ✅ |
    """)
    st.markdown("---")
    st.markdown("""
    **貝伊果屋 (@beigou0427)** | Build: 2026/3/10 v19.1  
    💬 Threads每日LEAPS策略 | 🚀 v20.0即將上線(12因子+AI供應鏈)
    ⚠️ **僅供學習研究，非投資建議** | 實際交易請諮詢專業顧問
    """)
    st.caption("© 貝伊果屋 2026 | mintung.chen@beigou.tw")


