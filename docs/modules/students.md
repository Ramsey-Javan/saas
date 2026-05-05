# Student Module Documentation

## 1. Overview

The **Students** module manages the complete lifecycle of student records in the school management system. It handles:
- Student admission, enrollment, and demographic data
- Student-guardian relationships
- Classroom assignments and transfers
- Status transitions (Active → Transferred → Graduated → Dropped)
- Bulk CSV import for mass student enrollment
- Multi-tenanted data isolation (schema-per-tenant)

**Stack:**
- Backend: Django 5 + Django REST Framework (DRF)
- Frontend: React + Vite + Tailwind + Zustand
- Auth: JWT tokens via tenant isolation
- Database: Multi-tenant with django-tenants

**Key File Paths:**
- Backend: `backend/students/`
- Frontend: `frontend/src/pages/students/` + `frontend/src/api/students.js`

---

## 2. Models

### Student
Represents an enrolled student with personal, academic, and medical information.

| Field | Type | Required | Unique | Notes |
|-------|------|----------|--------|-------|
| `id` | Integer | ✓ | ✓ | Primary key |
| `admission_number` | String(50) | ✓ | ✓ (per tenant) | Unique enrollment ID |
| `first_name` | String(150) | ✓ | | |
| `middle_name` | String(150) | | | Optional |
| `last_name` | String(150) | ✓ | | |
| `user` | FK(User) | | | OneToOne, null/blank (account optional) |
| `tenant` | FK(Tenant) | ✓ | | Schema isolation |
| `date_of_birth` | Date | ✓ | | Auto-calculated age property |
| `gender` | Choice | ✓ | | 'M' \| 'F' |
| `classroom` | FK(Classroom) | | | null/blank allowed |
| `primary_guardian` | FK(Guardian) | | | null/blank allowed |
| `status` | Choice | ✓ | | Default: 'active' |
| `admission_date` | DateTime | ✓ | | auto_now_add |
| `photo` | Image | | | Upload to `students/` media folder |
| `blood_group` | String(5) | | | e.g., 'O+', 'A-' |
| `birth_certificate_no` | String(100) | | | Government ID |
| `nemis_no` | String(100) | | | Education ministry ID |
| `medical_notes` | Text | | | Allergies, conditions, etc. |
| `special_needs` | Text | | | SEN documentation |
| `is_active` | Boolean | ✓ | | Soft delete flag (false = archived) |
| `created_at` | DateTime | ✓ | | auto_now_add |
| `updated_at` | DateTime | ✓ | | auto_now |

**Status Choices:**
```python
ACTIVE      = 'active'       # Enrolled, attending classes
TRANSFERRED = 'transferred'  # Moved to another school
GRADUATED   = 'graduated'    # Completed final grade
DROPPED     = 'dropped'      # Left school (archived)
```

**Key Methods:**
- `get_full_name()` → Returns "FirstName MiddleName LastName" (trimmed)
- `age` (property) → Integer years from date_of_birth
- `__str__()` → "FirstName LastName - ADM123"

**Constraints:**
- Composite unique: `(tenant, admission_number)`
- Soft-delete via `is_active=False` (not permanent deletion)

---

### Classroom
Represents a class cohort within an academic year.

| Field | Type | Required | Unique | Notes |
|-------|------|----------|--------|-------|
| `id` | Integer | ✓ | ✓ | |
| `tenant` | FK(Tenant) | ✓ | | Tenant isolation |
| `name` | String(50) | ✓ | | e.g., 'Grade 4', 'PP1' |
| `grade_level` | String(50) | ✓ | | Normalized grade (for filtering) |
| `stream` | String(10) | | | e.g., 'A', 'B', 'West' (blank allowed) |
| `class_teacher` | FK(User) | | | Related to teacher/admin user |
| `academic_year` | String(20) | ✓ | | e.g., '2024', '2025' |
| `capacity` | Integer | | | Default: 40 (max enrollment) |
| `is_active` | Boolean | ✓ | | Default: True |
| `created_at` | DateTime | | | auto_now_add |
| `updated_at` | DateTime | | | auto_now |

**Unique Constraint:**
- Composite: `(tenant, name, stream, academic_year)`

