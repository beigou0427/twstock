import streamlit as st
import pandas as pd
import numpy as np
import requests
from math import radians, degrees, sin, cos, atan2, sqrt

AMAP_KEY = "a9075050dd895616798e9d039d89bdde"

@st.cache_data
def calc_center(locs):
    if not locs: return [39.90, 116.40]
    x = y = z = 0.0
    for lat, lon in locs:
        try:
            rlat = radians(float(lat))
            rlon = radians(float(lon))
            x += cos(rlat) * cos(rlon)
            y += cos(rlat) * sin(rlon)
            z += sin(rlat)
        except:
            continue
    n = max(1, len(locs))
    x, y, z = x/n, y/n, z/n
    lon = degrees(atan2(y, x))
    hyp = sqrt(x*x + y*y)
    lat = degrees(atan2(z, hyp))
    return [round(float(lat), 6), round(float(lon), 6)]

@st.cache_data
def nearby_rest(lat, lon):
    url = "https://restapi.amap.com/v3/place/around"
    params = {
        "key": AMAP_KEY,
        "location": f"{lon},{lat}",
        "keywords": "餐厅",
        "types": "050000",
        "radius": 3000,
        "offset": 10
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data.get("status") == "1" and data.get("pois"):
            pois = []
            for p in data["pois"][:10]:
                biz = p.get("biz_ext", {})
                try:
                    dist = float(p.get("distance", 0)) / 1000
                    dist_str = f"{dist:.1f}km"
                except:
                    dist_str = "未知"
                pois.append({
                    "餐厅": p.get("name", "未知"),
                    "地址": p.get("address", ""),
                    "评分": biz.get("rating", "暂无"),
                    "均价": biz.get("cost", "暂无"),
                    "距离": dist_str,
                    "电话": p.get("tel", "")
                })
            return pd.DataFrame(pois)
    except Exception as e:
        st.error(f"API调用失败: {str(e)[:100]}")
    return pd.DataFrame(columns=["餐厅","地址","评分","均价","距离","电话"])

st.set_page_config(layout="wide")
st.title("🍽️ 聚会中点 + 餐厅推荐")

if "spots" not in st.session_state:
    st.session_state.spots = []

c1, c2 = st.columns([1, 2])
with c1:
    st.header("📍 位置")
    lat = st.number_input("纬度", 22.0, 45.0, 39.90)
    lon = st.number_input("经度", 100.0, 130.0, 116.40)
    if st.button("添加"):
        st.session_state.spots.append([lat, lon])
        st.rerun()

with c2:
    if st.button("北京"): st.session_state.spots.append([39.90,116.40]); st.rerun()
    if st.button("上海"): st.session_state.spots.append([31.23,121.47]); st.rerun()
    if st.button("台南"): st.session_state.spots.append([22.99,120.20]); st.rerun()

if st.session_state.spots:
    df = pd.DataFrame(st.session_state.spots, columns=["纬度", "经度"])
    center = calc_center(st.session_state.spots)
    
    st.header("🎯 结果")
    st.metric("中点纬度", center[0])
    st.metric("中点经度", center[1])
    st.metric("人数", len(df))
    
    st.subheader("🗺️ 地图")
    map_df = pd.DataFrame(st.session_state.spots + [center], columns=['lat', 'lon'])
    st.map(map_df)
    
    # 🔥 餐厅
    st.header("🍜 3km内餐厅推荐")
    rest_df = nearby_rest(center[0], center[1])
    if not rest_df.empty:
        st.dataframe(rest_df, use_container_width=True, hide_index=True)
        st.balloons()
    else:
        st.warning("🔄 刷新试试，或换城市")
    
    if st.button("清空", type="primary"):
        st.session_state.spots = []
        st.rerun()

st.caption("贝伊果屋 | Key已激活")
