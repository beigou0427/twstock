import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from math import radians, degrees, sin, cos, atan2, sqrt
from streamlit_server_state import server_state  # 多人实时共享！

# 安装：pip install streamlit-server-state streamlit-folium

@st.cache_data
def center_geolocation(locs):
    if not locs: return 39.90, 116.40
    x, y, z = 0, 0, 0
    for lat, lon in locs:
        lat, lon = radians(lat), radians(lon)
        x += cos(lat) * cos(lon); y += cos(lat) * sin(lon); z += sin(lat)
    x /= len(locs); y /= len(locs); z /= len(locs)
    lon = degrees(atan2(y, x)); hyp = sqrt(x*x + y*y); lat = degrees(atan2(z, hyp))
    return lat, lon

st.set_page_config(layout="wide", page_title="聚会中点神器")
st.title("🗺️ 终极版：多人实时选聚会中点！")

# 多人共享状态（服务器端，所有人实时同步）
if "locations" not in server_state:
    server_state.locations = []

tab1, tab2 = st.tabs(["📍 添加位置", "👥 实时地图&结果"])

with tab1:
    col1, col2, col3 = st.columns(3)
    with col1:
        lat = st.number_input("纬度", value=39.90, step=0.0001)
    with col2:
        lon = st.number_input("经度", value=116.40, step=0.0001)
    with col3:
        if st.button("🚀 添加我的位置", use_container_width=True):
            server_state.locations.append([lat, lon])
            st.success("✅ 已实时添加！所有人可见")
            st.rerun()

with tab2:
    if server_state.locations:
        df = pd.DataFrame(server_state.locations, columns=['lat', 'lon'])
        st.subheader("📊 当前位置列表")
        st.dataframe(df.style.format({'lat': '{:.4f}', 'lon': '{:.4f}'}))
        
        center_lat, center_lon = center_geolocation(server_state.locations)
        col_a, col_b = st.columns(2)
        col_a.metric("🎯 推荐中点", f"{center_lat:.4f}, {center_lon:.4f}")
        col_b.metric("👥 总人数", len(server_state.locations))
        
        # 交互地图：点击拾取+显示所有点
        m = folium.Map(location=[center_lat, center_lon], zoom_start=10)
        for i, (lat, lon) in enumerate(server_state.locations):
            folium.Marker([lat, lon], popup=f"玩家{i+1}", tooltip="位置").add_to(m)
        folium.Marker([center_lat, center_lon], popup="🎉 最佳聚点！", tooltip="中点", icon=folium.Icon(color='red', icon='star')).add_to(m)
        clicked = st_folium(m, key="map", width=800, height=500)
        
        # 点击拾取自动填入输入框！
        if clicked and 'last_clicked' in clicked:
            last_lat, last_lon = clicked['last_clicked']['lat'], clicked['last_clicked']['lng']
            st.session_state.map_lat = last_lat
            st.session_state.map_lon = last_lon
            st.info(f"🖱️ 点击了: {last_lat:.4f}, {last_lon:.4f} (自动填入输入框)")
        
        # 简单st.map备选
        st.map(df)
    else:
        st.info("🌟 第一人添加位置，其他人微信分享此页实时跟进！")

# 控制按钮
col_x, col_y = st.columns(2)
with col_x:
    if st.button("🗑️ 清空所有", type="primary"):
        server_state.locations = []
        st.rerun()
with col_y:
    st.caption("💡 经纬度查法：百度/高德地图右键复制 → 分享链接给朋友")

st.caption("✨ 由贝伊果屋出品 | 零API·大陆极速·实时协作")
