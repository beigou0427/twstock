import time
import random
import string
import threading
from math import radians, degrees, sin, cos, atan2, sqrt

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests


# ========= 你的高德Key（你要寫死就放這） =========
AMAP_KEY = "a9075050dd895616798e9d039d89bdde"


# ========= Query params（兼容新舊Streamlit） =========
def qp_get(key: str, default=None):
    # 新版：st.query_params
    try:
        qp = st.query_params
        if key in qp:
            v = qp[key]
            if isinstance(v, list):
                return v[0] if v else default
            return v
        return default
    except Exception:
        # 舊版：experimental
        qp = st.experimental_get_query_params()
        if key in qp and qp[key]:
            return qp[key][0]
        return default


def qp_set(**kwargs):
    try:
        # 新版：dict-like assign
        for k, v in kwargs.items():
            st.query_params[k] = str(v)
    except Exception:
        st.experimental_set_query_params(**{k: str(v) for k, v in kwargs.items()})


# ========= 全站共享房間資料（同一台server所有使用者共享） =========
@st.cache_resource
def get_store():
    # st.cache_resource 回傳的物件可在多 session 共享，且你對它的 mutation 會直接改到快取裡 [web:137][web:136]
    return {"lock": threading.Lock(), "rooms": {}}


def rand_room(n=6):
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(n))


def now_ts():
    return int(time.time())


# ========= 地理中點（球面平均） =========
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


def calc_center_median(locs):
    if not locs:
        return 39.90, 116.40
    lats, lons = [], []
    for lat, lon in locs:
        try:
            lats.append(float(lat))
            lons.append(float(lon))
        except Exception:
            pass
    if not lats:
        return 39.90, 116.40
    return round(float(pd.Series(lats).median()), 6), round(float(pd.Series(lons).median()), 6)


