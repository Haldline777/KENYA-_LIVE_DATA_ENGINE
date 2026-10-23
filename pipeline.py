"""
🌍 KENYA LIVE DATA ENGINE - pipeline.py (v2)

Collects real-time climate, air quality, news sentiment and satellite data
for key Kenyan cities, scores anomalies against a real historical baseline,
and archives everything to CSV for Power BI and the Streamlit app.

Outputs
  - nairobi_climate_anomalies.csv  main dataset (one row per city per run)
  - kenya_headlines_log.csv        audit trail of every headline scored
  - latest_snapshot.json           most recent run, handy for app.py

Environment variables (all optional)
  - EE_SERVICE_ACCOUNT_JSON : full JSON key of an Earth Engine service account
                              (store as a GitHub Actions secret for automation)
  - EE_PROJECT              : Earth Engine / Google Cloud project id
"""

import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote_plus

import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from textblob import TextBlob
from urllib3.util.retry import Retry

# 🛰️ Earth Engine is optional: the pipeline still runs without it
try:
    import ee
    from Satellite_engine import get_kenya_agri_grid

    EE_AVAILABLE = True
except Exception as _import_error:  # noqa: BLE001
    EE_AVAILABLE = False
    print(f"⚠️ Earth Engine modules unavailable: {_import_error}")

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
CSV_NAME = "nairobi_climate_anomalies.csv"
HEADLINES_CSV = "kenya_headlines_log.csv"
SNAPSHOT_JSON = "latest_snapshot.json"

EAT = timezone(timedelta(hours=3))  # East Africa Time

CITIES = {
    "Nairobi": (-1.2921, 36.8219),
    "Mombasa": (-4.0435, 39.6682),
    "Kisumu": (-0.0917, 34.7680),
    "Nakuru": (-0.3031, 36.0800),
    "Eldoret": (0.5143, 35.2698),
    "Garissa": (-0.4532, 39.6461),
    "Lodwar": (3.1191, 35.5973),
}

ANOMALY_Z = 2.0               # |z-score| at or above this = anomaly
LEGACY_ABS_THRESHOLD = 1.0    # used only if no historical std is available
BASELINE_YEARS = 10           # years of history for the climate baseline
BASELINE_WINDOW_DAYS = 7      # +/- days around today's date
FALLBACK_BASELINES = {"Nairobi": 24.0}  # last-resort static baseline

SATELLITE_LOOKBACK_DAYS = 90
SATELLITE_BUFFER_M = 25000

TENSION_FORMULA_VERSION = "v2"

PILLAR_QUERIES = {
    "economic": 'Kenya (fuel OR electricity OR tax OR "cost of living" OR prices) when:2d',
    "political": "Kenya (parliament OR governance OR protests OR corruption OR election) when:2d",
    "climate_agri": 'Kenya (drought OR floods OR "food prices" OR harvest OR rainfall) when:2d',
}

LEGACY_COLUMNS = [
    "timestamp", "city", "live_temperature_c", "historical_baseline_c",
    "climate_deviation", "anomaly_detected", "economic_sentiment",
    "political_sentiment", "kenya_public_sentiment_score",
    "civic_tension_index", "overall_social_mood",
    "satellite_grid_status", "satellite_layer_type",
]


