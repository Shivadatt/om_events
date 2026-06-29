$ErrorActionPreference = "Stop"
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py runserver 127.0.0.1:8000

