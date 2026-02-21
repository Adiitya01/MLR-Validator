"""
Django settings for config project.
"""

import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
import sys

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env from root directory
ROOT_DIR = BASE_DIR.parent
load_dotenv(ROOT_DIR / '.env')

# Ensure root and core directories are in sys.path for pipeline imports
CORE_DIR = BASE_DIR / 'core'
for path in [str(ROOT_DIR), str(CORE_DIR)]:
    if path not in sys.path:
        sys.path.append(path)

# Quick-start development settings - unsuitable for production
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-^@aglnsbh(ge6rf@dhmj9fzs&oos^&z540*1o48osxgz0)k(c@')
DEBUG = os.getenv('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = ["*"]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'rest_framework',
    'corsheaders',
    'django_celery_results',

    # Local apps
    'authentication',
    'validator',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # CORS must be high
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
# Using dj-database-url to parse the DATABASE_URL from .env
import dj_database_url

DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    # Handle the postgresql+psycopg2 scheme which dj-database-url doesn't like
    if 'postgresql+psycopg2' in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace('postgresql+psycopg2', 'postgres')
    
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600)
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'

# ==============================================================================
# CELERY CONFIGURATION (Production-Grade Async Processing)
# ==============================================================================

# --- Broker & Backend ---
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/1')
CELERY_RESULT_BACKEND = 'django-db'
CELERY_CACHE_BACKEND = 'default'

# --- Serialization ---
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# --- CRITICAL: Must be False in production for true async processing ---
# When True, tasks run synchronously inside the web process (blocks everything).
# Set to True ONLY for local development/testing without Redis.
CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_ALWAYS_EAGER', 'False') == 'True'

# --- Task Execution Limits ---
# Hard kill after 10 minutes (prevents zombie tasks from Gemini API hangs)
CELERY_TASK_TIME_LIMIT = int(os.getenv('CELERY_TASK_TIME_LIMIT', '600'))
# Soft warning at 8 minutes (gives task a chance to save partial results)
CELERY_TASK_SOFT_TIME_LIMIT = int(os.getenv('CELERY_TASK_SOFT_TIME_LIMIT', '480'))

# --- Worker Reliability ---
# Acknowledge AFTER task completes (not before). If a worker crashes mid-task,
# the task is re-delivered to another worker instead of being lost.
CELERY_TASK_ACKS_LATE = True
# Reject and re-queue tasks if worker is killed (e.g., during deploy)
CELERY_TASK_REJECT_ON_WORKER_LOST = True
# Each worker grabs only 1 task at a time (prevents one worker hoarding all AI jobs)
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# --- Broker Resilience ---
# If Redis broker goes down, keep retrying connection every 30 seconds
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_CONNECTION_MAX_RETRIES = None  # Retry forever
# If a task isn't ack'd within 12 minutes, make it visible to other workers
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'visibility_timeout': 720,  # 12 minutes (must be > TASK_TIME_LIMIT)
}

# --- Task Result Settings ---
CELERY_RESULT_EXPIRES = 60 * 60 * 24 * 7  # Keep results for 7 days
CELERY_TASK_TRACK_STARTED = True  # Track when tasks actually start running

# --- Concurrency (per worker process) ---
CELERY_WORKER_CONCURRENCY = int(os.getenv('CELERY_WORKER_CONCURRENCY', '2'))
CELERY_WORKER_MAX_TASKS_PER_CHILD = int(os.getenv('CELERY_MAX_TASKS_PER_CHILD', '50'))

# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]

# DRF Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '10/day',
        'user': '1000/day',
        'pipeline': '5/minute',  # Custom rate for expensive AI pipeline
    }
}

AUTH_USER_MODEL = 'authentication.User' 

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
}

