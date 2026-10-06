# UrbanLens: Product Requirements Document

**Tagline:** Seeing what the city needs fixed.
**Event:** Hacktoberfest '26 (AITR ACM x MLH), 6 Oct 2026
**Problem Statement:** PS1, AI-Powered Public Infrastructure Monitoring
**Team size:** 2 | **Build window:** 10:00 AM to 3:00 PM (5 hours)
**License:** MIT | **Status:** v0.2 (hackathon MVP + peer-learning features)

---

## 1. Overview
UrbanLens is an open-source AI system that automatically detects, classifies and prioritizes public infrastructure issues (potholes, damaged roads, broken streetlights, overflowing drains) from photos or video. It converts scattered, late and unverified complaints into a **ranked, evidence-backed repair queue** shown on a geotagged map dashboard.

## 2. Problem Statement
Infrastructure issues are reported late or never. Reports are vague (no photo, location or severity), duplicates flood the system, and repair crews work first-come-first-served instead of by danger. Detection, classification and prioritization are manual, slow and inconsistent.

**Impact of the problem:** accidents and vehicle damage, unsafe dark streets, waterlogging and disease, wasted inspection visits, and small damage growing into expensive reconstruction.

## 3. Goals and Non-Goals

### Goals
- G1: Detect and classify infrastructure issues from an image or video automatically.
- G2: Score severity and priority consistently with a transparent formula.
- G3: Geotag issues and show them on an interactive map with a ranked repair queue.
- G4: Ship as a clean, runnable, contributor-friendly open-source repo.
- G5: Provide role-based dashboards (Admin, Officer, Citizen/Guest) with permissions enforced in the backend.
- G6: Keep an audit trail and an order-tracking style status timeline for every issue.
- G7: Update dashboards live without page refresh and deploy to the cloud.

