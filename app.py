import json
import time
from math import radians, degrees, sin, cos, atan2, sqrt

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
import geocoder  # 新增 IP 定位庫

# ====== Key ======
AMAP_JS_KEY = "0cd3a5f0715be098c172e5359b94e99d"
AMAP_SECURITY_JS_CODE = "89b4b0c537e7e364af191c498542e593"
AMAP_REST_KEY = "a9075050dd895616798e9d039d89bdde"

# ---------- Query params ----------
def qp_get(key: str, default=None):
    try:
        qp = st.query_params
        if key not in qp:
            return default
        v = qp[key]
        if isinstance(v, list):
            return v[0] if v else default
        return v
    except:
        return default

def qp_del(*keys):
    try:
        for k in keys:
            if k in st.query_params:
                del st.query_params[k]
    except: pass

# ---------- 中點計算 ----------
@st.cache_data
def calc_center_spherical(locs):
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

# ---------- 餐廳推薦 ----------
@st.cache_data(ttl=120)
def amap_nearby_restaurants(lat, lon, radius_m=3000, keywords="餐厅", offset=20):
    url = "https://restapi.amap.com/v3/place/around"
    params = {
        "key": AMAP_REST_KEY, "location": f"{lon},{lat}",
        "keywords": keywords, "types": "050000",
        "radius": int(radius_m), "page": 1, "offset": int(offset), "extensions": "all"
    }
    r = requests.get(url, params=params, timeout=12)
    data = r.json()
    if data.get("status")!="1": return pd.DataFrame()
    rows=[]
    for p in (data.get("pois") or []):
        try: d = f"{float(p.get('distance','0'))/1000.0:.2f} km"
        except: d=""
        rows.append({
            "餐厅":p.get("name",""), "距离":d, "评分":p.get("biz_ext",{}).get("rating",""),
            "均价":p.get("biz_ext",{}).get("cost",""), "地址":p.get("address",""), "电话":p.get("tel","")
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        for c in df.columns: df[c] = df[c].astype(str).replace("nan","")
    return df

# ---------- 定位區塊（GPS + IP 雙軌） ----------
def location_block():
    st.subheader("📍 定位功能")
    
    # 讀取 URL 回填的參數
    lat = qp_get("lat")
    lon = qp_get("lon")
    acc = qp_get("acc")
    src = qp_get("src")
    err = qp_get("geo_err")

    if err:
        st.error(f"GPS 失敗: {err}")

    # 如果有座標，顯示出來
    if lat and lon:
        try:
            glat, glon = float(lat), float(lon)
            label = "GPS (高精度)" if src == "gps" else "IP (粗略)"
            st.info(f"✅ 已取得 {label}：{glat:.5f}, {glon:.5f}")
            return glat, glon, src
        except: pass

    col1, col2 = st.columns(2)
    
    with col1:
        # 選項A: HTML5 GPS
        html = """
        <div style="text-align:center;">
          <button onclick="getGPS()" style="width:100%;padding:10px;background:#000;color:#fff;border:none;border-radius:8px;cursor:pointer;">
            📡 精準 GPS
          </button>
          <div id="status" style="font-size:12px;color:#555;margin-top:5px;"></div>
        </div>
        <script>
          function go(lat, lon, acc, src) {
            const u = new URL(window.top.location.href);
            u.searchParams.set("lat", lat); u.searchParams.set("lon", lon);
            u.searchParams.set("acc", acc); u.searchParams.set("src", src);
            u.searchParams.delete("geo_err");
            window.top.location.href = u.toString();
          }
          function getGPS() {
            const s = document.getElementById("status");
            if (!navigator.geolocation) { s.innerText="不支援"; return; }
            s.innerText="定位中...";
            navigator.geolocation.getCurrentPosition(
              (p) => go(p.coords.latitude, p.coords.longitude, p.coords.accuracy, "gps"),
              (e) => { s.innerText="失敗:"+e.message; },
              {enableHighAccuracy:true, timeout:10000}
            );
          }
        </script>
        """
        components.html(html, height=80)

    with col2:
        # 選項B: IP 定位（Python 端處理）
        if st.button("🌐 IP 粗定位 (備用)", use_container_width=True):
            try:
                g = geocoder.ip("me")
                if g.ok:
                    qp_del("geo_err") # 清除舊錯誤
                    # 寫入 URL 讓邏輯統一
                    st.query_params["lat"] = str(g.latlng[0])
                    st.query_params["lon"] = str(g.latlng[1])
                    st.query_params["src"] = "ip"
                    st.rerun()
                else:
                    st.error("IP 定位失敗")
            except Exception as e:
                st.error(f"IP 定位錯誤: {e}")

    return None

# ---------- 高德地圖 ----------
def render_amap(spots, center, height=500):
    markers = []
    for s in spots:
        try: markers.append({"name":str(s.get("name","")), "lat":float(s["lat"]), "lon":float(s["lon"])})
        except: pass
    c_lat, c_lon = float(center[0]), float(center[1])
    
    html = f"""
    <div id="amap" style="width:100%;height:{height}px;"></div>
    <script>window._AMapSecurityConfig={{securityJsCode:"{AMAP_SECURITY_JS_CODE}"}};</script>
    <script src="https://webapi.amap.com/loader.js"></script>
    <script>
      AMapLoader.load({{key:"{AMAP_JS_KEY}", version:"2.0"}}).then((AMap)=>{{
        const map = new AMap.Map("amap", {{ zoom:12, center:[{c_lon},{c_lat}] }});
        map.add(new AMap.Marker({{ position:[{c_lon},{c_lat}], title:"中點", icon:"https://webapi.amap.com/theme/v1.3/markers/n/mark_r.png" }}));
        const ms = {json.dumps(markers, ensure_ascii=False)};
        ms.forEach(m => {{
            const mk = new AMap.Marker({{ position:[m.lon, m.lat], title:m.name }});
            mk.on("click", ()=>{{
                const u = new URL(window.top.location.href);
                u.searchParams.set("pick_lat", m.lat); u.searchParams.set("pick_lon", m.lon);
                window.top.location.href = u.toString();
            }});
            map.add(mk);
        }});
        map.on("click", (e)=>{{
            const u = new URL(window.top.location.href);
            u.searchParams.set("pick_lat", e.lnglat.getLat()); u.searchParams.set("pick_lon", e.lnglat.getLng());
            window.top.location.href = u.toString();
        }});
        map.setFitView();
      }}).catch(e=>console.error(e));
    </script>
    """
    components.html(html, height=height+20)

# =================== App ===================
st.set_page_config(page_title="聚会神器", layout="wide")
st.title("🍽️ 聚会中点 + 餐厅推荐")

if "spots" not in st.session_state: st.session_state.spots = []

# 地圖點選回填
pk_lat = qp_get("pick_lat"); pk_lon = qp_get("pick_lon")
if pk_lat and pk_lon: st.toast(f"📍 地圖選點: {pk_lat}, {pk_lon}")

left, right = st.columns([1, 2], gap="medium")

with left:
    # 1. 定位區塊（GPS/IP）
    loc_res = location_block()
    
    st.divider()
    st.subheader("➕ 加入位置")
    name = st.text_input("名字", placeholder="例如: 小明")
    
    # 自動切換模式
    idx = 0
    if loc_res: idx=0
    elif pk_lat: idx=1
    else: idx=2
    
    mode = st.radio("來源", ["使用定位結果", "使用地圖點選", "手動/批量"], index=idx)

    if mode == "使用定位結果":
        if loc_res:
            if st.button(f"✅ 加入 ({loc_res[2].upper()})", type="primary", use_container_width=True):
                st.session_state.spots.append({
                    "name": name.strip() or f"人{len(st.session_state.spots)+1}",
                    "lat": loc_res[0], "lon": loc_res[1], "source": loc_res[2]
                })
                st.toast("✅ 已加入！", icon="🎉")
                qp_del("lat", "lon", "acc", "src", "geo_err")
                time.sleep(0.5)
                st.rerun()
        else:
            st.caption("請先在上方取得定位")

    elif mode == "使用地圖點選":
        if pk_lat:
            if st.button("✅ 加入此點", type="primary", use_container_width=True):
                st.session_state.spots.append({
                    "name": name.strip() or f"人{len(st.session_state.spots)+1}",
                    "lat": float(pk_lat), "lon": float(pk_lon), "source": "map"
                })
                st.toast("✅ 已加入！", icon="🎉")
                qp_del("pick_lat", "pick_lon")
                time.sleep(0.5)
                st.rerun()
        else:
            st.caption("請在右側地圖點選")

    else:
        txt = st.text_area("批量 (名字,緯度,經度)", height=100)
        if st.button("批量加入", use_container_width=True):
            cnt=0
            for l in txt.splitlines():
                p=l.replace("，",",").split(",")
                try:
                    if len(p)==2: lat,lon=p[0],p[1]; nm=f"人{len(st.session_state.spots)+1}"
                    else: nm,lat,lon=p[0],p[1],p[2]
                    st.session_state.spots.append({"name":nm,"lat":float(lat),"lon":float(lon),"source":"bulk"})
                    cnt+=1
                except: pass
            if cnt: 
                st.toast(f"✅ 加入 {cnt} 筆", icon="🎉")
                time.sleep(0.5)
                st.rerun()

    st.divider()
    if st.button("🗑️ 清空", use_container_width=True):
        st.session_state.spots=[]
        qp_del("lat","lon","acc","src","pick_lat","pick_lon")
        st.rerun()

with right:
    if not st.session_state.spots:
        st.info("👈 請添加位置")
        render_amap([], (39.90, 116.40), height=400)
    else:
        df = pd.DataFrame(st.session_state.spots)
        st.dataframe(df[["name","lat","lon","source"]].astype(str), use_container_width=True, hide_index=True)
        
        locs = [(r["lat"], r["lon"]) for _,r in df.iterrows()]
        c_lat, c_lon = calc_center_spherical(locs)
        
        c1,c2,c3 = st.columns(3)
        c1.metric("人數", len(locs))
        c2.metric("中點緯度", f"{c_lat:.4f}")
        c3.metric("中點經度", f"{c_lon:.4f}")
        
        st.write("🗺️ **高德地圖**")
        render_amap(st.session_state.spots, (c_lat, c_lon), height=500)
        
        st.divider()
        kw = st.text_input("餐廳關鍵字", "餐厅")
        if st.button("🔍 搜尋附近"):
            rest = amap_nearby_restaurants(c_lat, c_lon, keywords=kw)
            if not rest.empty: st.dataframe(rest, use_container_width=True, hide_index=True)
            else: st.warning("無結果")
        
        st.divider()
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("下載 CSV", csv, "spots.csv", "text/csv")
