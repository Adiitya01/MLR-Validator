# MLR_AG Project Structure & File Guide

This document provides a comprehensive overview of the files in the project, explaining their role in the MVT (Model-View-Template) architecture and the overall system.

## 📂 Backend (`/backend`)
The backend is built with **Django** and **Django REST Framework (DRF)**. It handles API requests, database interactions, authentication, and background processing.

### 🔹 Configuration (`/backend/config`)
| File | Description |
| :--- | :--- |
| `settings.py` | **The Brain.** Contains all global settings: installed apps, database config (SQLite/Redis), Middleware (CORS), JWT settings, and Celery broker URL. |
| `urls.py` | **The Traffic Controller.** The main entry point for all URL routing. It directs incoming requests to the appropriate app (`authentication` or `validator`). |
| `wsgi.py` / `asgi.py` | Entry points for web servers (WSGI for synchronous, ASGI for asynchronous like WebSockets). |

### 🔹 Authentication App (`/backend/authentication`)
Handles user signup, login, and token generation.
| File | Description |
| :--- | :--- |
| `models.py` | Defines the Custom `User` model (extending AbstractUser) to store email, full name, and password. |
| `views.py` | **The Logic.** Contains `SignupView` (creates users) and `LoginView`/`CustomTokenObtainPairView` (issues JWT tokens). |
| `serializers.py` | **The Translator.** Converts User models into JSON. Handles input validation for signup and formatting the login response (tokens + user info). |
| `urls.py` | Defines routes like `/api/auth/login/`, `/api/auth/signup/`. |

### 🔹 Validator App (`/backend/validator`)
The core business logic for the MLR validation pipeline.
| File | Description |
| :--- | :--- |
| `models.py` | Defines `ValidationJob`. Stores the status, results, error messages, and links the job to a User. **(The "Model" in MVT)** |
| `views.py` | **The customized Views.** `UploadValidationView` (handles file uploads & triggers Celery) and `ValidationJobDetailView` (fetches results). |
| `serializers.py` | Converts `ValidationJob` database records into detailed JSON responses for the frontend. |
| `tasks.py` | **Background Worker.** Defines the Celery task `run_validation_task` that runs the heavy AI pipeline asynchronously so the server doesn't freeze. |
| `validator.py` | **The Pipeline Controller.** Orchestrates the entire flow: Extraction -> Conversion -> Gemini Validation -> Scoring -> Saving to DB. |
| `urls.py` | Defines routes like `/upload/`, `/result/<id>/`, `/brochures/` (History). |
| `compatibility.py` | helper endpoints for health checks or legacy support. |

---

## 📂 Frontend (`/MLR_UI_React`)
The frontend is a **React** Single Page Application (SPA) built with **Vite**.

### 🔹 Core Logic (`/MLR_UI_React/src`)
| File | Description |
| :--- | :--- |
| `main.jsx` | The entry point that mounts the React app to the DOM. |
| `App.jsx` | **The Main Container.** Logic for polling job status, routing to different pages, and managing global state (like user login status). |
| `Router.jsx` | Defines the client-side routes (e.g., `/login`, `/dashboard`, `/history`) and protects them using `ProtectedRoute`. |
| `api.js` | **The Bridge.** A centralized service class that makes all HTTP requests (`fetch`) to the Backend API. Handles token attachment (Bearer Auth). |
| `websocket.js` | Utility for handling real-time WebSocket connections (currently unused/fallback to polling). |

### 🔹 Components (`/MLR_UI_React/src/components`)
| File | Description |
| :--- | :--- |
| `LoginForm.jsx` | Form for user login. Calls `api.js` to get tokens and saves them to `localStorage`. |
| `SignupForm.jsx` | Form for user registration. |
| `VerifyOTP.jsx` | UI for entering OTP (if email verification is enabled). |
| `ProtectedRoute.jsx` | A wrapper component that checks if a user is logged in. If not, it redirects them to `/login`. |
| `Sidebar.jsx` | The navigation menu sidebar. |

---

## 📂 Core AI Scripts (Root Directory)
These scripts contain the specialized logic for processing PDFs and interacting with LLMs. They are called by `backend/validator/validator.py`.

| File | Description |
| :--- | :--- |
| `Superscript.py` | **Extraction Logic.** Parses PDF files to extract text, footnotes, and superscript references using OCR or PDF libraries. |
| `conversion.py` | **Data Transformation.** Converts the extracted raw text into a structured DataFrame or format suitable for the LLM. |
| `Gemini_version.py` | **The Judge.** Contains the prompt engineering and API calls to Google Gemini to validate the claims against the references. |
| `mongo_db.py` | Handles connections to the MongoDB database (used for storing complex result JSONs). |
| `mongo_schema.py` | Defines data schemas/optimizations for MongoDB storage. |

---

## 🔄 Data Flow Summary
1.  **User** uploads PDF via **React** (`App.jsx` -> `api.js`).
2.  **Django** receives request at `UploadValidationView`.
3.  **Django** acts:
    *   Saves file to temp storage.
    *   Creates a `ValidationJob` record in DB (Status: "Processing").
    *   Queues a **Celery** task.
    *   Returns "Job Queued" to User.
4.  **Celery Worker** picks up the task (`tasks.py`):
    *   Calls `validator.py`.
    *   `validator.py` uses `Superscript.py` to extract text.
    *   `validator.py` uses `Gemini_version.py` to validate claims.
    *   Updates `ValidationJob` to "Completed" with results.
5.  **React** polls endpoint (`ValidationJobDetailView`).
6.  **Django** returns JSON results.
7.  **React** displays the Validation Report.
