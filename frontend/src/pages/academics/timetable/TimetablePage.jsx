import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  CalendarClock,
  CheckCircle2,
  Eye,
  Grid3X3,
  Lock,
  Play,
  RefreshCcw,
  Save,
  Upload,
  Users,
  X,
  XCircle,
} from 'lucide-react'
import { academicsApi } from '@/api/academics'
import { studentsApi } from '@/api/students'
import { timetablingApi } from '@/api/timetabling'
import { useAuthStore } from '@/store/authStore'
import { Button, Card, EmptyState, Input, PageHeader, Select, Spinner } from '@/components/ui'
import { Modal, TERMS, classroomLabel, listFromResponse, thisYear } from './shared'
import TimetableSetupWizard from './TimetableSetupWizard'

const DAYS = [
  [1, 'Mon'],
  [2, 'Tue'],
  [3, 'Wed'],
  [4, 'Thu'],
  [5, 'Fri'],
]

const READ_ONLY_EMPTY = {
  title: 'Your timetable has not been generated yet',
  description: 'Check back once your school admin sets it up.',
}

const GENERATION_MESSAGES = [
  'Checking teacher and room availability…',
  'Fitting every subject into the bell schedule…',
  'Balancing each teacher\u2019s workload across the week…',
  'Trying a few different arrangements to find one that fits…',
  'Still working — this can take up to 5 minutes…',
]

