import { useMemo, useState } from 'react'
import { AlertTriangle, ChevronLeft, ChevronRight, Grid3X3, ListPlus, Plus, Trash2 } from 'lucide-react'
import { Button, Card, Select } from '@/components/ui'
import { timetablingApi } from '@/api/timetabling'
import api from '@/api/client'
import AssignmentFilterBar from '../components/AssignmentFilterBar'
import AssignmentMatrix from '../components/AssignmentMatrix'
import { buildRuleLookup } from '../AssignmentRules'

const PHASE_GRADES = {
  pp: [],
  lower_primary: ['Grade 1', 'Grade 2', 'Grade 3'],
  upper_primary: ['Grade 4', 'Grade 5', 'Grade 6'],
  jss: ['Grade 7', 'Grade 8', 'Grade 9'],
  sss: ['Grade 10', 'Grade 11', 'Grade 12'],
  all: [],
}

const TERM_LABELS = { term1: 'Term 1', term2: 'Term 2', term3: 'Term 3' }

function extractErrorMessage(err, fallback) {
  const data = err?.response?.data
  if (!data) return err?.message || fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  const firstValue = Object.values(data)[0]
  if (Array.isArray(firstValue)) return firstValue[0]
  if (typeof firstValue === 'string') return firstValue
  return fallback
}

function minSupplyFor(templateIds, templateSupply) {
  if (!templateIds || templateIds.size === 0) return 0
  return Math.min(...Array.from(templateIds).map((t) => templateSupply[t] || 0))
}

