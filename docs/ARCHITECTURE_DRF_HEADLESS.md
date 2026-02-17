# MLR Validator — Headless DRF Architecture

## 1. What is "Headless DRF"?

**Headless** means the Django backend serves **only JSON APIs** — no templates, no server-rendered HTML.  
The React frontend (`MLR_UI_React`) is a completely separate application that talks to these APIs.

```
┌─────────────────────┐         JSON / REST          ┌──────────────────────┐
│                     │ ◄──────────────────────────► │                      │
│  React Frontend     │    (Bearer JWT Auth)          │  Django DRF Backend  │
│  (Vite, port 5173)  │                               │  (port 8000)         │
│                     │                               │                      │
└─────────────────────┘                               └──────────────────────┘
                                                              │
                                                              ▼
                                                     ┌──────────────────┐
                                                     │  Celery Worker   │
                                                     │  (Background)    │
                                                     └────────┬─────────┘
                                                              │
                                                     ┌────────▼─────────┐
                                                     │  Redis (Broker)  │
                                                     └──────────────────┘
```

---

## 2. Current State Analysis (What we have today)

### 2.1 The Problem: Two Backends
Right now the project has **two overlapping backends**:

| Component | Location | Role | Status |
|-----------|----------|------|--------|
| `app.py` (FastAPI) | Root `/` | **Primary** — all endpoints live here | ✅ Active, frontend connects here |
| `backend/` (Django DRF) | `backend/` | **Partial** — has models/serializers but mostly unused | ⚠️ Scaffolded but not production-ready |

The React frontend hits `http://localhost:8000` which is **FastAPI** (`app.py`).

### 2.2 Current FastAPI Endpoints (from `app.py`)

| Method | URL | Auth | Purpose |
|--------|-----|------|---------|
| `GET` | `/health` | ❌ | Health check |
| `GET` | `/` | ❌ | Root status |
| `GET` | `/mongodb-status` | ❌ | MongoDB ping (bypassed) |
| `GET` | `/logs/latest` | ❌ | Poll recent logs |
| `GET` | `/validation-history` | ❌ | List past validations (from JSON files) |
| `GET` | `/validation-results/{brochure_id}` | ❌ | Get full results for a job |
| `GET` | `/job-status/{job_id}` | ❌ | Poll background job status |
| `POST` | `/run-pipeline` | ❌ | Upload brochure + refs → start validation |
| `POST` | `/manual-review` | ❌ | Validate single statement vs PDFs |
| `POST` | `/signup` | ❌ | Create user (commented out / bypassed) |
| `POST` | `/login` | ❌ | Login (commented out / bypassed) |
| `GET` | `/me` | Bearer | Get current user (commented out) |
| `POST` | `/auth/send-otp` | ❌ | Send OTP email (commented out) |
| `POST` | `/auth/verify-otp` | ❌ | Verify OTP (commented out) |
| `WS` | `/ws/job/{job_id}` | ❌ | WebSocket for real-time job updates |

### 2.3 Current Frontend API Calls (from `api.js` + components)

| Frontend Component | Endpoint Hit | Method |
|---------------------|-------------|--------|
| `api.js` → `testConnection()` | `GET /health` | fetch |
| `api.js` → `getResults()` | `GET /validation-results/{id}` | fetch + Bearer |
| `api.js` → `checkJobStatus()` | `GET /job-status/{id}` | fetch + Bearer |
| `api.js` → `runPipeline()` | `POST /run-pipeline` | FormData + Bearer |
| `api.js` → `getBrochures()` | `GET /brochures` | fetch |
| `LoginForm.jsx` | `POST /login` | JSON body |
| `SignupForm.jsx` | `POST /signup` | JSON body |
| `VerifyOTP.jsx` | `POST /auth/send-otp`, `/auth/verify-otp` | JSON body |
| `History.jsx` | `GET /validation-history` | fetch + Bearer |
| `App.jsx` | `GET /me` | fetch + Bearer |
| `App.jsx` | `POST /manual-review` | FormData |

### 2.4 Core Pipeline Services (pure Python, framework-agnostic)

