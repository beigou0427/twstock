import json
from math import radians, degrees, sin, cos, atan2, sqrt

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests

# ====== 你的高德Key（REST查餐廳、JS畫地圖）======
AMAP_KEY = "a9075050dd895616798e9d039d89bdde"

# 如你在高德控制台啟用了「安全密鑰」，把 securityJsCode 填在這（可留空）
AMAP_SECURITY_JS_CODE = ""  # 例如："xxxxxxxxxxxxxxxxxxxx"


# ---------- Query params（接收定位/地圖點擊回傳） ----------
def qp_get(key: str, default=None):
    try:
        qp = st.query_params
        if key in qp:
            v = qp[key]
            if isinstance(v, list):
                return v[0] if v else default
            return v
        return default
    except Exception:
        qp = st.experimental_get_query_params()
        if key in qp and qp[key]:
            return qp[key][0]
        return default


def qp_del(*keys):
    try:
        for k in keys:
            if k in st.query_params:
                del st.query_params[k]
    except Exception:
        # 舊版沒有好方法刪單一key，就忽略
        pass


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


# ---------- 高德周邊餐廳 ----------
@st.cache_data(ttl=120)
def amap_nearby_restaurants(lat, lon, radius_m=3000, keywords="餐厅|火锅|烧烤|咖啡", offset=20):
    url = "https://restapi.amap.com/v3/place/around"
    params = {
        "key": AMAP_KEY,
        "location": f"{lon},{lat}",
        "keywords": keywords,
        "types": "050000",  # 餐飲
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
        rows.append(
            {
                "餐厅": str(p.get("name", "")),
                "距离": dist,
                "评分": str(biz.get("rating", "")),
                "均价": str(biz.get("cost", "")),
                "地址": str(p.get("address", "")),
                "电话": str(p.get("tel", "")),
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        for c in df.columns:
            df[c] = df[c].astype(str).replace("nan", "")
    return df


# ---------- HTML5 手機定位（方案A） ----------
def geolocate_block():
    st.subheader("📍 手機一鍵定位（瀏覽器原生）")
    lat = qp_get("lat")
    lon = qp_get("lon")
    acc = qp_get("acc")

    if lat and lon:
        try:
            return float(lat), float(lon), (float(acc) if acc else None)
        except Exception:
            pass

    html = """
    <div style="padding:12px;border:2px dashed #999;border-radius:10px;">
      <button onclick="getLocation()"
        style="padding:12px 18px;font-size:16px;border:none;border-radius:10px;background:#111;color:#fff;cursor:pointer;">
        Get my GPS location
      </button>
      <div id="status" style="margin-top:10px;font-family:sans-serif;font-size:14px;color:#333;"></div>
      <div style="margin-top:6px;font-family:sans-serif;font-size:12px;color:#666;">
        若失敗：請在瀏覽器網站設定允許定位後再按一次；必須是HTTPS頁面。
      </div>
    </div>
    <script>
      function getLocation() {
        const status = document.getElementById("status");
        if (!navigator.geolocation) { status.innerText = "Geolocation not supported"; return; }
        status.innerText = "Locating… please allow permission";
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            const lat = pos.coords.latitude;
            const lon = pos.coords.longitude;
            const acc = pos.coords.accuracy;
            const url = new URL(window.location.href);
            url.searchParams.set("lat", lat);
            url.searchParams.set("lon", lon);
            url.searchParams.set("acc", acc);
            window.location.href = url.toString();
          },
          (err) => { status.innerText = "Error: " + err.message; },
          { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
        );
      }
    </script>
    """
    components.html(html, height=170)
    return None


# ---------- 高德JS地圖（嵌入） ----------
def render_amap(spots, center, height=520):
    """
    spots: list[dict] each has name, lat, lon
    center: (lat, lon)
    地圖點擊會把 pick_lat/pick_lon 寫回 URL
    """
    # 準備 markers data（JS 用 lng,lat）
    markers = []
    for s in spots:
        try:
            markers.append(
                {
                    "name": str(s.get("name", "")),
                    "lat": float(s.get("lat")),
                    "lon": float(s.get("lon")),
                    "source": str(s.get("source", "")),
                }
            )
        except Exception:
            pass

    c_lat, c_lon = float(center[0]), float(center[1])
    markers_json = json.dumps(markers, ensure_ascii=False)

    # AMap Loader +（可選）安全密鑰
    sec = AMAP_SECURITY_JS_CODE.strip()
    sec_line = f'window._AMapSecurityConfig = {{securityJsCode: "{sec}"}};' if sec else ""

    html = f"""
    <div id="amap_container" style="width: 100%; height: {height}px;"></div>

    <script>
      {sec_line}
    </script>

    <script src="https://webapi.amap.com/loader.js"></script>
    <script>
      const markers = {markers_json};

      function boot() {{
        AMapLoader.load({{
          key: "{AMAP_KEY}",
          version: "2.0"
        }}).then((AMap) => {{
          const map = new AMap.Map("amap_container", {{
            zoom: 12,
            center: [{c_lon}, {c_lat}]
          }});

          // 中點 marker（紅色）
          const centerMarker = new AMap.Marker({{
            position: [{c_lon}, {c_lat}],
            title: "Center",
            anchor: "bottom-center"
          }});
          map.add(centerMarker);

          // 其他人 marker
          const ms = [];
          markers.forEach((m) => {{
            const mk = new AMap.Marker({{
              position: [m.lon, m.lat],
              title: m.name || "spot"
            }});
            mk.on("click", () => {{
              const url = new URL(window.location.href);
              url.searchParams.set("pick_lat", m.lat);
              url.searchParams.set("pick_lon", m.lon);
              window.location.href = url.toString();
            }});
            ms.push(mk);
          }});
          map.add(ms);

          // 點地圖取座標
          map.on("click", (e) => {{
            // e.lnglat 有 getLng/getLat [事件文檔一般描述 lnglat] 
            const lat = e.lnglat.getLat();
            const lon = e.lnglat.getLng();
            const url = new URL(window.location.href);
            url.searchParams.set("pick_lat", lat);
            url.searchParams.set("pick_lon", lon);
            window.location.href = url.toString();
          }});

          // 自適應視野
          const all = ms.concat([centerMarker]);
          if (all.length) map.setFitView(all);

        }}).catch((e) => {{
          document.getElementById("amap_container").innerHTML =
            "<div style='padding:12px;font-family:sans-serif;color:#b00;'>AMap load failed: " + (e && e.message ? e.message : e) + "</div>";
        }});
      }}

      // loader.js 可能晚到，稍微等一下
      setTimeout(boot, 50);
    </script>
    """
    components.html(html, height=height + 10)


# =================== UI ===================
st.set_page_config(page_title="聚会中点 + 餐厅推荐（高德地图）", layout="wide")
st.title("聚会中点 + 餐厅推荐（地圖用高德）")

if "spots" not in st.session_state:
    st.session_state.spots = []

left, right = st.columns([1.15, 1.85], gap="large")

with left:
    loc = geolocate_block()
    st.divider()

    st.subheader("➕ 添加位置")
    name = st.text_input("名字（可选）", value="", placeholder="例如：阿明 / 小美")

    mode = st.radio("添加方式", ["用GPS(刚获取)", "手动输入", "批量粘贴"], horizontal=True)

    if mode == "用GPS(刚获取)":
        if loc:
            glat, glon, gacc = loc
            st.success(f"定位：{glat:.6f}, {glon:.6f}" + (f"（±{int(gacc)}m）" if gacc else ""))
            if st.button("加入这笔", type="primary", use_container_width=True):
                st.session_state.spots.append(
                    {"name": name.strip() or f"人{len(st.session_state.spots)+1}", "lat": glat, "lon": glon, "source": "gps"}
                )
                qp_del("lat", "lon", "acc")
                st.rerun()
        else:
            st.info("先按上面的 Get my GPS location。")

    elif mode == "手动输入":
        lat_in = st.number_input("纬度 lat", value=39.90, format="%.6f")
        lon_in = st.number_input("经度 lon", value=116.40, format="%.6f")
        if st.button("加入这笔", type="primary", use_container_width=True):
            st.session_state.spots.append(
                {"name": name.strip() or f"人{len(st.session_state.spots)+1}", "lat": float(lat_in), "lon": float(lon_in), "source": "manual"}
            )
            st.rerun()

    else:
        st.caption("每行一人：`名字,纬度,经度` 或 `纬度,经度`；逗号或空格都行。")
        bulk = st.text_area("批量输入", height=140, placeholder="阿明,39.9042,116.4074\n31.2304,121.4737")
        if st.button("批量导入", type="primary", use_container_width=True):
            added = 0
            for line in bulk.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = [p for p in line.replace("，", ",").replace(" ", ",").split(",") if p != ""]
                try:
                    if len(parts) == 2:
                        nm = f"人{len(st.session_state.spots)+1}"
                        latv, lonv = float(parts[0]), float(parts[1])
                    else:
                        nm = parts[0].strip() or f"人{len(st.session_state.spots)+1}"
                        latv, lonv = float(parts[1]), float(parts[2])
                    st.session_state.spots.append({"name": nm, "lat": latv, "lon": lonv, "source": "bulk"})
                    added += 1
                except Exception:
                    pass
            st.success(f"已导入 {added} 笔")
            st.rerun()

    st.divider()
    st.subheader("🧭 地圖點選結果")
    pick_lat = qp_get("pick_lat")
    pick_lon = qp_get("pick_lon")
    if pick_lat and pick_lon:
        st.info(f"你點的座標：{pick_lat}, {pick_lon}")
        if st.button("加入點選座標", use_container_width=True):
            try:
                st.session_state.spots.append(
                    {"name": name.strip() or f"人{len(st.session_state.spots)+1}", "lat": float(pick_lat), "lon": float(pick_lon), "source": "map_click"}
                )
                qp_del("pick_lat", "pick_lon")
                st.rerun()
            except Exception:
                st.warning("點選座標解析失敗")
        if st.button("清除點選座標", type="secondary", use_container_width=True):
            qp_del("pick_lat", "pick_lon")
            st.rerun()
    else:
        st.caption("在右側高德地圖上點一下，就會回填座標。")

    st.divider()
    if st.button("清空全部", type="primary", use_container_width=True):
        st.session_state.spots = []
        qp_del("pick_lat", "pick_lon", "lat", "lon", "acc")
        st.rerun()

with right:
    st.subheader("📌 当前位置清单")
    if not st.session_state.spots:
        st.info("先新增至少 1 個位置；右邊會用高德地圖顯示，並可點圖取座標。")
    else:
        df = pd.DataFrame(st.session_state.spots)
        # 顯示用：全轉字串避免 pyarrow 問題
        show_df = df.copy()
        for c in show_df.columns:
            show_df[c] = show_df[c].astype(str).replace("nan", "")
        st.dataframe(show_df[["name", "lat", "lon", "source"]], use_container_width=True, hide_index=True)

        locs = [(r["lat"], r["lon"]) for _, r in df.iterrows()]
        c_lat, c_lon = calc_center_spherical(locs)

        c1, c2, c3 = st.columns(3)
        c1.metric("人数", len(locs))
        c2.metric("推荐纬度", f"{c_lat}")
        c3.metric("推荐经度", f"{c_lon}")

        st.subheader("🗺️ 高德地图（可點擊取座標）")
        render_amap(st.session_state.spots, (c_lat, c_lon), height=540)

        st.divider()
        st.subheader("🍜 附近餐厅推荐（以中点为中心）")
        keywords = st.text_input("关键字", value="餐厅|火锅|烧烤|咖啡")
        radius = st.slider("半径（米）", 500, 5000, 3000, 100)
        topn = st.slider("显示数量", 5, 20, 10, 1)

        if st.button("查询餐厅", type="primary"):
            with st.spinner("查询中…"):
                rest = amap_nearby_restaurants(c_lat, c_lon, radius_m=radius, keywords=keywords, offset=20)
            if rest.empty:
                st.warning("查不到结果：可能是Key/额度/地点较偏或关键字太窄。")
            else:
                st.dataframe(rest.head(topn), use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("💾 导出")
        csv = show_df[["name", "lat", "lon", "source"]].to_csv(index=False, encoding="utf-8-sig")
        st.download_button("下载CSV", csv, file_name="meeting_spots.csv", mime="text/csv", use_container_width=True)

st.caption("提示：如果高德地圖空白，請確認你的 Key 已開啟 Web端(JS API)；若啟用安全密鑰，填入 securityJsCode 後再部署。")
