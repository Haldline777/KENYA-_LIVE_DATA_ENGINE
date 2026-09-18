import os
import requests
import pandas as pd
from datetime import datetime
from textblob import TextBlob

print("🔄 Initializing Advanced Kenyan Dual Data Engine...")

# ==========================================
# 📊 PART 1: NAIROBI CLIMATE ANALYTICS
# ==========================================
try:
    weather_url = "https://open-meteo.com"
    weather_res = requests.get(weather_url, timeout=10)
    weather_data = weather_res.json()
    current_temp = weather_data['current_weather']['temperature']
except Exception as e:
    print(f"⚠️ Weather API issue, using fallback: {e}")
    current_temp = 23.5

baseline_high = 24.0
climate_deviation = round(current_temp - baseline_high, 2)

# ==========================================
# 🤖 PART 2: KENYAN SOCIAL MEDIA SENTIMENT
# ==========================================
# We simulate a live public text scrape focusing on high-profile Kenyan topics
# In a full project, this can pull directly from localized RSS news or active feeds
local_trending_topics = [
    "Safaricom introduces new high-speed infrastructure upgrades",
    "Kenyans voice strong frustration over sudden transport fare increases",
    "A massive new tech hub opens up in Mombasa to support local engineering talent"
]

# We will analyze the sentiment score of the community conversations
total_polarity = 0
for topic in local_trending_topics:
    # TextBlob assigns a score from -1 (very negative) to +1 (very positive)
    analysis = TextBlob(topic)
    total_polarity += analysis.sentiment.polarity

# Calculate the mean public sentiment score for today
average_sentiment = round(total_polarity / len(local_trending_topics), 2)

if average_sentiment > 0.1:
    sentiment_label = "Positive 🟩"
elif average_sentiment < -0.1:
    sentiment_label = "Negative 🟥"
else:
    sentiment_label = "Neutral 🟨"

# ==========================================
# 💾 PART 3: ARCHIVING THE UNIFIED DATASET
# ==========================================
payload = {
    "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    "city": "Nairobi",
    "live_temperature_c": current_temp,
    "climate_deviation": climate_deviation,
    "kenya_public_sentiment_score": average_sentiment,
    "overall_social_mood": sentiment_label
}

csv_name = "nairobi_climate_anomalies.csv"
df_new = pd.DataFrame([payload])

if os.path.exists(csv_name):
    df_existing = pd.read_csv(csv_name)
    # Align structural column shapes if upgrading an existing file schema
    df_final = pd.concat([df_existing, df_new], ignore_index=True)
else:
    df_final = df_new

df_final.to_csv(csv_name, index=False)
print(f"✅ Master Log Archived! Temp: {current_temp}°C | Sentiment Score: {average_sentiment} ({sentiment_label})")
