import streamlit as st
import pandas as pd
import numpy as np
from math import radians, degrees, sin, cos, atan2, sqrt

@st.cache_data
def calc_center(locs):
    if not locs: return [39.90, 116.40]
    x = y = z = 0
    for lat, lon in locs:
        rlat, rlon = radians(float(lat)), radians(float(lon))
        x += cos(rlat) * cos(rlon)
        y += cos(rlat) * sin(rlon)
        z += sin(rlat)
    n = len(locs)
    x, y, z = x/n, y/n, z/n
    lon = degrees(atan2(y, x))
    hyp = sqrt(x*x + y*y)
    lat = degrees(atan2(z, hyp))
    return [round(lat, 6), round(lon, 6)]

st.set_page_config(layout="wide", page_title="Meeting Spot")
st.title("🎯 Meeting Spot Finder")

if "spots" not in st.session_state:
    st.session_state.spots = []

# Left: Input
col1, col2 = st.columns([1, 2])

with col1:
    st.header("Add Location")
    
    lat = st.number_input("Latitude", 22.0, 45.0, 39.90, 0.0001)
    lon = st.number_input("Longitude", 100.0, 130.0, 116.40, 0.0001)
    
    if st.button("Add Spot", use_container_width=True):
        st.session_state.spots.append([lat, lon])
        st.success("Added!")
        st.rerun()
    
    # Quick cities (English)
    st.subheader("Quick Cities")
    if st.button("Beijing"):
        st.session_state.spots.append([39.90, 116.40]); st.rerun()
    if st.button("Shanghai"):
        st.session_state.spots.append([31.23, 121.47]); st.rerun()
    if st.button("Tainan"):
        st.session_state.spots.append([22.99, 120.20]); st.rerun()

# Right: Results  
with col2:
    if st.session_state.spots:
        df = pd.DataFrame(st.session_state.spots, columns=["Lat", "Lon"])
        
        st.subheader("All Spots")
        st.dataframe(df.round(5))
        
        # Calculate center
        center = calc_center(st.session_state.spots)
        col1m, col2m, col3m = st.columns(3)
        col1m.metric("Center Lat", center[0])
        col2m.metric("Center Lon", center[1])
        col3m.metric("Count", len(df))
        
        # Native map (bulletproof!)
        st.subheader("Interactive Map")
        map_df = pd.DataFrame(st.session_state.spots + [center], columns=['lat', 'lon'])
        st.map(map_df, zoom=10, use_container_width=True)
        
        # Export
        csv = df.round(6).to_csv(index=False)
        st.download_button("Export CSV", csv, "spots.csv", use_container_width=True)
        
        st.info(f"**Recommended meeting spot:** {center[0]}, {center[1]}\nCopy to Google Maps/Baidu!")
        
        if st.button("Clear All", type="primary"):
            st.session_state.spots = []
            st.rerun()
    else:
        st.info("Add your first spot!")

st.markdown("---")
st.caption("Share this link with friends. Refresh to sync. By BeIGoU")
