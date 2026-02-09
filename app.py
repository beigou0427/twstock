import json
from math import radians, degrees, sin, cos, atan2, sqrt

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests

# streamlit-geolocation 組件
try:
    from streamlit_geolocation import streamlit_geolocation
    HAS_GEO = True
except ImportError:
    HAS_GEO = False

# ====== Key 分離 ======
AMAP_JS_KEY = "0cd3a5f0715be098c172e5359b94e99d"
AMAP_SECURITY_JS_CODE = "89b4b0c537e7e364af191c498542e593"
AMAP_REST_KEY = "a9075050dd895616798e9d039d89bdde"


# ---------- 地理中點（球面平均） ----------
@st.cache_data
def calc_center_spherical(locs):
    if not locs:
        return 39.90, 116.40
    x = y = z = 0.0
    cnt = 0
    for lat, lon in locs:
        try:
            rlat, rlon = radians(float(lat)), radians(float(lon))
            x += cos(rlat) * cos(rlon)
            y += cos(rlat) * sin(rlon)
            z += sin(rlat)
            cnt += 1
        except Exception:
            pass
    if cnt == 0:
        return 39.90, 116.40
    x, y, z = x / cnt, y / cnt, z / cnt
    lon = degrees(atan2(y, x))
    hyp = sqrt(x * x + y * y)
    lat = degrees(atan2(z, hyp))
    return round(float(lat), 6), round(float(lon), 6)


