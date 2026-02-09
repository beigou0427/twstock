import streamlit as st
import streamlit.components.v1 as components
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
    pois = []
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data.get("status") == "1" and data.get("pois"):
            for p in data["pois"][:10]:
                biz = p.get("biz_ext", {})
                dist = float(p.get("distance", "0")) / 1000
                pois.append({
                    "餐厅": str(p.get("name", "未知")),
                    "地址": str(p.get("address", "")),
                    "评分": str(biz.get("rating", "暂无")),
                    "均价": str(biz.get("cost", "暂无")),
                    "距离": f"{dist:.1f}km",
                    "电话": str(p.get("tel", ""))
                })
    except: pass
    df = pd.DataFrame(pois)
    if not df.empty:
        for col in df.columns: df[col] = df[col].astype(str).replace('nan', '暂无')
    return df

# 🔥 浏览器原生定位（手机一键GPS）
def get_location():
    st.subheader("📱 一键手机定位")
    st.caption("*首次需允许浏览器定位权限*")
    
    # 从URL参数读取定位结果
    qp = st.query_params
    if "lat" in qp and "lon" in qp:
        try:
            lat = float(qp["lat"][0])
            lon = float(qp["lon"][0])
            st.success(f"✅ 定位成功！{lat:.4f}, {lon:.4f}")
            return lat, lon
        except:
            pass
    
    # 注入HTML5 geolocation
    html = """
    <div style="padding: 10px; border: 2px dashed #ff6b6b; border-radius: 10px; text-align: center;">
      <button onclick="getLocation()" 
              style="padding: 12px 24px; font-size: 18px; background: #ff6b6b; color: white; border: none; border-radius: 25px; cursor: pointer;">
        📍 获取我的位置
      </button>
      <p id="status" style="margin-top: 10px; font-size: 14px; color: #666;"></p>
    </div>
    <script>
    function getLocation() {
      const status = document.getElementById("status");
      if (!navigator.geolocation) {
        status.innerHTML = "❌ 浏览器不支持定位";
        return;
      }
      status.innerHTML = "🔄 定位中，请允许位置权限...";
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const lat = pos.coords.latitude;
          const lon = pos.coords.longitude;
          const acc = pos.coords.accuracy;
          status.innerHTML = `✅ 定位成功！精度 ${Math.round(acc)}m`;
          const url = new URL(window.location.href);
          url.searchParams.set("lat", lat);
          url.searchParams.set("lon", lon);
          setTimeout(() => { window.location.href = url.toString(); }, 1000);
        },
        (err) => {
          status.innerHTML = "❌ " + {
            1: "用户拒绝定位",
            2: "定位失败",
            3: "超时"
          }[err.code] || err.message;
        },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
      );
    }
    </script>
    """
    components.html(html, height=200)
    return None

st.set_page_config(layout="wide")
st.title("🍽️ 贝伊果屋 · 聚会定位餐厅神器")

if "spots" not in st.session_state:
    st.session_state.spots = []

# 定位
user_loc = get_location()

# 手动输入
with st.expander("⌨️ 手动输入坐标"):
    col1, col2 = st.columns(2)
    lat_man = col1.number_input("纬度", 22.0, 45.0, 39.90)
    lon_man = col2.number_input("经度", 100.0, 130.0, 116.40)
    if st.button("手动添加"):
        st.session_state.spots.append([lat_man, lon_man])
        st.rerun()

# 快捷城市
st.subheader("🏙️ 快捷城市")
col_c1, col_c2, col_c3 = st.columns(3)
if col_c1.button("北京"): st.session_state.spots.append([39.90,116.40]); st.rerun()
if col_c2.button("上海"): st.session_state.spots.append([31.23,121.47]); st.rerun()
if col_c3.button("台南"): st.session_state.spots.append([22.99,120.20]); st.rerun()

# 添加定位结果
if user_loc:
    if st.button("🚀 添加定位结果", use_container_width=True):
        st.session_state.spots.append(user_loc)
        st.success("✅ 已添加你的位置！")
        st.rerun()

# 结果
if st.session_state.spots:
    st.header("🎯 中点计算")
    df = pd.DataFrame(st.session_state.spots, columns=["纬度", "经度"])
    center = calc_center(st.session_state.spots)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("中点纬度", center[0])
    col2.metric("中点经度", center[1])
    col3.metric("人数", len(df))
    
    st.subheader("🗺️ 地图")
    map_df = pd.DataFrame(st.session_state.spots + [center], columns=['lat', 'lon'])
    st.map(map_df)
    
    # 餐厅推荐
    st.header("🍜 附近餐厅 Top10")
    with st.spinner("搜索餐厅..."):
        rest_df = nearby_rest(center[0], center[1])
    
    if not rest_df.empty:
        st.dataframe(rest_df, use_container_width=True)
        st.success("📱 复制餐厅名 → 高德导航！")
    else:
        st.info("🔄 暂无餐厅，换城市试试")
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🗑️ 清空", type="primary"):
            st.session_state.spots.clear()
            st.rerun()
    with col_btn2:
        csv = df.round(6).to_csv(index=False, encoding='utf-8-sig')
        st.download_button("💾 导出", csv, "聚点.csv")

st.markdown("---")
st.caption("✨ 贝伊果屋 | 浏览器原生GPS | 无组件依赖")
