# CS172 Project — Bluesky Post Collector

## 📌 Overview
This project implements a real-time data pipeline that collects, stores, and cleans posts from the Bluesky platform. The system uses the Bluesky Jetstream WebSocket API to stream posts, stores them in JSONL format, and preprocesses the data for downstream search and analysis.

---

## ⚙️ System Architecture

The system is composed of three main components:

- **Data Collection (`BlueSkyStreamCollector.py`)**
  - Connects to the Bluesky Jetstream WebSocket API
  - Streams posts in real time
  - Performs deduplication using content identifiers
  - Extracts embedded URLs and fetches page titles

- **Storage**
  - Stores raw data in the `data/` directory
  - Uses JSON Lines format (one post per line)
  - Splits files into ~10MB chunks (`posts_0.jsonl`, `posts_1.jsonl`, ...)

- **Preprocessing (`clean_data.py`)**
  - Removes duplicates and low-quality posts
  - Normalizes timestamps and author identifiers
  - Outputs cleaned data to the `cleaned_data/` directory

---

## 🚀 How to Run

### 1. Install Dependencies
`pip install websockets requests beautifulsoup4`

### 2. Run Data Collection
`python main.py`

### 3. Run Data Cleaning
`python clean_data.py`

## ⚙️ Directory Structure
`.`
`├── main.py`
`├── BlueSkyStreamCollector.py`
`├── clean_data.py`
`├── data/                # Raw collected data (~500MB)`
`├── cleaned_data/        # Processed data`
`├── .gitignore`
`└── README.md`

## 📊 Dataset Summary
- Total Raw Data: ~500MB
- Files Generated: ~50 JSONL files
- Total Posts Processed: ~1.38 million
- Posts Retained After Cleaning: ~1.14 million
- Retention Rate: ~82%

## ⚠️ Notes
Raw data is excluded from the repository due to size constraints (`.gitignore`)
URL title extraction may fail for some links due to network timeouts or restricted access
The system relies on a live data stream, so some posts may be missed during connection interruptions

## 👥 Team Contributions
- Jasmine: Data collection pipeline
- Lahari: Data cleaning and preprocessing pipeline
- Connor: URL enrichment, testing, and validation
- Andrew: Organizing JSONL-based storage; Testing