| File | Purpose | Key Functions |
|------|---------|---------------|
| `Superscript.py` | PDF extraction | `extract_footnotes()`, `extract_drug_superscript_table_data()` |
| `conversion.py` | Data transformation | `build_validation_dataframe()`, `build_validation_rows_special_case()` |
| `Gemini_version.py` | AI validation | `GeminiClient`, `StatementValidator`, `PDFProcessor` |
| `Manual_Review.py` | Manual review logic | `validate_manual_review()`, `validate_manual_review_multi()` |
| `mongo_schema.py` | Result optimization | `StorageOptimizer`, `ConfidenceScoringOptimizer` |
| `otp_service.py` | OTP logic | `generate_otp()`, `store_otp()`, `send_otp_email()`, `verify_otp_hash()` |

---

## 3. Target Architecture

### 3.1 High-Level Diagram

```
┌──────────────────────────────────────────────┐
│              REACT FRONTEND                   │
│         (MLR_UI_React, Vite)                  │
│                                               │
│  api.js → all calls to /api/*                 │
│  No changes to UI logic, styles, or routing   │
└───────────────────┬──────────────────────────┘
                    │ HTTP (JSON + FormData)
                    │ JWT Bearer Token
                    ▼
┌──────────────────────────────────────────────┐
│           DJANGO DRF BACKEND                  │
│       (backend/, manage.py runserver)          │
│                                               │
│  ┌─────────────┐   ┌──────────────────────┐  │
│  │ config/     │   │ authentication/       │  │
│  │  settings   │   │  models.py  (User)    │  │
│  │  urls.py    │   │  views.py   (JWT)     │  │
│  │  celery.py  │   │  serializers.py       │  │
│  │  wsgi.py    │   │  urls.py              │  │
│  └─────────────┘   └──────────────────────┘  │
│                                               │
│  ┌──────────────────────────────────────────┐ │
│  │ validator/                                │ │
│  │  models.py     (ValidationJob)            │ │
│  │  views.py      (Upload, Status, Results)  │ │
│  │  serializers.py                           │ │
│  │  tasks.py      (Celery async pipeline)    │ │
│  │  services.py   (Pipeline orchestration)   │ │
│  │  urls.py                                  │ │
│  └──────────────────────────────────────────┘ │
│                                               │
│  ┌──────────────────────────────────────────┐ │
│  │ services/ (SHARED PURE PYTHON)            │ │
│  │  pipeline.py   ← wraps Superscript,      │ │
│  │                   conversion, Gemini      │ │
│  │  manual_review.py  ← Manual_Review.py    │ │
│  │  otp.py            ← otp_service.py      │ │
│  └──────────────────────────────────────────┘ │
└───────────────────┬──────────────────────────┘
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
┌────────────────┐    ┌────────────────┐
│  Celery Worker │    │  Redis         │
│  (processes    │    │  (Broker +     │
│   pipeline     │    │   OTP cache)   │
│   tasks)       │    │                │
└────────────────┘    └────────────────┘
         │
         ▼
┌────────────────┐
│  SQLite / PG   │  ← user accounts + job metadata
│  (Django ORM)  │
└────────────────┘
```

### 3.2 Key Principles

1. **`app.py` is RETIRED** — Django `manage.py runserver` replaces it entirely
2. **All endpoints live under Django DRF** — no FastAPI dependency
3. **Pipeline logic is untouched** — `Superscript.py`, `conversion.py`, `Gemini_version.py` stay as-is; they're imported by Django services
4. **Frontend needs minimal changes** — only the base URL path prefix changes (all requests go through `/api/`)
5. **SQLite for dev, PostgreSQL for prod** — no MongoDB dependency for this phase
6. **Celery + Redis for background tasks** — same as current architecture
7. **JWT auth via SimpleJWT** — already configured in settings.py

---

## 4. Detailed URL Mapping

### 4.1 Django URL Structure

```python
# config/urls.py
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('authentication.urls')),
    path('api/validator/', include('validator.urls')),
]
```

### 4.2 Complete API Endpoint Map

#### Authentication (`/api/auth/`)

| Method | DRF URL | Frontend Calls | View |
|--------|---------|----------------|------|
| `POST` | `/api/auth/signup/` | `SignupForm.jsx` | `SignupView` |
| `POST` | `/api/auth/login/` | `LoginForm.jsx` | `LoginView` (SimpleJWT) |
| `POST` | `/api/auth/token/refresh/` | auto token refresh | `TokenRefreshView` |
| `GET` | `/api/auth/me/` | `App.jsx` | `UserMeView` |
| `POST` | `/api/auth/send-otp/` | `VerifyOTP.jsx` | `SendOTPView` |
| `POST` | `/api/auth/verify-otp/` | `VerifyOTP.jsx` | `VerifyOTPView` |

