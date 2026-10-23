"""
🌌 KENYA LIVE DATA ENGINE - app.py 

Interactive Streamlit command center for the data produced by pipeline.py:
  - nairobi_climate_anomalies.csv  (multi-city climate, air, sentiment, satellite)
  - kenya_headlines_log.csv        (scored news headlines)
"""

import json
import os

import folium
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from streamlit_folium import st_folium

# 1. Page config (must be the first Streamlit command)
st.set_page_config(
    page_title="🌌 Kenya Socio-Environmental Data Fabric",
    page_icon="🇰🇪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. Optional Earth Engine integration (the app still works without it)
try:
    import ee

    EE_PACKAGE_OK = True
except Exception:  # noqa: BLE001
    EE_PACKAGE_OK = False

try:
    from Satellite_engine import get_kenya_agri_grid

    SAT_ENGINE_OK = True
except Exception:  # noqa: BLE001
    SAT_ENGINE_OK = False

try:
    from Satellite_engine import TARGET_PROJECT_ID
except Exception:  # noqa: BLE001
    TARGET_PROJECT_ID = os.getenv("EE_PROJECT", "kenya-live-data")

CSV_NAME = "nairobi_climate_anomalies.csv"
HEADLINES_CSV = "kenya_headlines_log.csv"

CITY_COORDS = {
    "Nairobi": (-1.2921, 36.8219),
    "Mombasa": (-4.0435, 39.6682),
    "Kisumu": (-0.0917, 34.7680),
    "Nakuru": (-0.3031, 36.0800),
    "Eldoret": (0.5143, 35.2698),
    "Garissa": (-0.4532, 39.6461),
    "Lodwar": (3.1191, 35.5973),
}

NUMERIC_COLS = [
    "live_temperature_c", "historical_baseline_c", "climate_deviation",
    "economic_sentiment", "political_sentiment", "kenya_public_sentiment_score",
    "civic_tension_index", "anomaly_z_score", "baseline_std_c", "temp_mean_today_c",
    "temp_max_c", "temp_min_c", "feels_like_c", "humidity_pct", "precipitation_mm",
    "rain_total_today_mm", "wind_speed_kmh", "cloud_cover_pct", "uv_index_max",
    "pm2_5", "pm10", "us_aqi", "climate_agri_sentiment", "satellite_primary_value",
    "data_quality_pct",
]

# ==============================================================================
# 🌌 STYLING (pure CSS starfield: reliable, light, respects reduced-motion)
# ==============================================================================
st.markdown(
    """
    <style>
    .stApp {
        background-color: #060613;
        background-image:
            radial-gradient(1.5px 1.5px at 20px 30px, #ffffff, transparent),
            radial-gradient(1px 1px at 90px 120px, #aae0ff, transparent),
            radial-gradient(1.5px 1.5px at 160px 70px, #f0b0ff, transparent),
            radial-gradient(1px 1px at 230px 180px, #7cd2ff, transparent),
            radial-gradient(ellipse at 50% 0%, rgba(80, 40, 160, 0.35), transparent 60%);
        background-size: 250px 220px, 250px 220px, 250px 220px, 250px 220px, 100% 100%;
        animation: drift 160s linear infinite;
    }
    @keyframes drift {
        from { background-position: 0 0, 0 0, 0 0, 0 0, 0 0; }
        to   { background-position: 250px 220px, -250px 220px, 250px -220px, -250px -220px, 0 0; }
    }
    @media (prefers-reduced-motion: reduce) { .stApp { animation: none; } }

    .block-container {
        background-color: rgba(15, 15, 35, 0.80) !important;
        border-radius: 20px;
        padding: 2.5rem !important;
        border: 1px solid rgba(255,255,255,0.08);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        backdrop-filter: blur(8px);
        margin-top: 20px;
    }
    h1, h2, h3, h4, p, span, label, li { color: #f0f2ff !important; }
    div[data-testid="stMetricValue"] { color: #50e4ff !important; font-family: monospace; }
    div[data-testid="stMetricLabel"] p { color: #aab4d6 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ==============================================================================
# 🔧 HELPERS
# ==============================================================================
def fmt(value, suffix="", digits=1, na="n/a"):
    """Format a number safely; returns `na` for missing values."""
    if value is None or (isinstance(value, float) and np.isnan(value)) or pd.isna(value):
        return na
    if isinstance(value, (int, float, np.integer, np.floating)):
        return f"{value:.{digits}f}{suffix}"
    return f"{value}{suffix}"


def getv(row, key):
    """Get a value from a row, returning None when missing/NaN."""
    try:
        v = row.get(key)
    except AttributeError:
        return None
    return None if v is None or (not isinstance(v, str) and pd.isna(v)) else v


def tension_color(v):
    if v is None or pd.isna(v):
        return "#888888"
    return "#2ecc71" if v < 3 else "#f1c40f" if v < 5 else "#e67e22" if v < 7 else "#e74c3c"


def aqi_label(aqi):
    if aqi is None or pd.isna(aqi):
        return None
    for limit, name in [(50, "Good"), (100, "Moderate"), (150, "Unhealthy for sensitive"),
                        (200, "Unhealthy"), (300, "Very unhealthy")]:
        if aqi <= limit:
            return name
    return "Hazardous"


def style_fig(fig, height=420):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    return fig


# ==============================================================================
# 📦 DATA LOADING
# ==============================================================================
def build_demo_data() -> pd.DataFrame:
    """Clearly-labelled sample data, used only if the pipeline has not run yet."""
    rng = np.random.default_rng(7)
    days = pd.date_range(end=pd.Timestamp.now(tz="UTC").floor("D"), periods=14, freq="D")
    rows = []
    for city, (lat, lon) in list(CITY_COORDS.items())[:3]:
        for d in days:
            dev = round(float(rng.normal(0.8, 1.2)), 2)
            sent = round(float(rng.normal(-0.15, 0.12)), 2)
            rows.append({
                "timestamp": d, "city": city, "live_temperature_c": round(24 + dev, 1),
                "historical_baseline_c": 24.0, "climate_deviation": dev,
                "anomaly_detected": "Yes" if abs(dev) > 2 else "No",
                "anomaly_severity": "Warning" if abs(dev) > 2 else "Normal",
                "kenya_public_sentiment_score": sent, "political_sentiment": sent - 0.05,
                "economic_sentiment": sent + 0.05,
                "civic_tension_index": round(min(10, abs(dev) * 1.5 + max(-sent, 0) * 8), 2),
                "overall_social_mood": "Negative (High Tension) 🟥" if sent < -0.1 else "Neutral 🟨",
                "latitude": lat, "longitude": lon, "satellite_grid_status": "OFFLINE",
            })
    return pd.DataFrame(rows)


@st.cache_data(ttl=300, show_spinner="Loading latest pipeline data...")
def load_data():
    if not os.path.exists(CSV_NAME):
        df, is_demo = build_demo_data(), True
    else:
        df, is_demo = pd.read_csv(CSV_NAME), False

    if "city" not in df.columns:
        df["city"] = "Nairobi"
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    df = df.dropna(subset=["timestamp"])
    df["local_time"] = df["timestamp"].dt.tz_convert("Africa/Nairobi")
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values("timestamp").reset_index(drop=True), is_demo


@st.cache_data(ttl=300)
def load_headlines():
    if not os.path.exists(HEADLINES_CSV):
        return None
    h = pd.read_csv(HEADLINES_CSV)
    h["timestamp"] = pd.to_datetime(h["timestamp"], errors="coerce", utc=True)
    h["polarity"] = pd.to_numeric(h.get("polarity"), errors="coerce")
    return h.sort_values("timestamp", ascending=False)


# ==============================================================================
# 🛰️ EARTH ENGINE (cached so it initialises once, not on every rerun)
# ==============================================================================
@st.cache_resource(show_spinner=False)
def init_earth_engine():
    if not (EE_PACKAGE_OK and SAT_ENGINE_OK):
        return False, "earthengine-api or Satellite_engine.py is not available"
    try:
        key = None
        try:
            key = st.secrets.get("EE_SERVICE_ACCOUNT_JSON")
        except Exception:  # noqa: BLE001
            pass
        key = key or os.getenv("EE_SERVICE_ACCOUNT_JSON")
        if key:
            if not isinstance(key, str):
                key = json.dumps(dict(key))
            email = json.loads(key)["client_email"]
            ee.Initialize(ee.ServiceAccountCredentials(email, key_data=key),
                          project=TARGET_PROJECT_ID)
        else:
            try:
                ee.Initialize(project=TARGET_PROJECT_ID)
            except Exception:  # noqa: BLE001
                ee.Initialize()
        return True, "ok"
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def _build_image(lat, lon, start, end, buffer_m):
    roi = ee.Geometry.Point([lon, lat]).buffer(buffer_m)
    layer = get_kenya_agri_grid(start_date=start, end_date=end, roi_geometry=roi)
    is_collection = layer.getInfo().get("type") == "ImageCollection"
    return (layer.mean() if is_collection else ee.Image(layer)), roi


@st.cache_data(ttl=3600, show_spinner=False)
def get_layer_bands(lat, lon, start, end, buffer_m):
    image, _ = _build_image(lat, lon, start, end, buffer_m)
    return image.bandNames().getInfo()


@st.cache_data(ttl=3600, show_spinner=False)
def get_tile_url(lat, lon, start, end, buffer_m, band, vmin, vmax):
    image, _ = _build_image(lat, lon, start, end, buffer_m)
    map_id = image.select(band).getMapId(
        {"min": vmin, "max": vmax, "palette": ["red", "yellow", "green"]}
    )
    return map_id["tile_fetcher"].url_format


# ==============================================================================
# 🎛️ SIDEBAR
# ==============================================================================
df_all, IS_DEMO = load_data()

st.sidebar.markdown("### 🪐 Spatial & Civic Command Core")

cities = sorted(df_all["city"].unique().tolist())
default_idx = cities.index("Nairobi") if "Nairobi" in cities else 0
selected_city = st.sidebar.selectbox("Select Target Urban Center", cities, index=default_idx)

window_label = st.sidebar.selectbox(
    "History window", ["Last 7 days", "Last 30 days", "Last 90 days", "All time"], index=1
)
window_days = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90, "All time": None}[window_label]
if window_days:
    cutoff = df_all["timestamp"].max() - pd.Timedelta(days=window_days)
    df_win = df_all[df_all["timestamp"] >= cutoff]
else:
    df_win = df_all

if st.sidebar.button("🔄 Refresh data"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption(
    f"Dataset: {len(df_all):,} records · {df_all['city'].nunique()} cities  \n"
    f"Latest run: {df_all['local_time'].max():%Y-%m-%d %H:%M} EAT"
)

city_df = df_win[df_win["city"] == selected_city].copy()
city_all = df_all[df_all["city"] == selected_city]
latest = (city_all.iloc[-1] if not city_all.empty else pd.Series(dtype=object))

# Latest record per city (for national views)
latest_per_city = df_all.sort_values("timestamp").groupby("city").tail(1).reset_index(drop=True)

# ==============================================================================
# 🧭 HEADER, STATUS & ALERTS
# ==============================================================================
st.title("🇰🇪 Kenya Live Data Engine: Command Center")
st.write(
    "Cross-referencing real-time climate stress, air quality and satellite signals "
    "with multi-pillar political, economic and agricultural public sentiment."
)

if IS_DEMO:
    st.warning("⚠️ **Demo data.** `nairobi_climate_anomalies.csv` was not found. "
               "Run `python pipeline.py` to load real data.")

age_h = (pd.Timestamp.now(tz="UTC") - df_all["timestamp"].max()).total_seconds() / 3600
if not IS_DEMO and age_h > 36:
    st.error(f"⏱️ Data is {age_h:.0f} hours old. The daily pipeline may have stopped.")

alerts = []
for _, r in latest_per_city.iterrows():
    if r.get("anomaly_severity") in ("Warning", "Critical"):
        alerts.append(f"🌡️ **{r['city']}**: {r['anomaly_severity']} temperature anomaly "
                      f"({fmt(r.get('climate_deviation'), '°C', 1)} vs baseline)")
    if r.get("civic_tension_index") is not None and not pd.isna(r.get("civic_tension_index")) \
            and r["civic_tension_index"] >= 7:
        alerts.append(f"🔥 **{r['city']}**: severe civic tension index "
                      f"({fmt(r['civic_tension_index'], '', 1)})")
    if r.get("us_aqi") is not None and not pd.isna(r.get("us_aqi")) and r["us_aqi"] > 100:
        alerts.append(f"😷 **{r['city']}**: air quality {aqi_label(r['us_aqi'])} "
                      f"(AQI {fmt(r['us_aqi'], '', 0)})")
if alerts:
    with st.expander(f"🚨 Active alerts ({len(alerts)})", expanded=True):
        for a in alerts:
            st.markdown(f"- {a}")

tab_nat, tab_city, tab_news, tab_sat, tab_data = st.tabs(
    ["🇰🇪 National Overview", f"📍 {selected_city} Command Center",
     "📰 Sentiment Feed", "🛰️ Satellite Grid", "📥 Data & Quality"]
)

# ==============================================================================
# 🇰🇪 TAB 1: NATIONAL OVERVIEW
# ==============================================================================
with tab_nat:
    n1, n2, n3, n4 = st.columns(4)
    n1.metric("Cities monitored", f"{latest_per_city['city'].nunique()}")
    anomalies_now = int((latest_per_city["anomaly_detected"] == "Yes").sum())
    n2.metric("Active temperature anomalies", f"{anomalies_now}")
    n3.metric("Avg civic tension (0-10)", fmt(latest_per_city["civic_tension_index"].mean(), "", 2))
    n4.metric("National sentiment (-1 to +1)",
              fmt(latest_per_city["kenya_public_sentiment_score"].mean(), "", 2))

    st.markdown("#### 🗺️ High-Resolution Global Satellite View")
    
    # Initialize map with high-definition Esri World Imagery (Global Forest Watch style)
    kenya_map = folium.Map(
        location=[0.5, 37.9], 
        zoom_start=6, 
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery"
    )
    
    # Add reference boundary and place labels overlay
    folium.TileLayer(
        tiles="https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
        attr="Esri Reference Overlay",
        name="Borders & Labels",
        overlay=True,
        control=True
    ).add_to(kenya_map)

    for _, r in latest_per_city.iterrows():
        lat_c, lon_c = CITY_COORDS.get(r["city"], (None, None))
        if lat_c is None:
            continue
        t = r.get("civic_tension_index")
        folium.CircleMarker(
            location=[lat_c, lon_c],
            radius=12 + (0 if pd.isna(t) else t * 1.5),
            color="#ffffff",
            weight=2,
            fill=True, 
            fill_color=tension_color(t), 
            fill_opacity=0.85,
            tooltip=(f"<b>{r['city']}</b> | Temp: {fmt(r.get('live_temperature_c'), '°C')} | "
                     f"Tension: {fmt(t, '', 1)} | {r.get('anomaly_severity', 'n/a')}"),
        ).add_to(kenya_map)
        
    folium.LayerControl().add_to(kenya_map)
    st_folium(kenya_map, width=None, height=460, returned_objects=[])
    st.caption("Global Observation Mode: High-resolution satellite backdrop displaying real-world terrain and urban nodes.")

    st.markdown("#### 🏙️ City comparison")
    comp = go.Figure(go.Bar(
        x=latest_per_city["city"], y=latest_per_city["civic_tension_index"],
        marker_color=[tension_color(v) for v in latest_per_city["civic_tension_index"]],
        text=latest_per_city["civic_tension_index"].round(1), textposition="outside",
    ))
    comp.update_layout(title="Civic tension index by city (latest run)", yaxis_range=[0, 10])
    st.plotly_chart(style_fig(comp, 360), use_container_width=True)

    show_cols = [c for c in ["city", "live_temperature_c", "climate_deviation", "anomaly_severity",
                             "civic_tension_index", "tension_level", "pm2_5", "us_aqi",
                             "humidity_pct", "rain_total_today_mm", "data_quality_pct"]
                 if c in latest_per_city.columns]
    st.dataframe(latest_per_city[show_cols].round(2), use_container_width=True, hide_index=True)

# ==============================================================================
# 📍 TAB 2: CITY COMMAND CENTER
# ==============================================================================
with tab_city:
    st.subheader(f"{selected_city}: live status")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        f"Live Temp ({selected_city})", fmt(getv(latest, "live_temperature_c"), "°C"),
        delta=(f"{fmt(getv(latest, 'climate_deviation'), '°C')} vs baseline"
               if getv(latest, "climate_deviation") is not None else None),
        delta_color="inverse",
    )
    z = getv(latest, "anomaly_z_score")
    c2.metric(
        "Anomaly status", str(getv(latest, "anomaly_severity") or "n/a"),
        delta=(f"z = {fmt(z, '', 2)} · {getv(latest, 'anomaly_direction')}" if z is not None else None),
        delta_color="off",
    )
    c3.metric(
        "Civic Tension Index (0-10)", fmt(getv(latest, "civic_tension_index"), "", 2),
        delta=getv(latest, "tension_level"), delta_color="inverse",
    )
    c4.metric("Overall Social Mood", str(getv(latest, "overall_social_mood") or "n/a"))

    d1, d2, d3, d4, d5 = st.columns(5)
    d1.metric("Humidity", fmt(getv(latest, "humidity_pct"), "%", 0))
    d2.metric("Rain today", fmt(getv(latest, "rain_total_today_mm"), " mm"))
    d3.metric("Wind", fmt(getv(latest, "wind_speed_kmh"), " km/h", 0))
    d4.metric("PM2.5", fmt(getv(latest, "pm2_5"), " µg/m³"),
              delta=aqi_label(getv(latest, "us_aqi")), delta_color="off")
    d5.metric("UV index (max)", fmt(getv(latest, "uv_index_max")))

    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("Economic sentiment", fmt(getv(latest, "economic_sentiment"), "", 2))
    sc2.metric("Political sentiment", fmt(getv(latest, "political_sentiment"), "", 2))
    sc3.metric("Climate/agri sentiment", fmt(getv(latest, "climate_agri_sentiment"), "", 2))

    st.markdown("---")
    st.subheader(f"📈 Socio-climatic timeline: {selected_city}")

    if len(city_df) > 1:
        ts = city_df["local_time"]
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.10,
            specs=[[{"secondary_y": False}], [{"secondary_y": True}]],
            subplot_titles=("Temperature vs historical baseline (°C)",
                            "Civic tension (0-10) and public sentiment (-1 to +1)"),
        )
        fig.add_trace(go.Scatter(x=ts, y=city_df["live_temperature_c"], name="Live temp",
                                 mode="lines+markers", line=dict(color="#ff7a59")), row=1, col=1)
        if "historical_baseline_c" in city_df:
            fig.add_trace(go.Scatter(x=ts, y=city_df["historical_baseline_c"], name="Baseline",
                                     mode="lines", line=dict(color="#7cd2ff", dash="dash")),
                          row=1, col=1)
        fig.add_trace(go.Scatter(x=ts, y=city_df["civic_tension_index"], name="Civic tension",
                                 mode="lines+markers", line=dict(color="#e74c3c")),
                      row=2, col=1, secondary_y=False)
        if "kenya_public_sentiment_score" in city_df:
            fig.add_trace(go.Scatter(x=ts, y=city_df["kenya_public_sentiment_score"],
                                     name="Public sentiment", mode="lines+markers",
                                     line=dict(color="#50e4ff")),
                          row=2, col=1, secondary_y=True)
        fig.update_yaxes(range=[0, 10], row=2, col=1, secondary_y=False)
        fig.update_yaxes(range=[-1, 1], row=2, col=1, secondary_y=True)
        st.plotly_chart(style_fig(fig, 560), use_container_width=True)

        valid = city_df[["climate_deviation", "civic_tension_index"]].dropna()
        if len(valid) >= 8 and valid["climate_deviation"].std() > 0 \
                and valid["civic_tension_index"].std() > 0:
            corr = valid["climate_deviation"].corr(valid["civic_tension_index"])
            st.caption(f"Heat vs tension correlation over this window: **{corr:+.2f}** "
                       f"({len(valid)} observations). Correlation does not imply causation.")
    else:
        st.info("Not enough history yet. Timelines appear after the pipeline has run on multiple days.")

# ==============================================================================
# 📰 TAB 3: SENTIMENT FEED
# ==============================================================================
with tab_news:
    st.subheader("📰 Scored headlines")
    headlines = load_headlines()
    if headlines is None or headlines.empty:
        st.info("No headline log yet. It is created by the v2 `pipeline.py` on its next run.")
    else:
        pillars = ["All"] + sorted(headlines["pillar"].dropna().unique().tolist())
        pick = st.radio("Pillar", pillars, horizontal=True)
        hv = headlines if pick == "All" else headlines[headlines["pillar"] == pick]

        avg = headlines.groupby("pillar")["polarity"].mean().reset_index()
        bar = go.Figure(go.Bar(
            x=avg["pillar"], y=avg["polarity"],
            marker_color=["#e74c3c" if v < -0.1 else "#2ecc71" if v > 0.1 else "#f1c40f"
                          for v in avg["polarity"]],
            text=avg["polarity"].round(2), textposition="outside",
        ))
        bar.update_layout(title="Average sentiment by pillar (all logged headlines)",
                          yaxis_range=[-1, 1])
        st.plotly_chart(style_fig(bar, 320), use_container_width=True)

        st.markdown("**Most negative headlines**")
        st.dataframe(
            hv.nsmallest(10, "polarity")[["timestamp", "pillar", "headline", "source", "polarity"]],
            use_container_width=True, hide_index=True,
        )
        st.markdown("**Most recent headlines**")
        st.dataframe(
            hv.head(15)[["timestamp", "pillar", "headline", "source", "polarity"]],
            use_container_width=True, hide_index=True,
        )
        st.caption("Sentiment is scored with TextBlob (English). Treat it as a rough signal, "
                   "not a measure of public opinion.")

# ==============================================================================
# 🛰️ TAB 4: SATELLITE GRID
# ==============================================================================
with tab_sat:
    st.subheader(f"🛰️ Orbital satellite grid: {selected_city}")
    lat, lon = CITY_COORDS.get(selected_city, (-1.2921, 36.8219))

    # Values archived by the pipeline
    if "satellite_primary_value" in city_df and city_df["satellite_primary_value"].notna().any():
        band_name = getv(latest, "satellite_primary_band") or "primary band"
        sat_fig = go.Figure(go.Scatter(
            x=city_df["local_time"], y=city_df["satellite_primary_value"],
            mode="lines+markers", line=dict(color="#2ecc71"),
        ))
        sat_fig.update_layout(title=f"Archived satellite value ({band_name}, 25 km zone mean)")
        st.plotly_chart(style_fig(sat_fig, 300), use_container_width=True)
    else:
        st.caption("No archived satellite values yet for this city.")

    live_on = st.toggle("🌌 Show live Earth Engine layer", value=False)
    if live_on:
        ee_ok, ee_msg = init_earth_engine()
        if not ee_ok:
            st.error("Earth Engine is not available in this environment.")
            st.caption(f"Details: {ee_msg}")
        else:
            today = pd.Timestamp.now().normalize()
            s_col, e_col, b_col = st.columns(3)
            start_q = s_col.date_input("Start date", value=(today - pd.Timedelta(days=90)).date())
            end_q = e_col.date_input("End date", value=today.date())
            buffer_km = b_col.slider("Zone radius (km)", 5, 50, 25)
            start_s, end_s, buffer_m = start_q.strftime("%Y-%m-%d"), end_q.strftime("%Y-%m-%d"), buffer_km * 1000
            try:
                with st.spinner(f"Streaming spatial layers for {selected_city}..."):
                    bands = get_layer_bands(lat, lon, start_s, end_s, buffer_m)
                    band = st.selectbox("Band to display", bands) if len(bands) > 1 else bands[0]
                    v1, v2 = st.slider("Display range (min / max)", -1.0, 2.0, (0.0, 0.8), 0.05)
                    tile_url = get_tile_url(lat, lon, start_s, end_s, buffer_m, band, v1, v2)

                m = folium.Map(
                    location=[lat, lon], 
                    zoom_start=10, 
                    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                    attr="Esri World Imagery"
                )
                folium.TileLayer(tiles=tile_url, attr="Google Earth Engine",
                                 name=f"{band} layer", overlay=True, control=True).add_to(m)
                folium.LayerControl().add_to(m)
                st_folium(m, width=None, height=480, returned_objects=[])
                st.success(f"Connected to Earth Engine project '{TARGET_PROJECT_ID}'.")
            except Exception as err:  # noqa: BLE001
                st.error("Could not load the live satellite layer.")
                st.caption(f"Details: {err}")
    else:
        fallback = folium.Map(
            location=[lat, lon], 
            zoom_start=10, 
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri World Imagery"
        )
        folium.Circle(
            radius=25000, location=[lat, lon], color="#50e4ff", fill=True,
            fill_color="#2050aa", fill_opacity=0.35,
            popup=f"Active monitoring perimeter: {selected_city}",
        ).add_to(fallback)
        folium.LayerControl().add_to(fallback)
        st_folium(fallback, width=None, height=420, returned_objects=[])
        st.caption("Switch on the toggle above to render the live Earth Engine layer over Esri satellite imagery.")

# ==============================================================================
# 📥 TAB 5: DATA & QUALITY
# ==============================================================================
with tab_data:
    st.subheader("📥 Data & pipeline health")

    if "data_quality_pct" in latest_per_city and latest_per_city["data_quality_pct"].notna().any():
        q = go.Figure(go.Bar(
            x=latest_per_city["city"], y=latest_per_city["data_quality_pct"],
            marker_color="#50e4ff", text=latest_per_city["data_quality_pct"], textposition="outside",
        ))
        q.update_layout(title="Data quality by city (% of sources that succeeded)",
                        yaxis_range=[0, 110])
        st.plotly_chart(style_fig(q, 300), use_container_width=True)

    st.markdown(f"**{selected_city} records in window:** {len(city_df):,}")
    st.dataframe(city_df.drop(columns=["local_time"], errors="ignore").tail(200),
                 use_container_width=True, hide_index=True)

    d_a, d_b = st.columns(2)
    d_a.download_button(
        f"⬇️ Download {selected_city} data (CSV)",
        city_df.drop(columns=["local_time"], errors="ignore").to_csv(index=False).encode("utf-8"),
        file_name=f"{selected_city.lower()}_climate_anomalies.csv", mime="text/csv",
    )
    d_b.download_button(
        "⬇️ Download all cities (CSV)",
        df_all.drop(columns=["local_time"], errors="ignore").to_csv(index=False).encode("utf-8"),
        file_name="kenya_live_data_all_cities.csv", mime="text/csv",
    )