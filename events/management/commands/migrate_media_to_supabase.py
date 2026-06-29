import os
import mimetypes
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from events.models import Category, DecorationItem, Review
from events.firebase_supabase import get_firestore_client, upload_media_to_supabase, detect_bucket_by_path, get_supabase_client

logger = logging.getLogger("events.migration")

def run_media_migration(db, stdout, stderr):
    client = get_supabase_client()
    if client is None:
        raise ValueError("Supabase storage client is not initialized (SUPABASE_KEY or SUPABASE_URL missing in .env). Cannot perform media migration.")

    # STEP 4: Auto-create required buckets if missing
    required_buckets = ["gallery", "services", "videos", "documents", "profile", "users", "bookings", "thumbnails"]
    try:
        existing_buckets = [b.id for b in client.storage.list_buckets()]
        for bucket in required_buckets:
            if bucket not in existing_buckets:
                stdout.write(f"Bucket '{bucket}' is missing. Attempting automatic creation...")
                client.storage.create_bucket(bucket, options={'public': True})
                stdout.write(f"Successfully created bucket '{bucket}'.")
    except Exception as exc:
        stderr.write(f"Error checking/creating buckets on Supabase: {exc}. Please verify dashboard permissions.")
        # If we cannot verify or create, we stop and report
        raise exc

    def resolve_local_path(val):
        if not isinstance(val, str) or not val:
            return None
        
        # If it's already a web URL, return None (skip it)
        if val.startswith("http://") or val.startswith("https://"):
            return None

        clean_val = val.split("?")[0].split("#")[0]
        
        candidates = [
            os.path.join(settings.BASE_DIR, "app", clean_val.lstrip("/")),
            os.path.join(settings.MEDIA_ROOT, clean_val.replace("/uploads/", "").lstrip("/")),
            os.path.join(settings.MEDIA_ROOT, clean_val.replace("media/", "").lstrip("/")),
            os.path.join(settings.BASE_DIR, clean_val.lstrip("/")),
            clean_val
        ]
        
        for cand in candidates:
            if os.path.isfile(cand):
                return cand
        return None

    summary = {
        "sql_item_count": 0,
        "sql_image_count": 0,
        "files_found": 0,
        "files_uploaded": 0,
        "firestore_image_url_populated": 0,
        "missing_images": 0,
        "failed_uploads": 0,
        "images_uploaded": 0,
        "videos_uploaded": 0,
        "documents_uploaded": 0,
        "skipped": 0
    }

    detail_report = []

    # 1. Migrate Categories Media
    categories = Category.objects.all()
    for cat in categories:
        local_path = resolve_local_path(cat.image_url)
        if local_path:
            filename = os.path.basename(local_path)
            path_on_storage = f"categories/{filename}"
            bucket = detect_bucket_by_path(path_on_storage)
            
            with open(local_path, "rb") as f:
                file_data = f.read()
            mime_type, _ = mimetypes.guess_type(local_path)
            
            supabase_url = upload_media_to_supabase(
                path_on_storage, 
                file_data, 
                content_type=mime_type, 
                bucket=bucket
            )
            
            db.collection("categories").document(cat.slug).update({"image_url": supabase_url})
            summary["files_found"] += 1
            summary["files_uploaded"] += 1
            summary["images_uploaded"] += 1
        elif cat.image_url and (cat.image_url.startswith("http://") or cat.image_url.startswith("https://")):
            summary["skipped"] += 1

    # 2. Step-by-Step Item Media Migration (with 10-step verification)
    items = DecorationItem.objects.all()
    summary["sql_item_count"] = items.count()

    for item in items:
        # 2a. Item Image Upload
        try:
            img_path = item.image_url
            if img_path:
                local_path = resolve_local_path(img_path)
                if local_path:
                    filename = os.path.basename(local_path)
                    path_on_storage = f"items/{filename}"
                    bucket = detect_bucket_by_path(path_on_storage)
                    
                    with open(local_path, "rb") as f:
                        file_data = f.read()
                    mime_type, _ = mimetypes.guess_type(local_path)
                    
                    supabase_url = upload_media_to_supabase(
                        path_on_storage, 
                        file_data, 
                        content_type=mime_type, 
                        bucket=bucket
                    )

                    db.collection("items").document(item.slug).update({"image_url": supabase_url})

                    doc_snap = db.collection("items").document(item.slug).get()
                    if doc_snap.exists:
                        doc_data = doc_snap.to_dict()
                        firestore_url = doc_data.get("image_url")
                        if firestore_url == supabase_url:
                            summary["files_found"] += 1
                            summary["files_uploaded"] += 1
                            summary["images_uploaded"] += 1
                            summary["firestore_image_url_populated"] += 1
                        else:
                            summary["failed_uploads"] += 1
                    else:
                        summary["failed_uploads"] += 1
                else:
                    summary["missing_images"] += 1
            else:
                summary["missing_images"] += 1
        except Exception as e:
            summary["failed_uploads"] += 1
            raise e

        # 2b. Item Video Upload
        try:
            vid_path = item.video_url
            if vid_path:
                local_path = resolve_local_path(vid_path)
                if local_path:
                    filename = os.path.basename(local_path)
                    path_on_storage = f"videos/{filename}"
                    bucket = detect_bucket_by_path(path_on_storage)
                    
                    with open(local_path, "rb") as f:
                        file_data = f.read()
                    mime_type, _ = mimetypes.guess_type(local_path)
                    
                    supabase_url = upload_media_to_supabase(
                        path_on_storage, 
                        file_data, 
                        content_type=mime_type, 
                        bucket=bucket
                    )

                    db.collection("items").document(item.slug).update({"video_url": supabase_url})

                    doc_snap = db.collection("items").document(item.slug).get()
                    if doc_snap.exists:
                        doc_data = doc_snap.to_dict()
                        firestore_url = doc_data.get("video_url")
                        if firestore_url == supabase_url:
                            summary["files_found"] += 1
                            summary["files_uploaded"] += 1
                            summary["videos_uploaded"] += 1
                        else:
                            summary["failed_uploads"] += 1
                    else:
                        summary["failed_uploads"] += 1
                else:
                    # Video doesn't exist locally or is already a web URL
                    if vid_path.startswith("http://") or vid_path.startswith("https://"):
                        summary["skipped"] += 1
            else:
                pass
        except Exception as e:
            summary["failed_uploads"] += 1
            raise e

    # 3. Item Gallery Images
    for item in items:
        gallery_urls = []
        for idx, img in enumerate(item.images.all()):
            summary["sql_image_count"] += 1
            try:
                local_path = resolve_local_path(img.image.name)
                if local_path:
                    filename = f"{item.slug}-gallery-{idx}{os.path.splitext(img.image.name)[1]}"
                    path_on_storage = f"items/{filename}"
                    bucket = detect_bucket_by_path(path_on_storage)
                    
                    with open(local_path, "rb") as f:
                        file_data = f.read()
                    mime_type, _ = mimetypes.guess_type(local_path)
                    
                    supabase_url = upload_media_to_supabase(
                        path_on_storage, 
                        file_data, 
                        content_type=mime_type, 
                        bucket=bucket
                    )
                    gallery_urls.append(supabase_url)
                    summary["files_found"] += 1
                    summary["files_uploaded"] += 1
                    summary["images_uploaded"] += 1
                else:
                    if img.image.name and (img.image.name.startswith("http://") or img.image.name.startswith("https://")):
                        gallery_urls.append(img.image.name)
                        summary["skipped"] += 1
                    else:
                        summary["missing_images"] += 1
            except Exception as e:
                summary["failed_uploads"] += 1
                raise e
        
        if gallery_urls:
            db.collection("items").document(item.slug).update({"gallery_urls": gallery_urls})

    # 4. Migrate Reviews Media
    reviews = Review.objects.all()
    for review in reviews:
        try:
            local_path = resolve_local_path(review.image_url)
            if local_path:
                filename = os.path.basename(local_path)
                path_on_storage = f"reviews/{filename}"
                bucket = detect_bucket_by_path(path_on_storage)
                
                with open(local_path, "rb") as f:
                    file_data = f.read()
                mime_type, _ = mimetypes.guess_type(local_path)
                
                supabase_url = upload_media_to_supabase(
                    path_on_storage, 
                    file_data, 
                    content_type=mime_type, 
                    bucket=bucket
                )
                
                db.collection("reviews").document(str(review.pk)).update({"images": [supabase_url]})
                summary["files_found"] += 1
                summary["files_uploaded"] += 1
                summary["images_uploaded"] += 1
            elif review.image_url and (review.image_url.startswith("http://") or review.image_url.startswith("https://")):
                summary["skipped"] += 1
        except Exception as e:
            raise e

    return summary, detail_report


