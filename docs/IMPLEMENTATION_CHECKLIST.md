
================================================================================
IMPLEMENTATION CHECKLIST — Copy this to your notes
================================================================================

□ STEP 1: Copy test files
  cp /mnt/agents/output/test_*.py backend/tests/

□ STEP 2: Run each file individually to find URL name mismatches
  docker compose exec backend python -m pytest tests/test_students_signals.py -v
  docker compose exec backend python -m pytest tests/test_communication_services.py -v
  docker compose exec backend python -m pytest tests/test_finance_statements.py -v
  docker compose exec backend python -m pytest tests/test_students_views.py -v
  docker compose exec backend python -m pytest tests/test_accounts_views.py -v
  docker compose exec backend python -m pytest tests/test_finance_fees.py -v
  docker compose exec backend python -m pytest tests/test_academics_views.py -v
  docker compose exec backend python -m pytest tests/test_dashboard_views.py -v
  docker compose exec backend python -m pytest tests/test_finance_waivers.py -v
  docker compose exec backend python -m pytest tests/test_communication_views.py -v
  docker compose exec backend python -m pytest tests/test_core_middleware.py -v
  docker compose exec backend python -m pytest tests/test_tenants_views.py -v

□ STEP 3: Fix reverse() URL names
  Common patterns to check:
  - DRF router: 'modelname-list', 'modelname-detail'
  - Custom: 'modelname-action-name'
  - Check your urls.py files for actual names

□ STEP 4: Add missing factories (if any)
  Check error messages for "Factory not found" or model not found

□ STEP 5: Run full suite
  docker compose exec backend python -m pytest tests/ -q --cov --cov-report=html

□ STEP 6: Check coverage report
  Open htmlcov/index.html in browser
  Target: ≥80% overall

□ STEP 7: Fix any remaining failures
  Focus on finance and auth tests first (money + users = critical)

□ STEP 8: Deploy when coverage ≥80% and all tests pass

================================================================================
PRIORITY ORDER (if you're short on time)
================================================================================

  P0 (MUST HAVE before any deployment):
    □ test_finance_payments.py     — already have ✅
    □ test_finance_tasks.py        — already have ✅
    □ test_finance_utils.py        — already have ✅
    □ test_auth_isolation.py       — already have ✅
    □ test_students_signals.py     — NEW — fee auto-generation
    □ test_communication_services.py — NEW — SMS/Email/WhatsApp

  P1 (HIGH — financial system integrity):
    □ test_finance_fees.py         — NEW — fee structures, invoices
    □ test_finance_statements.py   — NEW — statements, defaulters
    □ test_finance_waivers.py      — NEW — discounts, waivers
    □ test_accounts_views.py       — NEW — auth, invites, staff

  P2 (MEDIUM — day-to-day operations):
    □ test_students_views.py       — NEW — student CRUD, guardians
    □ test_communication_views.py  — NEW — announcements, templates
    □ test_academics_views.py      — NEW — exams, attendance, curriculum

  P3 (LOW — nice to have):
    □ test_dashboard_views.py      — NEW — stats, charts
    □ test_tenants_views.py        — NEW — superadmin tenant mgmt
    □ test_core_middleware.py      — NEW — middleware, exceptions

================================================================================
EXPECTED TIME ESTIMATE
================================================================================

  Fixing URL names:        30–60 minutes
  Adding missing factories:  15–30 minutes  
  Debugging test failures:   1–2 hours
  ─────────────────────────────────────
  Total to 80% coverage:   ~2–4 hours

================================================================================
