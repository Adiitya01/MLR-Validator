"""
AWS S3 Storage Service for MLR Validator

Replaces the ephemeral tempfile-based storage with persistent S3 storage.
PDFs uploaded by users are stored in S3, and Celery workers download them
for processing. This way:
  - Files survive server restarts and deploys
  - Multiple EC2 instances / Celery workers can access the same files
  - Files are automatically cleaned up via S3 lifecycle policies

Usage:
  from validator.s3_storage import S3StorageService
  s3 = S3StorageService()

  # Upload
  s3_key = s3.upload_file(file_bytes, "brochure.pdf", job_id="abc123")

  # Download (for Celery worker)
  local_path = s3.download_to_temp(s3_key)

  # Cleanup
  s3.delete_job_files(job_id="abc123")
"""

import os
import uuid
import logging
import tempfile
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from django.conf import settings
from typing import Optional, List

logger = logging.getLogger(__name__)


class S3StorageService:
    """
    Handles all S3 operations for the MLR Validator.
    
    Bucket structure:
      s3://mlr-validator-uploads/
        ├── jobs/
        │   ├── {job_id}/
        │   │   ├── brochure/
        │   │   │   └── document.pdf
        │   │   └── references/
        │   │       ├── ref1.pdf
        │   │       └── ref2.pdf
        │   └── {job_id}/
        │       └── ...
        └── results/
            └── {job_id}/
                └── result.json
    """

    def __init__(self):
        self.bucket_name = settings.AWS_S3_BUCKET_NAME
        self.region = settings.AWS_S3_REGION
        
        try:
            self.s3_client = boto3.client(
                's3',
                region_name=self.region,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )
            logger.info(f"S3 client initialized: bucket={self.bucket_name}, region={self.region}")
        except NoCredentialsError:
            logger.error("AWS credentials not found. S3 storage will not work.")
            self.s3_client = None

    def _build_key(self, job_id: str, category: str, filename: str) -> str:
        """Build an S3 object key following our folder structure."""
        # Sanitize filename to prevent path traversal
        safe_filename = os.path.basename(filename)
        return f"jobs/{job_id}/{category}/{safe_filename}"

    # =========================================================================
    # UPLOAD OPERATIONS
    # =========================================================================

    def upload_django_file(self, file_obj, job_id: str, category: str = "brochure") -> str:
        """
        Upload a Django UploadedFile directly to S3.
        
        Args:
            file_obj: Django UploadedFile object
            job_id: UUID of the validation job
            category: 'brochure' or 'references'
        
        Returns:
            S3 object key (e.g., 'jobs/abc123/brochure/document.pdf')
        """
        s3_key = self._build_key(job_id, category, file_obj.name)
        
        try:
            # Django UploadedFile supports .read(), so we can stream it
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': 'application/pdf',
                    'ServerSideEncryption': 'AES256',  # Encrypt at rest
                    'Metadata': {
                        'job_id': job_id,
                        'original_filename': file_obj.name,
                    }
                }
            )
            logger.info(f"Uploaded {file_obj.name} to s3://{self.bucket_name}/{s3_key}")
            return s3_key
            
        except ClientError as e:
            logger.error(f"Failed to upload {file_obj.name} to S3: {e}")
            raise Exception(f"File upload failed: {str(e)}")

    def upload_bytes(self, content: bytes, filename: str, job_id: str, category: str = "brochure") -> str:
        """
        Upload raw bytes to S3.
        
        Args:
            content: File content as bytes
            filename: Original filename
            job_id: UUID of the validation job
            category: 'brochure' or 'references'
        
        Returns:
            S3 object key
        """
        from io import BytesIO
        
        s3_key = self._build_key(job_id, category, filename)
        
        try:
            self.s3_client.upload_fileobj(
                BytesIO(content),
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': 'application/pdf',
                    'ServerSideEncryption': 'AES256',
                    'Metadata': {
                        'job_id': job_id,
                        'original_filename': filename,
                    }
                }
            )
            logger.info(f"Uploaded {filename} ({len(content)} bytes) to s3://{self.bucket_name}/{s3_key}")
            return s3_key
            
        except ClientError as e:
            logger.error(f"Failed to upload bytes to S3: {e}")
            raise Exception(f"File upload failed: {str(e)}")

    # =========================================================================
    # DOWNLOAD OPERATIONS (Used by Celery workers)
    # =========================================================================

    def download_to_temp(self, s3_key: str) -> str:
        """
        Download an S3 object to a local temp file.
        The Celery worker calls this to get PDFs for processing.
        
        Args:
            s3_key: S3 object key
        
        Returns:
            Local filesystem path to the downloaded file
        """
        filename = os.path.basename(s3_key)
        temp_dir = tempfile.mkdtemp(prefix="mlr_s3_")
        local_path = os.path.join(temp_dir, filename)
        
        try:
            self.s3_client.download_file(
                self.bucket_name,
                s3_key,
                local_path
            )
            logger.info(f"Downloaded s3://{self.bucket_name}/{s3_key} -> {local_path}")
            return local_path
            
        except ClientError as e:
            logger.error(f"Failed to download {s3_key} from S3: {e}")
            raise Exception(f"File download failed: {str(e)}")

    def download_bytes(self, s3_key: str) -> bytes:
        """
        Download an S3 object as raw bytes (in-memory).
        Use for smaller files where you don't need a local file.
        
        Args:
            s3_key: S3 object key
        
        Returns:
            File content as bytes
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            content = response['Body'].read()
            logger.info(f"Downloaded {s3_key} ({len(content)} bytes) from S3")
            return content
            
        except ClientError as e:
            logger.error(f"Failed to download bytes from S3: {e}")
            raise Exception(f"File download failed: {str(e)}")

    # =========================================================================
    # CLEANUP OPERATIONS
    # =========================================================================

    def delete_job_files(self, job_id: str):
        """
        Delete ALL files for a specific job from S3.
        Called after job completes (results are saved in the DB, not S3).
        
        Args:
            job_id: UUID of the validation job
        """
        prefix = f"jobs/{job_id}/"
        
        try:
            # List all objects with this prefix
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            objects = response.get('Contents', [])
            if not objects:
                logger.info(f"No S3 objects found for job {job_id}")
                return
            
            # Delete all objects (batch delete, max 1000 at a time)
            delete_keys = [{'Key': obj['Key']} for obj in objects]
            self.s3_client.delete_objects(
                Bucket=self.bucket_name,
                Delete={'Objects': delete_keys}
            )
            
            logger.info(f"Deleted {len(delete_keys)} files from S3 for job {job_id}")
            
        except ClientError as e:
            logger.error(f"Failed to delete S3 files for job {job_id}: {e}")
            # Don't raise — cleanup failure shouldn't break the pipeline

    def delete_single_file(self, s3_key: str):
        """Delete a single file from S3."""
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            logger.info(f"Deleted s3://{self.bucket_name}/{s3_key}")
        except ClientError as e:
            logger.error(f"Failed to delete {s3_key}: {e}")

    # =========================================================================
    # UTILITY OPERATIONS
    # =========================================================================

    def file_exists(self, s3_key: str) -> bool:
        """Check if a file exists in S3."""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError:
            return False

    def generate_presigned_url(self, s3_key: str, expiration: int = 3600) -> Optional[str]:
        """
        Generate a pre-signed URL for temporary download access.
        Useful if you want to let users download their original PDFs.
        
        Args:
            s3_key: S3 object key
            expiration: URL expiry time in seconds (default: 1 hour)
        
        Returns:
            Pre-signed URL string, or None on error
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': s3_key,
                },
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL for {s3_key}: {e}")
            return None

    def list_job_files(self, job_id: str) -> List[str]:
        """List all S3 keys for a given job."""
        prefix = f"jobs/{job_id}/"
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            return [obj['Key'] for obj in response.get('Contents', [])]
        except ClientError as e:
            logger.error(f"Failed to list files for job {job_id}: {e}")
            return []

    def health_check(self) -> bool:
        """Verify S3 connectivity (used by /api/health/)."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True
        except Exception:
            return False