#### Validator (`/api/validator/`)

| Method | DRF URL | Frontend Calls | View |
|--------|---------|----------------|------|
| `GET` | `/api/validator/health/` | `api.js testConnection()` | `health_check` |
| `POST` | `/api/validator/run-pipeline/` | `api.js runPipeline()` | `RunPipelineView` |
| `GET` | `/api/validator/job-status/<uuid:id>/` | `api.js checkJobStatus()` | `JobStatusView` |
| `GET` | `/api/validator/results/<uuid:id>/` | `api.js getResults()` | `ValidationResultsView` |
| `GET` | `/api/validator/history/` | `History.jsx` | `ValidationHistoryView` |
| `POST` | `/api/validator/manual-review/` | `App.jsx` Manual Review | `ManualReviewView` |
| `GET` | `/api/validator/logs/latest/` | frontend polling | `get_latest_logs` |

#### Legacy Compatibility (Root-level redirects)

To avoid breaking the frontend during migration, we add **temporary root-level routes**:

| Legacy URL | Redirects To |
|------------|-------------|
| `/health` | `/api/validator/health/` |
| `/login` | `/api/auth/login/` |
| `/signup` | `/api/auth/signup/` |
| `/me` | `/api/auth/me/` |
| `/run-pipeline` | `/api/validator/run-pipeline/` |
| `/job-status/<id>` | `/api/validator/job-status/<id>/` |
| `/validation-results/<id>` | `/api/validator/results/<id>/` |
| `/validation-history` | `/api/validator/history/` |
| `/manual-review` | `/api/validator/manual-review/` |

---

## 5. Django App Structure (Target)

```
backend/
├── manage.py
├── config/
│   ├── __init__.py          ← imports celery app
│   ├── settings.py          ← DRF, SimpleJWT, Celery, CORS config
│   ├── urls.py              ← root URL dispatcher
│   ├── celery.py            ← Celery app definition
│   ├── wsgi.py
│   └── asgi.py
│
├── authentication/
│   ├── __init__.py
│   ├── models.py            ← User, OTPAudit (EXISTING ✅)
│   ├── serializers.py       ← SignupSerializer, TokenSerializer (EXISTING ✅)
│   ├── views.py             ← SignupView, LoginView, MeView (EXISTING ✅)
│   │                           + SendOTPView, VerifyOTPView (NEW ⚡)
│   ├── urls.py              ← (EXISTING ✅, add OTP routes)
│   └── services/
│       └── otp.py           ← (MOVE from root otp_service.py)
│
├── validator/
│   ├── __init__.py
│   ├── models.py            ← ValidationJob (EXISTING ✅)
│   ├── serializers.py       ← UploadSerializer, JobSerializer (EXISTING ✅, EXPAND ⚡)
│   ├── views.py             ← REWRITE ⚡ — RunPipelineView, JobStatusView,
│   │                           ValidationResultsView, ManualReviewView
│   ├── tasks.py             ← Celery task (EXISTING ✅, REFACTOR ⚡)
│   ├── services/
│   │   └── pipeline.py      ← (Extracted pipeline orchestration)
│   ├── compatibility.py     ← Legacy endpoint shims (EXISTING ✅)
│   └── urls.py              ← (EXISTING ✅, EXPAND ⚡)
│
└── services/                ← SHARED pure-Python logic (NO Django imports)
    ├── __init__.py
    ├── extraction.py        ← wraps Superscript.py
    ├── conversion.py        ← wraps conversion.py
    ├── validation.py        ← wraps Gemini_version.py
    └── manual_review.py     ← wraps Manual_Review.py
```

---

## 6. Data Flow: Run Pipeline

