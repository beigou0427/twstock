# -------------------------
# 5) 載入數據
# -------------------------
with st.spinner("🚀 啟動財富引擎..."):
    try:
        S_current, df_latest, latest_date, ma20, ma60 = get_data(FINMIND_TOKEN)
    except Exception:
        st.error("連線逾時，請重整頁面")
        st.stop()

# -------------------------
# 6) 側邊欄（加 Quick Scan / Share）
# -------------------------
with st.sidebar:
    st.markdown("## 🔥**強烈建議**🔥")
    st.markdown("## **閱讀下列書籍後!才投資!**")

    st.image(
        "https://down-tw.img.susercontent.com/file/sg-11134201-7qvdl-lh2v8yc9n8530d.webp",
        caption="持續買進: 資料科學家的投資終極解答",
        use_container_width=True,
    )
    st.markdown("[🛒 購買『 持續買進 』](https://s.shopee.tw/5AmrxVrig8)")

    st.divider()

    st.image(
        "https://down-tw.img.susercontent.com/file/tw-11134207-7rasc-m2ba9wueqaze3a.webp",
        caption="長期買進：財金教授周冠男的42堂自制力投資課",
        use_container_width=True,
    )
    st.markdown("[🛒 購買『 長期買進 』](https://s.shopee.tw/6KypLiCjuy)")

    st.divider()
    st.caption("📊 功能導航：\n• Tab0 定投\n• Tab1 情報\n• Tab2 CALL獵人\n• Tab3 回測\n• Tab4 戰情室")

    st.divider()
    st.markdown("### ⚡ Quick Scan（跳到 Tab2）")
    qs_dir = st.selectbox("方向", ["CALL", "PUT"], index=0, key="qs_dir")
    qs_lev = st.slider("目標槓桿", 2.0, 20.0, 5.0, 0.5, key="qs_lev")

    # 預設遠月合約：由 df_latest 推最遠 contract_date
    sel_con_quick = ""
    try:
        if not df_latest.empty:
            con_all = (
                df_latest[df_latest["call_put"].astype(str).str.upper().str.strip() == qs_dir]["contract_date"]
                .dropna()
                .astype(str)
            )
            con_all = con_all[con_all.str.len() == 6].unique().tolist()
            con_all = sorted(con_all)
            if con_all:
                sel_con_quick = con_all[-1]
    except Exception:
        sel_con_quick = ""

    st.caption(f"預設月份：{sel_con_quick if sel_con_quick else 'N/A'}")

    if st.button("🔍 一鍵掃描 Top 15", type="primary", use_container_width=True):
        st.session_state["quick_scan_payload"] = {
            "sel_con": sel_con_quick,
            "op_type": qs_dir,
            "target_lev": qs_lev,
        }
        st.query_params["jump"] = "2"
        st.rerun()

    st.divider()
    st.markdown("### 🔗 分享")
    st.caption("把這頁貼到 Threads，配一張結果截圖效果最好。")
    st.code("https://你的網域或 streamlit app 連結", language="text")

# -------------------------
# 7) 主介面 & 市場快報
# -------------------------
st.markdown("# 🥯 **貝伊果屋：財富雙軌系統**")

st.markdown("---")
col1, col2, col3, col4 = st.columns(4)
with col1:
    change_pct = (S_current - ma20) / ma20 * 100 if ma20 else 0
    st.metric("📈 加權指數", f"{S_current:,.0f}", f"{change_pct:+.1f}%")
with col2:
    ma_trend = "🔥 多頭" if ma20 > ma60 else "⚖️ 盤整"
    st.metric("均線狀態", ma_trend)
with col3:
    st.metric("資料更新", latest_date.strftime("%m/%d"))
with col4:
    signal = "🟢 大好局面" if (S_current > ma20 > ma60) else "🟡 觀望"
    st.metric("今日建議", signal)
st.markdown("---")