**Key Properties:**
- `student_count` → Count of active students in classroom
- `__str__()` → "Grade 4 A" or "Grade 4" (if no stream)

---

### Guardian
Represents a parent/guardian linked to one or more students.

| Field | Type | Required | Unique | Notes |
|-------|------|----------|--------|-------|
| `id` | Integer | ✓ | ✓ | |
| `user` | FK(User) | | | OneToOne, optional (parent account) |
| `first_name` | String(150) | ✓ | | |
| `last_name` | String(150) | ✓ | | |
| `phone` | String(15) | ✓ | | SMS contact |
| `alt_phone` | String(15) | | | Secondary contact |
| `email` | Email | | | Optional communication |
| `relationship` | String(50) | ✓ | | e.g., 'Mother', 'Father', 'Aunt' |
| `national_id` | String(50) | | | Government ID for verification |
| `occupation` | String(100) | | | e.g., 'Teacher', 'Business' |
| `is_primary` | Boolean | | | Primary contact flag |

**Key Properties:**
- `full_name` / `name` → "FirstName LastName"
- `phone_number` → Alias for `.phone`

---

### Admission
Secondary model storing admission-specific metadata.

| Field | Type | Notes |
|-------|------|-------|
| `id` | Integer | |
| `student` | FK(Student) | OneToOne |
| `admission_date` | Date | auto_now_add |
| `class_admitted` | String(50) | Original class |
| `previous_school` | String(255) | Transfer history |
| `status` | Choice | 'active' \| 'inactive' |

---

## 3. API Endpoints

### Student List & Create
```
GET    /api/students/
POST   /api/students/
```

**Permissions:**
- GET: `IsAuthenticated` (teacher, admin, bursar, parent filtered)
- POST: `IsSchoolAdmin` (admin, superadmin only)

**Query Parameters (GET):**
- `page` (int) - Pagination (default: 1)
- `search` (string) - Search by first_name, last_name, admission_number, nemis_no
- `classroom` (int) - Filter by classroom ID
- `gender` (string) - 'M' or 'F'
- `status` (string) - 'active', 'transferred', 'graduated', 'dropped'
- `classroom__grade_level` (string) - Filter by grade
- `show_all` (bool, string: "true"/"false") - Include inactive (default: false)

**Request Body (POST):**
```json
{
  "admission_number": "ADM2024001",
  "first_name": "John",
  "middle_name": "Paul",
  "last_name": "Doe",
  "gender": "M",
  "date_of_birth": "2015-03-20",
  "classroom": 5,
  "primary_guardian": 12,
  "photo": "<file>",
  "nemis_no": "NEM123456",
  "birth_certificate_no": "CERT789",
  "blood_group": "O+",
  "medical_notes": "Allergy to peanuts",
  "special_needs": "None"
}
```

**Response (GET - List):**
```json
{
  "count": 145,
  "next": "http://api/students/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "admission_number": "ADM2024001",
      "full_name": "John Paul Doe",
      "first_name": "John",
      "last_name": "Doe",
      "gender": "M",
      "classroom": 5,
      "classroom_name": "Grade 4 A",
      "status": "active",
      "guardian_phone": "+254712345678",
      "age": 9,
      "photo": "http://media/students/photo.jpg"
    }
  ]
}
```

**Response (POST - Create):**
```json
{
  "id": 146,
  "admission_number": "ADM2024001",
  "first_name": "John",
  "middle_name": "Paul",
  "last_name": "Doe",
  "full_name": "John Paul Doe",
  "gender": "M",
  "date_of_birth": "2015-03-20",
  "age": 9,
  "classroom": 5,
  "classroom_data": {
    "id": 5,
    "name": "Grade 4",
    "stream": "A",
    "academic_year": "2024"
  },
  "primary_guardian": 12,
  "primary_guardian_data": {
    "id": 12,
    "first_name": "Jane",
    "last_name": "Doe",
    "phone": "+254712345678",
    "relationship": "Mother"
  },
  "status": "active",
  "is_active": true,
  "created_at": "2024-05-05T10:30:00Z",
  "updated_at": "2024-05-05T10:30:00Z"
}
```

