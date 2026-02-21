import os
import logging
from celery import Celery
from celery.signals import worker_ready, worker_shutting_down, task_failure

logger = logging.getLogger(__name__)

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


# ==============================================================================
# WORKER LIFECYCLE SIGNALS
# ==============================================================================

@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    """Log when a Celery worker starts and is ready to accept tasks."""
    logger.info(f"Celery worker READY: {sender}")
    print(f"✅ Celery worker is READY and accepting tasks")


@worker_shutting_down.connect
def on_worker_shutdown(sig, how, exitcode, **kwargs):
    """Log graceful worker shutdown (e.g., during deploy)."""
    logger.warning(f"Celery worker SHUTTING DOWN: sig={sig}, how={how}, exitcode={exitcode}")
    print(f"⚠️ Celery worker shutting down (sig={sig})")


@task_failure.connect
def on_task_failure(sender, task_id, exception, args, kwargs, traceback, einfo, **kw):
    """Log every task failure for monitoring/alerting."""
    logger.error(
        f"TASK FAILED: {sender.name} | task_id={task_id} | error={exception}",
        exc_info=True
    )


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Diagnostic task — call from shell to verify Celery is running async."""
    import time
    print(f'Request: {self.request!r}')
    print(f'Worker hostname: {self.request.hostname}')
    print(f'Task ID: {self.request.id}')
    time.sleep(2)
    print(f'Debug task completed on worker: {self.request.hostname}')
