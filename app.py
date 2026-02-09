import json
from math import radians, degrees, sin, cos, atan2, sqrt

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests

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

# ---------- 免費 IP 定位（替代 GPS） ----------
def get_ip_location():
    try:
        # 使用 ip-api.com (免費，不需 Key)
        r = requests.get("http://ip-api.com/json/?fields=status,message,country,regionName,city,lat,lon", timeout=5)
        data = r.json()
        if data["status"] == "success":
            return float(data["lat"]), float(data["lon"]), f"{data['city']}, {data['regionName']}"
        return None
    except:
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
    st.subheader("📍 定位 (IP 免費 API)")
    if st.button("🌍 取得我的大概位置", type="primary", use_container_width=True):
        loc = get_ip_location()
        if loc:
            lat, lon, city = loc
            st.session_state["ip_loc"] = (lat, lon, city)
            st.toast(f"✅ 定位成功: {city}", icon="🌍")
            st.rerun()
        else:
            st.error("定位失敗，請手動輸入")

    # 顯示 IP 定位結果
    ip_loc = st.session_state.get("ip_loc")
    
    st.divider()
    st.subheader("➕ 加入位置")
    name = st.text_input("名字", placeholder="例如: 小明")
    
    # 自動切換模式
    idx = 2
    if ip_loc: idx=0
    elif pk_lat: idx=1
    
    mode = st.radio("來源", ["使用 IP 定位", "使用地圖點選", "手動/批量"], index=idx)

    if mode == "使用 IP 定位":
        if ip_loc:
            st.info(f"📍 {ip_loc[2]} ({ip_loc[0]}, {ip_loc[1]})")
            if st.button("✅ 加入此位置", type="primary", use_container_width=True):
                st.session_state.spots.append({
                    "name": name.strip() or f"人{len(st.session_state.spots)+1}",
                    "lat": ip_loc[0], "lon": ip_loc[1], "source": "ip"
                })
                st.toast("✅ 已加入！", icon="🎉")
                st.rerun()
        else:
            st.caption("請先點上方按鈕取得位置")

    elif mode == "使用地圖點選":
        if pk_lat:
            if st.button("✅ 加入此點", type="primary", use_container_width=True):
                st.session_state.spots.append({
                    "name": name.strip() or f"人{len(st.session_state.spots)+1}",
                    "lat": float(pk_lat), "lon": float(pk_lon), "source": "map"
                })
                st.toast("✅ 已加入！", icon="🎉")
                qp_del("pick_lat", "pick_lon")
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
                st.rerun()

    st.divider()
    if st.button("🗑️ 清空", use_container_width=True):
        st.session_state.spots=[]
        if "ip_loc" in st.session_state: del st.session_state["ip_loc"]
        qp_del("pick_lat","pick_lon")
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