**Error Codes:**
- `400` - Validation error (e.g., duplicate admission_number)
- `401` - Unauthorized (not authenticated)
- `403` - Forbidden (insufficient permissions)
- `404` - Not found

---

### Student Detail, Update, Delete
```
GET    /api/students/<id>/
PATCH  /api/students/<id>/
DELETE /api/students/<id>/
```

**Permissions:**
- GET: `IsAuthenticated`
- PATCH, DELETE: `IsSchoolAdmin`

**Request Body (PATCH):**
```json
{
  "first_name": "Jonathan",
  "classroom": 6,
  "photo": "<file>",
  "blood_group": "A+"
}
```
All fields are optional. Read-only fields: `created_at`, `updated_at`, `admission_date`, `status`, `is_active`, `age`.

**Response:**
Same structure as POST (StudentDetailSerializer).

**DELETE Behavior:**
Soft-delete: Sets `is_active=False` and `status='dropped'`.
```json
{
  "detail": "Student archived as dropped."
}
```

---

### Student Search
```
GET /api/students/search/?q=<query>
```

**Permissions:** `IsAuthenticated`

**Query Parameters:**
- `q` (string, min 2 chars) - Search term

**Response:**
```json
[
  {
    "id": 1,
    "admission_number": "ADM2024001",
    "full_name": "John Paul Doe",
    "first_name": "John",
    "last_name": "Doe",
    "gender": "M",
    "classroom": 5,
    "classroom_name": "Grade 4 A",
    "status": "active",
    "guardian_phone": "+254712345678",
    "age": 9,
    "photo": "http://media/students/photo.jpg"
  }
]
```
Max results: 10 (lightweight, for dropdowns/autocomplete).

---

### Transfer Student
```
POST /api/students/<id>/transfer/
```

**Permissions:** `IsSchoolAdmin`

**Request Body:**
```json
{
  "classroom": 7
}
```

**Response:**
```json
{
  "detail": "John Paul Doe moved from Grade 4 A to Grade 5 B.",
  "student": { /* StudentDetailSerializer */ }
}
```

---

### Archive / Status Transition
```
POST /api/students/<id>/archive/
```

**Permissions:** `IsSchoolAdmin`

**Request Body:**
```json
{
  "status": "transferred"
}
```
Valid statuses: `"active"`, `"transferred"`, `"graduated"`, `"dropped"`

**Response:**
```json
{
  "detail": "Student status changed to transferred.",
  "student": { /* StudentDetailSerializer */ }
}
```
**Side Effect:** When status is set to non-active, `is_active` is set to False.

---

### Promote All Students
```
POST /api/students/promote-all/
```

**Permissions:** `IsSchoolAdmin`

**Request Body:**
```json
{
  "confirm": true
}
```

**Behavior:**
1. Increments all active students to next grade (e.g., Grade 4 → Grade 5)
2. Grade 9 students → Archived as `graduated`, `is_active=False`
3. Creates new classrooms if they don't exist
4. Atomic transaction (all-or-nothing)
5. Respects tenant isolation

**Response:**
```json
{
  "promoted_count": 120,
  "graduated_count": 25,
  "skipped": [
    {
      "student_id": 5,
      "admission_number": "ADM2024005",
      "reason": "Student has no classroom"
    }
  ]
}
```

**Errors:**
- `400` - confirm not true, or unsupported grade levels

---

### Bulk Import (CSV)
```
POST /api/students/bulk-import/
GET  /api/students/import-template/
```

**Permissions:** `IsSchoolAdmin`

**GET Template:**
Downloads CSV with headers:
```
admission_number,first_name,middle_name,last_name,gender,date_of_birth,classroom,guardian_name,guardian_phone,nemis_no,blood_group
```

**POST Import:**
Multipart form-data with file:
```
Content-Type: multipart/form-data
file=<csv_file>
```

**CSV Format (example):**
```csv
admission_number,first_name,middle_name,last_name,gender,date_of_birth,classroom,guardian_name,guardian_phone,nemis_no,blood_group
ADM2024100,Alice,Marie,Smith,F,2014-08-15,Grade 5 A,Mary Smith,+254712345678,NEM100001,O+
ADM2024101,Bob,James,Jones,M,2015-01-22,Grade 5 A,John Jones,+254723456789,NEM100002,A-
```

