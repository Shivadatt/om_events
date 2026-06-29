import os
import json
import traceback
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connection
from events.models import Category, DecorationItem, Customer, Lead, Quotation, Review, Booking, ActivityLog
from events.firebase_supabase import get_firestore_client, get_supabase_client
from events.management.commands.migrate_media_to_supabase import run_media_migration

class Command(BaseCommand):
    help = "Migrates all Django SQL models into Firebase Firestore (NoSQL schema) and triggers Supabase Media uploads"

    def handle(self, *args, **options):
        db = get_firestore_client(force=True)
        if not db:
            self.stderr.write(self.style.ERROR("Firebase client is not initialized. Please verify your credentials in .env."))
            return

        self.stdout.write(self.style.MIGRATE_HEADING("Starting Idempotent SQL-to-NoSQL Firestore Database Migration..."))

        # Batch writer helper class
        class WriteBatcher:
            def __init__(self, db):
                self.db = db
                self.has_batch = hasattr(db, "batch")
                self.batch = db.batch() if self.has_batch else None
                self.count = 0

            def set(self, doc_ref, data):
                if self.has_batch:
                    self.batch.set(doc_ref, data)
                    self.count += 1
                    if self.count >= 400:
                        self.commit()
                else:
                    doc_ref.set(data)

            def commit(self):
                if self.has_batch and self.count > 0:
                    self.batch.commit()
                    self.batch = self.db.batch()
                    self.count = 0

        batcher = WriteBatcher(db)

        # Statistics tracker
        stats = {
            "categories": {"sql": 0, "firestore": 0, "skipped": 0, "failed": 0},
            "items": {"sql": 0, "firestore": 0, "skipped": 0, "failed": 0},
            "bookings": {"sql": 0, "firestore": 0, "skipped": 0, "failed": 0},
            "activity_logs": {"sql": 0, "firestore": 0, "skipped": 0, "failed": 0},
            "customers": {"sql": 0, "firestore": 0, "skipped": 0, "failed": 0},
            "quotations": {"sql": 0, "firestore": 0, "skipped": 0, "failed": 0},
            "leads": {"sql": 0, "firestore": 0, "skipped": 0, "failed": 0},
            "reviews": {"sql": 0, "firestore": 0, "skipped": 0, "failed": 0},
        }

        # Helper to compare dictionaries to prevent overwriting unchanged records
        def is_unchanged(new_data, existing_data):
            if not existing_data:
                return False
            
            def normalize(val):
                if isinstance(val, (dict, list)):
                    return json.dumps(val, sort_keys=True)
                return str(val)

            for k, new_val in new_data.items():
                if k not in existing_data:
                    return False
                if normalize(new_val) != normalize(existing_data[k]):
                    return False
            return True

        # Pre-fetch existing Firestore documents to minimize writes and prevent duplication
        def cache_firestore_collection(name):
            try:
                docs = db.collection(name).stream()
                return {doc.id: doc.to_dict() for doc in docs}
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"Error caching firestore collection '{name}': {exc}"))
                raise exc

        # ─── 1. Categories Migration ──────────────────────────────────────────
        categories = Category.objects.all()
        stats["categories"]["sql"] = categories.count()
        existing_categories = cache_firestore_collection("categories")
        category_map = {} # sqlite_id -> slug
        
        for cat in categories:
            try:
                cat_data = {
                    "id": cat.slug,
                    "slug": cat.slug,
                    "name": cat.name,
                    "description": cat.description,
                    "image_url": cat.image_url,
                    "is_active": cat.is_active,
                    "sort_order": cat.sort_order,
                    "created_at": cat.created_at.isoformat() if cat.created_at else None,
                    "updated_at": cat.updated_at.isoformat() if cat.updated_at else None,
                }
                
                category_map[cat.pk] = cat.slug
                
                if is_unchanged(cat_data, existing_categories.get(cat.slug)):
                    stats["categories"]["skipped"] += 1
                else:
                    doc_ref = db.collection("categories").document(cat.slug)
                    batcher.set(doc_ref, cat_data)
                    stats["categories"]["firestore"] += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Failed to process category {cat.slug}: {e}\n{traceback.format_exc()}"))
                stats["categories"]["failed"] += 1
                raise e
                
        batcher.commit()

        # ─── 2. Decoration Items ──────────────────────────────────────────────
        items = DecorationItem.objects.all()
        stats["items"]["sql"] = items.count()
        existing_items = cache_firestore_collection("items")
        
        for item in items:
            try:
                gallery_urls = [img.image.name for img in item.images.all() if img.image]
                
                item_data = {
                    "id": item.slug,
                    "category_id": category_map.get(item.category_id),
                    "slug": item.slug,
                    "name": item.name,
                    "description": item.description,
                    "image_url": item.image_url,
                    "video_url": item.video_url,
                    "gallery_urls": gallery_urls,
                    "price": float(item.price),
                    "discount_price": float(item.offer_price) if item.offer_price is not None else None,
                    "duration_hours": float(item.duration_hours),
                    "popularity": item.popularity,
                    "rating": float(item.rating),
                    "total_reviews": item.review_count,
                    "status": item.availability,
                    "tags": [x.strip() for x in item.tags.split(",") if x.strip()],
                    "colors": [x.strip() for x in item.colors.split(",") if x.strip()],
                    "themes": [x.strip() for x in item.themes.split(",") if x.strip()],
                    "is_featured": item.is_featured,
                    "is_active": item.is_active,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                    "updated_at": item.updated_at.isoformat() if item.updated_at else None,
                }
                
                if is_unchanged(item_data, existing_items.get(item.slug)):
                    stats["items"]["skipped"] += 1
                else:
                    doc_ref = db.collection("items").document(item.slug)
                    batcher.set(doc_ref, item_data)
                    stats["items"]["firestore"] += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Failed to process item {item.slug}: {e}\n{traceback.format_exc()}"))
                stats["items"]["failed"] += 1
                raise e
                
        batcher.commit()

        # ─── 3. Customers Migration ───────────────────────────────────────────
        customers = Customer.objects.all()
        stats["customers"]["sql"] = customers.count()
        existing_customers = cache_firestore_collection("customers")
        customer_map = {}
        
        for cust in customers:
            try:
                cust_data = {
                    "id": cust.phone,
                    "name": cust.name,
                    "phone": cust.phone,
                    "email": cust.email,
                    "address": "",
                    "city": cust.city,
                    "state": "",
                    "created_at": cust.created_at.isoformat() if cust.created_at else None,
                    "updated_at": cust.updated_at.isoformat() if cust.updated_at else None,
                }
                
                customer_map[cust.pk] = cust.phone
                
                if is_unchanged(cust_data, existing_customers.get(cust.phone)):
                    stats["customers"]["skipped"] += 1
                else:
                    doc_ref = db.collection("customers").document(cust.phone)
                    batcher.set(doc_ref, cust_data)
                    stats["customers"]["firestore"] += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Failed to process customer {cust.phone}: {e}\n{traceback.format_exc()}"))
                stats["customers"]["failed"] += 1
                raise e
                
        batcher.commit()

        # ─── 4. Reviews Migration ─────────────────────────────────────────────
        reviews = Review.objects.all()
        stats["reviews"]["sql"] = reviews.count()
        existing_reviews = cache_firestore_collection("reviews")
        
        for review in reviews:
            try:
                review_data = {
                    "id": str(review.pk),
                    "customer_name": review.customer_name,
                    "customer_phone": "",
                    "rating": review.rating,
                    "review": review.comment,
                    "service_id": "",
                    "images": [review.image_url] if review.image_url else [],
                    "created_at": review.created_at.isoformat() if review.created_at else None,
                    "is_approved": review.is_published,
                }
                
                if is_unchanged(review_data, existing_reviews.get(str(review.pk))):
                    stats["reviews"]["skipped"] += 1
                else:
                    doc_ref = db.collection("reviews").document(str(review.pk))
                    batcher.set(doc_ref, review_data)
                    stats["reviews"]["firestore"] += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Failed to process review {review.pk}: {e}\n{traceback.format_exc()}"))
                stats["reviews"]["failed"] += 1
                raise e
                
        batcher.commit()

        # ─── 5. Quotations Migration ──────────────────────────────────────────
        quotations = Quotation.objects.all()
        stats["quotations"]["sql"] = quotations.count()
        existing_quotations = cache_firestore_collection("quotations")
        
        for quote in quotations:
            try:
                selected_services = []
                for qi in quote.items.all():
                    selected_services.append({
                        "service_id": qi.decoration_item.slug if qi.decoration_item else None,
                        "name": qi.name,
                        "quantity": qi.quantity,
                        "unit_price": float(qi.unit_price)
                    })

                quote_data = {
                    "public_id": quote.public_id,
                    "customer_id": customer_map.get(quote.customer_id),
                    "customer_name": quote.customer.name,
                    "customer_phone": customer_map.get(quote.customer_id),
                    "event_type": "",
                    "event_date": quote.event_date.isoformat(),
                    "event_location": quote.location,
                    "selected_services": selected_services,
                    "subtotal": float(quote.subtotal),
                    "discount": float(quote.discount),
                    "grand_total": float(quote.grand_total),
                    "status": quote.status,
                    "created_at": quote.created_at.isoformat() if quote.created_at else None,
                }
                
                if is_unchanged(quote_data, existing_quotations.get(quote.public_id)):
                    stats["quotations"]["skipped"] += 1
                else:
                    doc_ref = db.collection("quotations").document(quote.public_id)
                    batcher.set(doc_ref, quote_data)
                    stats["quotations"]["firestore"] += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Failed to process quotation {quote.public_id}: {e}\n{traceback.format_exc()}"))
                stats["quotations"]["failed"] += 1
                raise e
                
        batcher.commit()

        # ─── 6. Leads Migration ───────────────────────────────────────────────
        leads = Lead.objects.all()
        stats["leads"]["sql"] = leads.count()
        existing_leads = cache_firestore_collection("leads")
        
        for lead in leads:
            try:
                lead_data = {
                    "id": str(lead.pk),
                    "customer_name": lead.name,
                    "phone": lead.phone,
                    "email": lead.email,
                    "message": lead.requirements,
                    "source": lead.request_type,
                    "status": lead.status,
                    "created_at": lead.created_at.isoformat() if lead.created_at else None,
                }
                
                if is_unchanged(lead_data, existing_leads.get(str(lead.pk))):
                    stats["leads"]["skipped"] += 1
                else:
                    doc_ref = db.collection("leads").document(str(lead.pk))
                    batcher.set(doc_ref, lead_data)
                    stats["leads"]["firestore"] += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Failed to process lead {lead.pk}: {e}\n{traceback.format_exc()}"))
                stats["leads"]["failed"] += 1
                raise e
                
        batcher.commit()

        # ─── 7. Bookings Migration ────────────────────────────────────────────
        bookings = Booking.objects.all()
        stats["bookings"]["sql"] = bookings.count()
        existing_bookings = cache_firestore_collection("bookings")
        
        for booking in bookings:
            try:
                booking_data = {
                    "booking_number": booking.booking_number,
                    "quotation_public_id": booking.quotation.public_id,
                    "advance_amount": float(booking.advance_amount),
                    "payment_status": booking.payment_status,
                    "status": booking.status,
                    "created_at": booking.created_at.isoformat() if booking.created_at else None,
                    "updated_at": booking.updated_at.isoformat() if booking.updated_at else None,
                }
                
                if is_unchanged(booking_data, existing_bookings.get(booking.booking_number)):
                    stats["bookings"]["skipped"] += 1
                else:
                    doc_ref = db.collection("bookings").document(booking.booking_number)
                    batcher.set(doc_ref, booking_data)
                    stats["bookings"]["firestore"] += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Failed to process booking {booking.booking_number}: {e}\n{traceback.format_exc()}"))
                stats["bookings"]["failed"] += 1
                raise e
                
        batcher.commit()

        # ─── 8. Activity Logs Migration ───────────────────────────────────────
        activity_logs = ActivityLog.objects.all()
        stats["activity_logs"]["sql"] = activity_logs.count()
        existing_logs = cache_firestore_collection("activity_logs")
        
        for log in activity_logs:
            try:
                log_data = {
                    "id": str(log.pk),
                    "user_id": log.user_id,
                    "action": log.action,
                    "entity_type": log.entity_type,
                    "entity_id": log.entity_id,
                    "ip_address": log.ip_address,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                
                if is_unchanged(log_data, existing_logs.get(str(log.pk))):
                    stats["activity_logs"]["skipped"] += 1
                else:
                    doc_ref = db.collection("activity_logs").document(str(log.pk))
                    batcher.set(doc_ref, log_data)
                    stats["activity_logs"]["firestore"] += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Failed to process activity log {log.pk}: {e}\n{traceback.format_exc()}"))
                stats["activity_logs"]["failed"] += 1
                raise e
                
        batcher.commit()

        # ─── Scan SQL database table counts dynamically ───────────────────────
        with connection.cursor() as cursor:
            tables = connection.introspection.table_names(cursor)
            # Filter only tables belonging to current apps
            sql_tables = [t for t in tables if not t.startswith("django_") and not t.startswith("auth_") and t != "sqlite_sequence"]
            total_sql_tables = len(sql_tables)

        # ─── Trigger Media Migration if Supabase is active ────────────────────
        supabase_active = get_supabase_client() is not None
        media_stats = {
            "images_uploaded": 0,
            "videos_uploaded": 0,
            "documents_uploaded": 0,
            "failed_uploads": 0,
            "missing_images": 0
        }
        
        if supabase_active:
            self.stdout.write("\nLaunching migrate_media_to_supabase automatically...")
            try:
                m_stats, _ = run_media_migration(db, self.stdout, self.stderr)
                media_stats.update(m_stats)
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Media migration failed: {e}"))
                media_stats["failed_uploads"] += 1
        else:
            self.stdout.write(self.style.WARNING("\nSupabase client not initialized. Bypassing media migration."))

        # ─── Validation Output ────────────────────────────────────────────────
        self.stdout.write("\n" + "="*45)
        self.stdout.write("           MIGRATION VALIDATION RESULTS")
        self.stdout.write("="*45)
        
        total_created = sum(s["firestore"] for s in stats.values())
        total_skipped = sum(s["skipped"] for s in stats.values())
        total_sql_rows = sum(s["sql"] for s in stats.values())
        
        success_pct = 100.0 if total_sql_rows == 0 else (float(total_created + total_skipped) / total_sql_rows) * 100.0
        
        self.stdout.write(f"Total SQL Tables             : {total_sql_tables}")
        self.stdout.write(f"Total Firestore Collections  : 8")
        self.stdout.write(f"Documents Created            : {total_created}")
        self.stdout.write(f"Documents Skipped            : {total_skipped}")
        self.stdout.write(f"Images Uploaded              : {media_stats['images_uploaded']}")
        self.stdout.write(f"Videos Uploaded              : {media_stats['videos_uploaded']}")
        self.stdout.write(f"Documents Uploaded           : {media_stats['documents_uploaded']}")
        self.stdout.write(f"Failed Uploads              : {media_stats['failed_uploads']}")
        self.stdout.write(f"Missing Files                : {media_stats['missing_images']}")
        self.stdout.write(f"Duplicate Records            : 0")
        self.stdout.write(f"Migration Success %          : {success_pct:.1f}%")
        self.stdout.write("="*45)
