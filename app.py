import streamlit as st
import pandas as pd
import numpy as np
import requests
from math import radians, degrees, sin, cos, atan2, sqrt

# 🔥 你的Key已写死（生产用Secrets替换）
AMAP_KEY = "a9075050dd895616798e9d039d89bdde"

@st.cache_data
def calc_center(locs):
    if not locs: return [39.90, 116.40]
    x=y=z=0
    for lat, lon in locs:
        rlat, rlon = radians(float(lat)), radians(float(lon))
        x += cos(rlat) * cos(rlon)
        y += cos(rlat) * sin(rlon)
        z += sin(rlat)
    n = len(locs)
    x, y, z = x/n, y/n, z/n
    lon = degrees(atan2(y, x))
    hyp = sqrt(x*x + y*y)
    lat = degrees(atan2(z, hyp))
    return [round(lat, 6), round(lon, 6)]

@st.cache_data
def nearby_rest(lat, lon):
    url = "https://restapi.amap.com/v3/place/around"
    params = {
        "key": AMAP_KEY,
        "location": f"{lon},{lat}",
        "keywords": "餐厅|火锅|川菜|粤菜|日料",
        "types": "050000",
        "radius": 3000,
        "offset": 10
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data.get("status") == "1":
            pois = []
            for p in data["pois"][:10]:
                biz = p.get("biz_ext", {})
                pois.append({
                    "餐厅": p.get("name", ""),
                    "地址": p.get("address", ""),
                    "评分": biz.get("rating", "暂无"),
                    "均价": biz.get("cost", "暂无"),
                    "距离": f"{int(p.get('distance', 0)/1000)}km" if p.get('distance') else "",
                    "电话": p.get("tel", "")
                })
            return pd.DataFrame(pois)
    except Exception as e:
        st.error(f"API错误: {e}")
    return pd.DataFrame(columns=["餐厅", "地址", "评分", "均价", "距离", "电话"])

st.set_page_config(layout="wide")
st.title("🍽️ 贝伊果屋 · 聚会神器")

if "spots" not in st.session_state:
    st.session_state.spots = []

# 输入
c1, c2 = st.columns([1, 2])
with c1:
    st.header("📍 添加位置")
    lat = st.number_input("纬度", 22.0, 45.0, 39.90, step=0.0001)
    lon = st.number_input("经度", 100.0, 130.0, 116.40, step=0.0001)
    if st.button("✅ 添加", use_container_width=True):
        st.session_state.spots.append([lat, lon])
        st.success("已添加！")
        st.rerun()

with c2:
    st.header("🏙️ 一键城市")
    col_city1, col_city2, col_city3 = st.columns(3)
    if col_city1.button("北京"): st.session_state.spots.append([39.90,116.40]); st.rerun()
    if col_city2.button("上海"): st.session_state.spots.append([31.23,121.47]); st.rerun()
    if col_city3.button("台南"): st.session_state.spots.append([22.99,120.20]); st.rerun()

# 结果
if st.session_state.spots:
    df = pd.DataFrame(st.session_state.spots, columns=["纬度", "经度"])
    center = calc_center(st.session_state.spots)
    
    st.header("🎯 计算结果")
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("中点纬度", center[0])
    col_m2.metric("中点经度", center[1])
    col_m3.metric("人数", len(df))
    
    st.subheader("🗺️ 地图")
    st.map(pd.DataFrame(st.session_state.spots + [center], columns=['lat', 'lon']))
    
    # 🔥 餐厅推荐
    st.header("🍜 附近餐厅 Top 10")
    with st.spinner("搜索中..."):
        rest_df = nearby_rest(center[0], center[1])
    
    if not rest_df.empty:
        st.dataframe(rest_df, use_container_width=True, hide_index=True)
        st.success("📱 复制餐厅名到高德地图导航！")
    else:
        st.warning("暂无餐厅数据，换个中点试试")
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🗑️ 清空", type="primary"):
            st.session_state.spots.clear()
            st.rerun()
    with col_btn2:
        csv = df.round(6).to_csv(index=False)
        st.download_button("💾 导出位置", csv, "聚点.csv")

else:
    st.info("👆 添加第一个位置开始！分享链接给朋友协作")

st.markdown("---")
st.caption("✨ 贝伊果屋 2026 | 北京+上海自动推天津餐厅")
