from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
import logging
import threading

logger = logging.getLogger(__name__)

# --- In-Memory Log Store (Compatibility with FastAPI logs polling) ---
recent_logs = []
logs_lock = threading.Lock()

class QueueHandler(logging.Handler):
    def emit(self, record):
        try:
            log_entry = {
                "timestamp": self.format(record),
                "message": record.getMessage(),
                "level": record.levelname,
            }
            with logs_lock:
                recent_logs.append(log_entry)
                if len(recent_logs) > 100:
                    recent_logs.pop(0)
        except Exception:
            self.handleError(record)

# Attach handler to root logger so we catch logs from Superscript, conversion, Gemini_version
_root_logger = logging.getLogger()
_compatibility_handler = QueueHandler()
_compatibility_handler.setFormatter(logging.Formatter('%(asctime)s', datefmt='%H:%M:%S'))
_root_logger.addHandler(_compatibility_handler)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Compatibility health check for the frontend.
    """
    return Response({"status": "ok", "service": "MLR Validator (Django DRF)"})

@api_view(['GET'])
@permission_classes([AllowAny])
def get_latest_logs(request):
    """
    Polls the latest logs for real-time feedback in UI.
    """
    with logs_lock:
        return Response({"logs": list(recent_logs)})

@api_view(['GET'])
@permission_classes([AllowAny])
def mongodb_status(request):
    """
    Compatibility check for MongoDB status.
    """
    return Response({
        "status": "connected",
        "message": "[Bypassed] Using SQLite for this phase",
        "collections": {
            "validation_results": 0,
            "validation_results_v2": 0
        }
    })