**Response:**
```json
{
  "imported": 98,
  "skipped": 2,
  "errors": [
    {
      "row": 50,
      "admission_number": "ADM2024050",
      "error": "Invalid date format for 2014-13-45"
    }
  ]
}
```

---

### Classrooms - List & Create
```
GET  /api/students/classrooms/
POST /api/students/classrooms/
```

**Permissions:**
- GET: `IsAuthenticated`
- POST: `IsSchoolAdmin`

**Query Parameters (GET):**
- `year` (string) - Filter by academic_year
- `grade` (string) - Filter by grade_level

**Request Body (POST):**
```json
{
  "name": "Grade 5",
  "grade_level": "Grade 5",
  "stream": "B",
  "class_teacher": 3,
  "academic_year": "2024",
  "capacity": 45
}
```

**Response:**
```json
{
  "count": 12,
  "results": [
    {
      "id": 5,
      "name": "Grade 5",
      "grade_level": "Grade 5",
      "stream": "B",
      "class_teacher": 3,
      "class_teacher_name": "Mr. John Kamau",
      "academic_year": "2024",
      "capacity": 45,
      "student_count": 42
    }
  ]
}
```

---

### Classrooms - Detail, Update, Delete
```
GET    /api/students/classrooms/<id>/
PATCH  /api/students/classrooms/<id>/
DELETE /api/students/classrooms/<id>/
```

**Permissions:** `IsSchoolAdmin`

---

### Classroom Students
```
GET /api/students/classrooms/<id>/students/
```

**Permissions:** `IsAuthenticated`

**Response:**
List of StudentListSerializer objects for the classroom.

---

### Guardians - List & Create
```
GET  /api/students/guardians/
POST /api/students/guardians/
```

**Permissions:** `IsAuthenticated`

**Query Parameters (GET):**
- `search` (string) - Search by first_name, last_name, phone, national_id

**Request Body (POST):**
```json
{
  "first_name": "Jane",
  "last_name": "Doe",
  "phone": "+254712345678",
  "alt_phone": "+254734567890",
  "email": "jane@example.com",
  "relationship": "Mother",
  "national_id": "12345678",
  "occupation": "Teacher"
}
```

**Response:**
```json
{
  "count": 350,
  "results": [
    {
      "id": 12,
      "first_name": "Jane",
      "last_name": "Doe",
      "phone": "+254712345678",
      "alt_phone": "+254734567890",
      "email": "jane@example.com",
      "relationship": "Mother",
      "national_id": "12345678",
      "occupation": "Teacher",
      "user": null
    }
  ]
}
```

---

### Guardians - Detail, Update, Delete
```
GET    /api/students/guardians/<id>/
PATCH  /api/students/guardians/<id>/
DELETE /api/students/guardians/<id>/
```

**Permissions:** `IsSchoolAdmin` (POST allowed only to IsAuthenticated per view)

---

## 4. Serializers

### StudentListSerializer
**Used for:** List views (lightweight representation)

**Fields:**
- `id`, `admission_number`, `full_name` (computed), `first_name`, `last_name`, `gender`
- `classroom` (ID), `classroom_name` (computed)
- `status`, `guardian_phone` (computed from primary_guardian), `age` (computed)
- `photo`

**Read-only Computed Fields:**
- `full_name` → calls `Student.get_full_name()`
- `classroom_name` → string representation of classroom
- `guardian_phone` → `primary_guardian.phone` or None
- `age` → computed from date_of_birth

---

### StudentDetailSerializer
**Used for:** Create, retrieve, update operations (full representation)

**Fields:**
- All StudentListSerializer fields plus:
- `middle_name`, `date_of_birth`, `birth_certificate_no`, `nemis_no`
- `classroom_data` (nested ClassroomSerializer, read-only)
- `primary_guardian` (ID), `primary_guardian_data` (nested GuardianSerializer, read-only)
- `blood_group`, `medical_notes`, `special_needs`
- `is_active`, `admission_date`, `created_at`, `updated_at`

**Read-only Fields:**
- `created_at`, `updated_at`, `admission_date`, `status`, `is_active`, `age`, `full_name`
- `primary_guardian_data`, `classroom_data`

