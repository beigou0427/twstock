import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from math import radians, degrees, sin, cos, atan2, sqrt

@st.cache_data
def center_geolocation(locs):
    if not locs: return 39.90, 116.40  # 北京默认
    x, y, z = 0, 0, 0
    for lat, lon in locs:
        lat, lon = radians(float(lat)), radians(float(lon))
        x += cos(lat) * cos(lon); y += cos(lat) * sin(lon); z += sin(lat)
    n = len(locs); x /= n; y /= n; z /= n
    lon = degrees(atan2(y, x)); hyp = sqrt(x*x + y*y); lat = degrees(atan2(z, hyp))
    return lat, lon

st.set_page_config(layout="wide", page_title="聚会中点")
st.title("🎉 聚会中点神器 - 零API·大陆极速")

# 原生session_state（刷新同步）
if 'locations' not in st.session_state:
    st.session_state.locations = []
if 'map_clicked_lat' not in st.session_state:
    st.session_state.map_clicked_lat = 39.90
if 'map_clicked_lon' not in st.session_state:
    st.session_state.map_clicked_lon = 116.40

tab1, tab2 = st.tabs(["📍 我的位置", "🌍 实时结果"])

with tab1:
    col1, col2, col3 = st.columns([1,1,2])
    with col1:
        lat = st.number_input("纬度", value=st.session_state.map_clicked_lat, step=0.0001, key="lat_input")
    with col2:
        lon = st.number_input("经度", value=st.session_state.map_clicked_lon, step=0.0001, key="lon_input")
    with col3:
        if st.button("✅ 添加位置（所有人可见）", use_container_width=True):
            st.session_state.locations.append([lat, lon])
            st.success("🚀 已添加！刷新页看更新")
            st.rerun()
    
    st.info("💡 高德/百度地图右键→坐标复制，或地图点击拾取")

with tab2:
    st.subheader("📈 当前大家位置")
    if st.session_state.locations:
        df = pd.DataFrame(st.session_state.locations, columns=['lat', 'lon'])
        st.dataframe(df.round(4), use_container_width=True)
        
        center_lat, center_lon = center_geolocation(st.session_state.locations)
        c1, c2, c3 = st.columns(3)
        c1.metric("🎯 中点纬度", f"{center_lat:.4f}")
        c2.metric("🎯 中点经度", f"{center_lon:.4f}")
        c3.metric("👥 参与人数", len(st.session_state.locations))
        
        # 交互地图：点击返回坐标！
        m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles='OpenStreetMap')
        for i, row in df.iterrows():
            folium.Marker([row.lat, row.lon], popup=f"位置{i+1}", 
                         tooltip="玩家位置").add_to(m)
        folium.Marker([center_lat, center_lon], popup="⭐最佳聚点", 
                     tooltip="推荐中点", icon=folium.Icon(color='red')).add_to(m)
        
        map_data = st_folium(m, width=900, height=500, key="main_map")
        
        # 点击拾取→填输入框
        if map_data and 'last_clicked' in map_data:
            clicked_lat = map_data['last_clicked']['lat']
            clicked_lon = map_data['last_clicked']['lng']
            st.session_state.map_clicked_lat = clicked_lat
            st.session_state.map_clicked_lon = clicked_lon
            st.success(f"🖱️ 点击拾取成功！{clicked_lat:.4f}, {clicked_lon:.4f}")
        
        # 简单地图备选
        st.caption("🗺️ 双地图：Folium交互 + 原生显示")
        st.map(df, zoom=11, use_container_width=True)
    else:
        st.warning("👆 先添加第一个位置！")

st.sidebar.markdown("### 🔧 操作")
if st.sidebar.button("🗑️ 清空所有位置"):
    st.session_state.locations = []; st.rerun()
st.sidebar.markdown("**分享**：微信复制此页链接")
st.sidebar.caption("贝伊果屋出品 | 2026")

if st.button("💾 导出位置CSV"):
    df = pd.DataFrame(st.session_state.locations, columns=['lat', 'lon'])
    st.download_button("下载", df.to_csv(index=False), "聚点数据.csv")
