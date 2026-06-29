"""
Firebase & Supabase integration module for Om Events Django backend.

Initialization Modes
--------------------
Mode 1 — Admin SDK (FULL access, recommended for production):
    Requires FIREBASE_PRIVATE_KEY + FIREBASE_CLIENT_EMAIL in .env
    Provides: Firestore CRUD, server-side auth, cloud storage, FCM

Mode 2 — REST API mode (available with project ID + API key only):
    Uses FIREBASE_PROJECT_ID + FIREBASE_API_KEY
    Provides: Firestore reads/writes via HTTP REST API
    Limitation: No server-side token minting or Admin-only operations

Mode 3 — Local SQLite fallback:
    No Firebase credentials configured at all
    All data remains in local database only
"""

import json
import logging
import os
import urllib.request
import urllib.parse
import mimetypes
import time
import sys

from django.conf import settings

logger = logging.getLogger(__name__)

# ─── Internal state ──────────────────────────────────────────────────────────
_db = None                      # firebase_admin Firestore client (Mode 1)
_supabase_client = None         # Supabase Python client
_firebase_mode = "local"        # "admin" | "rest" | "local"
_project_id = getattr(settings, "FIREBASE_PROJECT_ID", "")
_api_key = getattr(settings, "FIREBASE_API_KEY", "")
_is_testing = "test" in sys.argv

# ─── Mode 1: Admin SDK initialisation ────────────────────────────────────────
if not _is_testing and _project_id and getattr(settings, "FIREBASE_CLIENT_EMAIL", "") and getattr(settings, "FIREBASE_PRIVATE_KEY", ""):
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            cred = credentials.Certificate({
                "type": "service_account",
                "project_id": _project_id,
                "private_key": settings.FIREBASE_PRIVATE_KEY,
                "client_email": settings.FIREBASE_CLIENT_EMAIL,
                "token_uri": "https://oauth2.googleapis.com/token",
            })
            firebase_admin.initialize_app(cred)

        _db = firestore.client()
        _firebase_mode = "admin"
        logger.info("[OK] Firebase Admin SDK initialised (Mode 1 - full access).")

    except Exception as exc:
        logger.error("Firebase Admin SDK initialisation failed: %s. Trying REST mode...", exc)

# ─── Mode 2: REST API fallback (project ID + API key only) ───────────────────
if not _is_testing and _firebase_mode == "local" and _project_id and _api_key:
    _firebase_mode = "rest"
    logger.info(
        "[INFO] Firebase REST API mode active (Mode 2 - project: %s). "
        "Full Admin SDK requires FIREBASE_PRIVATE_KEY + FIREBASE_CLIENT_EMAIL.",
        _project_id,
    )

if _firebase_mode == "local":
    logger.warning(
        "[WARN] No Firebase credentials found or test mode active. All data uses local SQLite."
    )

# ─── Startup data probe ───────────────────────────────────────────────────────
_firestore_has_data = False
if not _is_testing and _firebase_mode in ("admin", "rest"):
    try:
        import urllib.request as _urllib_req
        import json as _json

        def _probe_collection(name):
            """Return True if the named Firestore collection has at least 1 document."""
            if _firebase_mode == "admin":
                return len(list(_db.collection(name).limit(1).stream())) > 0
            _url = (
                f"https://firestore.googleapis.com/v1/projects/{_project_id}"
                f"/databases/(default)/documents/{name}?pageSize=1&key={_api_key}"
            )
            try:
                with _urllib_req.urlopen(_url, timeout=5) as _r:
                    return bool(_json.loads(_r.read()).get("documents"))
            except Exception:
                return False

        _has_categories = _probe_collection("categories")
        _has_items = _probe_collection("items")
        _firestore_has_data = _has_categories and _has_items

        if _firestore_has_data:
            logger.info("[INFO] Firestore probe OK (categories + items found) — using Firestore as primary store.")
        else:
            logger.info(
                "[INFO] Firestore probe: categories=%s items=%s — falling back to local SQLite. "
                "Run: python manage.py migrate_to_firebase  to populate Firestore.",
                _has_categories, _has_items,
            )
    except Exception as _probe_exc:
        logger.warning("[WARN] Firestore probe failed (%s). Using local SQLite.", _probe_exc)
        _firestore_has_data = False

# ─── Supabase initialisation ─────────────────────────────────────────────────
_supabase_url = getattr(settings, "SUPABASE_URL", "") or os.getenv("SUPABASE_URL", "")
_supabase_key = getattr(settings, "SUPABASE_KEY", "") or os.getenv("SUPABASE_KEY", "")

# Treat placeholder values as missing (e.g. YOUR_SUPABASE_SERVICE_ROLE_KEY)
_supabase_key_valid = bool(_supabase_key) and "YOUR_" not in _supabase_key and "REPLACE_WITH" not in _supabase_key
_supabase_url_valid = bool(_supabase_url) and "YOUR_" not in _supabase_url

