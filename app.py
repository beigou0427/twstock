import streamlit as st
import pandas as pd
import numpy as np
from math import radians, degrees, sin, cos, atan2, sqrt

@st.cache_data
def center_geolocation(locs):
    x, y, z = 0, 0, 0
    for lat, lon in locs:
        lat, lon = radians(lat), radians(lon)
        x += cos(lat) * cos(lon)
        y += cos(lat) * sin(lon)
        z += sin(lat)
    x /= len(locs); y /= len(locs); z /= len(locs)
    lon = degrees(atan2(y, x))
    hyp = sqrt(x * x + y * y)
    lat = degrees(atan2(z, hyp))
    return lat, lon

st.set_page_config(layout="wide")
st.title("🗺️ 无API大陆版：大家选聚会中点！")

if 'locations' not in st.session_state:
    st.session_state.locations = []

col1, col2 = st.columns([1,3])
with col1:
    with st.form("add"):
        lat = st.number_input("纬度", value=39.90)
        lon = st.number_input("经度", value=116.40)
        if st.form_submit_button("添加"):
            st.session_state.locations.append([lat, lon])
            st.rerun()

with col2:
    if st.session_state.locations:
        df = pd.DataFrame(st.session_state.locations, columns=['lat', 'lon'])
        center_lat, center_lon = center_geolocation(st.session_state.locations)
        st.metric("推荐中点", f"纬度: {center_lat:.4f} | 经度: {center_lon:.4f}")
        st.map(df, zoom=10)  # 自动居中显示所有点+中点！
    else:
        st.info("📍 添加位置后自动显示地图")

st.caption("微信分享此页，多人输入刷新可见更新。")
if st.button("清空", type="secondary"):
    st.session_state.locations = []
    st.rerun()
