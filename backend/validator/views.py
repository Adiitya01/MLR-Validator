import logging
from rest_framework import views, status, generics, permissions, throttling
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from .models import ValidationJob
from .serializers import UploadSerializer, ValidationJobSerializer
from .tasks import run_validation_task
from .services import PipelineService, ManualReviewService

logger = logging.getLogger(__name__)

class PipelineThrottle(throttling.UserRateThrottle):
    scope = 'pipeline'

class RunPipelineView(views.APIView):
    """
    Unified pipeline endpoint - Starts a background job and returns Job ID.
    Replaces FastAPI's /run-pipeline.
    """
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [PipelineThrottle]

    def post(self, request, *args, **kwargs):
        serializer = UploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        brochure_file = serializer.validated_data['brochure_pdf']
        reference_files = serializer.validated_data['reference_pdfs']
        validation_type = serializer.validated_data['validation_type']

        workspace_path = None
        try:
            # 1. Create Job Entry in DB
            job = ValidationJob.objects.create(
                user=request.user,
                brochure_filename=brochure_file.name,
                reference_file_count=len(reference_files),
                pipeline_type=validation_type,
                status='uploaded'
            )

            # 2. Create Workspace and save files
            workspace_path = PipelineService.create_workspace()
            brochure_path = PipelineService.save_upload(brochure_file, workspace_path)
            
            reference_paths = []
            for ref_file in reference_files:
                path = PipelineService.save_upload(ref_file, workspace_path)
                reference_paths.append(path)

            # 3. Dispatch to Celery
            run_validation_task.delay(
                job_id=str(job.id),
                brochure_path=brochure_path,
                reference_paths=reference_paths,
                workspace_path=workspace_path,
                validation_type=validation_type
            )

            return Response({
                "status": "success",
                "message": "Validation job started",
                "job_id": str(job.id),
                "filename": brochure_file.name
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Failed to initiate pipeline: {e}")
            if workspace_path:
                PipelineService.cleanup_workspace(workspace_path)
            return Response({
                "status": "error",
                "message": f"Failed to start validation job: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class JobStatusView(views.APIView):
    """
    Check the status of a background validation job.
    Replaces FastAPI's /job-status/{id}.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, job_id, *args, **kwargs):
        try:
            job = ValidationJob.objects.get(id=job_id, user=request.user)
            return Response({
                "status": "success",
                "job_id": str(job.id),
                "state": job.status,
                "filename": job.brochure_filename,
                "created_at": job.created_at,
                "message": f"Job is {job.status}"
            })
        except ValidationJob.DoesNotExist:
            return Response({"detail": "Job not found"}, status=status.HTTP_404_NOT_FOUND)

class ValidationResultsView(views.APIView):
    """
    Fetch results for a specific validation job.
    Replaces FastAPI's /validation-results/{id}.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, job_id, *args, **kwargs):
        try:
            job = ValidationJob.objects.get(id=job_id, user=request.user)
            if job.status != 'completed':
                return Response({
                    "detail": "Results not ready", 
                    "status": job.status
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # The result_json contains the exact shape expected by frontend
            return Response(job.result_json)
            
        except ValidationJob.DoesNotExist:
            return Response({"detail": "Results not found"}, status=status.HTTP_404_NOT_FOUND)

class ValidationHistoryView(generics.ListAPIView):
    """
    List past validation jobs for the user.
    Replaces FastAPI's /validation-history.
    """
    serializer_class = ValidationJobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ValidationJob.objects.filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        history = [
            {
                "brochure_id": str(job.id),
                "filename": job.brochure_filename,
                "status": job.status,
                "created_at": job.created_at
            }
            for job in queryset[:20]
        ]
        return Response({"status": "success", "history": history})

class ManualReviewView(views.APIView):
    """
    Standalone validation for a single statement against one or more PDFs.
    Replaces FastAPI's /manual-review.
    """
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [PipelineThrottle]

    def post(self, request, *args, **kwargs):
        statement = request.data.get('statement')
        reference_no = request.data.get('reference_no')
        files = request.FILES.getlist('reference_pdfs')

        if not statement or not files:
            return Response({
                "detail": "Statement and at least one PDF are required."
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Prepare file data for service
            pdf_files_data = []
            for f in files:
                pdf_files_data.append((f.name, f.read()))

            result = ManualReviewService.run_manual_review(
                statement=statement,
                pdf_files_data=pdf_files_data,
                reference_no=reference_no
            )

            return Response({
                "status": "success",
                "result": result
            })

        except Exception as e:
            logger.error(f"Manual review error: {e}")
            return Response({
                "detail": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
