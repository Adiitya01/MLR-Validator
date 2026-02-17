from django.urls import path
from .views import (
    RunPipelineView, 
    JobStatusView, 
    ValidationResultsView, 
    ValidationHistoryView,
    ManualReviewView
)
from .compatibility import health_check, mongodb_status, get_latest_logs

urlpatterns = [
    # Standard DRF Endpoints
    path('run-pipeline/', RunPipelineView.as_view(), name='validator-run-pipeline'),
    path('job-status/<uuid:job_id>/', JobStatusView.as_view(), name='validator-job-status'),
    path('results/<uuid:job_id>/', ValidationResultsView.as_view(), name='validator-results'),
    path('history/', ValidationHistoryView.as_view(), name='validator-history'),
    path('manual-review/', ManualReviewView.as_view(), name='validator-manual-review'),

    # Compatibility / Legacy Endpoints (Shims for Frontend)
    path('health/', health_check, name='legacy-health'),
    path('mongodb-status/', mongodb_status, name='legacy-mongodb-status'),
    path('logs/latest/', get_latest_logs, name='legacy-logs'),
    
    # Aliases and Shims for frontend compatibility
    path('run-pipeline', RunPipelineView.as_view()), # shim for missing slash
    path('validation-history', ValidationHistoryView.as_view()), # shim for missing slash
    path('history', ValidationHistoryView.as_view()), # shim
    path('brochures/', ValidationHistoryView.as_view(), name='legacy-brochures'),
    path('validation-results/<uuid:job_id>/', ValidationResultsView.as_view(), name='legacy-validation-results'),
    path('job-status/<uuid:job_id>/', JobStatusView.as_view(), name='legacy-job-status-alias'),
]