# ==========================================
# 🔧 HELPERS
# ==========================================
def make_session() -> requests.Session:
    """HTTP session with automatic retries and backoff."""
    session = requests.Session()
    retry = Retry(
        total=3, backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(
        {"User-Agent": "Mozilla/5.0 (compatible; KENYA_LIVE_DATA_ENGINE/2.0)"}
    )
    return session


SESSION = make_session()


def safe_round(value, digits=2):
    try:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return None
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def atomic_csv(df: pd.DataFrame, path: str) -> None:
    """Write via a temp file so a crash never corrupts the dataset."""
    tmp = f"{path}.tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)


# ==========================================
# 🌡️ PART 1: WEATHER, AIR QUALITY, BASELINE
# ==========================================
def fetch_weather(lat: float, lon: float) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                   "precipitation,wind_speed_10m,cloud_cover",
        "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,"
                 "precipitation_sum,uv_index_max",
        "timezone": "Africa/Nairobi",
        "forecast_days": 1,
    }
    r = SESSION.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    cur, daily = data.get("current", {}), data.get("daily", {})

    def first(key):
        values = daily.get(key)
        return values[0] if values else None

    return {
        "live_temperature_c": cur.get("temperature_2m"),
        "feels_like_c": cur.get("apparent_temperature"),
        "humidity_pct": cur.get("relative_humidity_2m"),
        "precipitation_mm": cur.get("precipitation"),
        "wind_speed_kmh": cur.get("wind_speed_10m"),
        "cloud_cover_pct": cur.get("cloud_cover"),
        "temp_max_c": first("temperature_2m_max"),
        "temp_min_c": first("temperature_2m_min"),
        "temp_mean_today_c": first("temperature_2m_mean"),
        "rain_total_today_mm": first("precipitation_sum"),
        "uv_index_max": first("uv_index_max"),
    }


def fetch_air_quality(lat: float, lon: float) -> dict:
    params = {"latitude": lat, "longitude": lon, "current": "pm10,pm2_5,us_aqi"}
    r = SESSION.get(
        "https://air-quality-api.open-meteo.com/v1/air-quality", params=params, timeout=15
    )
    r.raise_for_status()
    cur = r.json().get("current", {})
    return {"pm2_5": cur.get("pm2_5"), "pm10": cur.get("pm10"), "us_aqi": cur.get("us_aqi")}