# -------------------------
# 8) 合規聲明 Gate
# -------------------------
if not st.session_state.get("disclaimer_accepted", False):
    st.error("🚨 **股票完全新手必讀！**")
    st.markdown(
        """
**先搞懂股票基礎：**
- 💹 **股票** = 買公司股份，股價漲才賺錢
- 📈 **ETF** = 一籃子優質股票，新手首選
- 💳 **定期定額** = 每月固定買，避開追高殺低
"""
    )

    st.markdown("---")
    st.markdown("## 🎯 **貝伊果屋5大功能**")
    st.markdown(
        """
**🌱 新手起手（先練這3個）**
- **Tab0 定投計畫**：設定每月自動買ETF，複利致富
- **Tab1 智能情報**：看懂台股熱門 + 大盤趨勢
- **Tab4 戰情室**：追蹤市場熱門題材（AI、半導體）

**🚀 中級看多（看好中長期）**
- **Tab2 CALL獵人**：找**半年以上到期CALL**（低成本槓桿看多）

**🧠 高手專用（會寫策略）**
- **Tab3 回測系統**：驗證策略過去10年績效
"""
    )

    st.markdown("---")
    if st.button("✅ **我懂基礎，開始使用**", type="primary", use_container_width=True):
        st.session_state.disclaimer_accepted = True
        st.balloons()
        st.rerun()
    st.stop()

# -------------------------
# 9) Tabs
# -------------------------
tab_names = [
    "🏦 **穩健ETF**",
    "🌍 **智能情報**",
    "🔰 **期權獵人**",
    "📊 **歷史回測**",
    "🔥 **專業戰情室**",
]
tab_names += [f"🛠️ 擴充 {i+2}" for i in range(9)]
tabs = st.tabs(tab_names)

