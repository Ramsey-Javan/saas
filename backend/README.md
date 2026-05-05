# SaaS Backend

Django REST framework for multi-tenant school management system.

## Features

- Multi-tenancy support (Schools)
- User authentication with JWT
- Student management (admission, guardians)
- Finance management (fee structures, payments, M-Pesa integration)
- Academic management (classes, subjects, grades, attendance)
- Communication (SMS logs, notifications via Africa's Talking)

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Or seed a local demo tenant + login
python manage.py setup_demo

# Run development server
python manage.py runserver
```

## Environment Variables

```
DJANGO_SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_NAME=saas_db
DB_USER=postgres
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=5432
CORS_ALLOWED_ORIGINS=http://localhost:5173
```
