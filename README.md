# UrbanLens

> **Seeing what the city needs fixed.**

UrbanLens is an open-source AI system for municipal teams. It detects, classifies and prioritizes public infrastructure issues — potholes, road damage, broken streetlights, overflowing drains — from photos or video, geotags them, merges duplicates, and displays a ranked repair queue on a live, role-based dashboard with a full audit trail.

Built for **Hacktoberfest '26** (AITR ACM × MLH) · *Best Open-Source AI Project — Problem Statement 1: AI-Powered Public Infrastructure Monitoring* & *Best Use of Gemini API*.

---

## Features

- **100% Free Interactive MapKit** — Key-less OpenStreetMap standard, Esri World Street Map, Esri World Imagery (satellite), and OpenTopoMap layers with automatic startup tile health verification.
- **Rebuilt Landing & Split-Screen Login** — Full-viewport animated landing page with live database metrics and one-click demo login chips.
- **Role-Based Navigation (views/)** — Clean, role-filtered navigation via `st.navigation` with zero raw page auto-discovery leakage.
- **Issue Inspection Dialogs** — Inspect annotated images, AI qualitative assessments, score breakdowns, and status timeliners inside large modal dialogs.
- **Smart Scoring Formula** — Deterministic severity ($0.5 \times \text{area} + 0.3 \times \text{confidence} + 0.2 \times \text{count}$) and location-multiplier priority (1.5× near hospitals/schools, 1.3× on highways).
- **Auto-Deduplication** — Reports within 10 m radius of the same hazard type automatically merge with an updated counter.
- **Ranked Repair Queue** — Dense, filterable table with bulk actions, status transitions, and CSV exports.
- **Backend-Enforced RBAC** — Admin, Officer, Citizen, Guest roles with internal checks inside `core/db.py`.
- **Immutable Audit Trail** — Tracks every login, denied action, upload, merge, assignment, and export.
- **Plotly Analytics Dashboard** — Issues by type, severity splits, status funnels, resolution times, and regional hotspot bars.

---

## Google Gemini Hybrid Integration

UrbanLens features a hybrid intelligence architecture:

| Component | Responsibility |
|---|---|
| **YOLOv8** | High-speed, local computer vision detector for spatial bounding boxes and measured confidence. |
| **Google Gemini** | Deep visual reasoning: hazard confirmation, public safety impact analysis, repair action recommendations, natural-language search translation, and bilingual summaries. |
| **Scoring Formula** | **"Gemini advises, the formula decides."** Severity and priority remain 100% deterministic in code. |

### Hybrid Detector Modes (`DETECTOR` in `core/config.py`):
1. **`hybrid` (Default):** Runs YOLOv8 first. Gemini provides qualitative assessment, verifies hazard existence, and adds extra classes (e.g. streetlights) missed by YOLO.
2. **`gemini`:** Uses Gemini vision reasoning directly with normalized bounding boxes. Confidence is documented as `gemini_estimate` ($0.50$).
3. **`yolo`:** Local offline YOLOv8 mode. Zero external network calls required.

