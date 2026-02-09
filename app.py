import json
from math import radians, degrees, sin, cos, atan2, sqrt

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests

# ====== Key 分離 ======
# 地圖用（JS API + 安全密鑰）
AMAP_JS_KEY = "0cd3a5f0715be098c172e5359b94e99d"
AMAP_SECURITY_JS_CODE = "89b4b0c537e7e364af191c498542e593"
# 找餐廳用（Web Service / REST）
AMAP_REST_KEY = "a9075050dd895616798e9d039d89bdde"


# ---------- Query params（兼容新舊 Streamlit） ----------
def qp_get(key: str, default=None):
    try:
        # st.query_params：dict-like，value 通常是 str（重複 key 才需要 get_all）
        qp = st.query_params
        if key not in qp:
            return default
        v = qp[key]
        if isinstance(v, list):
            return v[0] if v else default
        return v
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


# ---------- GPS：HTML5 Geolocation（穩定回填版） ----------
def gps_block():
    st.subheader("📍 手機 GPS 定位（免安裝套件）")

    lat = qp_get("lat")
    lon = qp_get("lon")
    acc = qp_get("acc")
    err = qp_get("geo_err")

    if err:
        st.error(f"定位失敗：{err}")

    if lat and lon:
        try:
            glat, glon = float(lat), float(lon)
            gacc = float(acc) if acc else None
            st.success(f"✅ 已取得：{glat:.6f}, {glon:.6f}" + (f"（±{int(gacc)}m）" if gacc else ""))
            return glat, glon, gacc
        except Exception:
            st.warning("已取得定位但解析失敗，請再試一次。")

    html = """
    <div style="padding:12px;border:2px dashed #999;border-radius:10px;">
      <button id="btn" onclick="getLocation()"
        style="padding:12px 18px;font-size:16px;border:none;border-radius:10px;background:#111;color:#fff;cursor:pointer;">
        取得我的 GPS 座標
      </button>

      <div id="status" style="margin-top:10px;font-family:sans-serif;font-size:14px;color:#333;"></div>

      <!-- 如果自動跳轉失敗，顯示這個手動回填連結 -->
      <a id="backlink" target="_top" rel="noopener"
         style="display:none;margin-top:10px;padding:10px 14px;border-radius:10px;background:#0b5;color:#fff;text-decoration:none;">
         ✅ 點我完成回填
      </a>

      <div style="margin-top:8px;font-family:sans-serif;font-size:12px;color:#666;">
        若卡住：請點上方綠色按鈕。首次需授權；需 HTTPS。
      </div>
    </div>

    <script>
      function buildUrl(lat, lon, acc) {
        // 使用 document.referrer 比較容易拿到 parent 的 URL
        const base = document.referrer || window.location.href;
        try {
            const url = new URL(base);
            url.searchParams.set("lat", lat);
            url.searchParams.set("lon", lon);
            url.searchParams.set("acc", acc);
            url.searchParams.delete("geo_err");
            return url.toString();
        } catch(e) {
            return base + "?lat=" + lat + "&lon=" + lon + "&acc=" + acc;
        }
      }

      function setBacklink(u) {
        const a = document.getElementById("backlink");
        a.href = u;
        a.style.display = "inline-block";
      }

      function fail(msg) {
        const base = document.referrer || window.location.href;
        let u = base;
        try {
            const url = new URL(base);
            url.searchParams.set("geo_err", msg);
            u = url.toString();
        } catch(e) {}
        setBacklink(u);
        document.getElementById("status").innerText = "定位失敗：" + msg;
      }

      function tryNavigate(u) {
        // 依序嘗試跳轉
        try { window.top.location.href = u; return; } catch(e) {}
        try { window.parent.location.href = u; return; } catch(e) {}
        try { window.location.href = u; } catch(e) {}
      }

      function getLocation() {
        const status = document.getElementById("status");
        if (!navigator.geolocation) {
          fail("Geolocation not supported");
          return;
        }
        status.innerText = "定位中…請允許定位權限";
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            const lat = pos.coords.latitude;
            const lon = pos.coords.longitude;
            const acc = pos.coords.accuracy;

            const u = buildUrl(lat, lon, acc);
            status.innerText = "定位成功！若未自動回填，請點下方按鈕。";
            setBacklink(u);

            // 立刻嘗試自動回填
            tryNavigate(u);
          },
          (err) => {
            const msg = (err && err.message) ? err.message : "unknown error";
            fail(msg);
          },
          { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
        );
      }
    </script>
    """
    components.html(html, height=220)
    return None


