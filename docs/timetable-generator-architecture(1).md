# Shule360 Timetable Generator — Architecture

## 1. Decision: Build on OR-Tools, not a forked GitHub repo

Use **Google OR-Tools CP-SAT** (Python, Apache 2.0 license, `pip install ortools`) as the solver engine. You still build everything else yourself — models, constraint rules, API, UI — but the actual "solve the puzzle" math is delegated to a battle-tested constraint programming solver instead of hand-rolled or forked genetic-algorithm code.

Why not a GitHub timetable repo:
- Most are built around their *own* rigid data model (fixed periods, no multi-tenancy, no CBC concept) — you'd spend more time ripping out assumptions than building fresh.
- Many use genetic algorithms / simulated annealing, which give "pretty good" schedules with no guarantee of correctness and are hard to reason about when a school complains "why is Form 2 Blue's Chemistry double lesson split across days?"
- CP-SAT gives you hard-constraint guarantees (never violates a rule you declare as hard) and lets soft preferences act as penalties in an objective function — which maps naturally to "STEM shouldn't be after lunch" (soft) vs "no teacher in two places at once" (hard, non-negotiable).
- It's a library dependency, not a codebase you inherit and maintain.

## 2. Data model (tenant-scoped, new `timetabling` app)

```
ScheduleTemplate        tenant, name (e.g. "PP Schedule", "JSS Schedule")  — see §7a, each grade band gets its own
Period                  tenant, schedule_template (FK), day_of_week, order, start_time, end_time, is_break (bool)
TeacherAvailability     tenant, teacher, period, is_available (default True; block specific slots)
SubjectRule             tenant, subject, grade_band,
                         periods_per_week, requires_double (bool),
                         requires_lab (bool), excluded_periods (M2M to Period,
                         e.g. "no STEM in period right after lunch")
RoomResource             tenant, name, type (lab/classroom/hall), capacity
ClassStream              tenant, grade, stream, schedule_template (FK) — determines which bell schedule this class follows
TeacherSubjectAssignment tenant, teacher, subject, class_stream   (existing HR/academic data)
TimetableJob             tenant, term, status (pending/running/done/failed), created_by, solve_time_seconds
TimetableEntry           tenant, job (FK), class_stream, subject, teacher, room, period, locked (bool)
``

`locked=True` on an entry means "don't touch this on regenerate" — needed once admins start manually drag-editing (your chosen workflow).

`SubjectRule` is deliberately a **rules table, not hardcoded logic** — different CBC schools will want different fine-grained rules (STEM not after lunch is one instance of a general "excluded period" pattern). Keep it configurable per tenant rather than baking "STEM" into code.

## 3. Solver design (hard vs soft constraints)

**Hard constraints (must never be violated):**
- A teacher can't be in two places in the same period.
- A class-stream can't have two subjects in the same period.
- A room/lab can't host two classes in the same period.
- Each subject gets exactly its `periods_per_week` for that class-stream.
- Double-lesson subjects get two *consecutive* periods, same day.
- Respect `TeacherAvailability` blocks.
- Respect `SubjectRule.excluded_periods` (STEM-after-lunch etc.) — modeled as hard by default, but make it a per-rule toggle (hard vs soft) so schools can decide how strict they want to be.
- Lab-requiring subjects only assigned to `RoomResource` of type lab.
- **Teacher workload caps**: max periods per day and per week, per teacher (contractual limit) — add `Teacher.max_periods_per_day` / `max_periods_per_week` and enforce as hard constraints, not just availability blocks.

**Soft constraints (objective function, minimize penalty):**
- Spread a subject's periods across different days rather than clustering.
- Minimize gaps ("free periods sandwiched between classes") in teacher schedules.
- Honor teacher preferences if you capture them later (e.g. "prefers mornings").

CP-SAT handles this natively: hard constraints as `model.Add(...)`, soft ones added to `model.Minimize(sum(penalty_vars))`. Give it a time budget (e.g. 30–60s) via `solver.parameters.max_time_in_seconds` — it returns the best feasible solution found even if not proven optimal, which is what you want for a real-world web request.

## 4. Async execution (Celery)

Solving is not instant — treat it like a background job, not a request/response call:

1. `POST /api/timetable/generate/` → validates config completeness (all subjects have rules, all classes have teacher assignments) → creates `TimetableJob(status=pending)` → dispatches Celery task → returns `job_id` immediately.
2. Celery task builds the CP-SAT model from tenant data, solves, writes `TimetableEntry` rows, sets `status=done` (or `failed` with a reason — e.g. "infeasible: Form 2 Blue has 3 subjects with no available teacher").
3. Frontend polls `GET /api/timetable/jobs/<id>/` (or use your existing notification channel) until done, then renders the grid.

For your ~1,030-student public school: see §7c below — you can *only* solve grade bands independently if they share no teachers or rooms. Since shared labs and some teachers likely cross bands, plan on one unified model per term with shared-resource constraints coupling the bands, and benchmark solve time once you have real data volume.

## 5. Manual editing after generation

Since you want drag-edit after auto-generate:
- Build a **lightweight validator function** shared between the solver's hard constraints and the manual-edit endpoint — same rules, two callers. This keeps "the solver says it's valid" and "the UI says it's valid" from drifting apart.
- `PATCH /api/timetable/entries/<id>/` runs the validator against the proposed change (teacher/room/class clash, availability, excluded periods) before committing. Reject with a specific reason if it fails, don't silently allow a clash.
- Manually edited entries get `locked=True` so a future "regenerate" doesn't overwrite an admin's deliberate override.

## 6. Frontend

- Grid component: days × periods, draggable subject/teacher blocks (react-dnd or dnd-kit).
- Color-code by subject or by hard/soft-violation status if you ever allow provisional invalid states.
- "Regenerate" respects locked cells; "Regenerate all" clears locks with a confirmation.

## 7. Handling tenant heterogeneity (labs, rooms, and different bell schedules per grade band)

Three real gaps in the model above, all fixed by the same underlying change: stop treating "period" as one grid per tenant, and stop treating room-clash as "same period number."

### 7a. Different bell schedules per grade band (PP vs Junior vs Senior)

Replace the flat `Period` table with a **`ScheduleTemplate`** layer:

```
ScheduleTemplate   tenant, name (e.g. "PP Schedule", "Upper Primary", "JSS")
Period             tenant, schedule_template (FK), day_of_week, order,
                    start_time, end_time, is_break