export default function TeachersStep({
  teachers,
  subjects,
  classrooms,
  periods,
  teacherAssignments,
  setTeacherAssignments,
  subjectRules,
  term,
  academicYear,
  onBack,
  onNext,
}) {
  const [saving, setSaving] = useState(false)
  const [viewTab, setViewTab] = useState('grid')
  const [form, setForm] = useState({ classroom: '', subject: '', teacher: '' })
  const [filters, setFilters] = useState({ teacher: '', subject: '', classroom: '', grade: '' })
  const [formError, setFormError] = useState('')

  const selectedClassroom = classrooms.find((c) => String(c.id) === String(form.classroom))
  const ruleFor = useMemo(() => buildRuleLookup(subjectRules), [subjectRules])

  // Total non-break periods available per bell-schedule template. A teacher's
  // combined load across every classroom they teach can never legitimately
  // exceed the smallest of these among the templates their classrooms use —
  // they can only be in one period at a time.
  const templateSupply = useMemo(() => {
    const supply = {}
    ;(periods || []).forEach((p) => {
      if (!p.is_break) supply[p.schedule_template] = (supply[p.schedule_template] || 0) + 1
    })
    return supply
  }, [periods])

  // Current load per teacher, computed live from teacherAssignments + subjectRules
  // in memory — no server round trip needed, so it updates the instant an
  // assignment is added or removed.
  const teacherLoadMap = useMemo(() => {
    const map = new Map()
    teacherAssignments.forEach((a) => {
      const classroomId = typeof a.classroom === 'object' ? a.classroom.id : a.classroom
      const classroom = classrooms.find((c) => String(c.id) === String(classroomId))
      if (!classroom) return
      const subjectId = typeof a.subject === 'object' ? a.subject.id : a.subject
      const rule = ruleFor(classroom, subjectId)
      if (!rule) return
      const teacherId = typeof a.teacher === 'object' ? a.teacher.id : a.teacher
      if (!map.has(teacherId)) map.set(teacherId, { periods: 0, templates: new Set() })
      const entry = map.get(teacherId)
      entry.periods += rule.periods_per_week
      if (classroom.schedule_template) entry.templates.add(classroom.schedule_template)
    })
    return map
  }, [teacherAssignments, classrooms, ruleFor])

  const teacherName = (id) => {
    const t = teachers.find((t) => String(t.id) === String(id))
    return t ? ([t.first_name, t.last_name].filter(Boolean).join(' ') || t.email) : `Teacher ${id}`
  }

  // Live preview: what the selected teacher's load would become if the
  // currently-configured (classroom, subject) assignment is added — shown
  // BEFORE the admin clicks "Add Assignment", not after.
  const selectedTeacherId = form.teacher ? parseInt(form.teacher) : null
  const previewRule = form.subject && selectedClassroom ? ruleFor(selectedClassroom, parseInt(form.subject)) : null
  const previewPeriods = previewRule?.periods_per_week || 0

  const currentEntry = selectedTeacherId != null ? teacherLoadMap.get(selectedTeacherId) : null
  const currentLoad = currentEntry?.periods || 0
  const projectedTemplates = new Set(currentEntry?.templates || [])
  if (selectedClassroom?.schedule_template) projectedTemplates.add(selectedClassroom.schedule_template)
  const projectedSupply = minSupplyFor(projectedTemplates, templateSupply)
  const projectedLoad = currentLoad + previewPeriods

  // Check if subject already has a teacher assigned to this classroom
  const isSubjectAssigned = (subjectId, classroomId) => {
    return teacherAssignments.some((a) => {
      const sid = typeof a.subject === 'object' ? a.subject.id : a.subject
      const cid = typeof a.classroom === 'object' ? a.classroom.id : a.classroom
      return String(sid) === String(subjectId) && String(cid) === String(classroomId)
    })
  }

  // Subjects applicable to the selected classroom's grade. Prefers the explicit
  // grade_levels list (set per-subject in the Curriculum admin page) since it's
  // far more precise than the coarse curriculum_phase bucket.
  const applicableSubjects = useMemo(() => {
    if (!selectedClassroom) return []
    return subjects.filter((sub) => {
      if (Array.isArray(sub.grade_levels) && sub.grade_levels.length > 0) {
        return sub.grade_levels.includes(selectedClassroom.grade_level)
      }
      const phase = sub.curriculum_phase || 'all'
      if (phase === 'all') return true
      const allowed = PHASE_GRADES[phase] || []
      return allowed.includes(selectedClassroom.grade_level)
    })
  }, [selectedClassroom, subjects])

  const saveAssignment = async () => {
    const { teacher, subject, classroom } = form
    if (!teacher || !subject || !classroom) return
    setSaving(true)
    setFormError('')
    try {
      await timetablingApi.bulkTeacherAssignment({
        teacher: parseInt(teacher),
        subject: parseInt(subject),
        classrooms: [parseInt(classroom)],
        term,
        academic_year: academicYear,
      })
      const { data } = await timetablingApi.getTeacherAssignments({ term, academic_year: academicYear })
      setTeacherAssignments(data.results || data)
      setForm({ classroom: '', subject: '', teacher: '' })
    } catch (err) {
      setFormError(extractErrorMessage(err, 'Failed to save this assignment. Please try again.'))
    } finally {
      setSaving(false)
    }
  }

  const deleteAssignment = async (id) => {
    if (!window.confirm('Remove this assignment?')) return
    setSaving(true)
    setFormError('')
    try {
      await api.delete(`/timetabling/teacher-subject-assignments/${id}/`)
      setTeacherAssignments((prev) => prev.filter((a) => a.id !== id))
    } catch (err) {
      setFormError(extractErrorMessage(err, 'Failed to remove this assignment. Please try again.'))
    } finally {
      setSaving(false)
    }
  }

  const filteredAssignments = useMemo(() => {
    let list = [...teacherAssignments]
    if (filters.teacher) list = list.filter((a) => String(a.teacher) === String(filters.teacher))
    if (filters.subject) list = list.filter((a) => {
      const sid = typeof a.subject === 'object' ? a.subject.id : a.subject
      return String(sid) === String(filters.subject)
    })
    if (filters.classroom) list = list.filter((a) => {
      const cid = typeof a.classroom === 'object' ? a.classroom.id : a.classroom
      return String(cid) === String(filters.classroom)
    })
    if (filters.grade) {
      list = list.filter((a) => {
        const cls = classrooms.find((c) => String(c.id) === String(typeof a.classroom === 'object' ? a.classroom.id : a.classroom))
        return cls?.grade_level === filters.grade
      })
    }
    return list
  }, [teacherAssignments, filters, classrooms])

  const handleFilterChange = (key, value) => {
    setFilters((f) => ({ ...f, [key]: value }))
  }

  // Sorted, live overview of every teacher who has at least one assignment —
  // the same numbers the shell diagnostic script computes, always visible.
  const teacherLoadOverview = useMemo(() => {
    return Array.from(teacherLoadMap.entries())
      .map(([teacherId, entry]) => ({
        teacherId,
        name: teacherName(teacherId),
        load: entry.periods,
        supply: minSupplyFor(entry.templates, templateSupply),
      }))
      .sort((a, b) => b.load - a.load)
  }, [teacherLoadMap, templateSupply, teachers])

  return (
    <div className="space-y-6">
      <Card className="p-5">
        <div className="mb-1 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-gray-900">Assign Teachers</h3>
            <p className="mt-1 text-xs text-gray-400">
              For {TERM_LABELS[term] || 'this term'} {academicYear} — change the term/year above to see or edit a different one.
            </p>
          </div>
          <div className="flex overflow-hidden rounded-md border border-gray-200">
            <button
              type="button"
              onClick={() => setViewTab('grid')}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium ${
                viewTab === 'grid' ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'
              }`}
            >
              <Grid3X3 size={14} /> Grid
            </button>
            <button
              type="button"
              onClick={() => setViewTab('quick')}
              className={`flex items-center gap-1.5 border-l border-gray-200 px-3 py-1.5 text-sm font-medium ${
                viewTab === 'quick' ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'
              }`}
            >
              <ListPlus size={14} /> Quick Add
            </button>
          </div>
        </div>

        {formError && (
          <p className="mb-4 mt-3 rounded-md border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-700">
            {formError}
          </p>
        )}

        {viewTab === 'grid' && (
          <div className="mt-4">
            <AssignmentMatrix
              teachers={teachers}
              subjects={subjects}
              classrooms={classrooms}
              subjectRules={subjectRules}
              teacherAssignments={teacherAssignments}
              setTeacherAssignments={setTeacherAssignments}
              term={term}
              academicYear={academicYear}
              onError={setFormError}
            />
          </div>
        )}

        {viewTab === 'quick' && (
          <>
        <p className="mb-4 mt-3 text-sm text-gray-500">
          Pick a classroom first, then a subject, then the teacher.
        </p>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Classroom *</label>
            <Select
              value={form.classroom}
              onChange={(e) => setForm({ classroom: e.target.value, subject: '', teacher: '' })}
            >
              <option value="">Select classroom</option>
              {classrooms.map((c) => (
                <option key={c.id} value={c.id}>
                  {`${c.name || ''}${c.stream ? ` ${c.stream}` : ''}`.trim()} ({c.grade_level})
                </option>
              ))}
            </Select>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Subject *</label>
            <Select
              value={form.subject}
              onChange={(e) => setForm((f) => ({ ...f, subject: e.target.value }))}
              disabled={!form.classroom}
            >
              <option value="">
                {form.classroom ? 'Select subject' : 'Pick a classroom first'}
              </option>
              {applicableSubjects.map((s) => {
                const assigned = isSubjectAssigned(s.id, form.classroom)
                return (
                  <option key={s.id} value={s.id}>
                    {s.name} {assigned ? '✓ Assigned' : ''}
                  </option>
                )
              })}
            </Select>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Teacher *</label>
            <Select
              value={form.teacher}
              onChange={(e) => setForm((f) => ({ ...f, teacher: e.target.value }))}
              disabled={!form.subject}
            >
              <option value="">Select teacher</option>
              {teachers.map((t) => (
                <option key={t.id} value={t.id}>
                  {[t.first_name, t.last_name].filter(Boolean).join(' ') || t.email}
                </option>
              ))}
            </Select>
          </div>
        </div>

        {selectedTeacherId != null && (
          <div
            className={`mt-3 flex items-start gap-2 rounded-md border px-3 py-2 text-sm ${
              projectedLoad > projectedSupply
                ? 'border-red-200 bg-red-50 text-red-700'
                : projectedLoad === projectedSupply
                ? 'border-amber-200 bg-amber-50 text-amber-700'
                : 'border-gray-100 bg-gray-50 text-gray-600'
            }`}
          >
            {projectedLoad >= projectedSupply && <AlertTriangle size={16} className="mt-0.5 shrink-0" />}
            <span>
              <strong>{teacherName(selectedTeacherId)}</strong>: {currentLoad} period{currentLoad !== 1 ? 's' : ''}/week currently
              {previewPeriods > 0 && (
                <>
                  {' '}→ <strong>{projectedLoad}</strong> after adding this assignment
                  {' '}(<strong>{projectedSupply}</strong> available)
                </>
              )}
              {projectedLoad > projectedSupply && ' — over capacity, this will make generation fail.'}
              {projectedLoad === projectedSupply && projectedLoad > 0 && ' — fully booked, leaves no scheduling flexibility.'}
            </span>
          </div>
        )}

        <div className="mt-4 flex justify-end">
          <Button
            onClick={saveAssignment}
            loading={saving}
            disabled={!form.teacher || !form.subject || !form.classroom}
          >
            <Plus size={16} className="mr-1" /> Add Assignment
          </Button>
        </div>
        </>
        )}
      </Card>

      {teacherLoadOverview.length > 0 && (
        <Card className="p-5">
          <h3 className="mb-1 text-base font-semibold text-gray-900">Teacher Load Overview</h3>
          <p className="mb-3 text-sm text-gray-500">
            Total periods/week assigned vs. periods available in that teacher's bell schedule.
          </p>
          <div className="divide-y divide-gray-100">
            {teacherLoadOverview.map(({ teacherId, name, load, supply }) => {
              const over = load > supply
              const full = load === supply && supply > 0
              return (
                <div key={teacherId} className="flex items-center justify-between py-2 text-sm">
                  <span className="text-gray-700">{name}</span>
                  <span
                    className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 font-medium ${
                      over
                        ? 'bg-red-100 text-red-700'
                        : full
                        ? 'bg-amber-100 text-amber-700'
                        : 'bg-gray-100 text-gray-600'
                    }`}
                  >
                    {over && <AlertTriangle size={12} />}
                    {load} / {supply}
                  </span>
                </div>
              )
            })}
          </div>
        </Card>
      )}

      {teacherAssignments.length > 0 && (
        <Card className="p-5">
          <h3 className="mb-3 text-base font-semibold text-gray-900">Existing Assignments</h3>
          <AssignmentFilterBar
            teachers={teachers}
            subjects={subjects}
            classrooms={classrooms}
            filters={filters}
            onChange={handleFilterChange}
          />
          <p className="mb-3 text-xs text-gray-500">
            Showing {filteredAssignments.length} of {teacherAssignments.length} assignments
          </p>
          <div className="divide-y divide-gray-100">
            {filteredAssignments.map((a) => (
              <div key={a.id} className="flex items-center justify-between py-3">
                <div>
                  <p className="font-medium text-gray-900">{a.teacher_name || a.teacher}</p>
                  <p className="text-xs text-gray-500">
                    {a.subject_name || a.subject} · {a.classroom_name || a.classroom}
                  </p>
                </div>
                <button
                  onClick={() => deleteAssignment(a.id)}
                  className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-600"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="flex justify-between">
        <Button variant="secondary" onClick={onBack}>
          <ChevronLeft size={16} className="mr-1" /> Back
        </Button>
        <Button onClick={onNext}>
          Next: Review <ChevronRight size={16} className="ml-1" />
        </Button>
      </div>
    </div>
  )
}