if _is_testing or not _supabase_url_valid or not _supabase_key_valid:
    _supabase_client = None
    if not _is_testing:
        if not _supabase_key_valid:
            logger.warning("[WARN] Supabase credentials missing or placeholder: SUPABASE_KEY must be a real service_role JWT in .env. Media uploads disabled.")
        else:
            logger.error("[ERROR] Supabase credentials missing: SUPABASE_URL and SUPABASE_KEY must be populated in .env. Initialization stopped.")
else:
    try:
        from supabase import create_client
        _supabase_client = create_client(_supabase_url, _supabase_key)
        logger.info("[OK] Supabase client initialised successfully.")
    except Exception as exc:
        _supabase_client = None
        logger.error(f"[ERROR] Supabase client creation failed: {exc}. Initialization stopped.")


# ─── REST API helpers ─────────────────────────────────────────────────────────

_FIRESTORE_BASE = "https://firestore.googleapis.com/v1/projects/{project}/databases/(default)/documents"

def _rest_url(collection, document=None):
    base = _FIRESTORE_BASE.format(project=_project_id)
    url = f"{base}/{collection}"
    if document:
        url = f"{url}/{document}"
    return url

def _to_firestore_value(value):
    """Convert a Python value to a Firestore REST API value object."""
    if value is None:
        return {"nullValue": None}
    if isinstance(value, bool):
        return {"booleanValue": value}
    if isinstance(value, int):
        return {"integerValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, list):
        return {"arrayValue": {"values": [_to_firestore_value(v) for v in value]}}
    if isinstance(value, dict):
        return {"mapValue": {"fields": {k: _to_firestore_value(v) for k, v in value.items()}}}
    return {"stringValue": str(value)}

def _from_firestore_value(value_obj):
    """Convert a Firestore REST API value object back to a Python value."""
    if "nullValue" in value_obj:
        return None
    if "booleanValue" in value_obj:
        return value_obj["booleanValue"]
    if "integerValue" in value_obj:
        return int(value_obj["integerValue"])
    if "doubleValue" in value_obj:
        return value_obj["doubleValue"]
    if "stringValue" in value_obj:
        return value_obj["stringValue"]
    if "arrayValue" in value_obj:
        return [_from_firestore_value(v) for v in value_obj["arrayValue"].get("values", [])]
    if "mapValue" in value_obj:
        return {k: _from_firestore_value(v) for k, v in value_obj["mapValue"].get("fields", {}).items()}
    return None

def _parse_document(doc):
    """Convert a Firestore REST document to a plain dict."""
    fields = doc.get("fields", {})
    result = {k: _from_firestore_value(v) for k, v in fields.items()}
    name = doc.get("name", "")
    result["id"] = name.split("/")[-1] if name else None
    return result

def _rest_request(method, url, body=None):
    """Send an authenticated Firestore REST request using the API key."""
    full_url = f"{url}?key={_api_key}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        full_url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode()
        logger.error(f"Firestore REST {method} {url} failed [{exc.code}]: {error_body}")
        raise

def _rest_get_document(collection, document):
    """GET a single Firestore document via REST API."""
    url = _rest_url(collection, document)
    try:
        doc = _rest_request("GET", url)
        return _parse_document(doc)
    except Exception:
        return None

def _rest_set_document(collection, document, data):
    """PATCH (upsert) a Firestore document via REST API."""
    url = _rest_url(collection, document)
    fields = {k: _to_firestore_value(v) for k, v in data.items() if k != "id"}
    body = {"fields": fields}
    return _rest_request("PATCH", url, body)

def _rest_add_document(collection, data):
    """POST a new Firestore document via REST API (auto-ID)."""
    url = _rest_url(collection)
    fields = {k: _to_firestore_value(v) for k, v in data.items() if k != "id"}
    body = {"fields": fields}
    result = _rest_request("POST", url, body)
    return _parse_document(result)

def _rest_list_documents(collection, filters=None, limit=None):
    """List documents in a Firestore collection via REST API."""
    url = _rest_url(collection)
    if limit:
        url = f"{url}?pageSize={limit}&key={_api_key}"
        req = urllib.request.Request(url, method="GET", headers={"Content-Type": "application/json"})
    else:
        url = f"{url}?key={_api_key}"
        req = urllib.request.Request(url, method="GET", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
    except Exception as exc:
        logger.error(f"Firestore REST list {collection} failed: {exc}")
        return []

    docs = [_parse_document(d) for d in result.get("documents", [])]

    if filters:
        for field, value in filters.items():
            docs = [d for d in docs if d.get(field) == value]

    return docs


# ─── Public API ───────────────────────────────────────────────────────────────

class FirestoreProxy:
    """Unified Firestore interface that delegates to Admin SDK or Firestore REST API."""
    def collection(self, name):
        return CollectionProxy(name)


class CollectionProxy:
    def __init__(self, collection_name):
        self._col = collection_name

    def document(self, doc_id):
        return DocumentProxy(self._col, str(doc_id))

    def where(self, field, op, value):
        return QueryProxy(self._col, [(field, op, value)])

    def stream(self):
        if _firebase_mode == "admin":
            return _db.collection(self._col).stream()
        return _rest_list_documents(self._col)

    def limit(self, n):
        return QueryProxy(self._col, [], limit=n)

    def add(self, data):
        if _firebase_mode == "admin":
            return _db.collection(self._col).add(data)
        result = _rest_add_document(self._col, data)
        return None, type("DocRef", (), {"id": result.get("id")})()


class DocumentProxy:
    def __init__(self, collection, doc_id):
        self._col = collection
        self._id = doc_id

    def get(self):
        if _firebase_mode == "admin":
            return _db.collection(self._col).document(self._id).get()
        data = _rest_get_document(self._col, self._id)
        exists = data is not None
        return type("DocSnapshot", (), {
            "exists": exists,
            "to_dict": lambda self: data,
            "id": self._id,
        })()

    def set(self, data):
        if _firebase_mode == "admin":
            return _db.collection(self._col).document(self._id).set(data)
        return _rest_set_document(self._col, self._id, data)

    def update(self, data):
        if _firebase_mode == "admin":
            return _db.collection(self._col).document(self._id).update(data)
        existing = _rest_get_document(self._col, self._id) or {}
        existing.update(data)
        existing.pop("id", None)
        return _rest_set_document(self._col, self._id, existing)


class QueryProxy:
    def __init__(self, collection, filters, limit=None):
        self._col = collection
        self._filters = filters
        self._limit = limit

    def where(self, field, op, value):
        return QueryProxy(self._col, self._filters + [(field, op, value)], self._limit)

    def limit(self, n):
        return QueryProxy(self._col, self._filters, limit=n)

    def stream(self):
        if _firebase_mode == "admin":
            ref = _db.collection(self._col)
            for field, op, value in self._filters:
                ref = ref.where(field, op, value)
            if self._limit:
                ref = ref.limit(self._limit)
            return ref.stream()
        simple_filters = {f: v for f, op, v in self._filters if op == "=="}
        return _rest_list_documents(self._col, filters=simple_filters, limit=self._limit)


def get_firestore_client(force=False):
    if _firebase_mode in ("admin", "rest") and (force or _firestore_has_data):
        if _firebase_mode == "admin":
            return _db
        return FirestoreProxy()
    return None


def get_supabase_client():
    return _supabase_client


def get_firebase_mode():
    return _firebase_mode


# ─── Supabase storage helpers ─────────────────────────────────────────────────

def detect_bucket_by_path(path):
    """
    Detects which bucket to use based on prefix matching rules.
    Available buckets: gallery, services, videos, profile, users, documents, bookings, thumbnails
    """
    clean_path = path.replace("\\", "/").lower().lstrip("/")
    if clean_path.startswith("items/") or clean_path.startswith("services/"):
        return "services"
    elif clean_path.startswith("gallery/"):
        return "gallery"
    elif clean_path.startswith("videos/"):
        return "videos"
    elif clean_path.startswith("profile/"):
        return "profile"
    elif clean_path.startswith("users/"):
        return "users"
    elif clean_path.startswith("documents/") or clean_path.startswith("quotes/") or clean_path.endswith(".pdf"):
        return "documents"
    elif clean_path.startswith("bookings/"):
        return "bookings"
    elif clean_path.startswith("thumbnails/"):
        return "thumbnails"
    return "gallery"


def upload_media_to_supabase(path, file_data, content_type=None, bucket=None):
    """Upload file data directly to dynamic Supabase Storage bucket."""
    clean_path = path.replace("\\", "/").lstrip("/")
    
    if not bucket:
        bucket = detect_bucket_by_path(clean_path)
        
    VALID_BUCKETS = {"gallery", "services", "videos", "documents", "users", "profile", "bookings", "thumbnails"}
    if bucket not in VALID_BUCKETS:
        raise ValueError(f"Invalid storage bucket: '{bucket}'. Must be one of {VALID_BUCKETS}")
        
    supabase_buckets = getattr(settings, "SUPABASE_BUCKETS", {})
    bucket_name = supabase_buckets.get(bucket, bucket)

    if not content_type:
        content_type, _ = mimetypes.guess_type(clean_path)
    if not content_type:
        content_type = "application/octet-stream"

    client = get_supabase_client()
    if client is None:
        raise ValueError("Supabase storage client is not initialized (SUPABASE_KEY or SUPABASE_URL missing). Cannot perform upload.")

    # Retry logic: Try up to 3 times
    for attempt in range(1, 4):
        try:
            extra = {
                "cacheControl": "3600",
                "contentType": content_type,
                "upsert": "true"
            }
            client.storage.from_(bucket_name).upload(clean_path, file_data, file_options=extra)
            public_url = client.storage.from_(bucket_name).get_public_url(clean_path)
            logger.info(f"[OK] File successfully uploaded to Supabase bucket '{bucket_name}' path '{clean_path}' (Attempt {attempt}).")
            return public_url
        except Exception as exc:
            logger.warning(f"[WARN] Supabase upload attempt {attempt} failed for '{clean_path}' in bucket '{bucket_name}': {exc}")
            if attempt == 3:
                logger.error(f"[ERR] Failed to upload '{clean_path}' to Supabase bucket '{bucket_name}' after 3 attempts.")
                raise exc
            else:
                time.sleep(attempt * 0.5)
