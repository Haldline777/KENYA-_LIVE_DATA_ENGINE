# 🌍 KENYA LIVE DATA ENGINE 🇰🇪

> An automated, real-time data science pipeline designed to track, analyze, and visualize climate and societal anomalies across Kenya. Bridging robust data engineering with executive-level interactive intelligence.

[![Automated Daily Ingestion](https://github.com/Haldline777/KENYA-_-LIVE_DATA_ENGINE/actions/workflows/main.yml/badge.svg)](https://github.com/Haldline777/KENYA-_-LIVE_DATA_ENGINE/actions)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Power BI Ready](https://img.shields.io/badge/Power_BI-Live_Sync-yellow.svg)](https://powerbi.microsoft.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Live_App-ff4b4b.svg)](https://streamlit.io/)
[![Pipeline Status](https://img.shields.io/badge/Pipeline-Operational-success)]()

---

## 📌 Table of Contents

1. [Project Overview](#-project-overview)
2. [System Data Flow Architecture](#-system-data-flow-architecture-how-data-moves)
3. [Step-by-Step Data Pipeline Lifecycle](#-step-by-step-data-pipeline-lifecycle)
4. [Daily Automation Timeline](#-daily-automation-timeline)
5. [Anomaly Detection Logic](#-anomaly-detection-logic)
6. [Repository Structure](#-repository-structure)
7. [Quick Start](#-quick-start)
8. [Roadmap](#-roadmap)

---

## 🎯 Project Overview

The **Kenya Live Data Engine** automatically collects climate and atmospheric data, cleans it, detects anomalies, and publishes the results to dashboards that decision makers can open any day without touching code.

| Question | Answer |
|---|---|
| **What does it track?** | Climate, temperature and atmospheric anomalies, starting with Nairobi |
| **How often does it update?** | Automatically, every day (GitHub Actions cron) |
| **Who is it for?** | Analysts, policy teams, researchers and executives |
| **What do I get?** | A clean anomaly dataset, a Power BI dashboard and a Streamlit app |

---

## 🤖 System Data Flow Architecture (How Data Moves)

```mermaid
graph TD
    A[📡 External APIs & Satellite Feeds] -->|Automated Daily Trigger| B[⚙️ Python Pipeline Core]
    B -->|Data Cleansing & Matrix Math| C[🛰️ Satellite Engine]
    C -->|Anomaly Detection & Processing| D[📊 nairobi_climate_anomalies.csv]
    D -->|Live Data Connector| E[📈 Power BI Executive Dashboard]
    D -->|Interactive Web Layer| G[🖥️ Streamlit App - app.py]
    E -->|Actionable Insights| F[👥 Decision Makers & Stakeholders]
    G -->|Actionable Insights| F
```

---

## 🎯 Step-by-Step Data Pipeline Lifecycle

| Stage | Action / Flow Indicator | Core Module / File | Description & Technical Impact |
|:---:|:---|:---|:---|
| **01** | 📥 **INGEST** | GitHub Actions & Cron Workflows | Programmatically fetches raw real-time climate, temperature, and atmospheric streams autonomously. |
| **02** | ⚙️ **PROCESS** | `pipeline.py` & `Satellite_engine.py` | Cleans raw telemetry, runs complex matrix calculations, and flags environmental anomalies in real-time. |
| **03** | 🗄️ **STORE** | `nairobi_climate_anomalies.csv` | Acts as the structured local database snapshot holding historical and live anomaly records. |
| **04** | 📊 **PRESENT** | Power BI & `app.py` (Streamlit) | Serves executive-level dashboards and an interactive web app so stakeholders can explore the insights. |

### 🔄 Lifecycle at a Glance

```mermaid
flowchart LR
    S1["📥 01 INGEST<br/>GitHub Actions + Cron"] --> S2["⚙️ 02 PROCESS<br/>pipeline.py<br/>Satellite_engine.py"]
    S2 --> S3["🗄️ 03 STORE<br/>nairobi_climate_anomalies.csv"]
    S3 --> S4["📊 04 PRESENT<br/>Power BI + app.py"]

    style S1 fill:#dbeafe,stroke:#2563eb,color:#000
    style S2 fill:#fef3c7,stroke:#d97706,color:#000
    style S3 fill:#dcfce7,stroke:#16a34a,color:#000
    style S4 fill:#fce7f3,stroke:#db2777,color:#000
```

---

## ⏱️ Daily Automation Timeline

What happens each day without anyone pressing a button:

```mermaid
sequenceDiagram
    autonumber
    participant Cron as ⏰ GitHub Actions (Cron)
    participant API as 📡 External APIs
    participant Py as ⚙️ pipeline.py
    participant Sat as 🛰️ Satellite_engine.py
    participant CSV as 🗄️ nairobi_climate_anomalies.csv
    participant BI as 📈 Power BI / Streamlit

    Cron->>API: Request latest climate data
    API-->>Cron: Raw telemetry
    Cron->>Py: Run pipeline
    Py->>Py: Clean and validate data
    Py->>Sat: Send cleaned data
    Sat->>Sat: Matrix calculations and anomaly flags
    Sat-->>Py: Flagged results
    Py->>CSV: Append and commit new records
    CSV-->>BI: Dashboards refresh with latest data
```

---

## 🛰️ Anomaly Detection Logic

How a raw reading becomes an actionable alert:

```mermaid
flowchart TD
    R[🌡️ New Reading] --> C{Valid and complete?}
    C -- No --> X[🧹 Clean / Drop / Impute]
    X --> C
    C -- Yes --> B[📐 Compare against historical baseline]
    B --> D{Deviation beyond threshold?}
    D -- No --> N[✅ Normal - store record]
    D -- Yes --> A[🚨 Flag as anomaly]
    A --> S[🗄️ Store in nairobi_climate_anomalies.csv]
    N --> S
    S --> V[📊 Visualize on dashboards]
```

> 💡 **Customize:** replace "historical baseline" and "threshold" with the exact method used in `Satellite_engine.py` (for example z-score, rolling mean, or percentile).

---

## 📂 Repository Structure

```text
KENYA-_-LIVE_DATA_ENGINE/
├── .github/
│   └── workflows/
│       └── main.yml                  # ⏰ Daily automated ingestion trigger
├── pipeline.py                       # ⚙️ Core pipeline orchestration and cleaning
├── Satellite_engine.py               # 🛰️ Matrix math and anomaly detection
├── app.py                            # 🖥️ Streamlit interactive app
├── nairobi_climate_anomalies.csv     # 🗄️ Historical and live anomaly records
├── requirements.txt                  # 📦 Python dependencies
└── README.md                         # 📖 You are here
```

---

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/Haldline777/KENYA-_-LIVE_DATA_ENGINE.git
cd KENYA-_-LIVE_DATA_ENGINE

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the pipeline manually
python pipeline.py

# 4. Launch the interactive app
streamlit run app.py
```

**Power BI:** open Power BI Desktop, choose **Get Data → Web/Text**, and point it to the raw URL of `nairobi_climate_anomalies.csv` on GitHub for live sync.

---

## 🗺️ Roadmap

```mermaid
gantt
    title Project Roadmap
    dateFormat  YYYY-MM
    axisFormat  %b %Y
    section Core
    Daily climate ingestion        :done,    r1, 2026-01, 2026-03
    Anomaly detection engine       :done,    r2, 2026-02, 2026-05
    section Presentation
    Power BI dashboard             :done,    r3, 2026-04, 2026-07
    Streamlit app                  :active,  r4, 2026-07, 2026-11
    section Next
    More Kenyan counties           :         r5, 2026-11, 2027-02
    Societal indicators            :         r6, 2027-01, 2027-04
```

> 💡 **Customize:** adjust the dates and statuses in the Gantt chart to match your real progress.

---

## 👤 Author

**Haldline777** · Data Science and Data Engineering · Nairobi, Kenya 🇰🇪

⭐ If you find this project useful, please star the repository!