ClassStream        ...existing fields..., schedule_template (FK)
```

Each grade band gets its own template with its own break/lunch clock times. A `ClassStream` (Grade 3 West, Grade 8 Blue, etc.) points at whichever template applies to it. This is purely a config screen for the school admin during setup — "define your PP bell schedule, define your JSS bell schedule" — no code changes needed per school.

Critically: because every `Period` still carries real `start_time`/`end_time`, you can always answer "do these two periods overlap in actual clock time?" even when they come from different templates. That's the piece that makes the next two problems solvable.

### 7b. Rooms/labs are optional per tenant — don't hardcode

`RoomResource` and `SubjectRule.requires_lab` are already tenant-scoped in the model above, so this mostly falls out for free:

- School A creates a `RoomResource(type=lab)` and sets `requires_lab=True` on their Computer Studies `SubjectRule`.
- School B never creates a lab `RoomResource` at all, and leaves `requires_lab=False` on their own Computer Studies `SubjectRule` row (or the config UI simply doesn't offer "lab" as an option if no lab room exists for that tenant).
- Add a **pre-solve validation step**: before dispatching the Celery job, check that every `SubjectRule` with `requires_lab=True` has at least one matching `RoomResource` for that tenant. Fail fast with "Computer Studies requires a lab but none is configured" rather than letting the solver return a cryptic "infeasible."

Also worth adding: **most subjects don't need a tracked room at all** — Math, English, Kiswahili etc. just happen in the class's home classroom. Only model room-booking for *scarce shared resources* (lab, hall, music room). This keeps the room-constraint set small and fast instead of tracking a room for every single period.

### 7c. Cross-grade-band room contention (Grade 3 West and Grade 8 both want the lab)

This is where "same period number" breaks down — Grade 3 West's period 4 and Grade 8's period 4 may not even be at the same clock time if they're on different `ScheduleTemplate`s. The fix: model room bookings as **time intervals on a shared timeline, not period indices**.

OR-Tools CP-SAT has exactly the primitive for this: `NewOptionalIntervalVar` + `AddNoOverlap`. For each `RoomResource`, every candidate (class_stream, subject, period) assignment that would use that room becomes an optional interval `[period.start_time, period.end_time)`; `AddNoOverlap` on all intervals for that room guarantees the solver never double-books it — regardless of which grade band's schedule template each class is on, and regardless of whether the period numbers match.

The same real-time-interval approach also fixes a subtler bug the naive design would've had: **a teacher who teaches across grade bands** (say, a Computer Studies teacher covering both Grade 3 and Grade 8) needs their own clashes checked in real clock time too, not by period index — same `AddNoOverlap` pattern applied per teacher instead of per room.

**Practical implication for solving:** you can't solve each grade band as a fully independent CP-SAT model anymore if they share teachers or rooms, since the constraint (no room double-booked) spans bands. Solve per school-term as one unified model whose variables span all grade bands, with the shared-resource `NoOverlap` constraints tying them together. It's still fast — the number of shared-resource intervals (labs, halls, shared teachers) is much smaller than the full timetable, so the cross-band coupling is limited, not a full-join.

## 8. Admin workflow: who assigns teachers to classes, and how "bands" differ per school

The core insight: **the system never needs to know "this teacher is a junior-school teacher."** That's not a fact you model — it's an *outcome* that falls out of which classes a teacher gets explicitly assigned to. `TeacherSubjectAssignment` (already in §2) is the single source of truth:

```
TeacherSubjectAssignment   tenant, teacher, subject, class_stream
```

- School where teachers span Grade 1–9: that teacher simply has assignment rows across many class_streams in different bands. Nothing special happens — §7c's real-time-overlap clash checking already handles a teacher who crosses bands correctly.
- School split into bands (1–3 / 4–6 / 7–9, or 2 slots): teachers' assignment rows just happen to cluster within one band. Again, nothing extra needed — it's an emergent pattern from the data, not a rule you have to encode.
- You never hardcode "Grade 1–3 teachers can't teach Grade 8" — if a school genuinely enforces that, it's just a fact about which rows they create, not a system constraint.

Optionally, add a **non-binding `teaching_band` tag on the Teacher profile** purely as a UI convenience (lets an admin filter "show me only senior-band teachers" in a big dropdown at a large school) — but it should never feed the solver. If it did, you'd be baking one school's staffing philosophy into logic that has to work for every tenant.

### Admin-facing setup flow (per term)

Most of this reuses data you already have (Teacher, Subject, ClassStream from HR/academic modules) — the timetable module adds the *rules* and *assignments* layered on top:

1. **Log in as admin → Timetable module → "Set up new term."**
2. **Bell schedules** (§7a): create/reuse `ScheduleTemplate`s, only edited when a school changes break/lunch timing — persists term to term otherwise.
3. **Rooms**: create/reuse `RoomResource`s (labs, hall) — only relevant for schools that have them.
4. **Subject rules**: per subject per grade band — periods/week, double-lesson, requires_lab, excluded periods. Pre-fill from last term, admin edits deltas only.
5. **Teacher-subject-class assignment** — the step that actually changes most each term. This will be tedious at 1,000+ students unless the UI supports bulk entry: e.g. pick a teacher → pick a subject → multi-select all class streams they cover in one action, rather than one row per class. This is the highest-leverage screen to get right in the UI, since it's the one admins touch every term.
6. **Readiness check** (run automatically, block "Generate" until clean): every `(class_stream, subject)` implied by the subject rules has at least one teacher assigned; every `requires_lab` rule has a matching room; flag any teacher whose assigned periods look like an overload (soft warning, not necessarily a block).
7. **Generate** → Celery job as in §4 → review grid → drag-edit / lock → publish.

Steps 2–4 are largely set-once-per-school, low-frequency edits. Step 5 is the recurring term-to-term admin burden — worth investing UI effort there specifically (CSV import for assignments could be worth it once a school's staff list is large, similar to how you already think about CSV import for students).

## 10. Conflict diagnostics, live progress, and incremental re-solve

Three UX-critical gaps from the first draft:

**Conflict diagnostics on infeasibility.** Don't surface a raw "infeasible" — CP-SAT can identify a minimal set of conflicting constraints (via `AssumptionsAndCoreExtraction` or by relaxing constraints one group at a time and re-solving to find which one flips the result). Practical approach: run a "diagnostic pass" only when the main solve fails — relax each hard-constraint *category* in turn (workload caps, room availability, teacher availability) and report which relaxation made it feasible, e.g. "Grade 7A has no valid schedule: Chemistry needs 2 lab periods/week but the lab has only 1 free slot matching Grade 7A's schedule template." This is a second, cheaper solver pass, not something to build into the main solve.

**Live progress during solve.** CP-SAT's solver callback (`SolutionCallback`) fires each time it finds a better solution, with the current objective value. Have the Celery task write `TimetableJob.current_score` / `best_bound` on each callback; frontend polls and renders a progress indicator ("optimizing... penalty score improving") rather than a blank spinner for the 30–60s solve window.

**Incremental re-solve.** When a teacher leaves mid-term or a room becomes unavailable, don't force a full regenerate that could reshuffle every class's schedule. Design the solver call to accept a "fixed" subset from the start: pass all existing `TimetableEntry` rows *except* the ones touching the affected teacher/room/class as pre-set hard constraints (equivalent to `locked=True`, reusing the same mechanism from §5/§8), and let the solver only fill in the gap. This is the same CP-SAT model as a full generate — just with most variables pre-fixed — so it doesn't need separate solver logic, only a different Celery task entry point (`regenerate_partial(job, affected_class_streams)` vs `generate_full(job)`).

## 11. Where the proposal overshoots current scale

Worth being direct about this rather than adopting it wholesale: a dedicated message queue (RabbitMQ/Kafka), a separate solver microservice possibly in Java (Timefold/OptaPlanner), and per-tenant worker resource isolation are solving problems for a multi-region, many-large-tenant deployment. Right now you're one Azure B2als VM, Celery+Redis already running, one live client at ~1,030 students, planning a move to Oracle's free tier. At that scale:

- **Celery + Redis is the queue.** It already gives you async job execution, retries, and status tracking — a second message broker (RabbitMQ/Kafka) buys you higher throughput and stronger delivery guarantees you don't need yet, at the cost of another moving part to run and pay for.
- **The solver runs as a Celery task in the same Django/Python codebase**, calling `ortools` directly — not a separate Java microservice. Introducing a second language/runtime for one feature is a maintenance tax with no payoff until you have enough tenants that the solver genuinely needs independent scaling from the rest of the API.
- **Worker resource caps / tenant rate limiting** matter once you have many tenants solving concurrently and a large one could starve a small one. With one active client, this is a real concern to *design for* (keep the solver as an isolated Celery queue/worker pool, separate from your web-request workers, so a slow solve never blocks ordinary API traffic) but not to build (no need for per-tenant quotas yet).
- **Schema-per-tenant** is moot — you already deliberately chose shared-schema + tenant FK for the whole platform; revisiting that for timetabling alone would break consistency with every other module.

The right move: build the solver as a Celery task using OR-Tools, on a dedicated Celery queue (separate worker pool from your other background jobs) so a 60-second solve doesn't compete with routine tasks like M-Pesa callback processing. Revisit a standalone solver service only if/when you have enough concurrent tenants that solving genuinely needs to scale independently — that's a "when the data tells you," not a v1 decision.

## 12. Suggested build order

1. Models + admin config UI for `Period`, `SubjectRule`, `RoomResource` (schools need to set these up before anything can generate).
2. Solver service (`timetabling/services/solver.py`) — get it working correctly on one real school's data via a management command before wiring up Celery/API.
3. Celery task + job status API.
4. Read-only timetable view (grid, per class and per teacher).
5. Manual drag-edit + shared validator.
6. Soft-constraint tuning once real schools give feedback on generated output quality.

Steps 1–2 are the highest-risk, highest-value part — get the constraint model right on paper/one school before building UI around it.
