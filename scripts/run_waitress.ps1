$ErrorActionPreference = "Stop"
if (-not (Test-Path ".env")) {
    Write-Error "Create .env from .env.example before production startup."
}
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python -m waitress --listen=127.0.0.1:8000 --threads=8 event_platform.wsgi:application
