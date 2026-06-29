# Om Events — Django Event Management Platform

A runnable Django website for browsing event concepts, customising a selection, generating a trusted quotation and PDF, capturing leads, and managing the business through Django Admin.

## Run now

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py runserver
```

Or run the all-in-one starter:

```powershell
.\scripts\start_dev.ps1
```

Open:

- Customer website: `http://127.0.0.1:8000`
- Editorial team dashboard: `http://127.0.0.1:8000/admin`
- Full Django management: `http://127.0.0.1:8000/admin/`
- API reference: `http://127.0.0.1:8000/docs`

Initial administrator:

- Email/username: `admin@omevents.in`
- Password: `ChangeMe123!`

Change this password and both secrets in `.env` before deployment.

## Working features

- Premium responsive interface based on the supplied layout references
- Local royalty-free sample photography and an HD video showcase
- Mobile menu, dark mode, accessibility, motion preferences and loading states
- Database-driven categories, decoration experiences, offers, colors and themes
- Search, filters, sorting, customization and persistent selection
- Server-authoritative subtotal, discount, delivery, travel and GST calculations
- Saved customers and quotations with branded PDF download
- Callback/lead capture with validation and request throttling
- JWT-protected editorial dashboard
- Complete Django Admin CRUD for categories, items, media, leads, quotes, customers, bookings and reviews
- SQLite zero-configuration development and Microsoft SQL Server production support
- Security headers, secure cookies, password validators, upload limits and HTTPS settings
- Docker, Nginx, IIS/Waitress, system checks, migrations and tests

Vendor integrations such as live payments, WhatsApp Business, SMS, email delivery, Azure Blob and Google services require business accounts and credentials. The application does not fake those external services.

## Test

```powershell
python manage.py check
python manage.py test
```

## Microsoft SQL Server

Install Microsoft ODBC Driver 18 and configure `.env`:

```text
DB_ENGINE=mssql
DB_NAME=EventPlatform
DB_USER=event_user
DB_PASSWORD=your-url-unescaped-password
DB_HOST=sqlserver.example.com
DB_PORT=1433
DB_DRIVER=ODBC Driver 18 for SQL Server
DB_EXTRA_PARAMS=TrustServerCertificate=no
```

Then run `python manage.py migrate`. Django migrations in `events/migrations/` are the executable schema source. `database/schema.sql` documents optional reporting and integration tables.

## Production

### Docker and Nginx

Set strong secrets and `SA_PASSWORD` in `.env`, replace the domain in `deploy/nginx.conf`, install certificates in `certs/`, then:

```bash
docker compose up -d --build
```

The container applies migrations, collects static assets and starts Gunicorn automatically.

### Windows and IIS

Run `scripts/run_waitress.ps1` using a dedicated low-privilege service account. Install IIS URL Rewrite and ARR, enable proxying, place `deploy/web.config` at the IIS site root, and bind a trusted TLS certificate.

## Operations

- Logs rotate in `logs/application.log`.
- Back up SQL Server nightly, differentials every six hours, and transaction logs every 15 minutes.
- Back up `uploads/` with versioning and test database restores monthly.
- Keep `DEBUG=false`, enforce HTTPS and replace seed credentials before launch.
- Use a shared Django cache when running multiple application workers.