# ---------- 高德 JS 地圖（嵌入 Streamlit） ----------
def render_amap(spots, center, height=560):
    markers = []
    for s in spots:
        try:
            markers.append(
                {"name": str(s.get("name", "")), "lat": float(s.get("lat")), "lon": float(s.get("lon")), "source": str(s.get("source", ""))}
            )
        except Exception:
            pass

    c_lat, c_lon = float(center[0]), float(center[1])
    markers_json = json.dumps(markers, ensure_ascii=False)

    # 安全密鑰要先於 loader.js 設定，否則可能 INVALID_USER_SCODE/403
    html = f"""
    <div id="amap_container" style="width: 100%; height: {height}px;"></div>
    <div id="map_status" style="margin-top:8px;font-size:12px;color:#666;font-family:sans-serif;"></div>

    <script>
      window._AMapSecurityConfig = {{securityJsCode: "{AMAP_SECURITY_JS_CODE}"}};
    </script>
    <script src="https://webapi.amap.com/loader.js"></script>

    <script>
      const markers = {markers_json};
      const status = document.getElementById("map_status");

      function writePick(lat, lon) {{
        // 這邊也用 tryNavigate 的概念比較保險，但為了簡潔先用 window.top
        try {{
            const url = new URL(window.top.location.href);
            url.searchParams.set("pick_lat", lat);
            url.searchParams.set("pick_lon", lon);
            window.top.location.href = url.toString();
        }} catch(e) {{
            // 若被阻擋，就只能提示手動複製了（通常同源不會擋）
            status.innerText = "無法自動回填，請手動複製";
        }}
      }}

      function boot() {{
        if (typeof AMapLoader === "undefined") {{
          status.innerText = "AMapLoader 載入失敗";
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

          const centerMarker = new AMap.Marker({{
            position: [{c_lon}, {c_lat}],
            title: "中點"
          }});
          map.add(centerMarker);

          const ms = [];
          markers.forEach((m, idx) => {{
            const mk = new AMap.Marker({{
              position: [m.lon, m.lat],
              title: m.name || ("人" + (idx+1))
            }});
            mk.on("click", () => {{
              writePick(m.lat, m.lon);
            }});
            ms.push(mk);
          }});
          map.add(ms);

          map.on("click", (e) => {{
            const lat = e.lnglat.getLat();
            const lon = e.lnglat.getLng();
            status.innerText = `點擊座標：${{lat.toFixed(6)}}, ${{lon.toFixed(6)}}（已回填）`;
            writePick(lat, lon);
          }});

          const all = ms.concat([centerMarker]);
          if (all.length) map.setFitView(all);
          status.innerText = "地圖載入成功：點地圖可回填座標";
        }}).catch((e) => {{
          status.innerText = "地圖載入失敗：" + (e && e.message ? e.message : e);
        }});
      }}

      setTimeout(boot, 80);
    </script>
    """
    components.html(html, height=height + 40)


# =================== App UI ===================
st.set_page_config(page_title="聚会中点 + 餐厅推荐（高德地图）", layout="wide")
st.title("聚会中点 + 餐厅推荐（地圖用高德）")

if "spots" not in st.session_state:
    st.session_state.spots = []

left, right = st.columns([1.15, 1.85], gap="large")

with left:
    loc = gps_block()
    cbtn1, cbtn2 = st.columns(2)
    if cbtn1.button("清除GPS结果", use_container_width=True):
        qp_del("lat", "lon", "acc", "geo_err")
        st.rerun()
    if cbtn2.button("清除地图点选", use_container_width=True):
        qp_del("pick_lat", "pick_lon")
        st.rerun()

    st.divider()
    st.subheader("➕ 添加位置")
    name = st.text_input("名字（可选）", value="", placeholder="例如：阿明 / 小美")

    mode = st.radio("添加方式", ["用GPS(刚获取)", "手动输入", "批量粘贴"], horizontal=True)

    if mode == "用GPS(刚获取)":
        if loc:
            glat, glon, gacc = loc
            if st.button("加入这笔(GPS)", type="primary", use_container_width=True):
                st.session_state.spots.append(
                    {"name": name.strip() or f"人{len(st.session_state.spots)+1}", "lat": glat, "lon": glon, "source": "gps"}
                )
                qp_del("lat", "lon", "acc", "geo_err")
                st.rerun()
        else:
            st.info("先按上面『取得我的 GPS 座標』。")

    elif mode == "手动输入":
        lat_in = st.number_input("纬度 lat", value=39.90, format="%.6f")
        lon_in = st.number_input("经度 lon", value=116.40, format="%.6f")
        if st.button("加入这笔(手动)", type="primary", use_container_width=True):
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
    else:
        st.caption("到右側高德地圖點一下，就會回填座標到這裡。")

    st.divider()
    c3, c4 = st.columns(2)
    if c3.button("删除最后一笔", use_container_width=True) and st.session_state.spots:
        st.session_state.spots.pop()
        st.rerun()
    if c4.button("清空全部", type="primary", use_container_width=True):
        st.session_state.spots = []
        qp_del("pick_lat", "pick_lon", "lat", "lon", "acc", "geo_err")
        st.rerun()

with right:
    st.subheader("📌 位置清单 / 中点 / 地图")
    if not st.session_state.spots:
        st.info("先新增至少 1 個位置；右邊會用高德地圖顯示，並可點圖取座標。")
    else:
        df = pd.DataFrame(st.session_state.spots)
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
        render_amap(st.session_state.spots, (c_lat, c_lon), height=560)

        st.divider()
        st.subheader("🍜 附近餐厅推荐（以中点为中心）")
        keywords = st.text_input("关键字", value="餐厅|火锅|烧烤|咖啡")
        radius = st.slider("半径（米）", 500, 5000, 3000, 100)
        topn = st.slider("显示数量", 5, 20, 10, 1)

        if st.button("查询餐厅", type="primary"):
            with st.spinner("查询中…"):
                rest = amap_nearby_restaurants(c_lat, c_lon, radius_m=radius, keywords=keywords, offset=20)
            if rest.empty:
                st.warning("查不到结果：可能是 Key/额度/地点较偏或关键字太窄。")
            else:
                st.dataframe(rest.head(topn), use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("💾 导出")
        csv = show_df[["name", "lat", "lon", "source"]].to_csv(index=False, encoding="utf-8-sig")
        st.download_button("下载CSV", csv, file_name="meeting_spots.csv", mime="text/csv", use_container_width=True)

st.caption("GPS 需要 HTTPS + 使用者授權，且可能被瀏覽器/政策限制；若失敗請看上方錯誤提示並到瀏覽器網站設定允許定位。")
