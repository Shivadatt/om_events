import os
from io import BytesIO
from django.core.files.storage import Storage
from django.core.files.base import ContentFile
from django.conf import settings
from .firebase_supabase import get_supabase_client, detect_bucket_by_path

class SupabaseStorage(Storage):
    """
    Custom Django Storage class for Supabase Storage.
    Supports dynamic prefix-based bucket routing. Local fallbacks are completely removed.
    """
    def __init__(self, bucket_name=None):
        self.default_bucket_name = bucket_name
        self.client = get_supabase_client()
        if self.client is None:
            raise ValueError("Supabase storage client is not initialized. Please verify SUPABASE_URL and SUPABASE_KEY in .env.")

    def get_bucket_for_path(self, name):
        """Resolves target bucket from path prefix dynamically."""
        if self.default_bucket_name:
            return self.default_bucket_name
        
        # Clean path and detect prefix
        clean_name = name.replace("\\", "/").lstrip("/")
        bucket = detect_bucket_by_path(clean_name)
        supabase_buckets = getattr(settings, "SUPABASE_BUCKETS", {})
        return supabase_buckets.get(bucket, bucket)

    def _open(self, name, mode='rb'):
        clean_name = name.replace("\\", "/").lstrip("/")
        bucket_name = self.get_bucket_for_path(clean_name)
        
        try:
            response = self.client.storage.from_(bucket_name).download(clean_name)
            return ContentFile(response)
        except Exception as e:
            raise IOError(f"Could not open file '{clean_name}' from Supabase bucket '{bucket_name}': {e}")

    def _save(self, name, content):
        file_data = content.read()
        clean_name = name.replace("\\", "/").lstrip("/")
        bucket_name = self.get_bucket_for_path(clean_name)
        
        try:
            self.client.storage.from_(bucket_name).upload(
                clean_name, 
                file_data, 
                file_options={"cacheControl": "3600", "upsert": "true"}
            )
            return clean_name
        except Exception as e:
            raise IOError(f"Could not save file '{clean_name}' to Supabase bucket '{bucket_name}': {e}")

    def exists(self, name):
        clean_name = name.replace("\\", "/").lstrip("/")
        bucket_name = self.get_bucket_for_path(clean_name)
        
        try:
            res = self.client.storage.from_(bucket_name).list(os.path.dirname(clean_name) or None)
            base_name = os.path.basename(clean_name)
            return any(item.get("name") == base_name for item in res)
        except Exception:
            return False

    def url(self, name):
        clean_name = name.replace("\\", "/").lstrip("/")
        bucket_name = self.get_bucket_for_path(clean_name)
        
        try:
            res = self.client.storage.from_(bucket_name).get_public_url(clean_name)
            return res
        except Exception as e:
            raise IOError(f"Could not get public URL for '{clean_name}' from Supabase bucket '{bucket_name}': {e}")