**Validation:**
- `admission_number`: Must be unique per tenant (checked in `.validate_admission_number()`)

---

### ClassroomSerializer
**Fields:**
- `id`, `name`, `grade_level`, `stream`, `class_teacher`, `class_teacher_name` (computed)
- `academic_year`, `capacity`, `student_count` (computed)

**Read-only:**
- `student_count` → counts active students in classroom
- `class_teacher_name` → `class_teacher.get_full_name()` if exists

---

### GuardianSerializer
**Fields:**
- `id`, `first_name`, `last_name`, `phone`, `alt_phone`, `email`
- `relationship`, `national_id`, `occupation`, `user` (ID)

**Read-only:**
- `user` (set automatically on creation if linked)

---

## 5. Permissions Matrix

| Endpoint | Method | Anonymous | Parent | Teacher | Bursar | Admin | Superadmin |
|----------|--------|-----------|--------|---------|--------|-------|-----------|
| `/students/` | GET | ✗ | Own children | ✓ | ✓ | ✓ | ✓ |
| `/students/` | POST | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| `/students/<id>/` | GET | ✗ | Own only | ✓ | ✓ | ✓ | ✓ |
| `/students/<id>/` | PATCH | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| `/students/<id>/` | DELETE | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| `/students/search/` | GET | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `/students/<id>/transfer/` | POST | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| `/students/<id>/archive/` | POST | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| `/students/promote-all/` | POST | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| `/students/bulk-import/` | POST | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| `/classrooms/` | GET | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `/classrooms/` | POST | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| `/classrooms/<id>/` | GET/PATCH/DELETE | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| `/guardians/` | GET | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `/guardians/` | POST | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `/guardians/<id>/` | GET/PATCH/DELETE | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |

**Key Rules:**
- All endpoints require JWT authentication (except for public-facing pages outside API)
- Parents filtered to only view/access their own children (via `primary_guardian` relationship)
- Teachers have read-only access to student data
- Bursars have read-only access for billing/fee management
- Admin/Superadmin have full CRUD access

---

## 6. Frontend Pages

### StudentsPage
**Route:** `/students`
**Purpose:** Browse, search, and manage active students
**Key Features:**
- Paginated list (25 per page by default)
- Multi-filter sidebar: Grade, Classroom, Gender, Status
- Search bar: Searches admission_number, first_name, last_name
- Action buttons: "Admit Student" (→ AdmitStudentPage), "Bulk Import" (→ BulkImportPage)
- Classroom dropdown (reactive filter)
- Status badges (Active, Transferred, Graduated, Dropped)

**State Management (Zustand assumed):**
```javascript
const [students, setStudents] = useState([])
const [classrooms, setClassrooms] = useState([])
const [filters, setFilters] = useState({
  classroom: '', 
  gender: '', 
  grade: '', 
  status: 'active'  // Default to active
})
const [search, setSearch] = useState('')
const [page, setPage] = useState(1)
const [totalCount, setTotalCount] = useState(0)
```

**API Calls:**
- `studentsApi.getClassrooms()` - On mount
- `studentsApi.getStudents(params)` - On filter/search change (debounced)

**Response Handling:**
```javascript
const list = data?.results || (Array.isArray(data) ? data : [])
```

---

### AdmitStudentPage
**Route:** `/students/new`, `/students/:id` (edit mode)
**Purpose:** Create new or edit existing student record
**Key Features:**
- Two-step form: Student info + Guardian info
- Photo upload with preview (Camera icon)
- Classroom selector (auto-populated from backend)
- Gender radio: Male/Female
- Date picker for DOB
- Optional fields: Blood group, Medical notes, Special needs
- Form validation (Zod + React Hook Form)
- Error handling with toast notifications

**Form Schema:**
```javascript
const studentFields = {
  admission_number: string().min(1),
  first_name: string().min(1),
  middle_name: string().optional(),
  last_name: string().min(1),
  gender: enum(['M', 'F']),
  date_of_birth: string().min(1),
  classroom: string().min(1),
  nemis_no: string().optional(),
  birth_certificate_no: string().optional(),
  blood_group: string().optional(),
  medical_notes: string().optional(),
}

const guardianFields = {
  guardian_first_name: string().min(1),
  guardian_last_name: string().min(1),
  guardian_phone: string().min(10),
  guardian_relationship: string().min(1),
  guardian_national_id: string().optional(),
}

// Create uses both, Edit uses studentFields only
```

