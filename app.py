import json
import time
from math import radians, degrees, sin, cos, atan2, sqrt

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests

# ====== Key 分離 ======
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
    except:
        pass

# ---------- 地理中點 ----------
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
        except: pass
    if cnt == 0:
        return 39.90, 116.40
    x, y, z = x / cnt, y / cnt, z / cnt
    lon = degrees(atan2(y, x))
    hyp = sqrt(x * x + y * y)
    lat = degrees(atan2(z, hyp))
    return round(float(lat), 6), round(float(lon), 6)

# ---------- 高德餐廳 ----------
@st.cache_data(ttl=120)
def amap_nearby_restaurants(lat, lon, radius_m=3000, keywords="餐厅", offset=20):
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
            d = float(p.get("distance", "0")) / 1000.0
            dist = f"{d:.2f} km"
        except: dist = ""
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
        for c in df.columns: df[c] = df[c].astype(str).replace("nan", "")
    return df

# ---------- GPS Block (HTML5) ----------
def gps_block():
    st.subheader("📍 手機 GPS 定位")
    
    # 從 URL 讀取回填的座標
    lat = qp_get("lat")
    lon = qp_get("lon")
    acc = qp_get("acc")
    err = qp_get("geo_err")

    if err:
        st.error(f"定位失敗：{err}")

    # 顯示取得的座標（若有）
    if lat and lon:
        try:
            glat, glon = float(lat), float(lon)
            gacc = float(acc) if acc else None
            # 用 info 顯示，這樣加入後就算 URL 參數被清掉，也不會覺得這區塊怪怪的
            st.info(f"📍 已取得座標：{glat:.6f}, {glon:.6f}" + (f" (±{int(gacc)}m)" if gacc else ""))
            return glat, glon, gacc
        except:
            st.warning("座標解析錯誤")

    # 定位按鈕與腳本
    html = """
    <div style="padding:10px;border:1px dashed #aaa;border-radius:8px;background:#f9f9f9;">
      <button onclick="getLocation()" style="background:#000;color:#fff;border:none;padding:10px 16px;border-radius:6px;font-size:15px;cursor:pointer;">
        📡 點我獲取 GPS
      </button>
      <div id="status" style="margin-top:8px;color:#444;font-size:13px;"></div>
      <a id="backlink" target="_top" style="display:none;margin-top:8px;color:#007bff;font-weight:bold;cursor:pointer;">✅ 點此完成回填</a>
    </div>
    <script>
      function buildUrl(lat, lon, acc) {
        // 嘗試抓當前頁面 URL
        let base = document.referrer || window.location.href;
        try {
            let url = new URL(base);
            url.searchParams.set("lat", lat);
            url.searchParams.set("lon", lon);
            url.searchParams.set("acc", acc);
            url.searchParams.delete("geo_err");
            return url.toString();
        } catch(e) { return base; }
      }
      function getLocation() {
        const s = document.getElementById("status");
        if (!navigator.geolocation) { s.innerText = "瀏覽器不支援定位"; return; }
        s.innerText = "定位中...請允許權限";
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            const u = buildUrl(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy);
            s.innerText = "成功！正在回填...";
            document.getElementById("backlink").href = u;
            document.getElementById("backlink").style.display = "inline-block";
            // 自動跳轉
            try { window.top.location.href = u; } 
            catch(e) { try { window.location.href = u; } catch(z){} }
          },
          (err) => {
            s.innerText = "失敗: " + err.message;
            // 失敗也回填錯誤訊息
            let base = document.referrer || window.location.href;
            try {
                let url = new URL(base);
                url.searchParams.set("geo_err", err.message);
                window.top.location.href = url.toString();
            } catch(e){}
          },
          { enableHighAccuracy: true, timeout: 12000 }
        );
      }
    </script>
    """
    components.html(html, height=140)
    return None

# ---------- 高德 JS 地圖 ----------
def render_amap(spots, center, height=500):
    markers = []
    for s in spots:
        try:
            markers.append({"name": str(s.get("name","")), "lat": float(s.get("lat")), "lon": float(s.get("lon"))})
        except: pass
    c_lat, c_lon = float(center[0]), float(center[1])
    
    html = f"""
    <div id="amap" style="width:100%;height:{height}px;"></div>
    <script>
      window._AMapSecurityConfig = {{securityJsCode: "{AMAP_SECURITY_JS_CODE}"}};
    </script>
    <script src="https://webapi.amap.com/loader.js"></script>
    <script>
      AMapLoader.load({{key:"{AMAP_JS_KEY}", version:"2.0"}}).then((AMap)=>{{
        const map = new AMap.Map("amap", {{ zoom:12, center:[{c_lon}, {c_lat}] }});
        
        // 中點
        map.add(new AMap.Marker({{ position:[{c_lon}, {c_lat}], title:"中點", icon:"https://webapi.amap.com/theme/v1.3/markers/n/mark_r.png" }}));

        // 眾人
        const markers = {json.dumps(markers, ensure_ascii=False)};
        markers.forEach(m => {{
            const mk = new AMap.Marker({{ position:[m.lon, m.lat], title:m.name }});
            // 點 marker 回填座標
            mk.on("click", () => {{
                const u = new URL(window.top.location.href);
                u.searchParams.set("pick_lat", m.lat);
                u.searchParams.set("pick_lon", m.lon);
                window.top.location.href = u.toString();
            }});
            map.add(mk);
        }});
        
        // 點地圖空白處
        map.on("click", (e) => {{
            const u = new URL(window.top.location.href);
            u.searchParams.set("pick_lat", e.lnglat.getLat());
            u.searchParams.set("pick_lon", e.lnglat.getLng());
            window.top.location.href = u.toString();
        }});
        
        map.setFitView();
      }}).catch(e => console.error(e));
    </script>
    """
    components.html(html, height=height+20)

