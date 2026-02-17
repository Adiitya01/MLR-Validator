from django.db import models
from django.conf import settings
import uuid

class ValidationJob(models.Model):
    STATUS_CHOICES = (
        ('uploaded', 'Uploaded'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='validation_jobs')
    brochure_filename = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')
    result_json = models.JSONField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata for the pipeline (e.g. how many reference files)
    reference_file_count = models.IntegerField(default=0)
    pipeline_type = models.CharField(max_length=50, default="research") # "drug" or "research"

    def __str__(self):
        return f"{self.brochure_filename} - {self.status}"

    class Meta:
        ordering = ['-created_at']