```
Frontend                    Django DRF                  Celery Worker
────────                    ──────────                  ─────────────
   │                            │                            │
   │  POST /api/validator/      │                            │
   │  run-pipeline/             │                            │
   │  (FormData + JWT)          │                            │
   ├───────────────────────────►│                            │
   │                            │ 1. Validate JWT            │
   │                            │ 2. Parse files             │
   │                            │ 3. Create ValidationJob    │
   │                            │    (status='uploaded')     │
   │                            │ 4. Save PDFs to temp dir   │
   │                            │ 5. Dispatch Celery task    │
   │   { job_id: "uuid" }      │────────────────────────────►
   │◄───────────────────────────│                            │
   │                            │                            │
   │                            │              6. Extract (Superscript.py)
   │                            │              7. Convert (conversion.py)
   │                            │              8. Validate (Gemini_version.py)
   │                            │              9. Score (mongo_schema.py)
   │  GET /api/validator/       │             10. Save results → DB
   │  job-status/<uuid>/        │              11. Update status='completed'
   │  (polling every 2s)        │                            │
   ├───────────────────────────►│                            │
   │   { state: "processing" } │                            │
   │◄───────────────────────────│                            │
   │         ...                │                            │
   │   { state: "completed" }  │                            │
   │◄───────────────────────────│                            │
   │                            │                            │
   │  GET /api/validator/       │                            │
   │  results/<uuid>/           │                            │
   ├───────────────────────────►│                            │
   │   { results: [...] }      │                            │
   │◄───────────────────────────│                            │
```

---

## 7. Implementation Phases

### Phase 1: Core DRF Backend (Priority: HIGH)
**Goal:** Replace `app.py` entirely with Django DRF

| # | Task | Files Changed |
|---|------|--------------|
| 1.1 | Update `config/settings.py` — add env-based config, update CORS | `config/settings.py` |
| 1.2 | Rewrite `validator/views.py` — `RunPipelineView`, `JobStatusView`, `ValidationResultsView`, `ManualReviewView` | `validator/views.py` |
| 1.3 | Expand `validator/serializers.py` — add `ManualReviewSerializer`, `JobStatusSerializer` | `validator/serializers.py` |
| 1.4 | Update `validator/urls.py` — add all endpoint routes | `validator/urls.py` |
| 1.5 | Refactor `validator/tasks.py` — import pipeline from root files correctly | `validator/tasks.py` |
| 1.6 | Update `config/urls.py` — add legacy compatibility routes | `config/urls.py` |

### Phase 2: Authentication (Priority: HIGH)
**Goal:** Full auth with Signup → Login → JWT → OTP verification

| # | Task | Files Changed |
|---|------|--------------|
| 2.1 | Add `SendOTPView` and `VerifyOTPView` to `authentication/views.py` | `authentication/views.py` |
| 2.2 | Move OTP service to `authentication/services/otp.py` | new file |
| 2.3 | Update `authentication/urls.py` with OTP routes | `authentication/urls.py` |
| 2.4 | Add legacy compatibility routes (`/login`, `/signup`, `/me`) | `config/urls.py` |

### Phase 3: Frontend Alignment (Priority: MEDIUM)
**Goal:** Point React frontend at DRF backend with minimal changes

| # | Task | Files Changed |
|---|------|--------------|
| 3.1 | Update `api.js` — change base URL paths to `/api/validator/` | `api.js` |
| 3.2 | Update `LoginForm.jsx` — `/api/auth/login/` | `LoginForm.jsx` |
| 3.3 | Update `SignupForm.jsx` — `/api/auth/signup/` | `SignupForm.jsx` |
| 3.4 | Update `VerifyOTP.jsx` — `/api/auth/send-otp/`, `/api/auth/verify-otp/` | `VerifyOTP.jsx` |
| 3.5 | Update `App.jsx` — `/api/auth/me/`, `/api/validator/manual-review/` | `App.jsx` |

### Phase 4: Polish & Cleanup (Priority: LOW)
**Goal:** Remove legacy code and test end-to-end

| # | Task |
|---|------|
| 4.1 | Remove `app.py` after DRF backend is fully tested |
| 4.2 | Remove standalone `database.py`, `security.py`, `schemas.py`, `db.py` |
| 4.3 | Update `requirements.txt` — remove `fastapi`, `uvicorn`; add `django`, `djangorestframework`, etc. |
| 4.4 | Update `.env` configuration for Django |
| 4.5 | Update deploy scripts (`render.yaml`, `DEPLOY_GUIDE.md`) |

---

## 8. Settings Configuration

```python
# config/settings.py — KEY CHANGES

import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv(os.path.join(Path(__file__).resolve().parent.parent.parent, '.env'))

# Security
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
DEBUG = os.getenv('DEBUG', 'True') == 'True'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Celery
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/1')
CELERY_RESULT_BACKEND = 'django-db'

# DRF
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

# SimpleJWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=24),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}

# CORS
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
]
```

