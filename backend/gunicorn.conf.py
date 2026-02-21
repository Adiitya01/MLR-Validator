"""
Gunicorn Production Configuration for MLR Validator Backend

This replaces single-threaded `python manage.py runserver` with a production-grade
multi-worker WSGI server. Each worker is a separate OS process that can handle
requests independently — so one slow validation upload doesn't block other API calls.

Usage:
  gunicorn config.wsgi:application -c gunicorn.conf.py

Scaling Formula:
  workers = (2 * CPU_cores) + 1
  For Render standard plan (1 vCPU): 2*1 + 1 = 3 workers
  For Render pro plan (2 vCPU):      2*2 + 1 = 5 workers
"""

import os
import multiprocessing

# ==============================================================================
# SERVER SOCKET
# ==============================================================================
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"

# ==============================================================================
# WORKER PROCESSES
# ==============================================================================
# Each worker is a separate process that can handle 1 request at a time.
# Formula: (2 * num_cores) + 1
# Override with GUNICORN_WORKERS env var for different Render plans.
workers = int(os.getenv('GUNICORN_WORKERS', str((2 * multiprocessing.cpu_count()) + 1)))

# Use 'gthread' worker class for thread-based concurrency within each worker.
# This is ideal for I/O-bound apps (DB queries, API calls to Gemini).
# Each worker spawns multiple threads, so 3 workers × 4 threads = 12 concurrent requests.
worker_class = os.getenv('GUNICORN_WORKER_CLASS', 'gthread')

# Threads per worker (only relevant for gthread worker class)
threads = int(os.getenv('GUNICORN_THREADS', '4'))

# ==============================================================================
# WORKER LIFECYCLE
# ==============================================================================
# Restart workers after this many requests (prevents memory leaks)
max_requests = int(os.getenv('GUNICORN_MAX_REQUESTS', '500'))
# Add jitter so all workers don't restart at the same time
max_requests_jitter = int(os.getenv('GUNICORN_MAX_REQUESTS_JITTER', '50'))

# Kill a worker if it's been silent for 120 seconds
# (handles hung Gemini API calls in synchronous endpoints like /manual-review)
timeout = int(os.getenv('GUNICORN_TIMEOUT', '120'))

# Graceful shutdown: give workers 30s to finish current request before force-killing
graceful_timeout = int(os.getenv('GUNICORN_GRACEFUL_TIMEOUT', '30'))

# Time to wait for worker to boot up before considering it failed
worker_tmp_dir = '/dev/shm'  # Use shared memory for faster worker heartbeats

# ==============================================================================
# LOGGING
# ==============================================================================
accesslog = os.getenv('GUNICORN_ACCESS_LOG', '-')  # '-' = stdout
errorlog = os.getenv('GUNICORN_ERROR_LOG', '-')     # '-' = stderr
loglevel = os.getenv('GUNICORN_LOG_LEVEL', 'info')

# Log format: timestamp, method, URL, status, response time (ms)
access_log_format = '%(t)s "%(r)s" %(s)s %(b)s "%(f)s" %(L)ss'

# ==============================================================================
# PRELOADING
# ==============================================================================
# Preload app before forking workers — saves memory via copy-on-write.
# Each worker shares the Django app code in memory instead of loading it separately.
preload_app = True

# ==============================================================================
# HOOKS (for observability)
# ==============================================================================
def on_starting(server):
    """Called when Gunicorn master process starts."""
    print(f"🚀 Gunicorn starting with {server.cfg.workers} workers, {server.cfg.threads} threads each")
    print(f"   Max concurrent requests: {server.cfg.workers * server.cfg.threads}")


def post_fork(server, worker):
    """Called after a worker is forked."""
    print(f"   ✅ Worker {worker.pid} spawned")


def worker_exit(server, worker):
    """Called when a worker exits."""
    print(f"   ⚠️ Worker {worker.pid} exited")