# =================== App UI ===================
st.set_page_config(page_title="聚会神器", layout="wide")
st.title("🍽️ 聚会中点 + 餐厅推荐")

if "spots" not in st.session_state:
    st.session_state.spots = []

# --- 處理地圖點選回填 ---
pk_lat = qp_get("pick_lat")
pk_lon = qp_get("pick_lon")
if pk_lat and pk_lon:
    st.toast(f"📍 已選取地圖座標: {pk_lat}, {pk_lon}")

left, right = st.columns([1, 2], gap="medium")

with left:
    # 1. GPS 區塊
    loc_gps = gps_block()
    
    st.divider()
    
    # 2. 加入位置表單
    st.subheader("➕ 加入位置")
    name = st.text_input("名字", placeholder="例如: 小明")
    
    # 根據是否有 GPS 或 點選座標 來決定預設模式
    default_idx = 0
    if loc_gps: default_idx = 0
    elif pk_lat: default_idx = 1
    else: default_idx = 2
    
    mode = st.radio("來源", ["使用 GPS", "使用地圖點選", "手動/批量"], index=default_idx)

    if mode == "使用 GPS":
        if loc_gps:
            if st.button("✅ 加入此 GPS", type="primary", use_container_width=True):
                st.session_state.spots.append({
                    "name": name.strip() or f"人{len(st.session_state.spots)+1}",
                    "lat": loc_gps[0], "lon": loc_gps[1], "source": "gps"
                })
                # 用 toast 顯示成功，不依賴頁面文字
                st.toast(f"✅ 已加入 GPS 位置！", icon="🎉")
                qp_del("lat", "lon", "acc", "geo_err")
                time.sleep(0.5) # 稍等一下讓 toast 顯示
                st.rerun()
        else:
            st.caption("請先點上方「取得我的 GPS 座標」")

    elif mode == "使用地圖點選":
        if pk_lat and pk_lon:
            st.info(f"地圖點選: {pk_lat}, {pk_lon}")
            if st.button("✅ 加入此點", type="primary", use_container_width=True):
                st.session_state.spots.append({
                    "name": name.strip() or f"人{len(st.session_state.spots)+1}",
                    "lat": float(pk_lat), "lon": float(pk_lon), "source": "map"
                })
                st.toast(f"✅ 已加入地圖點選位置！", icon="🎉")
                qp_del("pick_lat", "pick_lon")
                time.sleep(0.5)
                st.rerun()
        else:
            st.caption("請在右側地圖上點一下")

    else:
        # 手動 / 批量
        txt = st.text_area("批量 (名字,緯度,經度)", height=100, placeholder="39.90,116.40\n小華,31.23,121.47")
        if st.button("批量加入", use_container_width=True):
            cnt = 0
            for line in txt.splitlines():
                parts = line.replace("，",",").split(",")
                try:
                    if len(parts)>=2:
                        # 簡單判斷
                        if len(parts)==2: lat,lon=parts[0],parts[1]; nm=f"人{len(st.session_state.spots)+1}"
                        else: nm,lat,lon=parts[0],parts[1],parts[2]
                        st.session_state.spots.append({"name":nm,"lat":float(lat),"lon":float(lon),"source":"bulk"})
                        cnt+=1
                except: pass
            if cnt>0:
                st.toast(f"✅ 已加入 {cnt} 筆資料！", icon="🎉")
                time.sleep(0.5)
                st.rerun()

    st.divider()
    if st.button("🗑️ 清空所有位置", use_container_width=True):
        st.session_state.spots = []
        qp_del("lat","lon","acc","pick_lat","pick_lon")
        st.rerun()

with right:
    # 顯示列表 & 地圖 & 推薦
    if not st.session_state.spots:
        st.info("👈 請在左側添加位置，開始計算中點")
        # 預設顯示北京地圖當背景
        render_amap([], (39.90, 116.40), height=400)
    else:
        # 列表
        df = pd.DataFrame(st.session_state.spots)
        st.dataframe(df[["name","lat","lon"]].astype(str), use_container_width=True, hide_index=True)
        
        # 中點
        locs = [(r["lat"], r["lon"]) for _, r in df.iterrows()]
        c_lat, c_lon = calc_center_spherical(locs)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("人數", len(locs))
        c2.metric("中點緯度", f"{c_lat:.4f}")
        c3.metric("中點經度", f"{c_lon:.4f}")
        
        # 地圖
        st.write("🗺️ **高德地圖** (點擊地圖可選點)")
        render_amap(st.session_state.spots, (c_lat, c_lon), height=500)
        
        st.divider()
        st.subheader("🍜 附近餐廳")
        kw = st.text_input("關鍵字", "餐厅")
        if st.button("🔍 搜尋附近", type="primary"):
            rest = amap_nearby_restaurants(c_lat, c_lon, keywords=kw)
            if not rest.empty:
                st.dataframe(rest, use_container_width=True, hide_index=True)
            else:
                st.warning("無結果")
        
        st.divider()
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("下載 CSV", csv, "spots.csv", "text/csv")
