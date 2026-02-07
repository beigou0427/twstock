"""
🔰 台指期權雙模式系統 (教學回歸版)
- TAB1：完整新手教學 (Lead Call、風險、名詞解釋) + 簡易操作
- TAB2：專業戰情室 (投組管理)
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from FinMind.data import DataLoader
import numpy as np
from scipy.stats import norm

# =========================
# Session State
# =========================
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []
if 'search_res_easy' not in st.session_state:
    st.session_state.search_res_easy = []

FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMi0wNyAyMDo0NjoxMiIsInVzZXJfaWQiOiJiYWdlbDA0MjciLCJlbWFpbCI6ImFzZDc4MzM1MjBAeWFob28uY29tLnR3IiwiaXAiOiIxMjIuMTIxLjE0Mi4xNiJ9.ReTy1gwAKK_UI-RrFJH1PpG8vupPY-dbMxBcVjbGYbM"

st.set_page_config(page_title="台指期權雙模式", layout="wide", page_icon="🔥")

# ---------------------------------
# 資料載入 & BS公式
# ---------------------------------
@st.cache_data(ttl=300)
def get_data(token):
    dl = DataLoader()
    dl.login_by_token(api_token=token)
    end_str = date.today().strftime("%Y-%m-%d")
    start_str = (date.today() - timedelta(days=10)).strftime("%Y-%m-%d")
    
    try:
        index_df = dl.taiwan_stock_daily("TAIEX", start_date=start_str, end_date=end_str)
        S = float(index_df["close"].iloc[-1]) if not index_df.empty else 23000.0
    except: S = 23000.0

    opt_start = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
    df = dl.taiwan_option_daily("TXO", start_date=opt_start, end_date=end_str)
    
    if df.empty: return S, pd.DataFrame(), pd.to_datetime(end_str)
    
    df["date"] = pd.to_datetime(df["date"])
    latest = df["date"].max()
    return S, df[df["date"] == latest].copy(), latest

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

with st.spinner("載入數據中..."):
    try:
        S_current, df_latest, latest_date = get_data(FINMIND_TOKEN)
    except:
        st.error("無法連線")
        st.stop()

# ==========================================
# 介面開始
# ==========================================
st.markdown("# 🔥 **台指期權雙模式系統**")
tab1, tab2 = st.tabs(["🔰 **簡易新手機** (推薦)", "🔥 **專業戰情室** (投組)"])

# ==========================================
# 分頁 1：簡易新手機 (含完整教學) - 只保留CALL
# ==========================================
with tab1:
    # === 完整新手教學區 (Lead Call / Theta / 名詞解釋) ===
    with st.expander("📚 **新手村：Lead Call 策略與名詞解釋（點我展開）**", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("""
            ### 🐣 **基礎名詞**
            *   **CALL (買權)** 📈：看漲。
            *   **成交價** 🟢：市場真實價格。
            *   **合理價** 🔵：理論計算價格 (無量時參考)。
            
            ### 🚀 **Lead Call 長期策略**
            1.  **買進**：選 **遠月 (季月)**，剩餘 >90 天。
            2.  **持有**：讓 Delta 成長，槓桿自然放大。
            3.  **賣出**：**剩餘 30~90 天** 賣出 (避開 Theta 加速區)。
            """)
        with c2:
            st.markdown("### 📉 **時間價值風險燈號**")
            risk_data = {
                "剩餘天數": [">90天", "30~90天", "<30天"],
                "狀態": ["🟢 安全 (持有)", "🟡 警戒 (準備賣)", "🔴 危險 (Theta加速)"],
                "動作": ["安心持有", "獲利了結", "強制平倉"]
            }
            st.dataframe(pd.DataFrame(risk_data), use_container_width=True)
            st.info("💡 **核心觀念**：遠月合約像股票，近月合約像樂透。新手請選遠月！")

    m1, m2 = st.columns(2)
    m1.metric("📈 加權指數", f"{S_current:,.0f}")
    m2.metric("📊 資料日期", latest_date.strftime("%Y-%m-%d"))

    st.divider()
    
    # ✅ 修正：補上 c4 變數，解決解包錯誤
    c1, c2, c3, c4 = st.columns([1.5, 2, 1.5, 1])

    with c1:
        st.markdown("### 📈 **固定CALL看漲**")
        st.info("✅ 已預設CALL策略")
        target_cp = "CALL"  # 固定CALL

    with c2:
        st.markdown("### 2️⃣ 月份 (預設遠月)")
        if not df_latest.empty:
            all_contracts = sorted(df_latest["contract_date"].astype(str).unique())
            ym_now = int(latest_date.strftime("%Y%m"))
            future_contracts = [c for c in all_contracts if c.isdigit() and int(c) >= ym_now]
            default_idx = len(future_contracts)-1 if future_contracts else 0
            sel_contract = st.selectbox("合約", future_contracts, index=default_idx, label_visibility="collapsed")
        else: sel_contract = ""

    with c3:
        st.markdown("### 3️⃣ 槓桿")
        target_lev = st.slider("倍數", 1.5, 20.0, 5.0, 0.5, label_visibility="collapsed")

    with c4:
        st.markdown("### 4️⃣ 篩選")
        safe_mode = st.checkbox("🔰 穩健模式", value=True, help="僅過濾極度價外 (Delta < 0.05)")

    if st.button("🎯 **尋找最佳CALL合約**", type="primary", use_container_width=True):
        if df_latest.empty:
            st.error("無資料")
        else:
            target_df = df_latest[(df_latest["contract_date"].astype(str) == sel_contract) & 
                                  (df_latest["call_put"].str.upper() == target_cp)].copy()
            
            y, m = int(sel_contract[:4]), int(sel_contract[4:6])
            days_left = max((date(y, m, 15) - latest_date.date()).days, 1)
            T = days_left / 365.0
            
            if 'implied_volatility' in target_df.columns:
                ivs = pd.to_numeric(target_df['implied_volatility'], errors='coerce').dropna()
                a_iv = ivs.median() if not ivs.empty else 0.2
            else: a_iv = 0.2
            
            results = []
            for _, row in target_df.iterrows():
                try:
                    K = float(row["strike_price"])
                    price = float(row["close"])
                    vol = int(row["volume"])
                    bs_p, delta = bs_price_delta(S_current, K, T, 0.02, a_iv, target_cp)
                    delta_abs = abs(delta)
                    
                    if safe_mode and delta_abs < 0.05: continue

                    if vol > 0 and price > 0:
                        calc_price = int(round(price, 0))
                        status = "🟢 成交價"
                    else:
                        calc_price = int(round(bs_p, 0))
                        status = "🔵 合理價"
                    
                    if calc_price <= 0: continue
                    
                    lev = (delta_abs * S_current) / calc_price
                    win = calculate_win_rate(delta_abs, days_left)
                    
                    results.append({
                        "履約價": int(K),
                        "參考價": calc_price,
                        "槓桿": round(lev, 2),
                        "成交量": vol,
                        "Delta": round(delta_abs, 2),
                        "勝率": round(win, 0),
                        "狀態": status,
                        "差距": abs(lev - target_lev)
                    })
                except: continue
            
            if results:
                results.sort(key=lambda x: x['差距'])
                best = results[0]
                st.session_state.search_res_easy = results
                
                st.balloons() # 🎉
                st.toast("🎉 找到最佳CALL合約！", icon="🚀")

                st.divider()
                st.markdown("### 🚀 **最佳推薦CALL合約**")
                
                c1, c2 = st.columns([2, 1])
                c1.metric(f"履約價 {best['履約價']}", f"{best['參考價']} 點", f"{best['狀態']}")
                c2.success("📈 CALL 看漲")
                
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("槓桿", f"{best['槓桿']}x")
                k2.metric("勝率", f"{best['勝率']}%")
                k3.metric("Delta", best['Delta'])
                k4.metric("成交量", best['成交量'])
                
                st.divider()
                
                # 10大警示
                with st.expander("⚠️ **操作前必看：10 大高風險警示**", expanded=False):
                    st.error("3️⃣ **資金鐵律**：1 口成本至少準備 **20倍** 本金，否則不要碰！")
                    st.error("6️⃣ **停損鐵律**：權利金跌 **20%** 立即平倉！")
                    st.warning("8️⃣ **時間風險**：到期前 30 天 Theta 加速，建議平倉。")
                    if days_left <= 30:
                        st.toast("🚨 警告：即將到期！", icon="⚠️")
                    
                st.markdown("### 📋 其他候選CALL合約")
                st.dataframe(pd.DataFrame(results).head(10)[["履約價","參考價","槓桿","勝率","Delta","狀態"]], use_container_width=True)
            else:
                st.warning("無符合條件的CALL合約")

# ==========================================
# 分頁 2：專業戰情室 (投組管理)
# ==========================================
with tab2:
    col_search, col_portfolio = st.columns([1.2, 0.8])
    
    # 左欄：搜尋
    with col_search:
        st.markdown("### 1️⃣ 合約搜尋")
        c1, c2, c3 = st.columns(3)
        with c1:
            dir_mode = st.selectbox("方向", ["CALL 📈", "PUT 📉"], key="pro_dir")
            target_cp_2 = "CALL" if "CALL" in dir_mode else "PUT"
        with c2:
            if not df_latest.empty:
                cons = sorted(df_latest["contract_date"].astype(str).unique())
                future_c = [c for c in cons if c.isdigit() and int(c) >= int(latest_date.strftime("%Y%m"))]
                sel_con_2 = st.selectbox("合約", future_c, index=len(future_c)-1 if future_c else 0, key="pro_con")
            else: sel_con_2 = ""
        with c3:
            lev_2 = st.slider("槓桿", 2.0, 15.0, 5.0, key="pro_lev")

        if st.button("🔥 搜尋", key="search_btn", use_container_width=True):
            if not df_latest.empty:
                tdf = df_latest[(df_latest["contract_date"].astype(str) == sel_con_2) & 
                                (df_latest["call_put"].str.upper() == target_cp_2)].copy()
                
                y, m = int(sel_con_2[:4]), int(sel_con_2[4:6])
                dl_2 = max((date(y, m, 15) - latest_date.date()).days, 1)
                T_2 = dl_2 / 365.0
                
                if 'implied_volatility' in tdf.columns:
                    ivs = pd.to_numeric(tdf['implied_volatility'], errors='coerce').dropna()
                    a_iv = ivs.median() if not ivs.empty else 0.2
                else: a_iv = 0.2

                res_2 = []
                for _, row in tdf.iterrows():
                    try:
                        K = float(row["strike_price"])
                        price = float(row["close"])
                        vol = int(row["volume"])
                        bs_p, d = bs_price_delta(S_current, K, T_2, 0.02, a_iv, target_cp_2)
                        d_abs = abs(d)
                        
                        if d_abs < 0.05: continue 
                        
                        cp = int(round(price, 0)) if vol > 0 else int(round(bs_p, 0))
                        if cp <= 0: continue
                        
                        l = (d_abs * S_current) / cp
                        w = calculate_win_rate(d_abs, dl_2)
                        
                        res_2.append({
                            "合約": sel_con_2, "類型": target_cp_2, "履約價": int(K),
                            "價格": cp, "槓桿": round(l, 2), "Delta": round(d_abs, 2),
                            "勝率": f"{int(w)}%", "剩餘天": dl_2, "差距": abs(l - lev_2)
                        })
                    except: continue
                
                if res_2:
                    res_2.sort(key=lambda x: x['差距'])
                    st.session_state.search_results = res_2
                    st.session_state.best_match = res_2[0]
        
        # 顯示搜尋結果與加入按鈕
        if 'best_match' in st.session_state and st.session_state.best_match:
            b = st.session_state.best_match
            st.success(f"🏆 推薦：{b['履約價']} {b['類型']} ({b['槓桿']}x)")
            if st.button("➕ 加入投組", key="add_pf"):
                exists = any(p['履約價'] == b['履約價'] and p['合約'] == b['合約'] for p in st.session_state.portfolio)
                if not exists: 
                    st.session_state.portfolio.append(b)
                    st.snow() # ❄️
                    st.toast("✅ 已加入投組", icon="❄️")
                else:
                    st.toast("⚠️ 已在投組中")
            
            st.dataframe(pd.DataFrame(st.session_state.search_results)[["履約價","價格","槓桿","勝率"]], use_container_width=True)

    # 右欄：投組
    with col_portfolio:
        st.markdown("### 2️⃣ 投組管理")
        if st.session_state.portfolio:
            pf = pd.DataFrame(st.session_state.portfolio)
            st.metric("總權利金", f"{pf['價格'].sum()} 點")
            
            def risk_color(val):
                color = 'red' if val <= 30 else 'orange' if val <= 90 else 'green'
                return f'color: {color}; font-weight: bold'
            
            st.dataframe(pf[["合約","履約價","槓桿","剩餘天"]].style.map(risk_color, subset=['剩餘天']), use_container_width=True)
            
            if st.button("🗑️ 清空"):
                st.session_state.portfolio = []
                st.rerun()
        else:
            st.info("投組為空")
