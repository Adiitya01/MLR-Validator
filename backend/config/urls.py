
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.conf import settings
from django.db import connection
import logging

logger = logging.getLogger(__name__)

def health_check(request):
    """
    Health check endpoint for Render auto-scaler and load balancer.
    Returns 200 if the service is healthy, 503 if critical services are down.
    """
    health = {
        "status": "healthy",
        "service": "mlr-backend",
        "celery_mode": "async" if not settings.CELERY_TASK_ALWAYS_EAGER else "sync (eager)",
        "checks": {}
    }
    
    # Check database connectivity
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        health["checks"]["database"] = "ok"
    except Exception as e:
        health["checks"]["database"] = f"error: {str(e)}"
        health["status"] = "degraded"
        logger.error(f"Health check - DB error: {e}")
    
    # Check Redis/Celery broker connectivity
    try:
        from config.celery import app as celery_app
        inspector = celery_app.control.inspect()
        # Don't block health check waiting for workers — just verify broker is reachable
        celery_app.connection().ensure_connection(max_retries=1, timeout=2)
        health["checks"]["broker"] = "ok"
    except Exception as e:
        health["checks"]["broker"] = f"error: {str(e)}"
        if not settings.CELERY_TASK_ALWAYS_EAGER:
            health["status"] = "degraded"
        logger.warning(f"Health check - Broker error: {e}")
    
    status_code = 200 if health["status"] == "healthy" else 503
    return JsonResponse(health, status=status_code)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', health_check, name='health-check'),
    path('api/auth/', include('authentication.urls')),
    path('api/validator/', include('validator.urls')),
    # Mount validator URLs at root for legacy frontend compatibility
    path('', include('validator.urls')),
]