# --------------------------
# Tab 0: 穩健 ETF
# --------------------------
with tabs[0]:
    if not st.session_state.get("etf_done", False):
        st.markdown("### 🚨 新手入門")
        st.info("ETF=股票籃子 | 定投=每月買")
        if st.button("開始"):
            st.session_state.etf_done = True
            st.rerun()
        st.stop()

    st.markdown("## 🐢 ETF 定投")

    @st.cache_data(ttl=1800)
    def safe_backtest(token: str):
        try:
            api = DataLoader()
            api.login_by_token(api_token=token)
            etfs = ["0050", "006208", "00662", "00757", "00646"]
            end = date.today().strftime("%Y-%m-%d")
            start = (date.today() - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
            rows = []
            for etf in etfs:
                df = api.taiwan_stock_daily(etf, start, end)
                if len(df) > 100:
                    first = float(df["close"].iloc[0])
                    last = float(df["close"].iloc[-1])
                    yrs = (pd.to_datetime(df["date"].iloc[-1]) - pd.to_datetime(df["date"].iloc[0])).days / 365.25
                    yrs = max(yrs, 0.1)
                    total = (last / first - 1) * 100
                    ann = ((last / first) ** (1 / yrs) - 1) * 100
                    cum_max = df["close"].expanding().max()
                    dd = ((df["close"] - cum_max) / cum_max * 100).min()
                    rows.append([etf, f"{total:.1f}%", f"{ann:.1f}%", f"{yrs:.1f}", f"{dd:.1f}%"])
                else:
                    rows.append([etf, "-", "-", "-", "-"])
            return pd.DataFrame(rows, columns=["ETF", "總報酬", "年化", "年數", "回撤"])
        except Exception:
            return pd.DataFrame(
                {
                    "ETF": ["0050", "006208", "00662", "00757", "00646"],
                    "總報酬": ["-", "-", "-", "-", "-"],
                    "年化": ["-", "-", "-", "-", "-"],
                    "年數": ["-", "-", "-", "-", "-"],
                    "回撤": ["-", "-", "-", "-", "-"],
                }
            )

    perf_df = safe_backtest(FINMIND_TOKEN)
    st.dataframe(perf_df, use_container_width=True)
    if st.button("🔄 刷新數據"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown("### 💰 定投試算器")
    c1, c2, c3 = st.columns(3)
    with c1:
        mon_in = st.number_input("每月投入", 1000, 50000, 10000, 1000)
    with c2:
        yrs_in = st.slider("年數", 5, 30, 10)
    with c3:
        etf_sel = st.selectbox("ETF", perf_df["ETF"].tolist())
        ann_val = perf_df[perf_df["ETF"] == etf_sel]["年化"].values[0]
        rate_use = float(str(ann_val).replace("%", "")) / 100 if "%" in str(ann_val) else 0.10

    final_amt = mon_in * 12 * (((1 + rate_use) ** yrs_in - 1) / max(rate_use, 1e-9))
    st.metric(f"{yrs_in}年總資產", f"NT${final_amt:,.0f}")

    yrs_arr = np.arange(1, yrs_in + 1)
    amt_arr = [mon_in * 12 * (((1 + rate_use) ** y - 1) / max(rate_use, 1e-9)) for y in yrs_arr]
    fig = px.line(pd.DataFrame({"年": yrs_arr, "資產": amt_arr}), x="年", y="資產")
    st.plotly_chart(fig, height=280, use_container_width=True)

# --------------------------
# Tab 1: 智能全球情報中心
# --------------------------
with tabs[1]:
    st.markdown("## 🌍 **智能全球情報中心**")

    m = get_real_market_ticker(FINMIND_TOKEN)
    st.markdown(
        f"""
<div class="ticker-wrap">
  🚀 <b>即時行情:</b>
  TAIEX: <span style="color:{m.get('taiex_color','gray')}">{m.get('taiex','N/A')} ({m.get('taiex_pct','')})</span> &nbsp;|&nbsp;
  台積電: <span style="color:{m.get('tsmc_color','gray')}">{m.get('tsmc','N/A')} ({m.get('tsmc_pct','')})</span> &nbsp;|&nbsp;
  Nasdaq期: <span style="color:{m.get('nq_color','gray')}">{m.get('nq','N/A')} ({m.get('nq_pct','')})</span> &nbsp;|&nbsp;
  Bitcoin: <span style="color:{m.get('btc_color','gray')}">{m.get('btc','N/A')} ({m.get('btc_pct','')})</span>
</div>
""",
        unsafe_allow_html=True,
    )
    st.caption("數據來源：FinMind (台股) + Yahoo Finance (國際/加密幣)")

    with st.spinner("🤖 正在掃描全球市場訊號..."):
        all_news, sentiment_idx, sentiment_label, top_keywords = build_news_feed(FINMIND_TOKEN)

    col_dash1, col_dash2 = st.columns([1, 2])
    with col_dash1:
        st.markdown(f"#### 🌡️ 市場情緒：{sentiment_label}")
        fig_gauge = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=50 + sentiment_idx * 50,
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "#4ECDC4"},
                    "steps": [
                        {"range": [0, 40], "color": "rgba(255,0,0,0.2)"},
                        {"range": [60, 100], "color": "rgba(0,255,0,0.2)"},
                    ],
                },
            )
        )
        fig_gauge.update_layout(height=220, margin=dict(l=20, r=20, t=10, b=20), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_gauge, use_container_width=True)

    with col_dash2:
        st.markdown("#### 🔥 **今日市場熱詞**")
        try:
            selected = st.pills("篩選新聞：", top_keywords, selection_mode="single", default="全部")
        except Exception:
            st.markdown(
                """
<style>
div[role="radiogroup"] {flex-direction: row; gap: 8px; flex-wrap: wrap;}
div[role="radiogroup"] label > div:first-child {display: none;}
div[role="radiogroup"] label {background: #333; padding: 4px 12px; border-radius: 15px; border: 1px solid #555; cursor: pointer; transition: 0.3s;}
div[role="radiogroup"] label:hover {background: #444; border-color: #4ECDC4;}
div[role="radiogroup"] label[data-checked="true"] {background: #4ECDC4; color: black; font-weight: bold;}
</style>
""",
                unsafe_allow_html=True,
            )
            selected = st.radio("篩選新聞：", top_keywords, label_visibility="collapsed")

        st.session_state["filter_kw"] = selected
        st.success(f"🔍 篩選：#{selected} | 📊 市場氣氛：{sentiment_label}")

    st.divider()
    st.markdown("### 📰 **精選快訊**")

    current_filter = st.session_state.get("filter_kw", "全部")
    filtered = []
    for n in all_news:
        title_str = str(n.get("title", ""))
        summary_str = str(n.get("summary", ""))
        if current_filter == "全部":
            filtered.append(n)
        elif (current_filter in title_str) or (current_filter in summary_str):
            filtered.append(n)

    if not filtered:
        st.info(f"⚠️ 暫無包含「{current_filter}」的新聞，顯示全部。")
        filtered = all_news

    left, right = st.columns(2)
    for i, n in enumerate(filtered[:20]):
        with (left if i % 2 == 0 else right):
            render_news_card(n)

