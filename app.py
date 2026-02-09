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
    valid_count = 0
    for lat, lon in locs:
        try:
            rlat = radians(float(lat))
            rlon = radians(float(lon))
            x += cos(rlat) * cos(rlon)
            y += cos(rlat) * sin(rlon)
            z += sin(rlat)
            valid_count += 1
        except:
            continue
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
    except:
        pass
    # 统一str类型防PyArrow错
    df = pd.DataFrame(pois)
    for col in df.columns:
        df[col] = df[col].astype(str).replace('nan', '暂无')
    return df

st.set_page_config(layout="wide")
st.title("🍽️ 聚会中点 + 餐厅推荐")

if "spots" not in st.session_state:
    st.session_state.spots = []

# 输入
col1, col2 = st.columns([1, 2])
with col1:
    lat = st.number_input("纬度", 22.0, 45.0, 39.90)
    lon = st.number_input("经度", 100.0, 130.0, 116.40)
    if st.button("添加位置"):
        st.session_state.spots.append([lat, lon])
        st.rerun()

with col2:
    if st.button("北京"): st.session_state.spots.append([39.90,116.40]); st.rerun()
    if st.button("上海"): st.session_state.spots.append([31.23,121.47]); st.rerun()
    if st.button("台南"): st.session_state.spots.append([22.99,120.20]); st.rerun()

# 结果
if st.session_state.spots:
    df_spots = pd.DataFrame(st.session_state.spots, columns=["纬度", "经度"])
    center = calc_center(st.session_state.spots)
    
    st.header("🎯 计算结果")
    col1, col2, col3 = st.columns(3)
    col1.metric("中点纬度", f"{center[0]}")
    col2.metric("中点经度", f"{center[1]}")
    col3.metric("人数", len(df_spots))
    
    st.subheader("🗺️ 地图")
    map_df = pd.DataFrame(st.session_state.spots + [center], columns=['lat', 'lon'])
    st.map(map_df)
    
    # 餐厅
    st.header("🍜 附近餐厅推荐")
    rest_df = nearby_rest(center[0], center[1])
    if not rest_df.empty and len(rest_df) > 0:
        st.dataframe(rest_df, use_container_width=True)
        st.success("✅ 推荐成功！复制餐厅名导航")
    else:
        st.warning("🔄 暂无餐厅，试试北京+上海组合")
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🗑️ 清空", type="primary"):
            st.session_state.spots = []
            st.rerun()
    with col_btn2:
        csv = df_spots.round(6).to_csv(index=False)
        st.download_button("💾 导出", csv, "位置.csv", use_container_width=True)

else:
    st.info("👆 添加位置开始吧！")

st.caption("贝伊果屋 | 修复完成，无PyArrow错误")