### Non-Goals (for this version)
- Real-time CCTV or drone streaming.
- MFA/OTP, verification and password-reset emails, SMS/mobile push (roadmap).
- Custom WebSocket server or separate React frontend (live refresh uses Streamlit's built-in WebSocket).
- Mobile app.
- Integration with real municipal systems.
- Training a model from scratch.
- Detecting all four classes at high accuracy (2 to 3 classes done well; the rest are marked extensible).

## 4. Users and Personas

| Persona | Need | How UrbanLens helps |
|---|---|---|
| **Citizen / commuter** | Report a problem quickly with proof | Upload a photo and get an instant detection and location pin |
| **Municipal officer** | Know what to fix first and where | Ranked repair queue with evidence |
| **Maintenance crew** | Clear, actionable job list | Map view plus issue type, severity and status |
| **City planner** | Spot hotspots for budgeting | Issue clusters on the map, CSV export |

**Role mapping:** Admin = municipal admin/planner, Editor = Officer/crew lead, Viewer = Citizen, Guest = public read-only map.

## 5. User Stories
1. As a citizen, I upload a photo so that the issue is detected and logged without writing a complaint.
2. As an officer, I see issues ranked by priority so that urgent ones are fixed first.
3. As an officer, I see duplicate reports merged so that I don't send crews twice.
4. As a crew member, I open the map to find where issues are and what type they are.
5. As an officer, I update an issue's status so that progress is tracked.
6. As a planner, I export the queue to CSV for reports.
7. As a contributor, I run the project with one command and add a new class or dataset easily.
8. As an Admin, I manage roles and see every user action in an audit log.
9. As an Officer, I filter issues by type, severity, status and date to focus on what matters.
10. As a Citizen, I track my reported issue like an order: Reported, Assigned, Fixed, with timestamps.
11. As any user, I see the dashboard update live without refreshing the page.

## 6. Scope and Features

| # | Feature | Description | Priority |
|---|---|---|---|
| F1 | Image/video upload | Upload photo or short clip via web UI | Must |
| F2 | AI damage detection | Fine-tuned YOLOv8 draws boxes with confidence | Must |
| F3 | Issue classification | Label by type (pothole + 1 to 2 other classes) | Must |
| F4 | Severity score | Formula from box size, confidence, count; Low/Med/High | Must |
| F5 | Location tagging | GPS from EXIF, manual lat/long fallback | Must |
| F6 | Map dashboard | Colour-coded pins by severity (Folium) | Must |
| F7 | Priority repair queue | Ranked table with photo, type, location, score | Must |
| F8 | Location risk boost | Higher priority near school, hospital, highway | Should |
| F9 | Duplicate merging | Same class within ~10 m merged, report count kept | Should |
| F10 | Status tracking | Reported, Assigned, Fixed | Should |
| F11 | Explainability | Confidence breakdown or Grad-CAM heatmap | Could |
| F12 | Auto summary | One-line plain-language report per issue | Could |
| F13 | CSV export | Download repair queue | Could |
| F14 | Open-source package | License, README, CONTRIBUTING, good first issues | Must |
| F15 | Role-Based Access Control | Admin, Officer (Editor), Citizen (Viewer), Guest; personalised dashboard per role | Should |
| F16 | Backend enforcement | Permission checks inside `db.py`, not just hidden buttons | Should |
| F17 | Audit log and status timeline | Logs every action; order-tracking style timeline per issue | Should |
| F18 | Drill-down filters | Filter by type, severity, status, date; click a pin for issue detail | Should |
| F19 | Live dashboard | Auto-refresh of map, queue and charts without page reload | Should |
| F20 | Rich visualization | Map, issues by type, severity split, resolved-over-time (success graph) in one page | Should |
| F21 | Cloud deployment | Public URL on Streamlit Community Cloud or Hugging Face Spaces | Should |
| F22 | Email alert | One SMTP email when a High-severity issue is logged | Could |
| F23 | Smooth UX | Drag-drop upload and `st.cache_data` caching | Could |

**Cut line:** if behind at 12:00 PM, ship F1 to F7 and F14.

**Add-on order (after F1 to F7 work):** F18 filters and F20 charts, then F15 + F16 RBAC, then F17 audit/timeline, then F19 live refresh, then F21 deploy. Drop F22 and F23 first if time is short.

### 6.1 Roles and Permissions (RBAC)

| Action | Admin | Officer (Editor) | Citizen (Viewer) | Guest |
|---|---|---|---|---|
| View public map | Yes | Yes | Yes | Yes |
| Upload a report | Yes | Yes | Yes | No |
| View full repair queue | Yes | Yes | Own reports only | No |
| Assign / change status | Yes | Yes | No | No |
| View audit log | Yes | No | No | No |
| Manage users and roles | Yes | No | No | No |
| Export CSV | Yes | Yes | No | No |

Permissions are checked inside backend functions (`db.py`), so a hidden button cannot be bypassed.

### 6.2 Audit Log and Status Timeline
- Every upload, status change, assignment, login and export writes a row to `audit_log` (user, role, action, issue id, timestamp).
- Each issue shows a Blinkit-style timeline: **Reported, Assigned, Fixed**, with time and actor for every step.

### 6.3 UI Pages by Role

| Page | Admin | Officer | Citizen | Guest |
|---|---|---|---|---|
| Login | Yes | Yes | Yes | Skip (guest mode) |
| Public map | Yes | Yes | Yes | Yes |
| Report an issue (upload) | Yes | Yes | Yes | No |
| My reports and timeline | Yes | Yes | Yes | No |
| Repair queue with filters | Yes | Yes | No | No |
| Analytics dashboard (charts) | Yes | Yes | No | No |
| Audit log and user management | Yes | No | No | No |

### 6.4 Live Updates
Streamlit already runs over WebSocket. A `st.fragment(run_every=3)` block refreshes the map, queue and charts every few seconds, so a status change made by an Officer appears on a Citizen's screen without a page reload.

### 6.5 Peer-Learning Feature Coverage

| Expected feature | Status in this build |
|---|---|
| 1, 2. Live updates, real-time dashboard | Done (auto-refresh over Streamlit WebSocket) |
| 3. Collaboration, notifications, success graph | Collaboration via shared DB; one email alert (Could); success graph done |
| 4. MFA, OTP, verification and reset emails | Roadmap |
| 5. Drill-down filters | Done |
| 6. RBAC with personalised dashboards | Done |
| 7. Audit logs and status tracking | Done |
| 8. Backend enforcement | Done |
| 9. Smooth UX (caching, drag-drop) | Partial: drag-drop upload and caching; no Kanban |
| 10. Rich visualization in one platform | Done |
| 11. Cloud deployment | Done (Streamlit Community Cloud) |

## 7. User Flow

**Today (manual):** damage appears, someone notices weeks later, complains, an official verifies on site, priority is guessed, crew assigned, repair often follows an accident.

**With UrbanLens:**
1. User uploads a photo or video.
2. Model detects and classifies issues.
3. System extracts GPS (EXIF) or takes a manual pin.
4. Severity and priority scores are computed.
5. Duplicates within 10 m and the same class are merged.
6. Issue is saved to the database.
7. Dashboard updates the map and ranked queue.
8. Officer assigns a crew and updates status.

## 8. Functional Requirements

| ID | Requirement |
|---|---|
| FR1 | The system shall accept JPG/PNG images and MP4 clips (clips sampled at 1 frame per second). |
| FR2 | The system shall return bounding boxes, class labels and confidence for each detection. |
| FR3 | Detections below a confidence threshold (default 0.40, adjustable) shall be discarded. |
| FR4 | The system shall compute a severity score and priority score per issue. |
| FR5 | The system shall read GPS from EXIF; if absent, prompt for manual lat/long or a map click. |
| FR6 | The system shall merge reports of the same class within 10 m and increment `report_count`. |
| FR7 | The system shall display issues on a map, colour-coded by severity. |
| FR8 | The system shall show a sortable repair queue (priority descending by default). |
| FR9 | The system shall allow status updates (Reported, Assigned, Fixed). |
| FR10 | The system shall export the queue as CSV. |
| FR11 | The system shall require login for Admin, Officer and Citizen roles and offer a read-only Guest mode. |
| FR12 | The system shall enforce permissions in backend functions for every write action. |
| FR13 | The system shall log every upload, status change, assignment, login and export to `audit_log`. |
| FR14 | The system shall show a per-issue status timeline with timestamps and actors. |
| FR15 | The system shall filter issues by type, severity, status and date range. |
| FR16 | The system shall auto-refresh the dashboard every few seconds without a page reload. |
| FR17 | The system shall optionally send an email when a High-severity issue is logged. |

## 9. Scoring Logic (transparent, no extra AI)

```
area_ratio  = box_area / image_area            (0 to 1, capped)
severity    = 0.5 * norm(area_ratio) + 0.3 * confidence + 0.2 * norm(count)
              -> Low < 0.35 | Medium 0.35-0.65 | High > 0.65

priority    = severity * location_multiplier * (1 + 0.1 * (report_count - 1))
location_multiplier: school/hospital = 1.5, highway = 1.3, default = 1.0
```
Weights are placeholders to tune during testing and are documented in `config.py`.

## 10. System Architecture

```
[Login + RBAC: auth.py]
        |
[Upload UI: Streamlit]
        |
[detect.py: YOLOv8 inference]
        |
[geo.py: EXIF GPS / manual pin]
        |
[score.py: severity + priority]
        |
[dedupe.py: haversine merge]
        |
[db.py: SQLite, permission checks enforced here]
        |
[audit.py: audit_log + status timeline]
        |
[Role-based dashboard: Folium map + ranked table + charts + filters, live refresh]
```

## 11. Tech Stack

| Layer | Choice |
|---|---|
| Frontend | Streamlit, streamlit-folium |
| Backend | Python modules called directly (optional FastAPI `/detect` as a stretch) |
| Database | SQLite |
| AI model | Ultralytics YOLOv8 (nano/small), fine-tuned in Google Colab |
| Helpers | Pillow (EXIF), haversine, pandas, OpenCV |
| Charts | Plotly |
| Auth and RBAC | Users and roles in SQLite, hashed passwords (hashlib/bcrypt) |
| Live updates | `st.fragment(run_every=...)` over Streamlit's WebSocket |
| Email (optional) | smtplib |
| Packaging | requirements.txt, optional Dockerfile |
| Deployment | Streamlit Community Cloud or Hugging Face Spaces |

## 12. Data Model: `issues` table

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| type | TEXT | pothole / streetlight / drain / road_damage |
| severity_score | REAL | 0 to 1 |
| severity_label | TEXT | Low / Medium / High |
| priority | REAL | Final ranking score |
| lat, lon | REAL | Location |
| location_type | TEXT | school / hospital / highway / default |
| image_path | TEXT | Annotated image |
| report_count | INTEGER | Default 1 |
| status | TEXT | Reported / Assigned / Fixed |
| assigned_to | TEXT | Officer username |
| reported_by | TEXT | Username of reporter |
| created_at | TEXT | ISO timestamp |

### `users` table

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| username | TEXT UNIQUE | Login name |
| password_hash | TEXT | Never store plain text |
| role | TEXT | admin / officer / citizen |

### `audit_log` table

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| user | TEXT | Who acted |
| role | TEXT | Role at the time |
| action | TEXT | upload / status_change / assign / login / export |
| issue_id | INTEGER | Nullable |
| detail | TEXT | e.g., "Reported to Assigned" |
| timestamp | TEXT | ISO timestamp |

## 13. Datasets and Model Plan
- **Datasets:** public pothole and road-damage sets (e.g., RDD2022, Kaggle/Roboflow pothole datasets). Streetlight and drain data are limited, so start with potholes plus the one class with the best available data.
- **Approach:** fine-tune pretrained YOLOv8n on 2 to 3 classes for about 30 to 50 epochs on Colab GPU.
- **Fallback:** if the model is not working by 12:00 PM, use a ready fine-tuned model from Roboflow/Hugging Face.
- **Metrics:** mAP@0.5 and precision/recall on a validation split; also report inference time per image.

## 14. Non-Functional Requirements
- **Performance:** under 3 seconds per image on CPU; under 15 seconds per 10-second clip.
- **Usability:** a new user completes upload to result in under 3 clicks.
- **Portability:** runs with `pip install -r requirements.txt && streamlit run app.py`.
- **Reliability:** graceful messages for missing GPS, no detections, or unsupported files.
- **Privacy:** no personal data stored; faces and number plates in images are not processed or logged (blurring listed as future work).
- **Maintainability:** modular files, type hints, short docstrings.
- **Security:** passwords hashed, permissions enforced in backend functions, every state change logged.
- **Freshness:** dashboard refreshes within about 3 seconds of a change.

## 15. Success Metrics

| Metric | Target (MVP) |
|---|---|
| End-to-end demo works (upload to map to queue) | Yes |
| Detection mAP@0.5 on chosen classes | 0.5 or higher (stretch: 0.65) |
| Classes supported | 2 to 3 |
| Time from upload to ranked result | Under 5 seconds |
| Repo checklist (license, README, CONTRIBUTING, issues) | 100% |
| Roles working with backend-enforced permissions | 3 roles plus Guest |
| Audit entry for every status change | 100% |
| Live dashboard refresh without page reload | Yes |
| Deployed public URL | Yes |

**Impact claims to present (illustrative, state assumptions):** detection in seconds vs. days to weeks, duplicates merged, crews dispatched in priority order.

## 16. Timeline (10:00 AM to 3:00 PM)

| Time | Task | Owner |
|---|---|---|
| 10:00 to 10:30 | Repo, license, README skeleton, datasets, roles | Both |
| 10:30 to 12:00 | Model fine-tune and test | A |
| 10:30 to 12:00 | Streamlit upload UI and DB | B |
| 12:00 to 1:00 | Scoring, EXIF/GPS, Folium map, queue | Both |
| 1:00 to 2:00 | Filters and charts, RBAC with backend checks, audit log and timeline, live refresh, duplicate merge | Both |
| 2:00 to 2:30 | Cloud deploy, README, demo GIF, CONTRIBUTING, good first issues | Both |
| 2:30 to 3:00 | Code freeze at 2:30, rehearse 2-minute demo | Both |

## 17. Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Model training fails or accuracy is poor | Medium | Use pretrained or Roboflow model; limit to 2 classes |
| Limited data for streetlight/drain | High | Do potholes well; mark other classes extensible |
| Images lack EXIF GPS | High | Manual lat/long and map-click fallback; prepare demo images with GPS |
| Colab or internet issues | Medium | Download weights and datasets early, keep a local fallback |
| Running out of time | High | Strict cut line at 12:00 PM; freeze code at 2:30 PM |
| Demo failure | Medium | Pre-load sample issues in the DB; keep a recorded demo GIF |
| Add-ons eat core time | High | Start add-ons only after F1 to F7 work; drop email and drag-drop first |
| SQLite resets on cloud redeploy | High | Seed demo users and issues on startup with `seed.py` |

## 18. Open-Source Plan (for "Best Open-Source AI Project")
- MIT license, clear README (problem, flow, architecture, how to run, demo GIF).
- `CONTRIBUTING.md` and a code of conduct.
- 4 to 5 "good first issue" tickets (add a class, add a dataset, improve scoring, add tests, Hindi UI).
- Clean commit history, `requirements.txt`, optional Dockerfile.
- Model weights and dataset links documented in the repo.

## 19. Demo Plan (2 minutes)
1. **Problem (20 s):** late, manual, unprioritized repairs.
2. **Live upload (30 s):** photo to detection boxes to severity.
3. **Dashboard (50 s):** log in as Officer, filter the queue, change a status, show it update live on the Citizen view, then open the audit log as Admin.
4. **Open source and impact (30 s):** repo, license, contribution path, time and cost saved.

**One-line pitch:** *"We turn scattered, late and unverified complaints into a ranked, evidence-backed repair queue."*

## 20. Future Scope
- Multi-factor authentication (OTP), verification and password-reset emails.
- SMS and mobile push notifications.
- FastAPI + Socket.IO backend and React frontend with Kanban drag-drop.
- PostgreSQL on cloud for persistent storage.
- Real-time CCTV, dashcam and drone feeds.
- Mobile app with citizen reporting and notifications.
- Integration with municipal complaint portals.
- Road-condition trends and predictive maintenance.
- Number-plate and face blurring for privacy.
- More classes (cracks, waterlogging, garbage, broken signage) and multilingual UI.

## 21. Assumptions and Dependencies
- Public datasets are available and licensed for use.
- Free Colab GPU is available during the event.
- Demo images either contain GPS or manual locations are acceptable.
- Both team members can access GitHub and have Python 3.10+ installed.
- Streamlit Community Cloud (or Hugging Face Spaces) is available for deployment.
