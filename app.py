import json
import time
from math import radians, degrees, sin, cos, atan2, sqrt

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests

# ====== Key (請填入你的) ======
AMAP_JS_KEY = "0cd3a5f0715be098c172e5359b94e99d"
AMAP_SECURITY_JS_CODE = "89b4b0c537e7e364af191c498542e593"
AMAP_REST_KEY = "a9075050dd895616798e9d039d89bdde"

# ---------- Utils ----------
def qp_get(key: str, default=None):
    try:
        qp = st.query_params
        if key not in qp: return default
        v = qp[key]
        return v[0] if isinstance(v, list) else v
    except: return default

def qp_del(*keys):
    try:
        for k in keys:
            if k in st.query_params: del st.query_params[k]
    except: pass

@st.cache_data
def calc_center(locs):
    if not locs: return 39.90, 116.40
    x=y=z=0.0; cnt=0
    for lat,lon in locs:
        try:
            rlat, rlon = radians(float(lat)), radians(float(lon))
            x+=cos(rlat)*cos(rlon); y+=cos(rlat)*sin(rlon); z+=sin(rlat); cnt+=1
        except: pass
    if cnt==0: return 39.90, 116.40
    x,y,z = x/cnt, y/cnt, z/cnt
    lon = degrees(atan2(y, x)); hyp = sqrt(x*x+y*y); lat = degrees(atan2(z, hyp))
    return round(float(lat),6), round(float(lon),6)

@st.cache_data(ttl=120)
def get_restaurants(lat, lon, kw="餐厅"):
    url = "https://restapi.amap.com/v3/place/around"
    params = {"key":AMAP_REST_KEY, "location":f"{lon},{lat}", "keywords":kw, "radius":3000, "offset":20, "types":"050000"}
    try:
        r = requests.get(url, params=params, timeout=10).json()
        if r.get("status")!="1": return pd.DataFrame()
        return pd.DataFrame([{
            "餐厅":p.get("name"), "距离":f"{float(p.get('distance',0))/1000:.2f}km",
            "评分":p.get("biz_ext",{}).get("rating"), "地址":p.get("address")
        } for p in r.get("pois",[])])
    except: return pd.DataFrame()

# ---------- IP 定位 ----------
def get_ip_loc():
    try:
        r = requests.get("http://ip-api.com/json/?fields=status,lat,lon,city", timeout=3).json()
        if r["status"]=="success": return float(r["lat"]), float(r["lon"]), r["city"]
    except: pass
    return None

# ---------- 高德地圖 (完善點擊版) ----------
def render_map(spots, center, height=500):
    markers = []
    for s in spots:
        try: markers.append({"name":str(s.get("name","")), "lat":float(s["lat"]), "lon":float(s["lon"])})
        except: pass
    
    html = f"""
    <div id="amap" style="width:100%;height:{height}px;"></div>
    <div id="msg" style="font-size:12px;color:#666;margin-top:5px;"></div>
    <script>window._AMapSecurityConfig={{securityJsCode:"{AMAP_SECURITY_JS_CODE}"}};</script>
    <script src="https://webapi.amap.com/loader.js"></script>
    <script>
      function updateURL(lat, lon) {{
        // 使用 URLSearchParams 更新參數，保留其他參數（除了 pick_lat/lon）
        try {{
            const url = new URL(window.top.location.href);
            url.searchParams.set("pick_lat", lat);
            url.searchParams.set("pick_lon", lon);
            window.top.location.href = url.toString(); 
        }} catch(e) {{
            document.getElementById("msg").innerText = "回填失敗(跨域限制)，請手動複製";
        }}
      }}

      AMapLoader.load({{key:"{AMAP_JS_KEY}", version:"2.0"}}).then((AMap)=>{{
        const map = new AMap.Map("amap", {{ zoom:12, center:[{center[1]}, {center[0]}] }});
        
        // 中點
        map.add(new AMap.Marker({{
            position:[{center[1]}, {center[0]}],
            title:"中點",
            icon: new AMap.Icon({{size:new AMap.Size(25,34), image:"https://webapi.amap.com/theme/v1.3/markers/n/mark_r.png"}})
        }}));

        // 既有點
        const ms = {json.dumps(markers, ensure_ascii=False)};
        ms.forEach(m => {{
            const mk = new AMap.Marker({{ position:[m.lon, m.lat], title:m.name }});
            mk.on("click", () => updateURL(m.lat, m.lon)); // 點 marker 也回填
            map.add(mk);
        }});

        // 點擊地圖空白處 -> 回填座標
        map.on("click", (e) => {{
            const lat = e.lnglat.getLat();
            const lon = e.lnglat.getLng();
            document.getElementById("msg").innerText = `選中: ${{lat.toFixed(5)}}, ${{lon.toFixed(5)}} (跳轉中...)`;
            
            // 添加臨時 marker 讓用戶知道點了哪
            new AMap.Marker({{ position:[lon, lat], icon:"https://webapi.amap.com/theme/v1.3/markers/n/mark_b.png" }}).setMap(map);
            
            setTimeout(() => updateURL(lat, lon), 200); // 稍微延遲讓用戶看到 marker
        }});

        if(ms.length > 0) map.setFitView();
        
      }}).catch(e=>console.error(e));
    </script>
    """
    components.html(html, height=height+30)


