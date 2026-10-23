import streamlit as st
import pandas as pd
import numpy as np
import os
import folium
from streamlit_folium import st_folium

# 🛰️ Import your verified engine architecture 
import ee
from Satellite_engine import get_kenya_agri_grid, TARGET_PROJECT_ID

# Set wide page properties with dark theme baseline
st.set_page_config(
    page_title="🌌 Cosmic Data Fabric Engine",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 🌌 1. INJECTED INTERACTIVE MOVING GALAXY BACKGROUND (HTML5 Canvas)
# ==============================================================================
galaxy_background_js = """
<canvas id="cosmicCanvas" style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: -2; background: #060613;"></canvas>
<script>
    const canvas = document.getElementById('cosmicCanvas');
    const ctx = canvas.getContext('2d');
    let stars = [];
    
    function resizeCanvas() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    class CosmicStar {
        constructor() {
            this.reset();
            this.x = Math.random() * canvas.width;
            this.y = Math.random() * canvas.height;
        }
        reset() {
            this.angle = Math.random() * Math.PI * 2;
            this.distance = Math.random() * (Math.max(canvas.width, canvas.height) / 2);
            this.speed = (Math.random() * 0.4 + 0.1) * (1 - this.distance / (canvas.width / 2));
            this.size = Math.random() * 1.8 + 0.2;
            this.color = ['#ffffff', '#aae0ff', '#f0b0ff', '#7cd2ff'][Math.floor(Math.random() * 4)];
        }
        update() {
            // Swirling orbital trajectory creating structural galaxy spiral arm motion
            this.angle += 0.0012;
            this.distance -= 0.05; // Gentle inward pull
            if (this.distance <= 10) this.reset();
            
            this.x = canvas.width / 2 + Math.cos(this.angle) * this.distance;
            this.y = canvas.height / 2 + Math.sin(this.angle) * this.distance;
        }
        draw() {
            ctx.fillStyle = this.color;
            ctx.shadowBlur = this.size * 2;
            ctx.shadowColor = this.color;
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    for (let i = 0; i < 200; i++) stars.push(new CosmicStar());

    function renderLoop() {
        ctx.fillStyle = 'rgba(6, 6, 19, 0.15)'; // Long visual trails
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.shadowBlur = 0; // Clear shadow rules for optimization
        stars.forEach(star => {
            star.update();
            star.draw();
        });
        requestAnimationFrame(renderLoop);
    }
    renderLoop();
</script>
"""
# 💡 FIXED: Changed 'scroller=False' to 'scrolling=False' to stop the TypeError crash
st.components.v1.html(galaxy_background_js, height=0, scrolling=False)

# Custom Global CSS to make container backgrounds glassmorphic over the moving galaxy
st.markdown("""
    <style>
    .block-container {
        background-color: rgba(15, 15, 35, 0.75) !important;
        border-radius: 20px;
        padding: 2.5rem !important;
        border: 1px solid rgba(255,255,255,0.08);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        margin-top: 20px;
    }
    h1, h2, h3, p, span { color: #f0f2ff !important; }
    div[data-testid="stMetricValue"] { color: #50e4ff !important; font-family: monospace; }
    </style>
""", unsafe_allow_html=True)


# ==============================================================================
# 🛰️ 2. BACKEND CONNECTIONS & DATA INGESTION
# ==============================================================================
st.title("🌌 Kenya Multi-Sector Cosmic Data Fabric")
st.write("Tracking telemetry anomalies, public sentiment metrics, and spatial pixel matrix gaps.")
st.markdown("---")

# Load existing archived dataset logs safely
csv_name = "nairobi_climate_anomalies.csv"
if os.path.exists(csv_name):
    df_metrics = pd.read_csv(csv_name)
else:
    # Build fallback dataframe matching your structural pipeline payload if file is not generated yet
    fallback_data = {
        "timestamp": pd.date_range(end=pd.Timestamp.now(), periods=10, freq='D').strftime("%Y-%m-%d %H:%M:%S"),
        "city": ["Nairobi"] * 10,
        "live_temperature_c": [22.1, 23.5, 24.2, np.nan, 21.9, 23.0, np.nan, 25.1, 24.0, 23.8], # Simulated gaps
        "climate_deviation": [-1.9, -0.5, 0.2, 0.0, -2.1, -1.0, 0.0, 1.1, 0.0, -0.2],
        "kenya_public_sentiment_score": [0.15, -0.05, 0.22, 0.11, -0.32, 0.05, 0.0, 0.41, 0.12, -0.02],
        "overall_social_mood": ["Positive 🟩", "Neutral 🟨", "Positive 🟩", "Positive 🟩", "Negative 🟥", "Neutral 🟨", "Neutral 🟨", "Positive 🟩", "Positive 🟩", "Negative 🟥"],
        "satellite_grid_status": ["SUCCESS"] * 10,
        "satellite_layer_type": ["Image"] * 10
    }
    df_metrics = pd.DataFrame(fallback_data)

# ==============================================================================
# 📊 3. THEMATIC DATA COMPLETENESS & GAP AUDITING SECTION
# ==============================================================================
st.subheader("⚠️ Spatiotemporal Missing Data Gaps")

# Calculate data gaps present inside the metrics tracking structure
total_records = len(df_metrics)
missing_temp_gaps = df_metrics["live_temperature_c"].isna().sum()
data_completeness_pct = round(((total_records - missing_temp_gaps) / total_records) * 100, 1)

metric_col1, metric_col2, metric_col3 = st.columns(3)
with metric_col1:
    st.metric(label="Total Ingested Log Packets", value=total_records)
with metric_col2:
    st.metric(label="Detected Timeline Gaps (Missing Records)", value=missing_temp_gaps, delta="Anomalies Found", delta_color="inverse")
with metric_col3:
    st.metric(label="System Pipeline Data Completeness", value=f"{data_completeness_pct}%")

# Create a visual timeline showing where gaps exist explicitly
st.markdown("#### 📈 Multi-Sector Metric Matrix Timeline")

# Display a chart mapping temperature and sentiment profiles over time
chart_df = df_metrics.copy()
chart_df['timestamp'] = pd.to_datetime(chart_df['timestamp'])
chart_df = chart_df.set_index('timestamp')

# Plot metrics (Streamlit automatically skips NaN entries, creating visual line breaks highlighting the gaps)
st.line_chart(chart_df[["live_temperature_c", "kenya_public_sentiment_score"]])


# ==============================================================================
# 🗺️ 4. GEOSPATIAL EARTH ENGINE VISUALIZATION HUB
# ==============================================================================
st.markdown("---")
st.subheader("🛰️ Orbital Agriculture Imagery & Spatial Boundaries")

# Sidebar Configuration for Data Pipeline Ingestion Queries
st.sidebar.markdown("### 🪐 Spatial Control Core")
start_query = st.sidebar.date_input("Engine Ingestion Start Date", value=pd.to_datetime("2026-01-01"))
end_query = st.sidebar.date_input("Engine Ingestion End Date", value=pd.to_datetime("2026-04-01"))

# Live Engine Execution Button
if st.sidebar.button("🌌 Synchronize Live Satellite Grid"):
    with st.spinner("Streaming spatial layers from Google Earth Engine..."):
        try:
            # 1. Initialize coordinate bounding region
            kenya_center_lon, kenya_center_lat = 36.8219, -1.2921
            roi_geom = ee.Geometry.Point([kenya_center_lon, kenya_center_lat]).buffer(25000)
            
            # 2. Fire backend query function from your custom Satellite_engine Blueprint
            live_layer = get_kenya_agri_grid(
                start_date=start_query.strftime("%Y-%m-%d"),
                end_date=end_query.strftime("%Y-%m-%d"),
                roi_geometry=roi_geom
            )
            
            # 3. Request temporary map tile url pointers generated by Earth Engine
            map_id_dict = ee.Image(live_layer).getMapId({'min': 0, 'max': 0.8, 'palette': ['red', 'yellow', 'green']})
            
            # 4. Construct Folium deployment widget map
            m = folium.Map(location=[kenya_center_lat, kenya_center_lon], zoom_start=10, tiles="CartoDB dark_matter")
            folium.TileLayer(
                tiles=map_id_dict['tile_fetcher'].url_format,
                attr='Google Earth Engine - Copernicus Sentinel-2',
                name='Filled NDVI Grid Layer',
                overlay=True,
                control=True
            ).add_to(m)
            
            # Render interactive canvas frame inside app layout
            st_folium(m, width=900, height=450)
            st.success(f"Successfully integrated live Earth Engine project instance: '{TARGET_PROJECT_ID}'")
            
        except Exception as ee_render_err:
            st.error(f"Could not load live interactive map layers. Displaying vector region framework instead.")
            st.info(f"Root Log Trace: {ee_render_err}")
else:
    # Static visual layout placeholder before user triggers engine synchronization
    st.info("Click 'Synchronize Live Satellite Grid' in the control sidebar to compile and overlay real-time Earth Engine map matrices.")
    
    # Initialize basic analytical tracking overview map
    fallback_map = folium.Map(location=[-1.2921, 36.8219], zoom_start=10, tiles="CartoDB dark_matter")
    # Draw simple perimeter showing where your 50km agriculture grid operates
    folium.Circle(
        radius=25000,
        location=[-1.2921, 36.8219],
        color="#50e4ff",
        fill=True,
        fill_color="#2050aa",
        fill_opacity=0.15,
        popup="Active Sentinel-2 Data Extraction Target Region"
    ).add_to(fallback_map)
    
    st_folium(fallback_map, width=900, height=400)

