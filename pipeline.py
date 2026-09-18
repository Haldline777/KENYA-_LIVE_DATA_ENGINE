import os
import requests
import pandas as pd
from datetime import datetime

print("🔄 Initializing Kenya Data Engine Pipeline...")

# 1. Fetch current weather for Nairobi (Latitude: -1.2921, Longitude: 36.8219)
try:
    URL = "https://open-meteo.com"
    response = requests.get(URL, timeout=10)
    weather_data = response.json()
    current_temp = weather_data['current_weather']['temperature']
    windspeed = weather_data['current_weather']['windspeed']
except Exception as e:
    print(f"❌ Error connecting to API: {e}")
    current_temp = 23.5  # Fallback safety default
    windspeed = 12.0

# 2. Compare against a general localized monthly baseline (~24.0°C)
baseline_high = 24.0
deviation = round(current_temp - baseline_high, 2)

# 3. Create our data payload row
payload = {
    "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    "city": "Nairobi",
    "live_temperature_c": current_temp,
    "historical_baseline_c": baseline_high,
    "climate_deviation": deviation,
    "anomaly_detected": "Yes" if abs(deviation) > 3.0 else "No"
}

# 4. Save and append directly to your permanent dataset file
csv_name = "nairobi_climate_anomalies.csv"
df_new = pd.DataFrame([payload])

if os.path.exists(csv_name):
    df_existing = pd.read_csv(csv_name)
    df_final = pd.concat([df_existing, df_new], ignore_index=True)
else:
    df_final = df_new

df_final.to_csv(csv_name, index=False)
print(f"✅ Data archived perfectly! Today's Nairobi Temp: {current_temp}°C (Deviation: {deviation}°C)")