function formatElapsed(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

/**
 * Extract the first human-readable error message from any backend response shape.
 * Handles:
 *   - { error: { details: { fields: { teacher: "..." } } } }   ← your backend wrapper
 *   - { detail: "..." }                                         ← standard DRF
 *   - { teacher: ["..."], non_field_errors: ["..."] }           ← standard DRF fields
 *   - { error: { message: "..." } }
 */
function extractApiError(err) {
  const data = err?.response?.data
  if (!data) return err?.message || 'Something went wrong.'

  // 1. Custom wrapped field errors: error.details.fields.{field}
  const fields = data?.error?.details?.fields
  if (fields && typeof fields === 'object') {
    for (const val of Object.values(fields)) {
      if (Array.isArray(val) && val[0]) return val[0]
      if (typeof val === 'string' && val) return val
    }
  }

  // 2. Wrapped generic message (skip the useless "Please correct the errors below")
  const wrappedMsg = data?.error?.message
  if (wrappedMsg && wrappedMsg !== 'Please correct the errors below.') {
    return wrappedMsg
  }

  // 3. Standard DRF detail
  if (data?.detail) return data.detail

  // 4. Standard DRF field errors
  for (const key of ['period', 'teacher', 'room', 'classroom', 'subject', 'non_field_errors', 'job']) {
    const val = data[key]
    if (val) {
      if (Array.isArray(val) && val[0]) return val[0]
      if (typeof val === 'string') return val
    }
  }

  return err?.message || 'Something went wrong.'
}

function SetupChecklist({
  scheduleTemplates,
  rooms,
  assignments,
  readiness,
  onOpenWizard,
}) {
  const [dismissed, setDismissed] = useState(() => {
    try {
      return localStorage.getItem('timetable_checklist_dismissed') === '1'
    } catch {
      return false
    }
  })

  const steps = [
    {
      id: 'bell',
      label: 'Create a bell schedule',
      description: 'Define your school days, periods, and break times (e.g. Mon–Fri, 8 periods).',
      done: scheduleTemplates.length > 0,
    },
    {
      id: 'rooms',
      label: 'Add rooms & labs',
      description: 'Only needed if subjects require special rooms (labs, halls, fields). Most classes use their home classroom.',
      done: rooms.length > 0,
    },
    {
      id: 'rules',
      label: 'Set subject rules',
      description: 'For each subject, set periods per week, double lessons, excluded slots, and room requirements.',
      done: readiness?.has_subject_rules ?? false,
    },
    {
      id: 'teachers',
      label: 'Assign teachers to classes',
      description: 'Link each teacher to the subjects and classrooms they teach.',
      done: assignments.length > 0,
    },
    {
      id: 'generate',
      label: 'Generate the timetable',
      description: 'Let the solver fill the grid. You can drag, edit, and lock lessons afterward.',
      done: false,
    },
  ]

  const allDone = steps.slice(0, 4).every((s) => s.done)
  if (dismissed || allDone) return null

  return (
    <Card className="p-4 border-l-4 border-l-blue-500">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-gray-900">Getting started with timetables</h3>
          <p className="mt-0.5 text-sm text-gray-500">
            Complete these steps to generate your first timetable. You only need to do this once per term.
          </p>
        </div>
        <button
          type="button"
          className="text-xs text-gray-400 hover:text-gray-600"
          onClick={() => {
            setDismissed(true)
            try {
              localStorage.setItem('timetable_checklist_dismissed', '1')
            } catch {}
          }}
        >
          Dismiss
        </button>
      </div>
      <ol className="mt-4 space-y-3">
        {steps.map((step, idx) => (
          <li key={step.id} className="flex items-start gap-3">
            <div
              className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                step.done ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
              }`}
            >
              {step.done ? '✓' : idx + 1}
            </div>
            <div className="flex-1">
              <div className="flex items-center justify-between gap-2">
                <p className={`text-sm font-medium ${step.done ? 'text-gray-500 line-through' : 'text-gray-900'}`}>
                  {step.label}
                </p>
                {!step.done && (
                  <Button size="sm" variant="secondary" onClick={onOpenWizard}>
                    Set up
                  </Button>
                )}
              </div>
              <p className="mt-0.5 text-xs text-gray-500">{step.description}</p>
            </div>
          </li>
        ))}
      </ol>
    </Card>
  )
}

function UploadModal({ classrooms, initial, onClose, onSaved }) {
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    classroom: initial.classroom || '',
    term: initial.term || 'term1',
    academic_year: initial.academic_year || thisYear(),
    file: null,
    notes: '',
  })
  const submit = async (event) => {
    event.preventDefault()
    const data = new FormData()
    Object.entries(form).forEach(([key, value]) => {
      if (value !== null && value !== '') data.append(key, value)
    })
    setSaving(true)
    try {
      await academicsApi.uploadTimetable(data)
      onSaved()
      onClose()
    } finally {
      setSaving(false)
    }
  }
  return (
    <Modal
      title="Upload PDF Fallback"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" form="timetable-upload-form" loading={saving}>Upload</Button>
        </>
      }
    >
      <form id="timetable-upload-form" onSubmit={submit} className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Select
            label="Classroom"
            value={form.classroom}
            onChange={(e) => setForm((f) => ({ ...f, classroom: e.target.value }))}
            required
          >
            <option value="">Select class</option>
            {classrooms.map((c) => (
              <option key={c.id ?? Math.random()} value={c.id ?? ''}>{classroomLabel(c)}</option>
            ))}
          </Select>
          <Select
            label="Term"
            value={form.term}
            onChange={(e) => setForm((f) => ({ ...f, term: e.target.value }))}
          >
            {TERMS.map((term) => (
              <option key={term.value} value={term.value}>{term.label}</option>
            ))}
          </Select>
          <Input
            label="Academic Year"
            type="number"
            value={form.academic_year}
            onChange={(e) => setForm((f) => ({ ...f, academic_year: e.target.value }))}
          />
        </div>
        <label className="flex min-h-28 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-gray-300 bg-gray-50 text-sm text-gray-500">
          <Upload size={20} className="mb-2" />
          {form.file ? form.file.name : 'Select a PDF timetable'}
          <input
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={(e) => setForm((f) => ({ ...f, file: e.target.files?.[0] || null }))}
            required
          />
        </label>
      </form>
    </Modal>
  )
}

function EditEntryModal({ entry, periods, rooms, onClose, onSaved }) {
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [form, setForm] = useState({
    classroom: entry.classroom,
    subject: entry.subject,
    teacher: entry.teacher,
    period: entry.period,
    room: entry.room || '',
  })
  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setSaveError(null)
    try {
      await timetablingApi.updateEntry(entry.id, { ...form, room: form.room || null })
      onSaved()
      onClose()
    } catch (err) {
      setSaveError(extractApiError(err))
    } finally {
      setSaving(false)
    }
  }
  return (
    <Modal
      title="Edit Lesson"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" form="entry-edit-form" loading={saving}>Save</Button>
        </>
      }
    >
      <form id="entry-edit-form" onSubmit={submit} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {saveError && (
          <div className="col-span-full rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-800">
            <p className="font-medium">Could not save</p>
            <p>{saveError}</p>
          </div>
        )}
        <Select
          label="Period"
          value={form.period}
          onChange={(e) => setForm((f) => ({ ...f, period: e.target.value }))}
        >
          {periods.map((period) => (
            <option key={period.id} value={period.id}>
              {period.day_name} P{period.order} {period.start_time}-{period.end_time}
            </option>
          ))}
        </Select>
        <Select
          label="Room"
          value={form.room}
          onChange={(e) => setForm((f) => ({ ...f, room: e.target.value }))}
        >
          <option value="">Home classroom</option>
          {rooms.map((room) => (
            <option key={room.id} value={room.id}>{room.name}</option>
          ))}
        </Select>
      </form>
    </Modal>
  )
}

function CreateEntryModal({ classroom, period, assignments, rooms, job, onClose, onSaved }) {
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [form, setForm] = useState({ subject: '', teacher: '', room: '' })

  const classroomAssignments = useMemo(() => {
    if (!classroom?.id) return []
    return assignments.filter((a) => String(a.classroom) === String(classroom.id))
  }, [assignments, classroom])

  const availableSubjects = useMemo(() => {
    const map = new Map()
    classroomAssignments.forEach((a) => {
      if (!map.has(a.subject)) {
        map.set(a.subject, { id: a.subject, name: a.subject_name || `Subject ${a.subject}` })
      }
    })
    return Array.from(map.values())
  }, [classroomAssignments])

  const availableTeachers = useMemo(() => {
    if (!form.subject) return []
    const map = new Map()
    classroomAssignments
      .filter((a) => String(a.subject) === String(form.subject))
      .forEach((a) => {
        if (!map.has(a.teacher)) {
          map.set(a.teacher, { id: a.teacher, name: a.teacher_name || `Teacher ${a.teacher}` })
        }
      })
    return Array.from(map.values())
  }, [classroomAssignments, form.subject])

  const periodDisplay = useMemo(() => {
    if (!period) return ''
    return `${period.day_name || ''} P${period.order} (${period.start_time || ''}-${period.end_time || ''})`
  }, [period])

  const handleSubmit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setSaveError(null)
    try {
      await timetablingApi.createEntry({
        job: job.id,
        classroom: classroom.id,
        subject: form.subject,
        teacher: form.teacher,
        period: period.id,
        room: form.room || null,
      })
      onSaved()
      onClose()
    } catch (err) {
      setSaveError(extractApiError(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      title={`Add Lesson — ${classroomLabel(classroom)} · ${periodDisplay}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            type="submit"
            form="entry-create-form"
            loading={saving}
            disabled={!form.subject || !form.teacher}
          >
            Save
          </Button>
        </>
      }
    >
      <form id="entry-create-form" onSubmit={handleSubmit} className="grid grid-cols-1 gap-4">
        {saveError && (
          <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-800">
            <p className="font-medium">Could not save</p>
            <p>{saveError}</p>
          </div>
        )}
        <Select
          label="Subject"
          value={form.subject}
          onChange={(e) => setForm({ subject: e.target.value, teacher: '', room: '' })}
          required
        >
          <option value="">Select subject</option>
          {availableSubjects.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </Select>
        <Select
          label="Teacher"
          value={form.teacher}
          onChange={(e) => setForm((f) => ({ ...f, teacher: e.target.value }))}
          required
          disabled={!form.subject}
        >
          <option value="">{form.subject ? 'Select teacher' : 'Select a subject first'}</option>
          {availableTeachers.map((t) => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </Select>
        <Select
          label="Room"
          value={form.room}
          onChange={(e) => setForm((f) => ({ ...f, room: e.target.value }))}
        >
          <option value="">Home classroom</option>
          {rooms.map((r) => (
            <option key={r.id} value={r.id}>{r.name}</option>
          ))}
        </Select>
      </form>
    </Modal>
  )
}

function ReadinessPanel({ readiness, loading, onRefresh }) {
  const errors = readiness?.errors || []
  const warnings = readiness?.warnings || []
  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 font-semibold text-gray-900">
          {readiness?.ready ? (
            <CheckCircle2 size={18} className="text-green-600" />
          ) : (
            <XCircle size={18} className="text-red-600" />
          )}
          Readiness
        </div>
        <Button variant="secondary" onClick={onRefresh} disabled={loading} aria-label="Refresh readiness">
          <RefreshCcw size={16} />
        </Button>
      </div>
      {loading ? (
        <Spinner className="h-5 w-5" />
      ) : (
        <div className="space-y-2 text-sm">
          {readiness?.ready && <p className="text-green-700">Ready to generate.</p>}
          {errors.map((item, index) => (
            <p key={`e-${index}`} className="text-red-700">{item.message}</p>
          ))}
          {warnings.map((item, index) => (
            <p key={`w-${index}`} className="text-amber-700">{item.message}</p>
          ))}
        </div>
      )}
    </Card>
  )
}

function TimetableGrid({
  entries,
  periods,
  isAdmin,
  onEdit,
  onLock,
  viewMode,
  selectedTeacher,
  onDropEntry,
  onCellClick,
  teachers,
}) {
  const [draggingId, setDraggingId] = useState(null)
  const [dragOverKey, setDragOverKey] = useState(null)

  const periodOrders = periods.filter((p) => !p.is_break).map((p) => p.order)
  const entryOrders = entries.map((entry) => entry.period_order)
  const orders = [...new Set(periodOrders.length ? periodOrders : entryOrders)].sort((a, b) => a - b)

  const entryMap = useMemo(() => {
    const map = new Map()
    entries.forEach((entry) => {
      const key = `${entry.day_of_week}-${entry.period_order}`
      if (!map.has(key)) map.set(key, [])
      map.get(key).push(entry)
    })
    return map
  }, [entries])

  const handleDragStart = (entry) => (e) => {
    if (!isAdmin) return
    setDraggingId(entry.id)
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', String(entry.id))
  }

  const handleDragOver = (key) => (e) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    setDragOverKey(key)
  }

  const handleDragLeave = () => {
    setDragOverKey(null)
  }

  const handleDrop = (day, order) => async (e) => {
    e.preventDefault()
    setDragOverKey(null)
    if (!isAdmin || !onDropEntry) return
    const entryId = parseInt(e.dataTransfer.getData('text/plain') || draggingId, 10)
    if (!entryId) return
    const targetPeriod = periods.find((p) => p.day_of_week === day && p.order === order && !p.is_break)
    if (!targetPeriod) return
    await onDropEntry(entryId, targetPeriod.id)
  }

  const renderEntryCard = (entry) => {
    const isDragging = draggingId === entry.id
    const primaryLabel = viewMode === 'teacher' ? entry.classroom_name : entry.subject_name
    const secondaryLabel = viewMode === 'teacher' ? entry.subject_name : entry.teacher_name
    return (
      <div
        key={entry.id}
        draggable={isAdmin}
        onDragStart={handleDragStart(entry)}
        className={`min-h-20 rounded-md border p-2 text-sm transition-opacity ${
          isDragging ? 'opacity-40' : ''
        } ${
          entry.locked
            ? 'border-amber-200 bg-amber-50 text-amber-950'
            : 'border-teal-100 bg-teal-50 text-teal-950'
        }`}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate font-semibold">{primaryLabel}</p>
            <p className="truncate text-xs text-teal-800">{secondaryLabel}</p>
            {entry.room_name && <p className="truncate text-xs text-teal-700">{entry.room_name}</p>}
          </div>
          {isAdmin && (
            <button
              type="button"
              className="shrink-0 rounded text-teal-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-primary)]"
              onClick={() => onLock(entry)}
              aria-label={entry.locked ? 'Unlock lesson' : 'Lock lesson'}
              title={entry.locked ? 'Unlock' : 'Lock'}
            >
              <Lock size={14} />
            </button>
          )}
        </div>
        {isAdmin && (
          <Button size="sm" variant="secondary" className="mt-2 w-full" onClick={() => onEdit(entry)}>
            Edit
          </Button>
        )}
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full border-separate border-spacing-0 text-sm">
        <thead>
          <tr>
            <th className="sticky left-0 z-10 bg-white px-3 py-2 text-left font-semibold text-gray-700">
              Day
            </th>
            {orders.map((order) => {
              const periodInfo = periods.find((p) => p.order === order) || entries.find((e) => e.period_order === order)
              const timeLabel = periodInfo
                ? `${periodInfo.start_time?.slice(0, 5) || ''}-${periodInfo.end_time?.slice(0, 5) || ''}`
                : ''
              return (
                <th
                  key={order}
                  className="min-w-40 border-l border-gray-100 px-3 py-2 text-left font-semibold text-gray-700"
                >
                  <div>P{order}</div>
                  {timeLabel && (
                    <div className="text-[11px] font-normal text-gray-400 leading-tight">
                      {timeLabel}
                    </div>
                  )}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {DAYS.map(([day, label]) => (
            <tr key={day}>
              <td className="sticky left-0 z-10 border-t border-gray-100 bg-white px-3 py-3 font-medium text-gray-700">
                {label}
              </td>
              {orders.map((order) => {
                const cellKey = `${day}-${order}`
                const cellEntries = entryMap.get(cellKey) || []
                const isDropTarget = dragOverKey === cellKey && isAdmin
                const isEmpty = cellEntries.length === 0
                return (
                  <td
                    key={order}
                    className={`h-28 border-l border-t border-gray-100 p-2 align-top transition-colors ${
                      isDropTarget ? 'bg-blue-50 ring-2 ring-blue-200 ring-inset' : ''
                    }`}
                    onDragOver={handleDragOver(cellKey)}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop(day, order)}
                  >
                    {isEmpty && isAdmin && onCellClick ? (
                      <div
                        className="flex h-full w-full min-h-[6rem] cursor-pointer items-center justify-center rounded border border-dashed border-gray-200 text-xs text-gray-300 hover:border-blue-300 hover:text-blue-400 hover:bg-blue-50 transition-colors"
                        onClick={() => onCellClick(day, order)}
                        role="button"
                        aria-label="Add lesson to empty slot"
                      >
                        +
                      </div>
                    ) : (
                      <div className="flex flex-col gap-1">
                        {cellEntries.map(renderEntryCard)}
                      </div>
                    )}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TeacherListView({ entries, teachers }) {
  const byTeacher = useMemo(() => {
    const map = new Map()
    teachers.forEach((t) => map.set(t.id, { teacher: t, entries: [] }))
    entries.forEach((entry) => {
      const bucket = map.get(entry.teacher)
      if (bucket) bucket.entries.push(entry)
    })
    return Array.from(map.values()).filter((b) => b.entries.length > 0)
  }, [entries, teachers])

  return (
    <div className="space-y-4">
      {byTeacher.map(({ teacher, entries: teacherEntries }) => {
        const name = [teacher.first_name, teacher.last_name].filter(Boolean).join(' ') || teacher.email
        const byDay = new Map()
        teacherEntries.forEach((e) => {
          if (!byDay.has(e.day_of_week)) byDay.set(e.day_of_week, [])
          byDay.get(e.day_of_week).push(e)
        })
        return (
          <Card key={teacher.id} className="p-4">
            <h4 className="mb-2 font-semibold text-gray-900">{name}</h4>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-5">
              {DAYS.map(([day, label]) => {
                const dayEntries = byDay.get(day) || []
                return (
                  <div key={day} className="rounded-md border border-gray-100 p-2">
                    <p className="mb-1 text-xs font-medium text-gray-500">{label}</p>
                    {dayEntries.length === 0 ? (
                      <p className="text-xs text-gray-300">—</p>
                    ) : (
                      dayEntries
                        .sort((a, b) => a.period_order - b.period_order)
                        .map((e) => (
                          <p key={e.id} className="truncate text-xs text-gray-700">
                            P{e.period_order}: {e.classroom_name} · {e.subject_name}
                          </p>
                        ))
                    )}
                  </div>
                )
              })}
            </div>
          </Card>
        )
      })}
    </div>
  )
}

function AdminTimetablePage() {
  const [filters, setFilters] = useState({
    classroom: '',
    teacher: '',
    term: 'term1',
    academic_year: thisYear(),
  })
  const [classrooms, setClassrooms] = useState([])
  const [periods, setPeriods] = useState([])
  const [rooms, setRooms] = useState([])
  const [entries, setEntries] = useState([])
  const [jobs, setJobs] = useState([])
  const [readiness, setReadiness] = useState(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [editEntry, setEditEntry] = useState(null)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [pdfTimetables, setPdfTimetables] = useState([])
  const [showWizard, setShowWizard] = useState(false)
  const [scheduleTemplates, setScheduleTemplates] = useState([])
  const [viewMode, setViewMode] = useState('class')
  const [teacherViewFilter, setTeacherViewFilter] = useState('')
  const [teachers, setTeachers] = useState([])
  const [classroomError, setClassroomError] = useState(null)
  const [actionError, setActionError] = useState(null)
  const [assignments, setAssignments] = useState([])
  const [createModal, setCreateModal] = useState(null)

  const [generationStartedAt, setGenerationStartedAt] = useState(null)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)

  const latestJob = useMemo(() => jobs[0], [jobs])
  const jobInProgress = latestJob && ['pending', 'running'].includes(latestJob.status)

  useEffect(() => {
    if (!jobInProgress) {
      setGenerationStartedAt(null)
      setElapsedSeconds(0)
      return undefined
    }
    setGenerationStartedAt((prev) => prev || Date.now())
    const timer = window.setInterval(() => {
      setGenerationStartedAt((startedAt) => {
        if (startedAt) setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000))
        return startedAt
      })
    }, 1000)
    return () => window.clearInterval(timer)
  }, [jobInProgress])

  const fetchReadiness = useCallback(async () => {
    try {
      const { data } = await timetablingApi.getReadiness({
        term: filters.term,
        academic_year: filters.academic_year,
      })
      setReadiness(data)
    } catch {
      setReadiness({ ready: false, errors: [{ message: 'Could not load readiness.' }], warnings: [] })
    }
  }, [filters.term, filters.academic_year])

  const loadClassrooms = useCallback(() => {
    let cancelled = false
    setClassroomError(null)
    studentsApi.getClassrooms()
      .then((res) => {
        if (cancelled) return
        const raw = res?.data ?? res
        let list = listFromResponse(raw)
        if (list.length === 0) {
          list = raw?.results || raw?.data || raw?.items || raw?.classrooms || raw?.records || []
        }
        if (!cancelled) setClassrooms(list)
      })
      .catch((err) => {
        if (!cancelled) setClassroomError(err?.message || 'Failed to load classrooms')
      })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    return loadClassrooms()
  }, [loadClassrooms])

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const [jobRes, roomRes, pdfRes, tempRes, userRes] = await Promise.all([
        timetablingApi.getJobs({ term: filters.term, academic_year: filters.academic_year }),
        timetablingApi.getRooms({ is_active: true }),
        academicsApi.getTimetables({
          classroom: filters.classroom || undefined,
          term: filters.term,
          academic_year: filters.academic_year,
        }),
        timetablingApi.getScheduleTemplates({}),
        timetablingApi.getTeacherAssignments({}),
      ])

      const jobList = listFromResponse(jobRes.data)
      const selectedJob = jobList[0]

      const entryRes = await timetablingApi.getEntries({
        classroom: filters.classroom || undefined,
        teacher: filters.teacher || undefined,
        job: selectedJob?.id || undefined,
      })

      const assigns = listFromResponse(userRes.data)
      setAssignments(assigns)

      const uniqueTeachers = []
      const seen = new Set()
      assigns.forEach((a) => {
        if (!seen.has(a.teacher)) {
          seen.add(a.teacher)
          uniqueTeachers.push({
            id: a.teacher,
            first_name: a.teacher_name?.split(' ')[0] || '',
            last_name: a.teacher_name?.split(' ').slice(1).join(' ') || '',
            email: a.teacher_name || '',
          })
        }
      })

      setJobs(jobList)
      setRooms(listFromResponse(roomRes.data))
      setEntries(listFromResponse(entryRes.data))
      setPdfTimetables(listFromResponse(pdfRes.data))
      setTeachers(uniqueTeachers)

      const tempList = listFromResponse(tempRes.data)
      setScheduleTemplates(tempList)
      if (tempList.length === 0 && !showWizard) {
        setShowWizard(true)
      }

      const selected = classrooms.find((c) => String(c.id) === String(filters.classroom))
      if (selected?.schedule_template) {
        const periodRes = await timetablingApi.getPeriods({ schedule_template: selected.schedule_template })
        setPeriods(listFromResponse(periodRes.data))
      } else {
        setPeriods([])
      }
    } catch {
      setEntries([])
    } finally {
      setLoading(false)
    }
  }, [filters, showWizard, classrooms])

  useEffect(() => {
    fetchReadiness()
  }, [fetchReadiness])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  useEffect(() => {
    if (!latestJob || !['pending', 'running'].includes(latestJob.status)) return undefined
    const timer = window.setInterval(fetchData, 4000)
    return () => window.clearInterval(timer)
  }, [fetchData, latestJob])

  const generate = async () => {
    if (jobInProgress) return
    setGenerating(true)
    setGenerationStartedAt(Date.now())
    setElapsedSeconds(0)
    try {
      await timetablingApi.createJob({
        term: filters.term,
        academic_year: Number(filters.academic_year),
      })
      await fetchData()
    } finally {
      setGenerating(false)
    }
  }

  const publishJob = async () => {
    if (!latestJob) return
    setPublishing(true)
    try {
      await timetablingApi.publishJob(latestJob.id)
      await fetchData()
    } finally {
      setPublishing(false)
    }
  }

  const lockEntry = async (entry) => {
    try {
      await timetablingApi.lockEntry(entry.id, !entry.locked)
      fetchData()
    } catch (err) {
      setActionError(extractApiError(err))
    }
  }

  const handleDropEntry = async (entryId, periodId) => {
    const entry = entries.find((e) => e.id === entryId)
    if (!entry || entry.period === periodId) return
    try {
      await timetablingApi.updateEntry(entryId, {
        period: periodId,
        room: entry.room || null,
      })
      setActionError(null)
      fetchData()
    } catch (err) {
      setActionError(extractApiError(err))
    }
  }

  const handleCellClick = (day, order) => {
    setActionError(null)

    if (!filters.classroom) {
      setActionError('Please select a specific classroom from the filter before adding lessons.')
      return
    }

    if (!latestJob || latestJob.status !== 'done') {
      setActionError('Please generate a timetable first before manually adding lessons.')
      return
    }

    const targetPeriod = periods.find((p) => p.day_of_week === day && p.order === order && !p.is_break)
    if (!targetPeriod) return

    const selectedClassroom = classrooms.find((c) => String(c.id) === String(filters.classroom))
    if (!selectedClassroom) return

    setCreateModal({ classroom: selectedClassroom, period: targetPeriod })
  }

  const regenerateSelected = async () => {
    if (!latestJob || !filters.classroom || jobInProgress) return
    await timetablingApi.regeneratePartial(latestJob.id, [Number(filters.classroom)])
    fetchData()
  }

  const selectedPdf = pdfTimetables[0]

  const filteredEntries = useMemo(() => {
    if (viewMode === 'teacher' && teacherViewFilter) {
      return entries.filter((e) => String(e.teacher) === String(teacherViewFilter))
    }
    return entries
  }, [entries, viewMode, teacherViewFilter])

  if (showWizard) {
    return (
      <div className="space-y-6">
        <PageHeader title="Timetable Setup" />
        <TimetableSetupWizard
          onComplete={() => {
            setShowWizard(false)
            fetchData()
          }}
        />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Timetable"
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setShowWizard(true)}>
              Setup Wizard
            </Button>
            <Button variant="secondary" onClick={() => setUploadOpen(true)}>
              <Upload size={16} /> PDF
            </Button>
            <Button
              onClick={generate}
              loading={generating}
              disabled={!readiness?.ready || jobInProgress}
              title={jobInProgress ? 'A generation job is already running' : undefined}
            >
              <Play size={16} /> Generate
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_20rem]">
        <Card className="p-4">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
            <div>
              <Select
                label="Classroom"
                value={filters.classroom}
                onChange={(e) => setFilters((f) => ({ ...f, classroom: e.target.value }))}
              >
                <option value="">All classes</option>
                {classrooms.map((c) => (
                  <option key={c.id ?? `c-${Math.random()}`} value={c.id ?? ''}>
                    {classroomLabel(c)}
                  </option>
                ))}
              </Select>
              <div className="mt-1 flex items-center gap-2">
                <span className="text-xs text-gray-400">
                  {classrooms.length} class{classrooms.length !== 1 ? 'es' : ''} loaded
                </span>
                {classroomError && (
                  <span className="text-xs text-red-600">{classroomError}</span>
                )}
                {classrooms.length === 0 && !classroomError && (
                  <button
                    type="button"
                    className="text-xs text-blue-600 hover:underline"
                    onClick={loadClassrooms}
                  >
                    Retry
                  </button>
                )}
              </div>
            </div>
            <Input
              label="Teacher ID"
              value={filters.teacher}
              onChange={(e) => setFilters((f) => ({ ...f, teacher: e.target.value }))}
            />
            <Select
              label="Term"
              value={filters.term}
              onChange={(e) => setFilters((f) => ({ ...f, term: e.target.value }))}
            >
              {TERMS.map((term) => (
                <option key={term.value} value={term.value}>
                  {term.label}
                </option>
              ))}
            </Select>
            <Input
              label="Academic Year"
              type="number"
              value={filters.academic_year}
              onChange={(e) => setFilters((f) => ({ ...f, academic_year: e.target.value }))}
            />
          </div>
        </Card>
        <ReadinessPanel readiness={readiness} loading={!readiness} onRefresh={fetchReadiness} />
      </div>

      <SetupChecklist
        scheduleTemplates={scheduleTemplates}
        rooms={rooms}
        assignments={assignments}
        readiness={readiness}
        onOpenWizard={() => setShowWizard(true)}
      />

      {latestJob && (
        <Card className="p-4">
          {jobInProgress ? (
            <div className="flex items-start gap-3">
              <Spinner className="h-5 w-5 shrink-0 text-[var(--brand-primary)]" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-3 text-sm text-gray-800">
                  <span className="font-medium">Generating timetable…</span>
                  <span className="shrink-0 font-mono text-xs text-gray-400">
                    {formatElapsed(elapsedSeconds)}
                  </span>
                </div>
                <p className="mt-1 text-xs text-gray-500">
                  {GENERATION_MESSAGES[Math.floor(elapsedSeconds / 6) % GENERATION_MESSAGES.length]}
                </p>
                <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-gray-100">
                  <div className="h-full w-1/3 animate-pulse rounded-full bg-[var(--brand-primary)]" />
                </div>
                <p className="mt-2 text-xs text-gray-400">
                  This can take up to 5 minutes — several arrangements are tried automatically if the first doesn't fit.
                </p>
              </div>
            </div>
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
                <div className="flex items-center gap-2 text-gray-700">
                  <CalendarClock size={18} />
                  Job #{latestJob.id}:{' '}
                  <span className="font-semibold capitalize">{latestJob.status}</span>
                  {latestJob.published && (
                    <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                      Published
                    </span>
                  )}
                  {latestJob.current_score !== null && latestJob.current_score !== undefined && (
                    <span>Score {latestJob.current_score}</span>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {latestJob.status === 'done' && !latestJob.published && (
                    <Button size="sm" onClick={publishJob} loading={publishing}>
                      <Save size={14} className="mr-1" /> Publish
                    </Button>
                  )}
                  {filters.classroom && (
                    <Button size="sm" variant="secondary" onClick={regenerateSelected}>
                      <RefreshCcw size={14} className="mr-1" /> Regenerate Class
                    </Button>
                  )}
                </div>
              </div>
              {latestJob.failure_reason && (
                <p className="mt-2 text-sm text-red-700">{latestJob.failure_reason}</p>
              )}
            </>
          )}
        </Card>
      )}

      {actionError && (
        <div className="flex items-start gap-3 rounded-md bg-red-50 border border-red-200 p-4 text-sm text-red-800">
          <XCircle size={18} className="shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-medium">Action failed</p>
            <p>{actionError}</p>
          </div>
          <button
            type="button"
            className="shrink-0 rounded p-1 hover:bg-red-100"
            onClick={() => setActionError(null)}
            aria-label="Dismiss error"
          >
            <X size={14} />
          </button>
        </div>
      )}

      <Card className="p-4">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant={viewMode === 'class' ? 'primary' : 'secondary'}
              onClick={() => setViewMode('class')}
            >
              <Grid3X3 size={14} className="mr-1" /> By Class
            </Button>
            <Button
              size="sm"
              variant={viewMode === 'teacher' ? 'primary' : 'secondary'}
              onClick={() => setViewMode('teacher')}
            >
              <Users size={14} className="mr-1" /> By Teacher
            </Button>
          </div>

          {viewMode === 'class' && (
            <Select
              value={filters.classroom}
              onChange={(e) => setFilters((f) => ({ ...f, classroom: e.target.value }))}
              className="w-48"
            >
              <option value="">All Classes</option>
              {classrooms.map((c) => (
                <option key={c.id ?? `hdr-${Math.random()}`} value={c.id ?? ''}>
                  {classroomLabel(c)}
                </option>
              ))}
            </Select>
          )}

          {viewMode === 'teacher' && (
            <Select
              value={teacherViewFilter}
              onChange={(e) => setTeacherViewFilter(e.target.value)}
              className="w-48"
            >
              <option value="">All Teachers</option>
              {teachers.map((t) => (
                <option key={t.id} value={t.id}>
                  {[t.first_name, t.last_name].filter(Boolean).join(' ') || t.email}
                </option>
              ))}
            </Select>
          )}
        </div>

        {loading ? (
          <div className="flex justify-center py-16">
            <Spinner className="h-7 w-7" />
          </div>
        ) : viewMode === 'teacher' && !teacherViewFilter ? (
          <TeacherListView entries={entries} teachers={teachers} />
        ) : filteredEntries.length || periods.length ? (
          <TimetableGrid
            entries={filteredEntries}
            periods={periods}
            isAdmin
            onEdit={setEditEntry}
            onLock={lockEntry}
            viewMode={viewMode}
            selectedTeacher={teacherViewFilter}
            onDropEntry={handleDropEntry}
            onCellClick={viewMode === 'class' && filters.classroom ? handleCellClick : undefined}
            teachers={teachers}
          />
        ) : (
          <EmptyState
            icon={CalendarClock}
            title="No generated timetable"
            description="Run the readiness check, then generate a timetable for this term."
          />
        )}
      </Card>

      {selectedPdf && (
        <Card className="p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="font-semibold text-gray-900">PDF fallback</p>
              <p className="text-sm text-gray-500">{selectedPdf.classroom_name}</p>
            </div>
            <a href={selectedPdf.file_url || selectedPdf.file} target="_blank" rel="noreferrer">
              <Button variant="secondary">Download PDF</Button>
            </a>
          </div>
        </Card>
      )}

      {editEntry && (
        <EditEntryModal
          entry={editEntry}
          periods={periods}
          rooms={rooms}
          onClose={() => setEditEntry(null)}
          onSaved={fetchData}
        />
      )}

      {createModal && (
        <CreateEntryModal
          classroom={createModal.classroom}
          period={createModal.period}
          assignments={assignments}
          rooms={rooms}
          job={latestJob}
          onClose={() => setCreateModal(null)}
          onSaved={fetchData}
        />
      )}

      {uploadOpen && (
        <UploadModal
          classrooms={classrooms}
          initial={filters}
          onClose={() => setUploadOpen(false)}
          onSaved={fetchData}
        />
      )}
    </div>
  )
}

function ReadOnlyTimetablePage() {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    timetablingApi
      .getEntries(undefined, { skipErrorToast: true })
      .then(({ data }) => {
        if (!cancelled) setEntries(listFromResponse(data))
      })
      .catch(() => {
        if (!cancelled) setEntries([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="space-y-6">
      <PageHeader title="Timetable" />
      <Card className="p-4">
        <p className="text-sm text-gray-600">
          Your school timetable appears here once an admin generates it.
        </p>
      </Card>
      <Card className="p-4">
        {loading ? (
          <div className="flex justify-center py-16">
            <Spinner className="h-7 w-7" />
          </div>
        ) : entries.length ? (
          <TimetableGrid
            entries={entries}
            periods={[]}
            isAdmin={false}
            onEdit={() => {}}
            onLock={() => {}}
            viewMode="teacher"
          />
        ) : (
          <EmptyState
            icon={CalendarClock}
            title={READ_ONLY_EMPTY.title}
            description={READ_ONLY_EMPTY.description}
          />
        )}
      </Card>
    </div>
  )
}

export default function TimetablePage() {
  const role = useAuthStore((state) => state.user?.role)

  if (role === 'admin' || role === 'superadmin') {
    return <AdminTimetablePage />
  }

  if (role === 'teacher' || role === 'parent' || role === 'guardian') {
    return <ReadOnlyTimetablePage />
  }

  return <ReadOnlyTimetablePage />
}