class Command(BaseCommand):
    help = "Scans Firestore collections, detects local media paths, uploads them to Supabase Storage, and updates Firestore"

    def handle(self, *args, **options):
        db = get_firestore_client(force=True)
        if not db:
            self.stderr.write(self.style.ERROR("Firebase client is not initialized. Please verify your credentials in .env."))
            return

        self.stdout.write(self.style.MIGRATE_HEADING("Starting Media Migration to Supabase..."))
        summary, detail_report = run_media_migration(db, self.stdout, self.stderr)

        self.stdout.write(self.style.SUCCESS("\n" + "="*55))
        self.stdout.write(self.style.SUCCESS("        MEDIA MIGRATION SUMMARY"))
        self.stdout.write(self.style.SUCCESS("="*55))
        self.stdout.write(f"SQL Item Count              : {summary['sql_item_count']}")
        self.stdout.write(f"SQL Image Count             : {summary['sql_image_count']}")
        self.stdout.write(f"Files Found                 : {summary['files_found']}")
        self.stdout.write(f"Files Uploaded              : {summary['files_uploaded']}")
        self.stdout.write(f"Firestore URL Populated     : {summary['firestore_image_url_populated']}")
        self.stdout.write(f"Missing Images              : {summary['missing_images']}")
        self.stdout.write(f"Failed Uploads              : {summary['failed_uploads']}")
        self.stdout.write(self.style.SUCCESS("="*55))
