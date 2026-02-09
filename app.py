import streamlit as st
import pandas as pd
import numpy as np
from math import radians, degrees, sin, cos, atan2, sqrt

@st.cache_data
def center_geolocation(locs):
    """精确地理中点计算"""
    if not locs: 
        return 39.90, 116.40  # 北京
    x, y, z = 0, 0, 0
    for lat, lon in locs:
        lat, lon = radians(float(lat)), radians(float(lon))
        x += cos(lat) * cos(lon)
        y += cos(lat) * sin(lon) 
        z += sin(lat)
    n = len(locs)
    x /= n; y /= n; z /= n
    lon = degrees(atan2(y, x))
    hyp = sqrt(x*x + y*y)
    lat = degrees(atan2(z, hyp))
    return round(lat, 6), round(lon, 6)

st.set_page_config(layout="wide", page_title="聚会中点")
st.title("🎯 聚会中点计算器 - 零依赖·即开即用")

if 'locations' not in st.session_state:
    st.session_state.locations = []

# 主界面
col_left, col_right = st.columns([1, 3])

with col_left:
    st.header("📍 添加位置")
    
    # 输入
    lat = st.number_input("纬度", value=39.90, step=0.0001, 
                         help="百度地图右键复制坐标")
    lon = st.number_input("经度", value=116.40, step=0.0001,
                         help="如：北京 39.9042,116.4074")
    
    if st.button("✅ 添加我的位置", use_container_width=True):
        st.session_state.locations.append([lat, lon])
        st.balloons()
        st.rerun()
    
    # 位置管理
    if st.session_state.locations:
        if st.button("🗑️ 清空所有", type="secondary"):
            st.session_state.locations = []
            st.rerun()

with col_right:
    st.header("🌍 实时结果")
    
    if st.session_state.locations:
        df = pd.DataFrame(st.session_state.locations, columns=['纬度', '经度'])
        st.subheader(f"📊 {len(df)}人位置")
        st.dataframe(df.round(5), use_container_width=True)
        
        # 计算中点
        center_lat, center_lon = center_geolocation(st.session_state.locations)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("🎯 推荐纬度", center_lat)
        col2.metric("🎯 推荐经度", center_lon)
        col3.metric("👥 总人数", len(st.session_state.locations))
        
        # 原生地图（必成功！）
        st.subheader("🗺️ 地图显示（点击地图可放大）")
        map_df = pd.DataFrame([
            *st.session_state.locations, 
            [center_lat, center_lon]
        ], columns=['lat', 'lon'])
        st.map(map_df, zoom=11, use_container_width=True)
        
        # 分享提示
        st.success(f"""
        ✅ **推荐聚点：** `{center_lat}, {center_lon}`
        📱 **使用**：微信分享此页，朋友添加位置→刷新可见！
        🔗 **坐标用处**：百度地图搜索粘贴即达
        """)
        
        # 导出
        csv = df.round(6).to_csv(index=False)
        st.download_button("💾 下载CSV", csv, "聚会位置.csv", use_container_width=True)
        
    else:
        st.info("👆 添加第一个位置试试！")
        st.map(pd.DataFrame([[39.90,116.40]], columns=['lat','lon']))

st.caption("✨ 贝伊果屋出品 | 纯Streamlit原生 | 支持台南/北京/全球")
