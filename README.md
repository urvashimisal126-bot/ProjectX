# UrbanLens

> **Seeing what the city needs fixed.**

UrbanLens is an open-source AI system for municipal teams. It detects, classifies and prioritizes public infrastructure issues — potholes, road damage, broken streetlights, overflowing drains — from photos or video, geotags them, merges duplicates, and displays a ranked repair queue on a live, role-based dashboard with a full audit trail.

Built for **Hacktoberfest '26** (AITR ACM × MLH) · *Best Open-Source AI Project — Problem Statement 1: AI-Powered Public Infrastructure Monitoring*

---

## Features

- **AI Detection** — YOLOv8 on uploaded images or video; falls back to Demo Mode if no custom model is present
- **Smart Scoring** — severity from area coverage, confidence and detection count; priority multiplied by location type (school/hospital/highway)
- **Auto-Deduplication** — same issue within 10 m is merged; report count tracked
- **Live Map** — CartoDB Positron basemap, severity-colored markers, image popups
- **Repair Queue** — ranked, filterable table with inline status updates and CSV export
- **Role-Based Access** — Admin, Officer, Citizen, Guest — enforced in the DB layer, not just the UI
- **Audit Trail** — every login, upload, assignment, merge, and export logged
- **Analytics** — issue trends, severity split, status funnel, time-to-fix, hotspot chart
- **Comments** — threaded comments on each issue, visible to all permitted users
- **Optional Email** — SMTP alert to admins for High-severity issues

---

## Demo Credentials

| Role    | Username  | Password    |
|---------|-----------|-------------|
| Admin   | admin     | admin123    |
| Officer | officer1  | officer123  |
| Officer | officer2  | officer123  |
| Citizen | citizen1  | citizen123  |

A "Continue as Guest" option is available on the login page (read-only public map).

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/urvashimisal126-bot/ProjectX.git
cd ProjectX

# 2. Install
pip install -r requirements.txt

# 3. Run (DB and seed created automatically on first launch)
streamlit run app.py
```

Open http://localhost:8501 in your browser.

---

## Docker

```bash
docker build -t urbanlens .
docker run -p 8501:8501 urbanlens
```

---

## Deploy to Streamlit Community Cloud

1. Push this repository to GitHub (public or private).
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your repo.
3. Set **Main file path** to `app.py`.
4. The `packages.txt` file handles system dependencies (OpenCV).

---

## Custom Model

Place your YOLOv8 weights at `models/best.pt`. The app detects the file automatically and exits Demo Mode. The class list is configured in `core/config.py` (`ISSUE_CLASSES`).

---

## Project Structure

```
urbanlens/
├── app.py                  # Entry point, login gate, navigation
├── pages/                  # One file per page
├── core/
│   ├── auth.py             # Login, session, role checks
│   ├── db.py               # All DB access + RBAC enforcement
│   ├── detect.py           # YOLOv8 inference
│   ├── geo.py              # EXIF GPS, haversine, location lookup
│   ├── score.py            # Severity + priority scoring
│   ├── dedupe.py           # Haversine merge
│   ├── audit.py            # Audit log helpers
│   ├── notify.py           # Optional SMTP email
│   └── config.py           # Weights, thresholds, landmarks
├── ui/
│   ├── theme.py            # CSS injection, color tokens
│   └── components.py       # KPI cards, badges, timeline, header
├── assets/                 # logo.png, icon.png
├── models/                 # best.pt (custom weights)
├── data/samples/           # Placeholder annotated images
├── seed.py                 # Demo data seeder
├── requirements.txt
├── packages.txt            # System deps for Streamlit Cloud
└── Dockerfile
```

---

## Role Permissions

| Action               | Admin | Officer | Citizen | Guest |
|----------------------|-------|---------|---------|-------|
| View public map      | Y     | Y       | Y       | Y     |
| Upload a report      | Y     | Y       | Y       | N     |
| View repair queue    | Y     | Y       | Own     | N     |
| Assign / set status  | Y     | Y       | N       | N     |
| View analytics       | Y     | Y       | N       | N     |
| View audit log       | Y     | N       | N       | N     |
| Manage users         | Y     | N       | N       | N     |
| Export CSV           | Y     | Y       | N       | N     |

All permissions are enforced in `core/db.py` — UI hiding is convenience only.

---

## Optional Email

Set these environment variables to enable SMTP notifications:

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@email.com
SMTP_PASS=your_app_password
```

If not set, email is silently skipped with no broken UI.

---

## Roadmap

- MFA / OTP login
- SMS and push notifications
- FastAPI backend + WebSocket live updates
- Kanban drag-and-drop repair board
- PostgreSQL for production scale
- Mobile-responsive PWA

---

## License

MIT — see [LICENSE](LICENSE)