def fetch_baseline(lat: float, lon: float, today: date):
    """Mean and std of daily temperature around today's date over past years."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date(today.year - BASELINE_YEARS, 1, 1).isoformat(),
        "end_date": date(today.year - 1, 12, 31).isoformat(),
        "daily": "temperature_2m_mean",
        "timezone": "Africa/Nairobi",
    }
    r = SESSION.get("https://archive-api.open-meteo.com/v1/archive", params=params, timeout=30)
    r.raise_for_status()
    daily = r.json()["daily"]
    df = pd.DataFrame(
        {"date": pd.to_datetime(daily["time"]), "t": daily["temperature_2m_mean"]}
    ).dropna()

    doy_today = today.timetuple().tm_yday
    diff = (df["date"].dt.dayofyear - doy_today).abs()
    diff = np.minimum(diff, 365 - diff)  # wrap around new year
    window = df[diff <= BASELINE_WINDOW_DAYS]
    if window.empty:
        raise ValueError("No baseline samples found")
    return float(window["t"].mean()), float(window["t"].std()), int(len(window))


def classify_anomaly(deviation, baseline_std):
    """Return (anomaly_flag, severity, direction, z_score)."""
    if deviation is None:
        return "Unknown", "Unknown", "Unknown", None

    direction = "Warmer" if deviation > 0 else "Cooler" if deviation < 0 else "Normal"
    if baseline_std and baseline_std > 0:
        z = deviation / baseline_std
        a = abs(z)
        severity = "Critical" if a >= 3 else "Warning" if a >= 2 else "Watch" if a >= 1 else "Normal"
        flag = "Yes" if a >= ANOMALY_Z else "No"
        return flag, severity, direction, round(z, 2)

    flag = "Yes" if abs(deviation) > LEGACY_ABS_THRESHOLD else "No"
    return flag, ("Warning" if flag == "Yes" else "Normal"), direction, None


# ==========================================
# 📰 PART 2: LIVE NEWS SENTIMENT (3 PILLARS)
# ==========================================
def fetch_headlines(query: str, limit: int = 15) -> list:
    url = (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}&hl=en-KE&gl=KE&ceid=KE:en"
    )
    r = SESSION.get(url, timeout=15)
    r.raise_for_status()
    root = ET.fromstring(r.content)

    items, seen = [], set()
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        source = (item.findtext("source") or "").strip()
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3]
        key = title.lower()
        if not title or key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "headline": title,
                "source": source,
                "link": item.findtext("link") or "",
                "polarity": round(TextBlob(title).sentiment.polarity, 3),
            }
        )
        if len(items) >= limit:
            break
    return items


def collect_sentiment(run_ts: str):
    """Returns (pillar_scores, headline_rows, news_ok)."""
    scores, rows, successes = {}, [], 0
    for pillar, query in PILLAR_QUERIES.items():
        try:
            items = fetch_headlines(query)
            if items:
                scores[pillar] = float(np.mean([i["polarity"] for i in items]))
                successes += 1
            else:
                scores[pillar] = None
            for i in items:
                rows.append({"timestamp": run_ts, "pillar": pillar, **i})
            print(f"📰 {pillar}: {len(items)} headlines scored")
        except Exception as e:  # noqa: BLE001
            scores[pillar] = None
            print(f"⚠️ News feed failed for '{pillar}': {e}")
    return scores, rows, successes > 0


def sentiment_label(score):
    if score is None:
        return "Unavailable ⬜"
    if score > 0.1:
        return "Positive 🟩"
    if score < -0.1:
        return "Negative (High Tension) 🟥"
    return "Neutral 🟨"


# ==========================================
# 🔥 PART 3: CIVIC TENSION INDEX (0-10)
# ==========================================
def compute_tension(deviation, sentiment, pm25):
    """Weighted blend of climate stress, negative mood and air pollution.
    Missing components are skipped and the weights re-normalised."""
    parts = []
    if deviation is not None:
        parts.append((0.35, min(abs(deviation) / 3.0, 1.0)))
    if sentiment is not None:
        parts.append((0.50, min(max(-sentiment, 0.0) / 0.5, 1.0)))
    if pm25 is not None:
        parts.append((0.15, min(pm25 / 75.0, 1.0)))
    if not parts:
        return None
    total = sum(w for w, _ in parts)
    return round(10 * sum(w * v for w, v in parts) / total, 2)


def tension_level(score):
    if score is None:
        return "Unknown"
    return "Low" if score < 3 else "Moderate" if score < 5 else "High" if score < 7 else "Severe"


# ==========================================
# 🛰️ PART 4: SATELLITE AGRICULTURE GRID
# ==========================================
def init_earth_engine() -> bool:
    if not EE_AVAILABLE:
        return False
    project = os.getenv("EE_PROJECT", "kenya-live-data")
    key_json = os.getenv("EE_SERVICE_ACCOUNT_JSON")
    try:
        if key_json:  # automated / GitHub Actions mode
            email = json.loads(key_json)["client_email"]
            creds = ee.ServiceAccountCredentials(email, key_data=key_json)
            ee.Initialize(creds, project=project)
        else:  # local mode
            try:
                ee.Initialize(project=project)
            except Exception:  # noqa: BLE001
                ee.Initialize()
        print("🛰️ Earth Engine initialised")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Earth Engine init failed: {e}")
        return False


def fetch_satellite(lat: float, lon: float, start: str, end: str) -> dict:
    roi = ee.Geometry.Point([lon, lat]).buffer(SATELLITE_BUFFER_M)
    layer = get_kenya_agri_grid(start_date=start, end_date=end, roi_geometry=roi)
    layer_type = layer.getInfo().get("type", "Image")
    image = layer.mean() if layer_type == "ImageCollection" else layer

    stats = image.reduceRegion(
        reducer=ee.Reducer.mean(), geometry=roi, scale=1000,
        maxPixels=1e9, bestEffort=True,
    ).getInfo() or {}
    stats = {k: round(v, 4) for k, v in stats.items() if isinstance(v, (int, float))}

    band, value = (next(iter(stats.items())) if stats else (None, None))
    return {
        "satellite_grid_status": "SUCCESS",
        "satellite_layer_type": layer_type,
        "satellite_primary_band": band,
        "satellite_primary_value": value,
        "satellite_stats_json": json.dumps(stats) if stats else None,
    }


# ==========================================
# 🚀 MAIN PIPELINE
# ==========================================
def main() -> None:
    print("🔄 Initializing Kenya Live Data Engine v2...")
    now_utc = datetime.now(timezone.utc)
    run_ts = now_utc.strftime("%Y-%m-%d %H:%M:%S")
    local_ts = now_utc.astimezone(EAT).strftime("%Y-%m-%d %H:%M:%S")
    today = now_utc.astimezone(EAT).date()

    # --- News sentiment (national level, shared by every city) ---
    pillar_scores, headline_rows, news_ok = collect_sentiment(run_ts)
    econ, pol, agri = (pillar_scores.get(k) for k in ("economic", "political", "climate_agri"))
    core = [s for s in (econ, pol) if s is not None]
    avg_sentiment = safe_round(np.mean(core)) if core else None

    # --- Earth Engine ---
    ee_ready = init_earth_engine()
    sat_start = (today - timedelta(days=SATELLITE_LOOKBACK_DAYS)).isoformat()
    sat_end = today.isoformat()

    rows = []
    for city, (lat, lon) in CITIES.items():
        print(f"\n📍 Processing {city}...")
        sources_ok = {"news": news_ok}

        # Weather
        try:
            weather = fetch_weather(lat, lon)
            weather_status = "LIVE"
        except Exception as e:  # noqa: BLE001
            print(f"⚠️ Weather failed for {city}: {e}")
            weather, weather_status = {}, "UNAVAILABLE"
        sources_ok["weather"] = weather_status == "LIVE"

        # Air quality
        try:
            air = fetch_air_quality(lat, lon)
            sources_ok["air"] = True
        except Exception as e:  # noqa: BLE001
            print(f"⚠️ Air quality failed for {city}: {e}")
            air, sources_ok["air"] = {}, False

        # Historical baseline
        baseline_std, baseline_n = None, None
        try:
            baseline, baseline_std, baseline_n = fetch_baseline(lat, lon, today)
            baseline_source = f"open-meteo-archive-{BASELINE_YEARS}y"
            sources_ok["baseline"] = True
        except Exception as e:  # noqa: BLE001
            print(f"⚠️ Baseline failed for {city}: {e}")
            baseline = FALLBACK_BASELINES.get(city)
            baseline_source = "static_fallback" if baseline is not None else "unavailable"
            sources_ok["baseline"] = False

        # Deviation: today's expected daily mean vs the climatological daily mean
        expected_today = weather.get("temp_mean_today_c")
        if expected_today is None:
            expected_today = weather.get("live_temperature_c")
        deviation = (
            round(expected_today - baseline, 2)
            if expected_today is not None and baseline is not None
            else None
        )
        anomaly_flag, severity, direction, z_score = classify_anomaly(deviation, baseline_std)

        # Tension
        tension = compute_tension(deviation, avg_sentiment, air.get("pm2_5"))

        # Satellite
        sat = {
            "satellite_grid_status": "OFFLINE",
            "satellite_layer_type": "UNKNOWN",
            "satellite_primary_band": None,
            "satellite_primary_value": None,
            "satellite_stats_json": None,
        }
        if ee_ready:
            try:
                sat = fetch_satellite(lat, lon, sat_start, sat_end)
                print(f"📊 Satellite metrics extracted for {city}")
            except Exception as e:  # noqa: BLE001
                print(f"⚠️ Satellite fallback for {city}: {e}")
        sources_ok["satellite"] = sat["satellite_grid_status"] == "SUCCESS"

        quality = round(100 * sum(sources_ok.values()) / len(sources_ok))

        rows.append(
            {
                # ---- legacy columns (unchanged names) ----
                "timestamp": run_ts,
                "city": city,
                "live_temperature_c": weather.get("live_temperature_c"),
                "historical_baseline_c": safe_round(baseline),
                "climate_deviation": deviation,
                "anomaly_detected": anomaly_flag,
                "economic_sentiment": safe_round(econ),
                "political_sentiment": safe_round(pol),
                "kenya_public_sentiment_score": avg_sentiment,
                "civic_tension_index": tension,
                "overall_social_mood": sentiment_label(avg_sentiment),
                "satellite_grid_status": sat["satellite_grid_status"],
                "satellite_layer_type": sat["satellite_layer_type"],
                # ---- new columns ----
                "local_time_eat": local_ts,
                "latitude": lat,
                "longitude": lon,
                "anomaly_z_score": z_score,
                "anomaly_severity": severity,
                "anomaly_direction": direction,
                "baseline_std_c": safe_round(baseline_std),
                "baseline_samples": baseline_n,
                "baseline_source": baseline_source,
                "temp_mean_today_c": safe_round(weather.get("temp_mean_today_c")),
                "temp_max_c": weather.get("temp_max_c"),
                "temp_min_c": weather.get("temp_min_c"),
                "feels_like_c": weather.get("feels_like_c"),
                "humidity_pct": weather.get("humidity_pct"),
                "precipitation_mm": weather.get("precipitation_mm"),
                "rain_total_today_mm": weather.get("rain_total_today_mm"),
                "wind_speed_kmh": weather.get("wind_speed_kmh"),
                "cloud_cover_pct": weather.get("cloud_cover_pct"),
                "uv_index_max": weather.get("uv_index_max"),
                "pm2_5": air.get("pm2_5"),
                "pm10": air.get("pm10"),
                "us_aqi": air.get("us_aqi"),
                "climate_agri_sentiment": safe_round(agri),
                "headlines_scored": len(headline_rows),
                "tension_level": tension_level(tension),
                "tension_formula_version": TENSION_FORMULA_VERSION,
                "satellite_primary_band": sat["satellite_primary_band"],
                "satellite_primary_value": sat["satellite_primary_value"],
                "satellite_stats_json": sat["satellite_stats_json"],
                "weather_status": weather_status,
                "data_quality_pct": quality,
            }
        )
        print(
            f"✅ {city}: {weather.get('live_temperature_c')}°C | "
            f"dev {deviation} | {severity} | tension {tension} | quality {quality}%"
        )

    # Stop (and fail the GitHub Action) rather than archive an empty run
    if not any(r["weather_status"] == "LIVE" for r in rows):
        print("❌ No weather data retrieved for any city. Nothing archived.")
        sys.exit(1)

    # ---- Archive main dataset ----
    df_new = pd.DataFrame(rows)
    if os.path.exists(CSV_NAME):
        df_existing = pd.read_csv(CSV_NAME)
        df_final = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_final = df_new
    df_final = df_final.drop_duplicates(subset=["timestamp", "city"], keep="last")
    ordered = LEGACY_COLUMNS + [c for c in df_final.columns if c not in LEGACY_COLUMNS]
    atomic_csv(df_final[ordered], CSV_NAME)

    # ---- Archive headline audit log ----
    if headline_rows:
        df_h = pd.DataFrame(headline_rows)
        if os.path.exists(HEADLINES_CSV):
            df_h = pd.concat([pd.read_csv(HEADLINES_CSV), df_h], ignore_index=True)
        df_h = df_h.drop_duplicates(subset=["pillar", "headline"], keep="first")
        atomic_csv(df_h, HEADLINES_CSV)

    # ---- Latest snapshot for the app ----
    with open(SNAPSHOT_JSON, "w", encoding="utf-8") as f:
        json.dump(json.loads(df_new[ordered].to_json(orient="records")), f, indent=2)

    n_anom = int((df_new["anomaly_detected"] == "Yes").sum())
    print(
        f"\n✅ Archived {len(df_new)} city records | anomalies: {n_anom} | "
        f"national sentiment: {avg_sentiment} | file: {CSV_NAME}"
    )


if __name__ == "__main__":
    main()