# --------------------------
# Tab 2: 期權獵人（LEAPS CALL）
# --------------------------
with tabs[2]:
    KEY_RES = "results_lev_v185"
    KEY_BEST = "best_lev_v185"
    KEY_PF = "portfolio_lev"
    st.session_state.setdefault(KEY_RES, [])
    st.session_state.setdefault(KEY_BEST, None)
    st.session_state.setdefault(KEY_PF, [])

    st.markdown("### ♟️ **專業戰情室 (槓桿篩選 + 微觀勝率 + LEAPS CALL)**")

    col_search, col_portfolio = st.columns([1.3, 0.7])

    with col_search:
        st.markdown("#### 🔍 **槓桿掃描 (LEAPS CALL 優化)**")
        if df_latest.empty:
            st.error("⚠️ 無期權資料")
            st.stop()

        df_work = df_latest.copy()
        df_work["call_put"] = df_work["call_put"].astype(str).str.upper().str.strip()

        c1, c2, c3, c4 = st.columns([1, 1, 1, 0.6])
        with c1:
            dir_mode = st.selectbox("方向", ["📈 CALL (LEAPS)", "📉 PUT"], 0, key="v185_dir")
            op_type = "CALL" if "CALL" in dir_mode else "PUT"
        with c2:
            contracts = df_work[df_work["call_put"] == op_type]["contract_date"].dropna().astype(str)
            available = sorted([c for c in contracts.unique().tolist() if len(str(c)) == 6])
            default_idx = len(available) - 1 if available else 0
            sel_con = st.selectbox("月份", available if available else [""], index=default_idx, key="v185_con")
        with c3:
            target_lev = st.slider("目標槓桿", 2.0, 20.0, 5.0, 0.5, key="v185_lev")
        with c4:
            if st.button("🧹 重置", key="v185_reset"):
                st.session_state[KEY_RES] = []
                st.session_state[KEY_BEST] = None
                st.rerun()

        # Quick Scan 進來就直接跑一次（避免使用者還要再按）
        if "quick_scan_payload" in st.session_state and st.session_state["quick_scan_payload"]:
            payload = st.session_state["quick_scan_payload"]
            st.session_state["quick_scan_payload"] = None
            sel_con = payload.get("sel_con", sel_con)
            op_type = payload.get("op_type", op_type)
            target_lev = float(payload.get("target_lev", target_lev))

            st.info(f"已套用 Quick Scan：{op_type} / {sel_con} / 目標槓桿 {target_lev:.1f}x")

            results = scan_leaps(df_latest, S_current, latest_date, sel_con, op_type, target_lev)
            st.session_state[KEY_RES] = results
            st.session_state[KEY_BEST] = results[0] if results else None

        if st.button("🚀 執行掃描", type="primary", use_container_width=True, key="v185_scan"):
            results = scan_leaps(df_latest, S_current, latest_date, sel_con, op_type, target_lev)
            st.session_state[KEY_RES] = results
            st.session_state[KEY_BEST] = results[0] if results else None
            if results:
                st.success(f"掃描完成！最佳槓桿：{results[0]['槓桿']:.1f}x")
            else:
                st.warning("無符合資料")

        if st.session_state[KEY_RES]:
            best = st.session_state[KEY_BEST]
            st.markdown("---")
            cA, cB = st.columns([2, 1])
            with cA:
                st.markdown("#### 🏆 **最佳推薦 (LEAPS CALL)**")
                p_int = int(round(float(best["價格"])))
                st.markdown(
                    f"`{best['合約']} {best['履約價']} {best['類型']}` **{p_int}點**  \n"
                    f"槓桿 `{best['槓桿']:.1f}x` | 勝率 `{best['勝率']:.1f}%` | 天數 `{best.get('天數', 0)}天`"
                )
            with cB:
                if st.button("➕ 加入", key="add_pf_v185"):
                    exists = any(
                        (p.get("履約價") == best.get("履約價")) and (p.get("合約") == best.get("合約"))
                        for p in st.session_state[KEY_PF]
                    )
                    if not exists:
                        st.session_state[KEY_PF].append(best)
                        st.toast("✅ 已加入投組")
                    else:
                        st.toast("⚠️ 已存在")

            with st.expander("📋 搜尋結果 (依槓桿→勝率→天數排序)", expanded=True):
                df_show = pd.DataFrame(st.session_state[KEY_RES]).copy()
                df_show["權利金"] = df_show["價格"].round(0).astype(int)
                df_show["槓桿"] = df_show["槓桿"].map(lambda x: f"{x:.1f}x")
                df_show["Delta"] = df_show["Delta"].map(lambda x: f"{float(x):.2f}")
                df_show["勝率"] = df_show["勝率"].map(lambda x: f"{float(x):.1f}%")
                cols = ["合約", "履約價", "權利金", "槓桿", "勝率", "天數", "差距"]
                st.dataframe(df_show[cols], use_container_width=True, hide_index=True)

    with col_portfolio:
        st.markdown("#### 💼 **LEAPS CALL 投組**")
        if st.session_state[KEY_PF]:
            pf = pd.DataFrame(st.session_state[KEY_PF])
            total = pf["價格"].sum() * 50
            avg_win = pf["勝率"].mean()
            avg_lev = pf["槓桿"].mean()
            st.metric("總權利金", f"${int(total):,}")
            st.caption(f"{len(pf)}口 | Avg槓桿 {avg_lev:.1f}x | Avg勝率 {avg_win:.1f}%")

            pf_s = pf.copy()
            pf_s["權利金"] = pf_s["價格"].round(0).astype(int)
            pf_s["Delta"] = pf_s["Delta"].map(lambda x: f"{float(x):.2f}")
            pf_s["勝率"] = pf_s["勝率"].map(lambda x: f"{float(x):.1f}%")
            pf_s["槓桿"] = pf_s["槓桿"].map(lambda x: f"{x:.1f}x")
            st.dataframe(pf_s[["合約", "履約價", "權利金", "槓桿", "勝率"]], use_container_width=True, hide_index=True)

            c_clr, c_dl = st.columns(2)
            with c_clr:
                if st.button("🗑️ 清空投組", key="clr_pf_v185"):
                    st.session_state[KEY_PF] = []
                    st.rerun()
            with c_dl:
                st.download_button(
                    "📥 CSV匯出",
                    pf.to_csv(index=False).encode("utf-8"),
                    "LEAPs_call_pf_v185.csv",
                    key="dl_pf_v185",
                )
        else:
            st.info("💡 請先掃描並加入合約")

    st.markdown("---")
    st.markdown("#### 📚 **LEAPS / LEAPS CALL 策略簡介**")
    st.markdown(
        """
**LEAPS CALL (長期看漲選擇權)**：
- 到期日 > 6個月，時間衰減緩慢，適合長期看多標的（如AI、指數）
- **優勢**：高槓桿、低成本替代現股，時間價值損耗少
- **本系統優化**：預設遠月合約 + 槓桿篩選，優先推薦深度價內/價平合約
"""
    )

