import streamlit as st
import pandas as pd
import numpy as np
import requests
from streamlit_geolocation import streamlit_geolocation
from math import radians, degrees, sin, cos, atan2, sqrt

AMAP_KEY = "a9075050dd895616798e9d039d89bdde"

@st.cache_data
def calc_center(locs):
    if not locs: return [39.90, 116.40]
    x = y = z = 0.0
    valid_count = 0
    for lat, lon in locs:
        try:
            rlat = radians(float(lat))
            rlon = radians(float(lon))
            x += cos(rlat) * cos(rlon)
            y += cos(rlat) * sin(rlon)
            z += sin(rlat)
            valid_count += 1
        except: continue
    n = max(1, valid_count)
    x, y, z = x/n, y/n, z/n
    lon = degrees(atan2(y, x))
    hyp = sqrt(x*x + y*y)
    lat = degrees(atan2(z, hyp))
    return [round(float(lat), 6), round(float(lon), 6)]

@st.cache_data
def nearby_rest(lat, lon):
    url = "https://restapi.amap.com/v3/place/around"
    params = {"key": AMAP_KEY, "location": f"{lon},{lat}", "keywords": "餐厅", "types": "050000", "radius": 3000, "offset": 10}
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data.get("status") == "1":
            pois = []
            for p in data["pois"][:10]:
                biz = p.get("biz_ext", {})
                dist = float(p.get("distance", "0")) / 1000
                pois.append({
                    "餐厅": str(p.get("name", "")),
                    "地址": str(p.get("address", "")),
                    "评分": str(biz.get("rating", "")),
                    "均价": str(biz.get("cost", "")),
                    "距离": f"{dist:.1f}km",
                    "电话": str(p.get("tel", ""))
                })
            df = pd.DataFrame(pois)
            for col in df: df[col] = df[col].astype(str).replace('nan', '暂无')
            return df
    except: pass
    return pd.DataFrame()

st.set_page_config(layout="wide")
st.title("📍 一键定位 · 聚会餐厅推荐")

if "spots" not in st.session_state:
    st.session_state.spots = []

# 🔥 一键手机定位！
st.header("📱 手机定位（一键GPS）")
location = streamlit_geolocation()
if location and location.get('latitude') and location.get('longitude'):
    lat, lon = location['latitude'], location['longitude']
    st.success(f"✅ 定位成功！{lat:.4f}, {lon:.4f} (精度:{location.get('accuracy', '未知')}m)")
    if st.button("🚀 添加我的位置", use_container_width=True):
        st.session_state.spots.append([lat, lon])
        st.balloons()
        st.rerun()
else:
    st.info("👆 点击定位按钮（手机允许GPS权限）")

# 手动输入备份
with st.expander("⌨️ 手动输入"):
    col1, col2 = st.columns(2)
    lat = col1.number_input("纬度", 22.0, 45.0, 39.90)
    lon = col2.number_input("经度", 100.0, 130.0, 116.40)
    if st.button("手动添加"):
        st.session_state.spots.append([lat, lon])
        st.rerun()

# 一键城市
st.header("🏙️ 快捷城市")
col_c1, col_c2, col_c3 = st.columns(3)
if col_c1.button("北京"): st.session_state.spots.append([39.90,116.40]); st.rerun()
if col_c2.button("上海"): st.session_state.spots.append([31.23,121.47]); st.rerun()
if col_c3.button("台南"): st.session_state.spots.append([22.99,120.20]); st.rerun()

# 结果
if st.session_state.spots:
    st.header("🎯 中点计算")
    df = pd.DataFrame(st.session_state.spots, columns=["纬度", "经度"])
    center = calc_center(st.session_state.spots)
    
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("纬度", center[0])
    col_m2.metric("经度", center[1])
    col_m3.metric("人数", len(df))
    
    st.subheader("🗺️ 地图")
    st.map(pd.DataFrame(st.session_state.spots + [center], columns=['lat', 'lon']))
    
    # 餐厅
    st.header("🍜 附近餐厅推荐")
    rest_df = nearby_rest(center[0], center[1])
    if not rest_df.empty:
        st.dataframe(rest_df, use_container_width=True)
    else:
        st.warning("暂无数据")
    
    if st.button("清空", type="primary"):
        st.session_state.spots = []
        st.rerun()

st.markdown("---")
st.caption("贝伊果屋 | 手机GPS + 高德餐厅API")
