import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from math import radians, degrees, sin, cos, atan2, sqrt
import streamlit.components.v1 as components

# 多页面配置
PAGES = {
    "聚会中点": "pages/meeting_spot.py",  # 新增页面
    "股票分析": "twstock.py"  # 原有
}

st.sidebar.selectbox("导航", PAGES.keys())

# 主聚会功能（单文件版）
@st.cache_data
def calc_center(locs):
    if not locs: return 39.90, 116.40
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
    return round(lat, 6), round(lon, 6)

st.title("🎯 贝伊果屋 · 聚会中点神器")
st.caption("台南/北京/全球通用 · 实时多人协作")

if 'spots' not in st.session_state:
    st.session_state.spots = []

# ——输入区——
col1, col2 = st.columns(2)
with col1:
    with st.expander("📍 手动输入坐标", expanded=True):
        lat = st.number_input("纬度", 22.0, 45.0, 39.90, 0.0001)
        lon = st.number_input("经度", 100.0, 130.0, 116.40, 0.0001)
        
        if st.button("➕ 添加位置", use_container_width=True):
            st.session_state.spots.append([lat, lon])
            st.balloons()
            st.rerun()

with col2:
    # 常用城市快捷
    st.subheader("🏙️ 一键城市")
    cities = {
        "北京": [39.9042, 116.4074],
        "上海": [31.2304, 121.4737], 
        "深圳": [22.5431, 114.0579],
        "台南": [22.9908, 120.2014],
        "广州": [23.1291, 113.2644]
    }
    selected = st.selectbox("选择城市", list(cities.keys()))
    if st.button(f"🚀 我在北京{selected}", use_container_width=True):
        st.session_state.spots.extend(list(cities.values())[:1])  # 示例
        st.rerun()

# ——结果区——
if st.session_state.spots:
    df = pd.DataFrame(st.session_state.spots, columns=["纬度", "经度"])
    
    st.subheader(f"📊 {len(df)}个位置")
    st.dataframe(df.round(5), use_container_width=True)
    
    # 计算
    clat, clon = calc_center(st.session_state.spots)
    c1, c2, c3 = st.columns(3)
    c1.metric("🎯 最佳纬度", clat)
    c2.metric("🎯 最佳经度", clon)
    c3.metric("👥 位置数", len(df))
    
    # Folium交互地图
    m = folium.Map([clat, clon], zoom_start=10, tiles="OpenStreetMap")
    for i, (lat, lon) in enumerate(st.session_state.spots):
        folium.Marker([lat, lon], popup=f"位置#{i+1}", 
                     tooltip=f"({lat:.4f},{lon:.4f})").add_to(m)
    folium.Marker([clat, clon], popup="⭐推荐聚点", icon=folium.Icon("star", color="red")).add_to(m)
    
    clicked_map = st_folium(m, width=1000, height=500)
    
    # 点击拾取
    if clicked_map.get('last_clicked'):
        clck_lat = clicked_map['last_clicked']['lat']
        clck_lon = clicked_map['last_clicked']['lng']
        st.info(f"🖱️ 点击坐标：{clck_lat:.4f}, {clck_lon:.4f}")
    
    # 原生地图
    st.map(df.append({"lat": clat, "lon": clon}, ignore_index=True))
    
    # 操作
    colx, coly = st.columns(2)
    with colx:
        if st.button("🗑️ 清空", type="primary"):
            st.session_state.spots.clear()
            st.rerun()
    with coly:
        csv = df.round(6).to_csv(index=False)
        st.download_button("💾 导出CSV", csv, "聚点.csv")
    
    st.success(f"**最终推荐**：纬度{clat}, 经度{clon}\n百度地图直接搜索粘贴！")

else:
    st.info("👆 添加位置开始吧！分享链接给朋友协作")

# 底部
st.markdown("---")
share_md = """
**📱 使用指南**：
1. 添加你的位置（城市一键/手动）
2. 微信分享页面链接给朋友
3. 大家添加→刷新→自动计算中点
4. 复制坐标到高德/百度导航！

**🎥 Threads demo**：多人实时选KTV完美！
"""
st.markdown(share_md)
