# 🔍 UrbanLens

**Seeing what the city needs fixed.**

UrbanLens is an open-source AI system that detects, classifies and prioritizes public infrastructure issues (potholes, damaged roads, broken streetlights, overflowing drains) from photos or video, and turns them into a **ranked, geotagged repair queue**.

Built for **Hacktoberfest '26** (AITR ACM x MLH) · Problem Statement 1: *AI-Powered Public Infrastructure Monitoring*

![demo](docs/demo.gif)
<!-- Replace with your demo GIF -->

**Live demo:** `<Streamlit Cloud URL>`

---

## 🚨 The Problem
Infrastructure issues are reported late or never. Reports are vague, duplicates pile up, and crews fix what is complained about loudest, not what is most dangerous. Detection, classification and prioritization are manual, slow and inconsistent.

**Who is affected:** commuters, pedestrians, residents, municipal staff and city budgets.

## 💡 Our Solution
Upload a photo or clip → AI detects the issue → severity and priority are scored → duplicates are merged → issues appear on a map and a ranked repair queue.

| Today | With UrbanLens |
|---|---|
| Days or weeks to notice | Detection in seconds |
| Manual site verification | Photo evidence plus GPS |
| Guesswork priority | Transparent scoring formula |
| Duplicate complaints | Auto-merged by location |

## ✨ Features
- 📷 Image and video upload
- 🤖 YOLOv8 damage detection and classification
- 📊 Severity score (Low / Medium / High)
- 📍 GPS from EXIF with manual location fallback
- 🗺️ Interactive map dashboard with colour-coded pins
- 📋 Priority-ranked repair queue
- 🏫 Location risk boost (schools, hospitals, highways)
- 🔁 Duplicate merging (same class within ~10 m)
- ✅ Status tracking: Reported → Assigned → Fixed
- 📥 CSV export
- 🔐 Role-based access (Admin, Officer, Citizen, Guest) with a personalised dashboard per role
- 🛡️ Permissions enforced in the backend, not just hidden in the UI
- 🧾 Audit log and an order-tracking style status timeline per issue
- 🔎 Drill-down filters by type, severity, status and date
- ⚡ Live dashboard refresh without a page reload
- 📈 Charts: issues by type, severity split, resolved over time
- ✉️ Optional email alert for High-severity issues
- ☁️ Cloud deployment

## 🏗️ Architecture
```
Login (auth.py, RBAC) → Streamlit UI → detect.py (YOLOv8) → geo.py (EXIF/GPS) → score.py → dedupe.py → db.py (SQLite, permission checks) → audit.py → Role-based dashboard (live refresh)
```

## 🧰 Tech Stack
Python · Streamlit · Ultralytics YOLOv8 · SQLite · Folium · Plotly · Pillow · OpenCV · pandas

## 🚀 Quick Start
```bash
git clone https://github.com/<your-username>/urbanlens.git
cd urbanlens
pip install -r requirements.txt
python seed.py        # creates demo users and sample issues
streamlit run app.py
```
Place model weights at `models/best.pt` (see [Model](#-model)).

**Docker (optional):**
```bash
docker build -t urbanlens .
docker run -p 8501:8501 urbanlens
```

## 👤 Roles and Demo Accounts

| Role | What they can do |
|---|---|
| **Admin** | Everything: manage users, view audit log, analytics, export |
| **Officer (Editor)** | View queue, filter, assign and update status, export |
| **Citizen (Viewer)** | Report issues, track own reports on a status timeline |
| **Guest** | Read-only public map |

Demo logins are created by `seed.py` (usernames and passwords: `<fill in>`). Change them before any real deployment.

## 📁 Project Structure
```
urbanlens/
├── app.py            # Streamlit UI
├── detect.py         # YOLOv8 inference
├── geo.py            # EXIF GPS and location helpers
├── score.py          # Severity and priority scoring
├── dedupe.py         # Haversine duplicate merge
├── db.py             # SQLite operations with permission checks
├── auth.py           # Login and role-based access control
├── audit.py          # Audit log and status timeline
├── seed.py           # Demo users and sample issues
├── config.py         # Thresholds and weights
├── models/           # best.pt
├── data/             # sample images, issues.db
├── docs/             # PRD, demo GIF
├── requirements.txt
├── CONTRIBUTING.md
└── LICENSE
```

## 🧠 Model
- Base: pretrained YOLOv8n/s, fine-tuned on public road-damage and pothole datasets.
- Classes: pothole + <add your classes>. More classes are easy to add (see Contributing).
- Training notebook: `notebooks/train.ipynb` (Google Colab).
- Metrics: mAP@0.5 = `<fill in>` · Precision = `<fill in>` · Recall = `<fill in>`

## 📐 Scoring Logic
```
severity = 0.5 * norm(area_ratio) + 0.3 * confidence + 0.2 * norm(count)
priority = severity * location_multiplier * (1 + 0.1 * (report_count - 1))
```
Location multiplier: school/hospital = 1.5, highway = 1.3, default = 1.0. Weights live in `config.py`.

## 🗃️ Datasets
- RDD2022 (road damage) — `<link>`
- Pothole dataset — `<link>`

Check each dataset's license before reuse.

## 🤝 Contributing
We welcome contributions. Good first issues:
- Add a new class (cracks, waterlogging, garbage)
- Add a new dataset or improve accuracy
- Tune the scoring weights
- Add unit tests
- Add a Hindi UI

See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

## 🛣️ Roadmap
- Multi-factor authentication (OTP), verification and password-reset emails
- SMS and mobile push notifications
- FastAPI + Socket.IO backend and React frontend with Kanban drag-drop
- PostgreSQL on cloud for persistent storage
- Real-time CCTV, dashcam and drone feeds
- Mobile app for citizen reporting
- Municipal portal integration
- Predictive maintenance and hotspot analytics
- Privacy blurring for faces and number plates

## ⚠️ Limitations
- Accuracy depends on training data; some classes have limited data.
- Photos without GPS need a manual location.
- Scoring weights are heuristic and should be tuned with real municipal data.
- Live refresh uses periodic updates over Streamlit's WebSocket, not a custom WebSocket server.
- Demo authentication has no MFA or password reset yet.
- SQLite data resets on some cloud redeploys; `seed.py` restores the demo data.

## 👥 Team
- `<Name>` — `<role>` · [GitHub](https://github.com/)
- `<Name>` — `<role>` · [GitHub](https://github.com/)

## 📄 License
Released under the [MIT License](LICENSE).

## 🙏 Acknowledgements
AITR ACM, ACM-W, ACM SIGAI, Major League Hacking, Ultralytics, and the open datasets used.
