import streamlit as st
import pandas as pd
import numpy as np
import requests
from math import radians, degrees, sin, cos, atan2, sqrt

# 手机定位组件（已确认Cloud支持）
try:
    from streamlit_geolocation import streamlit_geolocation
    LOCATION_AVAILABLE = True
except ImportError:
    LOCATION_AVAILABLE = False
    st.warning("手机定位组件暂不可用，使用手动输入")

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
    params = {
        "key": AMAP_KEY,
        "location": f"{lon},{lat}",
        "keywords": "餐厅",
        "types": "050000",
        "radius": 3000,
        "offset": 10
    }
    pois = []
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data.get("status") == "1" and data.get("pois"):
            for p in data["pois"][:10]:
                biz = p.get("biz_ext", {})
                try:
                    dist = float(p.get("distance", "0")) / 1000
                    dist_str = f"{dist:.1f}km"
                except:
                    dist_str = "未知"
                pois.append({
                    "餐厅": str(p.get("name", "未知")),
                    "地址": str(p.get("address", "")),
                    "评分": str(biz.get("rating", "暂无")),
                    "均价": str(biz.get("cost", "暂无")),
                    "距离": dist_str,
                    "电话": str(p.get("tel", ""))
                })
    except Exception as e:
        st.error(f"API错误: {str(e)[:50]}")
    df = pd.DataFrame(pois)
    if not df.empty:
        for col in df.columns:
            df[col] = df[col].astype(str).replace('nan', '暂无')
    return df

st.set_page_config(layout="wide", page_title="聚会神器")
st.title("📱 一键定位 · 聚会餐厅推荐")

if "spots" not in st.session_state:
    st.session_state.spots = []

# 🔥 手机定位
st.header("📍 我的位置")
if LOCATION_AVAILABLE:
    location = streamlit_geolocation()
    if location and 'latitude' in location and 'longitude' in location:
        lat, lon = location['latitude'], location['longitude']
        st.success(f"✅ 定位成功！纬度: {lat:.4f}, 经度: {lon:.4f}")
        col_add1, col_add2 = st.columns(2)
        if col_add1.button("🚀 添加我的位置", use_container_width=True):
            st.session_state.spots.append([lat, lon])
            st.balloons()
            st.rerun()
    else:
        st.info("📱 手机点击定位按钮 → 允许GPS权限")
else:
    st.warning("定位组件加载中，刷新试试")

# 手动输入
with st.expander("⌨️ 手动输入坐标", expanded=False):
    col_man1, col_man2 = st.columns(2)
    lat_man = col_man1.number_input("纬度", 22.0, 45.0, 39.90)
    lon_man = col_man2.number_input("经度", 100.0, 130.0, 116.40)
    if st.button("手动添加"):
        st.session_state.spots.append([lat_man, lon_man])
        st.rerun()

# 快捷城市
st.header("🏙️ 快捷城市")
col_city1, col_city2, col_city3 = st.columns(3)
if col_city1.button("北京"): st.session_state.spots.append([39.90,116.40]); st.rerun()
if col_city2.button("上海"): st.session_state.spots.append([31.23,121.47]); st.rerun()
if col_city3.button("台南"): st.session_state.spots.append([22.99,120.20]); st.rerun()

# 结果
if st.session_state.spots:
    st.header("🎯 中点计算结果")
    df = pd.DataFrame(st.session_state.spots, columns=["纬度", "经度"])
    center = calc_center(st.session_state.spots)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("中点纬度", center[0])
    col2.metric("中点经度", center[1])
    col3.metric("总人数", len(df))
    
    st.subheader("🗺️ 地图预览")
    map_df = pd.DataFrame(st.session_state.spots + [center], columns=['lat', 'lon'])
    st.map(map_df)
    
    # 餐厅推荐
    with st.spinner('🔍 搜索附近餐厅...'):
        rest_df = nearby_rest(center[0], center[1])
    
    st.header("🍜 3km内餐厅推荐")
    if not rest_df.empty:
        st.dataframe(rest_df, use_container_width=True, hide_index=True)
        st.success("📱 复制餐厅名 → 高德地图导航！")
    else:
        st.warning("🔄 暂无餐厅数据，换个城市试试")
    
    # 操作按钮
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🗑️ 清空所有", type="primary"):
            st.session_state.spots.clear()
            st.rerun()
    with col_btn2:
        csv = df.round(6).to_csv(index=False, encoding='utf-8')
        st.download_button("💾 导出CSV", csv, "聚会位置.csv", "text/csv")

else:
    st.info("👆 先定位或选择城市开始！分享此链接给朋友协作")

st.markdown("---")
st.caption("✨ 贝伊果屋 2026 | 手机GPS + 高德API | 北京+上海=天津餐厅")