# --------------------------
# Tab 3: 歷史回測（保留你的 Pro gate）
# --------------------------
with tabs[3]:
    st.markdown("### 📊 **策略時光機：真實歷史驗證**")

    if not st.session_state.is_pro:
        col_lock1, col_lock2 = st.columns([2, 1])
        with col_lock1:
            st.warning("🔒 **此為 Pro 會員專屬功能**")
            st.info("解鎖後可查看：\n- ✅ 真實歷史數據回測\n- ✅ 策略 vs 大盤績效\n- ✅ 詳細訊號點位")
        with col_lock2:
            st.metric("累積報酬率", "🔒 ???%", "勝率 ???%")
            if st.button("⭐ 免費升級 Pro", key="upgrade_btn_tab3"):
                st.session_state.is_pro = True
                st.balloons()
                st.rerun()
        st.image("https://via.placeholder.com/1000x300?text=Pro+Feature+Locked", use_container_width=True)
    else:
        with st.expander("⚙️ **回測參數設定**", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                period_days = st.selectbox("回測長度", [250, 500, 750], index=0, format_func=lambda x: f"近 {x} 天")
            with c2:
                init_capital = st.number_input("初始本金 (萬)", 10, 500, 100)
            with c3:
                leverage = st.slider("模擬槓桿", 1, 3, 1)

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
                    df_hist["close"] = df_hist["close"].astype(float)
                    df_hist["MA20"] = df_hist["close"].rolling(20).mean()
                    df_hist["MA60"] = df_hist["close"].rolling(60).mean()
                    df_hist = df_hist.dropna().tail(period_days).reset_index(drop=True)

                    df_hist["Signal"] = (df_hist["close"] > df_hist["MA20"]) & (df_hist["MA20"] > df_hist["MA60"])
                    df_hist["Daily_Ret"] = df_hist["close"].pct_change().fillna(0)
                    df_hist["Strategy_Ret"] = df_hist["Signal"].shift(1).fillna(False) * df_hist["Daily_Ret"] * leverage

                    df_hist["Equity_Strategy"] = init_capital * (1 + df_hist["Strategy_Ret"]).cumprod()
                    df_hist["Equity_Benchmark"] = init_capital * (1 + df_hist["Daily_Ret"]).cumprod()

                    total_ret = (df_hist["Equity_Strategy"].iloc[-1] / init_capital - 1) * 100
                    bench_ret = (df_hist["Equity_Benchmark"].iloc[-1] / init_capital - 1) * 100
                    denom = len(df_hist[df_hist["Signal"].shift(1) == True])
                    win_rate = (len(df_hist[df_hist["Strategy_Ret"] > 0]) / denom * 100) if denom > 0 else 0

                    st.divider()
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("💰 策略最終資產", f"{int(df_hist['Equity_Strategy'].iloc[-1]):,} 萬", f"{total_ret:+.1f}%")
                    k2.metric("🐢 大盤同期表現", f"{bench_ret:+.1f}%", f"超額 {total_ret - bench_ret:+.1f}%", delta_color="off")
                    k3.metric("🏆 交易勝率 (日)", f"{win_rate:.1f}%")
                    k4.metric("📅 交易天數", f"{int(df_hist['Signal'].sum())} 天", f"佔比 {df_hist['Signal'].mean()*100:.0f}%")

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df_hist["date"], y=df_hist["Equity_Strategy"], name="貝伊果策略",
                                             line=dict(color="#00CC96", width=2)))
                    fig.add_trace(go.Scatter(x=df_hist["date"], y=df_hist["Equity_Benchmark"], name="大盤指數",
                                             line=dict(color="#EF553B", width=2, dash="dash")))
                    fig.update_layout(title="資金權益曲線 (真實歷史)", yaxis_title="資產淨值 (萬)", hovermode="x unified", height=400)
                    st.plotly_chart(fig, use_container_width=True)

