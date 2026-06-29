from datetime import timedelta
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Base Directory Setup
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment configuration
load_dotenv(BASE_DIR / ".env")

# Basic Settings
SECRET_KEY = os.getenv("SECRET_KEY", "django-development-key-change-before-production-please")
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = [host.strip() for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host.strip()]

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "events.apps.EventsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "events.middleware.SecurityHeadersMiddleware",
]

ROOT_URLCONF = "event_platform.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "app" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

WSGI_APPLICATION = "event_platform.wsgi.application"
ASGI_APPLICATION = "event_platform.asgi.application"

# Database Configuration
# Fallback to local SQLite unless DB_ENGINE is explicitly set to mssql (migration only)
if os.getenv("DB_ENGINE", "").lower() == "mssql" and "test" not in sys.argv:
    DATABASES = {
        "default": {
            "ENGINE": "mssql",
            "NAME": os.getenv("DB_NAME", "EventPlatform"),
            "USER": os.getenv("DB_USER", ""),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "1433"),
            "OPTIONS": {
                "driver": os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server"),
                "extra_params": os.getenv("DB_EXTRA_PARAMS", "TrustServerCertificate=yes"),
            },
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "instance" / "events.sqlite3",
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Static and Media Files
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "app" / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = DEBUG
WHITENOISE_MAX_AGE = 0 if DEBUG else 31536000

STORAGES = {
    "default": {"BACKEND": "events.supabase_storage.SupabaseStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

MEDIA_URL = "/uploads/"
MEDIA_ROOT = BASE_DIR / "uploads"
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("MAX_CONTENT_LENGTH_MB", "20")) * 1024 * 1024

# Business Configuration Settings
BUSINESS_NAME = os.getenv("BUSINESS_NAME", "Om Events")
BUSINESS_PHONE = os.getenv("BUSINESS_PHONE", "919876543210")
BUSINESS_EMAIL = os.getenv("BUSINESS_EMAIL", "hello@omevents.in")
GST_PERCENT = float(os.getenv("GST_PERCENT", "18"))
DELIVERY_CHARGE = float(os.getenv("DELIVERY_CHARGE", "500"))
TRAVEL_CHARGE = float(os.getenv("TRAVEL_CHARGE", "0"))

# Security Settings for JWT Authentication
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY + "-jwt")
JWT_ACCESS_LIFETIME = timedelta(hours=8)

# Cache Setup
CACHES = {
    "default": {
        "BACKEND": os.getenv("CACHE_BACKEND", "django.core.cache.backends.locmem.LocMemCache"),
        "LOCATION": os.getenv("CACHE_LOCATION", "om-events"),
    }
}

# Production Security Headers
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False

# Dynamic Security settings based on DEBUG environment flag
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "false").lower() == "true"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG

# Firebase & Supabase API Credentials
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY", "")
FIREBASE_PRIVATE_KEY = os.getenv("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n")
FIREBASE_CLIENT_EMAIL = os.getenv("FIREBASE_CLIENT_EMAIL", "")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_BUCKETS = {
    "gallery": os.getenv("SUPABASE_BUCKET_GALLERY", "gallery"),
    "services": os.getenv("SUPABASE_BUCKET_SERVICES", "services"),
    "videos": os.getenv("SUPABASE_BUCKET_VIDEOS", "videos"),
    "profile": os.getenv("SUPABASE_BUCKET_PROFILE", "profile"),
    "users": os.getenv("SUPABASE_BUCKET_USERS", "users"),
    "documents": os.getenv("SUPABASE_BUCKET_DOCUMENTS", "documents"),
    "bookings": os.getenv("SUPABASE_BUCKET_BOOKINGS", "bookings"),
    "thumbnails": os.getenv("SUPABASE_BUCKET_THUMBNAILS", "thumbnails"),
}

# Production Logging Configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("LOG_LEVEL", "INFO"),
    },
}
