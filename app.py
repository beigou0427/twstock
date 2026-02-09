import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
from math import radians, degrees, sin, cos, atan2, sqrt

AMAP_KEY = "a9075050dd895616798e9d039d89bdde"

# ---------- Query params（用于接收HTML5定位结果） ----------
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

def qp_clear(keys):
    try:
        for k in keys:
            if k in st.query_params:
                del st.query_params[k]
    except Exception:
        # 老版只能整包重设，保留其它参数的需求这里不做
        pass

# ---------- 地理中点（球面平均） ----------
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

# ---------- 高德周边餐厅 ----------
@st.cache_data(ttl=120)
def amap_nearby_restaurants(lat, lon, radius_m=3000, keywords="餐厅|火锅|烧烤|咖啡", offset=20):
    # 参数：location/key/keywords/types/radius/offset/page/extensions [web:145][web:156]
    url = "https://restapi.amap.com/v3/place/around"
    params = {
        "key": AMAP_KEY,
        "location": f"{lon},{lat}",
        "keywords": keywords,
        "types": "050000",          # 餐饮
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

# ---------- HTML5 手机定位（方案A） ----------
def geolocate_block():
    st.subheader("📍 手机一键定位（浏览器原生）")
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

# ---------- App ----------
st.set_page_config(page_title="聚会中点 + 餐厅推荐", layout="wide")
st.title("聚会中点 + 餐厅推荐（无房间版）")

if "spots" not in st.session_state:
    # spots: list of dict {name, lat, lon, source}
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
                # 加完可清理query params，避免下次误用
                qp_clear(["lat", "lon", "acc"])
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

    else:  # 批量粘贴
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
    st.subheader("🧹 管理")
    if st.button("清空全部", type="primary", use_container_width=True):
        st.session_state.spots = []
        st.rerun()

with right:
    st.subheader("📌 当前位置清单")
    if not st.session_state.spots:
        st.info("先添加至少 1 个位置。多人聚会时，最简单做法是：你开这个网页，朋友把坐标发你，你用「批量粘贴」导入。")
    else:
        df = pd.DataFrame(st.session_state.spots)
        # 防 pyarrow 类型问题：全部转字符串显示
        show_df = df.copy()
        for c in show_df.columns:
            show_df[c] = show_df[c].astype(str).replace("nan", "")
        st.dataframe(show_df[["name", "lat", "lon", "source"]], use_container_width=True, hide_index=True)

        # 计算中点
        locs = [(r["lat"], r["lon"]) for _, r in df.iterrows()]
        c_lat, c_lon = calc_center_spherical(locs)

        c1, c2, c3 = st.columns(3)
        c1.metric("人数", len(locs))
        c2.metric("推荐纬度", f"{c_lat}")
        c3.metric("推荐经度", f"{c_lon}")

        # 地图：所有点 + 中点
        map_df = pd.DataFrame([{"lat": float(a), "lon": float(b)} for (a, b) in locs] + [{"lat": c_lat, "lon": c_lon}])
        st.subheader("🗺️ 地图")
        st.map(map_df.rename(columns={"lat": "lat", "lon": "lon"}), zoom=11, use_container_width=True)

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
                rest = rest.head(topn).copy()
                st.dataframe(rest, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("💾 导出")
        csv = show_df[["name", "lat", "lon", "source"]].to_csv(index=False, encoding="utf-8-sig")
        st.download_button("下载CSV", csv, file_name="meeting_spots.csv", mime="text/csv", use_container_width=True)