# ========= 高德餐廳（周邊POI） =========
@st.cache_data(ttl=120)
def amap_around_poi(lat, lon, radius_m=3000, keywords="餐厅", types="050000", page=1, offset=20):
    # 高德周邊搜尋常用參數：location/key/keywords/types/radius/offset/page [web:145]
    url = "https://restapi.amap.com/v3/place/around"
    params = {
        "key": AMAP_KEY,
        "location": f"{lon},{lat}",
        "keywords": keywords,
        "types": types,
        "radius": int(radius_m),
        "page": int(page),
        "offset": int(offset),
        "extensions": "all",
    }
    r = requests.get(url, params=params, timeout=12)
    data = r.json()
    if data.get("status") != "1":
        return pd.DataFrame()
    pois = data.get("pois") or []
    rows = []
    for p in pois:
        biz = p.get("biz_ext") or {}
        loc = (p.get("location") or "").split(",")
        plon = loc[0] if len(loc) == 2 else ""
        plat = loc[1] if len(loc) == 2 else ""
        # distance 可能是字串
        try:
            dist_km = float(p.get("distance", "0")) / 1000.0
            dist_str = f"{dist_km:.2f} km"
        except Exception:
            dist_str = ""
        rows.append(
            {
                "name": str(p.get("name", "")),
                "address": str(p.get("address", "")),
                "distance": dist_str,
                "rating": str(biz.get("rating", "")),
                "cost": str(biz.get("cost", "")),
                "tel": str(p.get("tel", "")),
                "poi_lat": str(plat),
                "poi_lon": str(plon),
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        for c in df.columns:
            df[c] = df[c].astype(str).replace("nan", "")
    return df


# ========= HTML5 定位（方案A） =========
def geolocate_block():
    st.subheader("📍 手機一鍵定位")
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
        style="padding:12px 18px;font-size:16px;border:none;border-radius:8px;background:#111;color:#fff;cursor:pointer;">
        Get my GPS location
      </button>
      <div id="status" style="margin-top:10px;font-family:sans-serif;font-size:14px;color:#333;"></div>
      <div style="margin-top:6px;font-family:sans-serif;font-size:12px;color:#666;">
        iPhone請用Safari/Chrome；若被拒絕，請到瀏覽器網站設定允許定位後再按一次。
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
    components.html(html, height=180)
    return None


# ========= App UI =========
st.set_page_config(page_title="聚會中點 + 餐廳推薦", layout="wide")
st.title("聚會中點 + 餐廳推薦（手機一鍵定位版）")

# Session身分（用來更新/刪除自己）
if "user_id" not in st.session_state:
    st.session_state.user_id = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(10))
if "nickname" not in st.session_state:
    st.session_state.nickname = f"user_{st.session_state.user_id[-4:]}"


# 房間：用URL ?room=XXXXXX
room = (qp_get("room") or "").strip().upper()
if not room:
    room = rand_room()
    qp_set(room=room)

store = get_store()
with store["lock"]:
    store["rooms"].setdefault(room, {"spots": []})

room_url_hint = f"?room={room}"

st.sidebar.header("房間")
st.sidebar.code(room, language="text")
st.sidebar.caption("把房間碼/連結分享給朋友一起加位置。")

new_room = st.sidebar.text_input("加入/切換房間（輸入房間碼）", value=room, max_chars=12)
if new_room and new_room.strip().upper() != room:
    qp_set(room=new_room.strip().upper())
    st.rerun()

# 個人設定
st.sidebar.header("我")
st.session_state.nickname = st.sidebar.text_input("暱稱", value=st.session_state.nickname, max_chars=20)

# 讀房間spots
with store["lock"]:
    spots = list(store["rooms"][room]["spots"])

# 將 spots 轉 DataFrame
def spots_df(spots_list):
    df = pd.DataFrame(spots_list)
    if df.empty:
        return df
    # 避免 pyarrow 型別混雜
    for c in df.columns:
        df[c] = df[c].astype(str).replace("nan", "")
    return df

# 主區：定位/新增
left, right = st.columns([1.1, 1.9], gap="large")

with left:
    loc = geolocate_block()
    st.divider()

    st.subheader("新增位置")
    add_mode = st.radio("方式", ["用GPS(剛剛獲取)", "手動輸入"], horizontal=True)

    if add_mode == "用GPS(剛剛獲取)":
        if loc:
            glat, glon, gacc = loc
            st.write(f"GPS: {glat:.6f}, {glon:.6f}" + (f"（±{int(gacc)}m）" if gacc else ""))
            if st.button("加入我的位置", type="primary", use_container_width=True):
                with store["lock"]:
                    store["rooms"][room]["spots"].append(
                        {
                            "user_id": st.session_state.user_id,
                            "name": st.session_state.nickname,
                            "lat": glat,
                            "lon": glon,
                            "source": "gps",
                            "ts": now_ts(),
                        }
                    )
                st.rerun()
        else:
            st.info("先按上面的 Get my GPS location。")
    else:
        lat_in = st.number_input("緯度 lat", value=39.90, format="%.6f")
        lon_in = st.number_input("經度 lon", value=116.40, format="%.6f")
        if st.button("加入手動位置", type="primary", use_container_width=True):
            with store["lock"]:
                store["rooms"][room]["spots"].append(
                    {
                        "user_id": st.session_state.user_id,
                        "name": st.session_state.nickname,
                        "lat": float(lat_in),
                        "lon": float(lon_in),
                        "source": "manual",
                        "ts": now_ts(),
                    }
                )
            st.rerun()

    st.divider()
    st.subheader("我的位置管理")

    if st.button("更新我最後一筆為目前GPS", use_container_width=True):
        if not loc:
            st.warning("你尚未獲取GPS。")
        else:
            glat, glon, _ = loc
            with store["lock"]:
                room_spots = store["rooms"][room]["spots"]
                # 找到我最後一筆
                idx = None
                for i in range(len(room_spots) - 1, -1, -1):
                    if room_spots[i].get("user_id") == st.session_state.user_id:
                        idx = i
                        break
                if idx is None:
                    room_spots.append(
                        {"user_id": st.session_state.user_id, "name": st.session_state.nickname, "lat": glat, "lon": glon, "source": "gps", "ts": now_ts()}
                    )
                else:
                    room_spots[idx]["name"] = st.session_state.nickname
                    room_spots[idx]["lat"] = glat
                    room_spots[idx]["lon"] = glon
                    room_spots[idx]["source"] = "gps"
                    room_spots[idx]["ts"] = now_ts()
            st.rerun()

    if st.button("刪除我在這房間的所有位置", use_container_width=True):
        with store["lock"]:
            room_spots = store["rooms"][room]["spots"]
            store["rooms"][room]["spots"] = [s for s in room_spots if s.get("user_id") != st.session_state.user_id]
        st.rerun()

    if st.sidebar.button("清空整個房間（慎用）"):
        with store["lock"]:
            store["rooms"][room]["spots"] = []
        st.rerun()

with right:
    st.subheader(f"房間 {room} 的所有人位置")
    df = spots_df(spots)

    if df.empty:
        st.info(f"把這個房間碼分享給朋友：{room}（或在網址後加 {room_url_hint}）")
    else:
        # 轉成數值 list 用於計算
        locs = []
        for _, r in df.iterrows():
            try:
                locs.append((float(r["lat"]), float(r["lon"])))
            except Exception:
                pass

        c_lat_s, c_lon_s = calc_center_spherical(locs)
        c_lat_m, c_lon_m = calc_center_median(locs)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("人數", len(locs))
        m2.metric("球面中點lat", f"{c_lat_s}")
        m3.metric("球面中點lon", f"{c_lon_s}")
        m4.metric("Median中點", f"{c_lat_m}, {c_lon_m}")

        # 表格
        show_cols = [c for c in ["name", "lat", "lon", "source", "ts"] if c in df.columns]
        st.dataframe(df[show_cols], use_container_width=True)

        # 地圖（原生 st.map）
        map_points = pd.DataFrame([{"lat": float(a), "lon": float(b)} for (a, b) in locs] + [{"lat": c_lat_s, "lon": c_lon_s}])
        st.map(map_points.rename(columns={"lon": "lon", "lat": "lat"}), zoom=11, use_container_width=True)

        st.divider()
        st.subheader("餐廳推薦（以球面中點為中心）")

        kw = st.text_input("關鍵字", value="餐厅|火锅|烧烤|咖啡", help="用 | 分隔會更好找")
        radius = st.slider("搜尋半徑（公尺）", 500, 5000, 3000, 100)
        topn = st.slider("顯示筆數", 5, 20, 10, 1)

        if st.button("搜尋附近餐廳", type="primary"):
            with st.spinner("查詢中…"):
                rest = amap_around_poi(c_lat_s, c_lon_s, radius_m=radius, keywords=kw, types="050000", page=1, offset=20)

            if rest.empty:
                st.warning("查不到結果：可能是Key/額度/地點太偏，或關鍵字太窄。")
            else:
                rest = rest.head(topn).copy()
                # 給一個「在高德打開」的搜尋連結（用中心點 + 關鍵字）
                amap_search_url = (
                    "https://uri.amap.com/search?"
                    + f"keyword={requests.utils.quote(kw)}"
                    + f"&center={c_lon_s},{c_lat_s}"
                    + f"&radius={int(radius)}"
                )
                st.write("在高德打開（搜尋）:", amap_search_url)

                # 顯示表格
                rest_show = rest[["name", "distance", "rating", "cost", "address", "tel"]].copy()
                for c in rest_show.columns:
                    rest_show[c] = rest_show[c].astype(str).replace("nan", "")
                st.dataframe(rest_show, use_container_width=True)

        st.divider()
        st.subheader("匯出")
        csv = df[show_cols].to_csv(index=False, encoding="utf-8-sig")
        st.download_button("下載位置CSV", data=csv, file_name=f"meeting_{room}.csv", mime="text/csv", use_container_width=True)