# --------------------------
# Tab 4: 專業戰情室（保留你的視覺與籌碼）
# --------------------------
with tabs[4]:
    st.markdown("## 📰 **專業戰情中心**")
    st.caption(f"📅 資料日期：{latest_date.strftime('%Y-%m-%d')} | 💡 模型版本：v6.1 (UI/UX)")

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
            name_map = {
                "Foreign_Investors": "外資",
                "Investment_Trust": "投信",
                "Dealer_Self": "自營商(自行)",
                "Dealer_Hedging": "自營商(避險)",
            }
            df_chips["name_tw"] = df_chips["name"].map(name_map).fillna(df_chips["name"])
            fig_chips = px.bar(
                df_chips,
                x="name_tw",
                y="net",
                color="net",
                color_continuous_scale=["green", "red"],
                labels={"net": "買賣超(億)", "name_tw": "法人身分"},
                text="net",
                title=f"三大法人合計買賣超 ({df_chips['date'].iloc[0].strftime('%m/%d')})",
            )
            fig_chips.update_traces(texttemplate="%{text:.1f} 億", textposition="outside")
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
            st.metric("🛑 波段壓力 (20日高)", f"{int(real_pressure)}", delta=f"{real_pressure - S_current:.0f}", delta_color="inverse")
            st.metric("🏠 目前點位", f"{int(S_current)}")
            st.metric("🛡️ 波段支撐 (60日低)", f"{int(real_support)}", delta=f"{real_support - S_current:.0f}")
        else:
            st.warning("⚠️ K 線資料連線中斷")

    st.markdown("#### 💼 **我的投組**")
    if st.button("➕ 加入虛擬倉位"):
        st.session_state.portfolio.append({"K": 23000, "P": 180, "Date": str(date.today())})
    if st.session_state.portfolio:
        st.dataframe(pd.DataFrame(st.session_state.portfolio), use_container_width=True)
    else:
        st.info("暫無持倉")

# --------------------------
# Tab 5~14: 擴充預留位
# --------------------------
with tabs[5]:
    st.info("🚧 擴充功能 2：大戶籌碼追蹤 (開發中)")
with tabs[6]:
    st.info("🚧 擴充功能 3：自動下單串接 (開發中)")
with tabs[7]:
    st.info("🚧 擴充功能 4：Line 推播 (開發中)")
with tabs[8]:
    st.info("🚧 擴充功能 5：期貨價差監控 (開發中)")
with tabs[9]:
    st.info("🚧 擴充功能 6：美股連動分析 (開發中)")
with tabs[10]:
    st.info("🚧 擴充功能 7：自定義策略腳本 (開發中)")
with tabs[11]:
    st.info("🚧 擴充功能 8：社群討論區 (開發中)")
with tabs[12]:
    st.info("🚧 擴充功能 9：課程學習中心 (開發中)")
with tabs[13]:
    st.info("🚧 擴充功能 10：VIP 專屬通道 (開發中)")