# =================== App ===================
st.set_page_config(page_title="聚会神器", layout="wide")
st.title("🍽️ 聚会中点 + 餐厅推荐")

if "spots" not in st.session_state: st.session_state.spots = []

# 1. 處理地圖點擊 (優先)
pk_lat = qp_get("pick_lat")
pk_lon = qp_get("pick_lon")
if pk_lat and pk_lon:
    st.toast(f"📍 已選地圖點: {pk_lat}, {pk_lon}")

left, right = st.columns([1, 2], gap="medium")

with left:
    st.subheader("📍 定位 / 加入")
    
    # IP 定位按鈕
    if st.button("🌍 IP 粗定位 (免GPS)", use_container_width=True):
        loc = get_ip_loc()
        if loc:
            st.session_state["ip_res"] = loc
            st.toast(f"IP定位: {loc[2]}", icon="✅")
            st.rerun()
        else: st.error("IP定位失敗")

    ip_res = st.session_state.get("ip_res")
    
    # 判斷預設模式
    idx = 2
    if ip_res: idx=0
    elif pk_lat: idx=1
    
    name = st.text_input("名字", "朋友"+str(len(st.session_state.spots)+1))
    mode = st.radio("來源", ["IP定位結果", "地圖點選", "手動輸入"], index=idx)

    if mode == "IP定位結果":
        if ip_res:
            st.info(f"📍 {ip_res[2]}")
            if st.button("✅ 加入 IP 點", type="primary", use_container_width=True):
                st.session_state.spots.append({"name":name, "lat":ip_res[0], "lon":ip_res[1], "src":"ip"})
                st.toast("已加入", icon="🎉")
                del st.session_state["ip_res"]
                st.rerun()
        else: st.caption("請先點上方 IP 定位")

    elif mode == "地圖點選":
        if pk_lat:
            st.info(f"📍 {pk_lat}, {pk_lon}")
            if st.button("✅ 加入地圖點", type="primary", use_container_width=True):
                st.session_state.spots.append({"name":name, "lat":float(pk_lat), "lon":float(pk_lon), "src":"map"})
                st.toast("已加入", icon="🎉")
                qp_del("pick_lat", "pick_lon")
                time.sleep(0.5)
                st.rerun()
        else: st.caption("請在右側地圖點選位置")

    else:
        l_in = st.text_input("緯度,經度 (或批量)", placeholder="39.90,116.40")
        if st.button("✅ 加入", type="primary", use_container_width=True):
            try:
                # 簡單批量支援
                for line in l_in.split("\n"):
                    parts = line.replace("，",",").split(",")
                    if len(parts)>=2:
                        st.session_state.spots.append({"name":name, "lat":float(parts[0]), "lon":float(parts[1]), "src":"manual"})
                st.toast("已加入", icon="🎉")
                st.rerun()
            except: st.error("格式錯誤")

    st.divider()
    if st.button("🗑️ 清空", use_container_width=True):
        st.session_state.spots=[]
        qp_del("pick_lat", "pick_lon")
        if "ip_res" in st.session_state: del st.session_state["ip_res"]
        st.rerun()

with right:
    if not st.session_state.spots:
        st.info("👈 請添加位置")
        render_map([], (39.90, 116.40), height=450)
    else:
        # 列表
        df = pd.DataFrame(st.session_state.spots)
        st.dataframe(df[["name","lat","lon"]].astype(str), use_container_width=True, hide_index=True)
        
        # 中點
        locs = [(r["lat"],r["lon"]) for _,r in df.iterrows()]
        c_lat, c_lon = calc_center(locs)
        
        c1,c2 = st.columns(2)
        c1.metric("中點緯度", f"{c_lat:.4f}")
        c2.metric("中點經度", f"{c_lon:.4f}")
        
        # 地圖
        st.write("🗺️ **高德地圖** (點擊任意處可選點)")
        render_map(st.session_state.spots, (c_lat, c_lon), height=500)
        
        # 餐廳
        st.divider()
        kw = st.text_input("🔍 找餐廳", "餐厅")
        if st.button("搜尋附近"):
            rest = get_restaurants(c_lat, c_lon, kw)
            if not rest.empty: st.dataframe(rest, use_container_width=True, hide_index=True)
            else: st.warning("無結果")