**API Calls:**
- `studentsApi.getClassrooms()` - On mount (dropdown population)
- `studentsApi.getStudent(id)` - On mount if editing (load data)
- `studentsApi.createStudent(formData)` - On submit (create mode)
- `studentsApi.updateStudent(id, formData)` - On submit (edit mode)

**Photo Handling:**
```javascript
// Convert to FormData for multipart upload
const formData = new FormData()
if (photoFile) formData.append('photo', photoFile)
formData.append('first_name', data.first_name)
// ... other fields
```

---

### StudentDetailPage
**Route:** `/students/:id` (view-only, edit via AdmitStudentPage)
**Purpose:** View full student record with readonly display
**Expected Features:**
- Full student info (demographics, medical, academic)
- Guardian details (name, phone, email)
- Classroom assignment
- Student photo (large)
- Action buttons: Edit (→ AdmitStudentPage), Generate ID Card (→ StudentIdCardPage)
- Status badge with change dropdown (admin only)

**API Calls:**
- `studentsApi.getStudent(id)` - On mount

---

### StudentIdCardPage
**Route:** `/students/:id/id-card`
**Purpose:** Generate and print student ID card
**Features:** Name, admission number, photo, class, QR code (optional)

---

### BulkImportPage
**Route:** `/students/import`
**Purpose:** CSV bulk import for enrollment campaigns
**Features:**
- Download template button (→ CSV file)
- File upload input
- Preview table of pending imports
- Import button with confirmation modal
- Progress bar during import
- Success/error summary

**API Calls:**
- `studentsApi.downloadImportTemplate()` - On "Download Template"
- `studentsApi.bulkImport(formData)` - On "Import" submission

---

## 7. Status Flow Diagram

```
                    ┌─────────────┐
                    │   ACTIVE    │ (Enrolled, attending)
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        ┌─────────────┐ ┌──────────┐ ┌──────────┐
        │ TRANSFERRED │ │GRADUATED │ │  DROPPED │
        │(moved school)│ │(Gr 9→end)│ │(left)    │
        └─────────────┘ └──────────┘ └──────────┘
              
    ── promote-all endpoint ──→ Grade 9: GRADUATED, is_active=False
    ── transfer endpoint ────→ ACTIVE (but different classroom)
    ── archive endpoint ────→ New status set
    ── DELETE endpoint ─────→ is_active=False, status=DROPPED

    Status Transitions:
    - ACTIVE → TRANSFERRED (manual via archive endpoint)
    - ACTIVE → GRADUATED (automatic on promote-all, is_active=False)
    - ACTIVE → DROPPED (on DELETE, is_active=False)
    - TRANSFERRED → ACTIVE (manual re-admission, rare)
    - GRADUATED → (terminal state)
    - DROPPED → (terminal state)

    Note: is_active=False for GRADUATED, DROPPED, TRANSFERRED
          is_active=True only for ACTIVE status
```

---

## 8. Setup & Dependencies

### Backend Requirements

**Core Dependencies** (in `requirements.txt`):
```
Django==5.0
djangorestframework>=3.14.0
django-tenants>=3.0.0        # Multi-tenancy
django-filter>=23.0           # QuerySet filtering
Pillow>=10.0.0                # Image handling
python-dateutil>=2.8.0        # Date parsing
```

**Django Apps** (in `settings.py`):
```python
INSTALLED_APPS = [
    ...
    'rest_framework',
    'django_filters',
    'tenants',
    'accounts',
    'students',
]
```

**Middleware** (for tenant isolation):
```python
MIDDLEWARE = [
    ...
    'tenants.middleware.TenantMiddleware',  # Must run before auth
    'rest_framework.middleware.MiddlewareName',
]
```

**REST Framework Config**:
```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
    ],
}
```

**URL Registration** (in `core/urls.py`):
```python
from django.urls import path, include

urlpatterns = [
    ...
    path('api/students/', include('students.urls')),
]
```