### Gemini API Key Configuration
Create a free Gemini API key at [Google AI Studio](https://aistudio.google.com/apikey).
Add it to `.streamlit/secrets.toml` or set an environment variable:
```toml
# .streamlit/secrets.toml
GEMINI_API_KEY = "your_gemini_api_key_here"
GEMINI_MODEL = "gemini-2.5-flash"
DETECTOR = "hybrid"
```
*Note: Both `.streamlit/secrets.toml` and `.env` are excluded by `.gitignore`.*

### Data Privacy & Offline Graceful Degradation
- If no Gemini key is configured or the internet is offline, UrbanLens gracefully switches to offline YOLO mode with clear "AI assessment unavailable" banners. Deterministic scoring is never disrupted.
- Image text is treated strictly as passive data to prevent prompt injection.

---

## Interactive Map & Geospatial Kit

UrbanLens uses **100% free, key-less geospatial libraries and tile servers**:

- **Engine:** Folium (Leaflet) + `streamlit-folium` + Branca.
- **Base Layers (Switchable via Layer Control in top right):**
  - **Light (Default):** CARTO Positron (`https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png`)
  - **Streets:** OpenStreetMap Standard (`https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`)
  - **Dark:** CARTO Dark Matter (`https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png`)
  - **Satellite (Optional):** Esri World Imagery (`https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/...`)
- **Attribution & Usage Terms:** All tile layers include legal attribution links (`OpenStreetMap contributors`, `CARTO`, `Esri`). Review tile provider terms for high-volume or commercial usage.
- **Nominatim Reverse Geocoding Policy:** Identified with custom User-Agent in `config.py`, cached in SQLite `geo_cache`, with a strict 1 request/second rate limiter.
- **Marker Styling & XSS Safety:** Circle markers colored by severity with radius scaled by priority (6 to 16 px); interactive popups with embedded base64 thumbnails and HTML-escaped text.
- **Toggles:** Dynamic Marker Clustering (`MarkerCluster`, auto-enabled when > 40 issues), Priority Heatmap (`HeatMap`), and Simple Scatter View fallback for slow connections.
- **Click-to-Pick Geotagging:** Draggable / click-to-pick interactive pin on the Report Issue page synced with coordinate inputs and nearest landmark multiplier feedback.
- **Custom City & Wards:** To customize, edit `DEFAULT_LAT`, `DEFAULT_LON`, and `DEFAULT_CITY` in `core/config.py`. Optional ward boundary polygons can be placed at `data/wards.geojson`.

---

## Demo Credentials

| Role    | Username  | Password    | Permissions & Capabilities |
|---------|-----------|-------------|----------------------------|
| **Admin**   | `admin`     | `admin123`    | Full system access, Audit Log, User & Role Management, Weekly Briefs |
| **Officer** | `officer1`  | `officer123`  | Repair Queue, Status Updates & Assignment, Ask UrbanLens Assistant, Analytics |
| **Officer** | `officer2`  | `officer123`  | Repair Queue, Status Updates & Assignment, Ask UrbanLens Assistant, Analytics |
| **Citizen** | `citizen1`  | `citizen123`  | Report an Issue, My Reports with order-tracking timeline |
| **Guest**   | *(Click "Continue as Guest")* | N/A | Read-only public map and aggregate issue counters |

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/urvashimisal126-bot/ProjectX.git
cd ProjectX

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run Unit Tests (16/16 passing)
python test_core.py
python test_gemini.py

# 4. Start UrbanLens (Auto-seeds on first start)
python -m streamlit run app.py
```

Open **[http://localhost:8501](http://localhost:8501)** in your browser.

---

## Live Smoke Test Script
To run an automated connectivity, parsing, and structured output test of your Gemini configuration:
```bash
python scripts/test_gemini.py
```

---

## Docker

```bash
docker build -t urbanlens .
docker run -p 8501:8501 urbanlens
```

---

## Deploy to Streamlit Community Cloud

1. Push this repository to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your repository.
3. Set **Main file path** to `app.py`.
4. In Advanced Settings, add `GEMINI_API_KEY = "..."` under Secrets.
5. `packages.txt` automatically handles OpenCV system libraries (`libgl1-mesa-glx`, `libglib2.0-0`).

---

## Project Structure

```
urbanlens/
├── app.py                  # Entry point, login gate, role-based navigation
├── test_core.py            # Core engine unit tests (7/7 passing)
├── test_gemini.py          # Gemini & hybrid unit tests (9/9 passing)
├── seed.py                 # DB initialization and Indore seed dataset
├── Dockerfile              # Container deployment
├── requirements.txt        # Pinned dependencies
├── packages.txt            # System dependencies for cloud deployment
├── core/
│   ├── ai_assess.py        # Gemini vision assessment, bilingual summaries, weekly brief
│   ├── gemini_client.py    # Google GenAI SDK wrapper, caching, exponential backoff
│   ├── auth.py             # Bcrypt hashing & session security
│   ├── db.py               # SQLite storage + internal RBAC check enforcement
│   ├── detect.py           # Hybrid YOLOv8 + Gemini detection engine
│   ├── geo.py              # EXIF GPS parser & Indore landmark proximity lookup
│   ├── score.py            # Explainable severity & priority formulas
│   ├── dedupe.py           # 10 m Haversine spatial duplicate merger
│   ├── audit.py            # Immutable system audit trail & timeline helpers
│   ├── notify.py           # Optional SMTP notification dispatcher
│   └── config.py           # Thresholds, landmarks, Gemini models, detector modes
├── ui/
│   ├── theme.py            # CSS injection, color tokens, responsive styling
│   └── components.py       # KPI cards, badges, AI assessment cards, order stepper
├── pages/
│   ├── login.py            # Login portal with demo chips & guest bypass
│   ├── overview.py         # Role-personalized operational dashboard
│   ├── assistant.py        # "Ask UrbanLens" natural-language query assistant
│   ├── report.py           # Hybrid issue upload, detection, and AI assessment
│   ├── map.py              # Interactive CartoDB Folium map
│   ├── queue.py            # Ranked repair queue with bulk actions & CSV export
│   ├── issue_detail.py     # Deep inspection, bilingual summaries, order timeline
│   ├── analytics.py        # Civic charts and executive weekly brief generator
│   ├── my_reports.py       # Citizen order-tracking views
│   ├── audit_log.py        # Admin searchable audit log with CSV export
│   └── users.py            # Admin user and role management console
├── scripts/
│   └── test_gemini.py      # Live Gemini test and diagnostic utility
└── assets/
    ├── logo.png            # UrbanLens brand mark
    └── icon.png            # Favicon and navigation icon
```

---

## Roadmap
- MFA / OTP authentication for field officers.
- SMS / WhatsApp push notifications for citizen report updates.
- Fast, asynchronous WebSocket gateway for real-time fleet telematics.
- PostgreSQL / PostGIS backend adapter for multi-city scaling.
