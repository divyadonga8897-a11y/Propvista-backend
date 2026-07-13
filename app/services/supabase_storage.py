import httpx
import uuid
import mimetypes
from typing import Optional
from app.core.config import settings
from app.utils.logging import logger

class SupabaseStorageService:
    def __init__(self):
        self.url = settings.SUPABASE_URL
        self.key = settings.SUPABASE_SERVICE_ROLE_KEY
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}"
        }

    async def upload_file(
        self, 
        bucket: str, 
        file_bytes: bytes, 
        original_filename: str, 
        content_type: Optional[str] = None
    ) -> str:
        """
        Uploads file bytes to a Supabase storage bucket and returns the public URL.
        Buckets: 'property-images', 'floor-plans', 'unit-images', 'documents'
        """
        if not self.url or not self.key:
            # Fallback mock URL if Supabase settings are missing
            logger.warning("Supabase URL or Key not set. Returning a mock upload URL.")
            mock_id = uuid.uuid4().hex
            return f"https://mock-storage.propvista.com/{bucket}/{mock_id}_{original_filename}"

        # Generate a unique path/filename
        ext = original_filename.split(".")[-1] if "." in original_filename else "bin"
        unique_filename = f"{uuid.uuid4().hex}.{ext}"
        upload_url = f"{self.url}/storage/v1/object/{bucket}/{unique_filename}"

        if not content_type:
            content_type = mimetypes.guess_type(original_filename)[0] or "application/octet-stream"

        headers = {
            **self.headers,
            "Content-Type": content_type
        }

        # Perform async POST request to Supabase Storage REST API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                upload_url,
                content=file_bytes,
                headers=headers,
                timeout=5.0
            )
            
            if response.status_code != 200:
                logger.error(f"Supabase upload failed: {response.status_code} - {response.text}")
                # Try to create bucket if it doesn't exist, and retry upload
                bucket_created = await self._ensure_bucket_exists(bucket)
                if bucket_created:
                    # Retry
                    retry_response = await client.post(
                        upload_url,
                        content=file_bytes,
                        headers=headers,
                        timeout=5.0
                    )
                    if retry_response.status_code == 200:
                        return f"{self.url}/storage/v1/object/public/{bucket}/{unique_filename}"
                
                raise Exception(f"Failed to upload file to Supabase: {response.text}")

        # Return the public URL for the uploaded asset
        return f"{self.url}/storage/v1/object/public/{bucket}/{unique_filename}"

    async def _ensure_bucket_exists(self, bucket: str) -> bool:
        """Attempts to create the bucket if it does not exist using Supabase Storage API."""
        try:
            create_bucket_url = f"{self.url}/storage/v1/bucket"
            payload = {
                "id": bucket,
                "name": bucket,
                "public": True,
                "file_size_limit": 52428800, # 50MB
                "allowed_mime_types": None
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    create_bucket_url,
                    json=payload,
                    headers=self.headers
                )
                if response.status_code in [200, 201]:
                    logger.info(f"Bucket '{bucket}' verified/created.")
                    return True
        except Exception as e:
            logger.error(f"Error checking/creating storage bucket '{bucket}': {str(e)}")
        return False

# Initialize singleton storage service
storage_service = SupabaseStorageService()