### Frontend Requirements

**Core Dependencies** (in `package.json`):
```json
{
  "dependencies": {
    "react": "^18.0.0",
    "react-dom": "^18.0.0",
    "react-router-dom": "^6.0.0",
    "zustand": "^4.0.0",
    "axios": "^1.5.0",
    "react-hook-form": "^7.48.0",
    "@hookform/resolvers": "^3.3.0",
    "zod": "^3.22.0",
    "lucide-react": "^0.292.0",
    "tailwindcss": "^3.3.0"
  }
}
```

**Environment Variables** (`.env` or `.env.local`):
```env
VITE_API_BASE_URL=http://localhost:8000
VITE_API_TIMEOUT=10000
```

**API Client Setup** (`src/api/client.js`):
```javascript
import axios from 'axios'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
  timeout: parseInt(import.meta.env.VITE_API_TIMEOUT) || 10000,
})

// Add JWT token interceptor
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export default apiClient
```

### Running Locally

**Backend:**
```bash
cd backend

# Migrations (first time)
python manage.py migrate

# Load demo data (optional)
python manage.py setup_demo

# Start server
python manage.py runserver 0.0.0.0:8000
```

**Frontend:**
```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev  # Vite dev server (typically port 5173)
```

**Docker Compose:**
```bash
docker-compose up -d

# Access:
# - Backend API: http://localhost:8000
# - Frontend: http://localhost:3000 (or configured port)
```

### Database Migrations

**Schema Migrations:**
```bash
python manage.py migrate students

# Check migration status
python manage.py showmigrations students
```

**Initial Setup:**
1. Run core migrations (users, tenants, auth)
2. Run students app migrations
3. Create classrooms via admin or API
4. Admit students via bulk import or API

### Tenant Isolation

All models include `tenant` FK to enforce schema-per-tenant pattern:
- Queries auto-filtered by `request.user.tenant`
- No cross-tenant data leakage
- Each tenant has isolated student records
- Teachers/staff linked to single tenant

### Common Customizations

**Add Photo Processing:**
```python
# In serializers or signals
from PIL import Image

def process_student_photo(image):
    img = Image.open(image)
    img.thumbnail((800, 800))
    img.save(image)
```

**Add SMS Notifications:**
```python
# In views.py signal or celery task
from communication.sms import send_sms

@receiver(post_save, sender=Student)
def notify_guardian_on_admission(sender, instance, created, **kwargs):
    if created and instance.primary_guardian:
        send_sms(
            instance.primary_guardian.phone,
            f"Student {instance.get_full_name()} admitted. Adm: {instance.admission_number}"
        )
```

**Add Attendance Integration:**
```python
# Link attendance records to students
from academics.models import Attendance

student = Student.objects.get(pk=1)
attendance_records = Attendance.objects.filter(student=student)
```

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| 403 Forbidden on POST | Missing `IsSchoolAdmin` role | Verify user role is 'admin' or 'superadmin' |
| Duplicate admission_number error | Submission retry or import conflict | Check `.admission_number` uniqueness; add retry logic |
| Guardian not linked after import | CSV format mismatch | Ensure `guardian_name`, `guardian_phone` columns match |
| File upload fails | Missing `multipart/form-data` header | Use FormData in frontend; check parser_classes on view |
| Parent sees no students | `primary_guardian` not set | Ensure Student record has `primary_guardian` FK to Guardian |
| Promote-all fails | Unsupported grade level format | Ensure classrooms have valid grade_level (PP1, PP2, Grade 1–9) |
| Photo not displaying | Incorrect MEDIA_URL config | Set `MEDIA_URL`, `MEDIA_ROOT` in Django settings |
| CORS errors on file upload | Cross-origin request blocked | Add `django-cors-headers` middleware |

---

## References

- [Django REST Framework Docs](https://www.django-rest-framework.org/)
- [Django-Tenants Docs](https://django-tenants.readthedocs.io/)
- [React Hook Form](https://react-hook-form.com/)
- [Zustand State Management](https://github.com/pmndrs/zustand)
- [Tailwind CSS](https://tailwindcss.com/)

---

**Last Updated:** May 2024
**Module Version:** 1.0
**Authors:** Development Team