# ---------- 高德周邊餐廳（REST） ----------
@st.cache_data(ttl=120)
def amap_nearby_restaurants(lat, lon, radius_m=3000, keywords="餐厅|火锅|烧烤|咖啡", offset=20):
    url = "https://restapi.amap.com/v3/place/around"
    params = {
        "key": AMAP_REST_KEY,
        "location": f"{lon},{lat}",
        "keywords": keywords,
        "types": "050000",
        "radius": int(radius_m),
        "page": 1,
        "offset": int(offset),
        "extensions": "all",
    }
    r = requests.get(url, params=params, timeout=12)
    data = r.json()
    if data.get("status") != "1":
        return pd.DataFrame()

    rows = []
    for p in (data.get("pois") or []):
        biz = p.get("biz_ext") or {}
        try:
            dist_km = float(p.get("distance", "0")) / 1000.0
            dist = f"{dist_km:.2f} km"
        except Exception:
            dist = ""
        rows.append({
            "餐厅": str(p.get("name", "")),
            "距离": dist,
            "评分": str(biz.get("rating", "")),
            "均价": str(biz.get("cost", "")),
            "地址": str(p.get("address", "")),
            "电话": str(p.get("tel", "")),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        for c in df.columns:
            df[c] = df[c].astype(str).replace("nan", "")
    return df


# ---------- streamlit-geolocation 組件定位 ----------
def geolocate_block():
    st.subheader("📍 手機GPS定位")
    
    if not HAS_GEO:
        st.error("streamlit-geolocation 未安裝，請用手動輸入")
        return None
    
    location = streamlit_geolocation()
    
    if location and location.get("latitude") and location.get("longitude"):
        lat = location["latitude"]
        lon = location["longitude"]
        acc = location.get("accuracy", 0)
        st.success(f"✅ 定位成功：{lat:.6f}, {lon:.6f}（精度: ±{int(acc)}m）")
        return lat, lon, acc
    else:
        st.info("👆 點上面按鈕允許GPS權限（需HTTPS）")
        return None


# ---------- 高德 JS 地圖 ----------
def render_amap(spots, center, height=560):
    markers = []
    for s in spots:
        try:
            markers.append({
                "name": str(s.get("name", "")),
                "lat": float(s.get("lat")),
                "lon": float(s.get("lon")),
            })
        except Exception:
            pass

    c_lat, c_lon = float(center[0]), float(center[1])
    markers_json = json.dumps(markers, ensure_ascii=False)

    html = f"""
    <div id="amap_container" style="width: 100%; height: {height}px;"></div>
    <div id="map_status" style="margin-top:8px;font-size:12px;color:#666;"></div>

    <script>
      window._AMapSecurityConfig = {{securityJsCode: "{AMAP_SECURITY_JS_CODE}"}};
    </script>
    <script src="https://webapi.amap.com/loader.js"></script>

    <script>
      const markers = {markers_json};
      const status = document.getElementById("map_status");

      function boot() {{
        if (typeof AMapLoader === "undefined") {{
          status.innerText = "AMapLoader 加載失敗";
          return;
        }}

        AMapLoader.load({{
          key: "{AMAP_JS_KEY}",
          version: "2.0"
        }}).then((AMap) => {{
          const map = new AMap.Map("amap_container", {{
            zoom: 12,
            center: [{c_lon}, {c_lat}]
          }});

          // 中點 marker（紅色）
          const centerMarker = new AMap.Marker({{
            position: [{c_lon}, {c_lat}],
            title: "推薦中點",
            label: {{content: "⭐中點", direction: "top"}}
          }});
          map.add(centerMarker);

          // 用戶 marker
          const ms = [];
          markers.forEach((m, idx) => {{
            const mk = new AMap.Marker({{
              position: [m.lon, m.lat],
              title: m.name,
              label: {{content: m.name || `人${{idx+1}}`, direction: "bottom"}}
            }});
            ms.push(mk);
          }});
          map.add(ms);

          // 點地圖取座標（透過 postMessage 回傳 Streamlit）
          map.on("click", (e) => {{
            const lat = e.lnglat.getLat();
            const lon = e.lnglat.getLng();
            status.innerText = `點擊座標：${{lat.toFixed(6)}}, ${{lon.toFixed(6)}}`;
            
            // 添加臨時標記
            const tempMarker = new AMap.Marker({{
              position: [lon, lat],
              icon: new AMap.Icon({{
                size: new AMap.Size(25, 34),
                image: '//a.amap.com/jsapi_demos/static/demo-center/icons/poi-marker-default.png'
              }})
            }});
            map.add(tempMarker);
          }});

          // 自適應視野
          const all = ms.concat([centerMarker]);
          if (all.length) map.setFitView(all);
          status.innerText = "地圖載入成功！點擊地圖可顯示座標";

        }}).catch((e) => {{
          status.innerText = "地圖加載失敗: " + (e && e.message ? e.message : e);
        }});
      }}

      setTimeout(boot, 100);
    </script>
    """
    components.html(html, height=height + 30)


# =================== App UI ===================
st.set_page_config(page_title="聚会中点 + 餐厅推荐", layout="wide")
st.title("🍽️ 聚会中点 + 餐厅推荐")
st.caption("手機GPS定位 + 高德地圖 + 周邊餐廳推薦")

if "spots" not in st.session_state:
    st.session_state.spots = []

left, right = st.columns([1.15, 1.85], gap="large")

with left:
    loc = geolocate_block()
    st.divider()

    st.subheader("➕ 添加位置")
    name = st.text_input("名字", value="", placeholder="例如：小明")

    mode = st.radio("方式", ["用GPS定位", "手動輸入", "批量粘貼"], horizontal=True)

    if mode == "用GPS定位":
        if loc:
            glat, glon, gacc = loc
            if st.button("✅ 加入GPS位置", type="primary", use_container_width=True):
                st.session_state.spots.append({
                    "name": name.strip() or f"人{len(st.session_state.spots)+1}",
                    "lat": glat,
                    "lon": glon,
                    "source": "gps"
                })
                st.balloons()
                st.rerun()
        else:
            st.info("等待GPS定位...")

    elif mode == "手動輸入":
        lat_in = st.number_input("緯度", value=39.90, format="%.6f")
        lon_in = st.number_input("經度", value=116.40, format="%.6f")
        if st.button("加入", type="primary", use_container_width=True):
            st.session_state.spots.append({
                "name": name.strip() or f"人{len(st.session_state.spots)+1}",
                "lat": float(lat_in),
                "lon": float(lon_in),
                "source": "manual"
            })
            st.rerun()

    else:
        st.caption("每行：`名字,緯度,經度` 或 `緯度,經度`")
        bulk = st.text_area("批量", height=120, placeholder="小明,39.9042,116.4074\n31.2304,121.4737")
        if st.button("批量導入", type="primary", use_container_width=True):
            added = 0
            for line in bulk.splitlines():
                parts = [p.strip() for p in line.replace("，", ",").replace(" ", ",").split(",") if p.strip()]
                try:
                    if len(parts) == 2:
                        nm = f"人{len(st.session_state.spots)+1}"
                        latv, lonv = float(parts[0]), float(parts[1])
                    else:
                        nm = parts[0] or f"人{len(st.session_state.spots)+1}"
                        latv, lonv = float(parts[1]), float(parts[2])
                    st.session_state.spots.append({"name": nm, "lat": latv, "lon": lonv, "source": "bulk"})
                    added += 1
                except:
                    pass
            st.success(f"已導入 {added} 筆")
            st.rerun()

    st.divider()
    if st.button("🗑️ 清空全部", type="secondary", use_container_width=True):
        st.session_state.spots = []
        st.rerun()

with right:
    if not st.session_state.spots:
        st.info("👈 先添加位置")
    else:
        df = pd.DataFrame(st.session_state.spots)
        show_df = df.copy()
        for c in show_df.columns:
            show_df[c] = show_df[c].astype(str)

        st.subheader("📌 位置清單")
        st.dataframe(show_df[["name", "lat", "lon", "source"]], use_container_width=True, hide_index=True)

        locs = [(r["lat"], r["lon"]) for _, r in df.iterrows()]
        c_lat, c_lon = calc_center_spherical(locs)

        col1, col2, col3 = st.columns(3)
        col1.metric("人數", len(locs))
        col2.metric("中點緯度", f"{c_lat}")
        col3.metric("中點經度", f"{c_lon}")

        st.subheader("🗺️ 高德地圖")
        render_amap(st.session_state.spots, (c_lat, c_lon))

        st.divider()
        st.subheader("🍜 附近餐廳")
        keywords = st.text_input("關鍵字", value="餐厅|火锅|烧烤|咖啡")
        radius = st.slider("半徑(米)", 500, 5000, 3000, 100)
        topn = st.slider("顯示數", 5, 20, 10)

        if st.button("🔍 查詢餐廳", type="primary"):
            with st.spinner("搜索中..."):
                rest = amap_nearby_restaurants(c_lat, c_lon, radius_m=radius, keywords=keywords)
            if rest.empty:
                st.warning("查無結果")
            else:
                st.dataframe(rest.head(topn), use_container_width=True, hide_index=True)

        st.divider()
        csv = show_df[["name", "lat", "lon"]].to_csv(index=False, encoding="utf-8-sig")
        st.download_button("💾 下載CSV", csv, "meeting_spots.csv", "text/csv", use_container_width=True)