---

## 9. Frontend Response Contract

The DRF backend must return responses in the **exact same JSON shape** that the React frontend expects. Here are the contracts:

### POST `/api/auth/login/`
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "John Doe"
  }
}
```

### POST `/api/auth/signup/`
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "John Doe"
  },
  "message": "User created successfully"
}
```

### POST `/api/validator/run-pipeline/`
```json
{
  "status": "success",
  "message": "Validation job started in background",
  "job_id": "uuid",
  "filename": "brochure.pdf"
}
```

### GET `/api/validator/job-status/<uuid>/`
```json
{
  "status": "success",
  "job_id": "uuid",
  "state": "processing" | "completed" | "failed",
  "filename": "brochure.pdf",
  "created_at": "2026-02-16T...",
  "message": "Job is processing"
}
```

### GET `/api/validator/results/<uuid>/`
```json
{
  "job_id": "uuid",
  "brochure_id": "uuid",
  "brochure_name": "brochure.pdf",
  "status": "completed",
  "results": [
    {
      "statement": "...",
      "reference_no": 1,
      "reference": "...",
      "matched_paper": "...",
      "matched_evidence": "...",
      "validation_result": "Supported",
      "page_location": "...",
      "confidence_score": 0.85,
      "matching_method": "...",
      "analysis_summary": "..."
    }
  ],
  "created_at": "2026-02-16T..."
}
```

### POST `/api/validator/manual-review/`
```json
{
  "status": "success",
  "result": {
    "statement": "...",
    "reference": "...",
    "validation_result": "Supported",
    "matched_evidence": "...",
    "page_location": "...",
    "confidence_score": 0.85,
    "analysis_summary": "..."
  }
}
```

### GET `/api/validator/history/`
```json
{
  "status": "success",
  "history": [
    {
      "brochure_id": "uuid",
      "filename": "brochure.pdf",
      "status": "completed",
      "created_at": "2026-02-16T..."
    }
  ]
}
```

---

## 10. How to Run (After Migration)

```bash
# Terminal 1: Django Backend
cd backend
python manage.py migrate
python manage.py runserver 0.0.0.0:8000

# Terminal 2: Celery Worker
cd backend
celery -A config worker --loglevel=info --pool=solo

# Terminal 3: Redis
redis-server

# Terminal 4: React Frontend
cd MLR_UI_React
npm run dev
```

---

## 11. Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Background tasks | **Celery + Redis** | Already configured, production-ready |
| Auth | **SimpleJWT** | Already in settings, industry standard |
| Database | **SQLite (dev) / PostgreSQL (prod)** | Django ORM handles both transparently |
| File storage | **Temp directory** | PDFs are transient, discarded after pipeline |
| Job results | **Django JSONField** | `ValidationJob.result_json` stores full results |
| Real-time updates | **Polling (GET /job-status/)** | Simpler than WebSockets for DRF, frontend already does this |
| CORS | **django-cors-headers** | Already installed and configured |

---

## Summary: Files to Change

| File | Action | Priority |
|------|--------|----------|
| `backend/config/settings.py` | UPDATE — env vars, paths | 🔴 Phase 1 |
| `backend/config/urls.py` | UPDATE — legacy compat routes | 🔴 Phase 1 |
| `backend/validator/views.py` | REWRITE — all validator views | 🔴 Phase 1 |
| `backend/validator/serializers.py` | EXPAND — ManualReview, JobStatus | 🔴 Phase 1 |
| `backend/validator/tasks.py` | REFACTOR — fix imports | 🔴 Phase 1 |
| `backend/validator/urls.py` | UPDATE — full route map | 🔴 Phase 1 |
| `backend/authentication/views.py` | EXPAND — OTP views | 🟡 Phase 2 |
| `backend/authentication/urls.py` | UPDATE — OTP routes | 🟡 Phase 2 |
| `MLR_UI_React/src/api.js` | UPDATE — API paths | 🟢 Phase 3 |
| `MLR_UI_React/src/components/LoginForm.jsx` | UPDATE — endpoint URL | 🟢 Phase 3 |
| `MLR_UI_React/src/components/SignupForm.jsx` | UPDATE — endpoint URL | 🟢 Phase 3 |
| `MLR_UI_React/src/components/VerifyOTP.jsx` | UPDATE — endpoint URLs | 🟢 Phase 3 |
