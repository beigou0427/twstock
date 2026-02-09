import streamlit as st
import pandas as pd
import numpy as np
import requests
from math import radians, degrees, sin, cos, atan2, sqrt

# 高德Key（你的申请后填入）
AMAP_KEY = st.secrets.get("AMAP_KEY", "YOUR_KEY_HERE")  # Streamlit Secrets最佳

@st.cache_data
def calc_center(locs):
    if not locs: return [39.90, 116.40]
    x = y = z = 0
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
def nearby_restaurants(lat, lon, key, radius=2000):
    """高德附近餐厅"""
    url = "https://restapi.amap.com/v3/place/around"
    params = {
        "key": key,
        "location": f"{lon},{lat}",
        "keywords": "餐厅|美食",
        "types": "050000",  # 餐饮
        "radius": radius,
        "offset": 10,
        "page": 1
    }
    try:
        resp = requests.get(url, params=params)
        data = resp.json()
        if data["status"] == "1":
            pois = []
            for item in data["pois"][:8]:
                pois.append({
                    "name": item.get("name", ""),
                    "address": item.get("address", ""),
                    "rating": item.get("biz_ext", {}).get("rating", ""),
                    "price": item.get("biz_ext", {}).get("cost", ""),
                    "distance": item.get("distance", ""),
                    "tel": item.get("tel", "")
                })
            return pd.DataFrame(pois)
    except:
        pass
    return pd.DataFrame()

st.set_page_config(layout="wide")
st.title("🍽️ 聚会中点 + 餐厅推荐")

if "spots" not in st.session_state:
    st.session_state.spots = []

# 输入
col1, col2 = st.columns([1, 2])
with col1:
    st.header("📍 Locations")
    lat = st.number_input("Lat", 22.0, 45.0, 39.90)
    lon = st.number_input("Lon", 100.0, 130.0, 116.40)
    
    if st.button("Add", use_container_width=True):
        st.session_state.spots.append([lat, lon])
        st.rerun()

with col2:
    st.header("🏙️ Quick Add")
    colq1, colq2, colq3 = st.columns(3)
    if colq1.button("Beijing"): st.session_state.spots.append([39.90,116.40]); st.rerun()
    if colq2.button("Shanghai"): st.session_state.spots.append([31.23,121.47]); st.rerun()
    if colq3.button("Tainan"): st.session_state.spots.append([22.99,120.20]); st.rerun()

# 结果
if st.session_state.spots:
    df = pd.DataFrame(st.session_state.spots, columns=["Lat", "Lon"])
    center = calc_center(st.session_state.spots)
    
    st.subheader("📊 Results")
    colr1, colr2, colr3 = st.columns(3)
    colr1.metric("Center Lat", center[0])
    colr2.metric("Center Lon", center[1])
    colr3.metric("Spots", len(df))
    
    st.map(pd.DataFrame(st.session_state.spots + [center], columns=['lat','lon']))
    
    # 🔥 餐厅推荐！
    st.subheader("🍽️ Nearby Restaurants (2km)")
    if AMAP_KEY != "YOUR_KEY_HERE":
        rest_df = nearby_restaurants(center[0], center[1], AMAP_KEY)
        if not rest_df.empty:
            st.dataframe(rest_df, use_container_width=True)
        else:
            st.warning("No restaurants found, check Key")
    else:
        st.warning("👆 Add AMAP_KEY to Streamlit Secrets")
    
    if st.button("Clear", type="primary"):
        st.session_state.spots = []
        st.rerun()

st.caption("High moral Key needed for restaurants. BeIGoU 2026")
