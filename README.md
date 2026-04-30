# School SaaS Platform

Multi-tenant school management system built for Kenyan CBC schools with Django + React.

## Stack

- **Backend:** Django + DRF
- **Frontend:** React + Vite + Tailwind
- **DB:** PostgreSQL
- **Queue:** Celery + Redis
- **SMS:** Africa's Talking
- **Payments:** M-Pesa Daraja API

## Backend (Django)

- **core/**: Django settings, URLs, WSGI
- **tenants/**: Multi-tenancy support (Schools)
- **accounts/**: User authentication with JWT
- **students/**: Student, Guardian, Admission models
- **finance/**: Fee structures, Payments, M-Pesa integration
- **academics/**: Classes, Subjects, Grades, Attendance
- **communication/**: SMS logs, Notifications (Africa's Talking)

## Frontend (React + Vite)

- **api/**: Axios client, API endpoints
- **components/**: shadcn/ui + custom components
- **pages/**: Organized by feature (auth, dashboard, etc.)
- **store/**: Zustand state management
- **hooks/**: Custom React hooks

## Getting Started

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Environment Setup

Create `.env` files in both backend and frontend directories with required environment variables.

The backend `.env` supports PostgreSQL, Redis/Celery, M-Pesa Daraja, and Africa's Talking values. Start PostgreSQL, Redis, the Django backend, and the Celery worker with:

```bash
docker compose up -d
```
