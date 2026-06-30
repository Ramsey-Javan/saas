import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ClipboardList, Plus, Settings, RefreshCw } from 'lucide-react'
import { academicsApi } from '@/api/academics'
import { studentsApi } from '@/api/students'
import { useAuthStore } from '@/store/authStore'
import { Button, Card, EmptyState, Input, PageHeader, Select, Spinner } from '@/components/ui'
import { LEVEL_COLORS, Modal, StatCard, TERMS, classroomLabel, listFromResponse, termLabel, thisYear, todayISO } from './shared'

const EXAM_TYPES = [
  { value: 'opener', label: 'Opener Exam' },
  { value: 'midterm', label: 'Mid-Term Exam' },
  { value: 'endterm', label: 'End Term Exam' },
  { value: 'mock', label: 'Mock Exam' },
  { value: 'other', label: 'Other' },
]

const defaults = { be_min: 0, be_max: 29, ae_min: 30, ae_max: 49, me_min: 50, me_max: 74, ee_min: 75, ee_max: 100 }

function ExamConfigModal({ onClose }) {
  const [form, setForm] = useState(defaults)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    academicsApi.getExamConfig().then(({ data }) => setForm(data))
  }, [])

  const setNumber = (key, value) => setForm(current => ({ ...current, [key]: Number(value) }))
  const valid = form.ae_min === form.be_max + 1 && form.me_min === form.ae_max + 1 && form.ee_min === form.me_max + 1

  const save = async (event) => {
    event.preventDefault()
    if (!valid) {
      setError('Threshold ranges must be contiguous.')
      return
    }
    setSaving(true)
    setError('')
    try {
      await academicsApi.updateExamConfig(form)
      onClose()
    } catch (err) {
      setError(err.response?.data?.detail || err.response?.data?.non_field_errors?.[0] || 'Could not save thresholds.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      title="Configure CBC Thresholds"
      onClose={onClose}
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" form="exam-config-form" loading={saving}>Save Thresholds</Button></>}
    >
      <form id="exam-config-form" onSubmit={save} className="space-y-4">
        {[
          ['BE', 'be_min', 'be_max', LEVEL_COLORS.BE],
          ['AE', 'ae_min', 'ae_max', LEVEL_COLORS.AE],
          ['ME', 'me_min', 'me_max', LEVEL_COLORS.ME],
          ['EE', 'ee_min', 'ee_max', LEVEL_COLORS.EE],
        ].map(([label, minKey, maxKey, color]) => (
          <div key={label} className={`rounded-lg border p-3 ${color.border} ${color.bg}`}>
            <div className="mb-2 flex items-center justify-between text-sm font-semibold">
              <span className={color.text}>{label}</span>
              <span className="text-gray-700">{form[minKey]} - {form[maxKey]}</span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Input label="Minimum" type="number" min="0" max="100" value={form[minKey]} onChange={e => setNumber(minKey, e.target.value)} disabled={label === 'BE'} />
              <Input label="Maximum" type="number" min="0" max="100" value={form[maxKey]} onChange={e => setNumber(maxKey, e.target.value)} disabled={label === 'EE'} />
            </div>
          </div>
        ))}
        <Button type="button" variant="secondary" onClick={() => setForm(defaults)}>Reset to KNEC Defaults</Button>
        {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
      </form>
    </Modal>
  )
}

function CreateExamModal({ classrooms, onClose, onDone }) {
  const [saving, setSaving] = useState(false)
  const [availableSubjects, setAvailableSubjects] = useState([])
  const [subjectsLoading, setSubjectsLoading] = useState(false)
  const [form, setForm] = useState({
    name: '',
    exam_type: 'endterm',
    classroom: '',
    term: 'term1',
    academic_year: thisYear(),
    start_date: todayISO(),
    end_date: todayISO(),
    instructions: '',
    subjects: [],
  })

  // Fetch subjects filtered by selected classroom
  useEffect(() => {
    if (!form.classroom) {
      setAvailableSubjects([])
      return
    }
    setSubjectsLoading(true)
    academicsApi.getSubjects({ classroom: form.classroom })
      .then(({ data }) => setAvailableSubjects(listFromResponse(data)))
      .catch(() => setAvailableSubjects([]))
      .finally(() => setSubjectsLoading(false))
  }, [form.classroom])

  const toggleSubject = (subjectId) => {
    setForm(current => ({
      ...current,
      subjects: current.subjects.includes(subjectId)
        ? current.subjects.filter(id => id !== subjectId)
        : [...current.subjects, subjectId],
    }))
  }

  const handleClassroomChange = (classroomId) => {
    setForm(current => ({
      ...current,
      classroom: classroomId,
      subjects: [], // Clear selected subjects when classroom changes
    }))
  }

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      const { subjects: selectedSubjects, ...payload } = form
      const { data } = await academicsApi.createExamSetup(payload)
      for (const subject of selectedSubjects) {
        await academicsApi.addExamSubject(data.id, { subject, total_marks: 100 })
      }
      onDone()
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="Create Exam" onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" form="create-exam-form" loading={saving}>Create Exam</Button></>}>
      <form id="create-exam-form" onSubmit={submit} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input label="Exam Name" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} required />
          <Select label="Exam Type" value={form.exam_type} onChange={e => setForm(f => ({ ...f, exam_type: e.target.value }))}>
            {EXAM_TYPES.map(type => <option key={type.value} value={type.value}>{type.label}</option>)}
          </Select>
          <Select label="Classroom" value={form.classroom} onChange={e => handleClassroomChange(e.target.value)} required>
            <option value="">Select class</option>
            {classrooms.map(c => <option key={c.id} value={c.id}>{classroomLabel(c)}</option>)}
          </Select>
          <Select label="Term" value={form.term} onChange={e => setForm(f => ({ ...f, term: e.target.value }))}>
            {TERMS.map(term => <option key={term.value} value={term.value}>{term.label}</option>)}
          </Select>
          <Input label="Academic Year" type="number" value={form.academic_year} onChange={e => setForm(f => ({ ...f, academic_year: e.target.value }))} required />
          <Input label="Start Date" type="date" value={form.start_date} onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))} required />
          <Input label="End Date" type="date" value={form.end_date} onChange={e => setForm(f => ({ ...f, end_date: e.target.value }))} required />
        </div>
        <textarea value={form.instructions} onChange={e => setForm(f => ({ ...f, instructions: e.target.value }))} placeholder="Instructions" className="min-h-20 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-[var(--brand-primary)]" />
        <div>
          <p className="mb-2 text-sm font-medium text-gray-700">Subjects</p>
          {!form.classroom ? (
            <p className="text-sm text-gray-500">Select a classroom to see available subjects.</p>
          ) : subjectsLoading ? (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Spinner className="h-4 w-4" /> Loading subjects...
            </div>
          ) : availableSubjects.length === 0 ? (
            <p className="text-sm text-gray-500">No subjects assigned to this classroom.</p>
          ) : (
            <div className="grid max-h-52 grid-cols-1 gap-2 overflow-y-auto sm:grid-cols-2">
              {availableSubjects.map(subject => (
                <label key={subject.id} className="flex items-center gap-2 rounded-lg border border-gray-100 px-3 py-2 text-sm hover:bg-gray-50 cursor-pointer">
                  <input type="checkbox" checked={form.subjects.includes(subject.id)} onChange={() => toggleSubject(subject.id)} />
                  <span>{subject.name}</span>
                </label>
              ))}
            </div>
          )}
        </div>
      </form>
    </Modal>
  )
}

export default function ExamsDashboard() {
  const navigate = useNavigate()
  const user = useAuthStore(state => state.user)
  const isAdmin = ['admin', 'superadmin'].includes(user?.role)
  const [exams, setExams] = useState([])
  const [classrooms, setClassrooms] = useState([])
  const [filters, setFilters] = useState({ term: '', academic_year: thisYear(), classroom: '', exam_type: '' })
  const [loading, setLoading] = useState(true)
  const [configOpen, setConfigOpen] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [message, setMessage] = useState('')

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const params = Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== ''))
      const [examRes, classRes] = await Promise.all([
        academicsApi.getExamSetups(params),
        studentsApi.getClassrooms(),
      ])
      setExams(listFromResponse(examRes.data))
      setClassrooms(listFromResponse(classRes.data))
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => { fetchData() }, [fetchData])

  const stats = useMemo(() => {
    const active = exams.filter(exam => exam.is_active).length
    const results = exams.reduce((sum, exam) => sum + (exam.results_count || 0), 0)
    const pending = exams.filter(exam => (exam.results_count || 0) > 0 && !exam.last_sync_at).length
    const synced = exams.filter(exam => exam.last_sync_at).length
    return { active, results, pending, synced }
  }, [exams])

  const syncExam = async (id) => {
    const { data } = await academicsApi.syncToCBC(id)
    setMessage(data.message)
    fetchData()
  }

  if (loading) return <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div>

  return (
    <div className="space-y-6">
      <PageHeader
        title="Examinations"
        action={
          <div className="flex flex-wrap gap-2">
            {isAdmin && <Button variant="secondary" onClick={() => setConfigOpen(true)} className="gap-2"><Settings size={16} /> Configure Thresholds</Button>}
            {isAdmin && <Button onClick={() => setCreateOpen(true)} className="gap-2"><Plus size={16} /> Create Exam</Button>}
          </div>
        }
      />
      {message && <div className="rounded-lg bg-green-50 px-4 py-3 text-sm text-green-700">{message}</div>}
      <Card className="p-4 grid grid-cols-1 md:grid-cols-4 gap-3">
        <Select label="Term" value={filters.term} onChange={e => setFilters(f => ({ ...f, term: e.target.value }))}>
          <option value="">All terms</option>
          {TERMS.map(term => <option key={term.value} value={term.value}>{term.label}</option>)}
        </Select>
        <Input label="Academic Year" type="number" value={filters.academic_year} onChange={e => setFilters(f => ({ ...f, academic_year: e.target.value }))} />
        <Select label="Classroom" value={filters.classroom} onChange={e => setFilters(f => ({ ...f, classroom: e.target.value }))}>
          <option value="">All classes</option>
          {classrooms.map(c => <option key={c.id} value={c.id}>{classroomLabel(c)}</option>)}
        </Select>
        <Select label="Exam Type" value={filters.exam_type} onChange={e => setFilters(f => ({ ...f, exam_type: e.target.value }))}>
          <option value="">All types</option>
          {EXAM_TYPES.map(type => <option key={type.value} value={type.value}>{type.label}</option>)}
        </Select>
      </Card>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard icon={ClipboardList} label="Active Exams" value={stats.active} />
        <StatCard icon={ClipboardList} label="Results Entered" value={stats.results} tone="green" />
        <StatCard icon={RefreshCw} label="Pending Sync" value={stats.pending} tone="orange" />
        <StatCard icon={RefreshCw} label="CBC Grades Synced" value={stats.synced} tone="purple" />
      </div>
      {exams.length === 0 ? (
        <Card><EmptyState title="No exams found" description="Create an exam setup to start entering marks." /></Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
          {exams.map(exam => {
            const total = (exam.total_students || 0) * (exam.subjects_count || 0)
            const progress = total ? Math.round(((exam.results_count || 0) / total) * 100) : 0
            return (
              <Card key={exam.id} className="p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-gray-900">{exam.name}</p>
                    <p className="text-sm text-gray-500">{exam.classroom_name} - {termLabel(exam.term)} {exam.academic_year}</p>
                  </div>
                  <span className="rounded-full bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-700">{exam.exam_type}</span>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                  <div><p className="text-gray-500">Subjects</p><p className="font-semibold">{exam.subjects_count || 0}</p></div>
                  <div><p className="text-gray-500">Results</p><p className="font-semibold">{exam.results_count || 0}/{total}</p></div>
                </div>
                <div className="mt-4 h-2 rounded-full bg-gray-100">
                  <div className="h-2 rounded-full bg-[var(--brand-primary)]" style={{ width: `${Math.min(progress, 100)}%` }} />
                </div>
                <p className="mt-1 text-xs text-gray-500">{progress}% marks entry completion</p>
                {exam.last_sync_at && <p className="mt-2 text-xs text-green-700">Last synced {new Date(exam.last_sync_at).toLocaleString()}</p>}
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button size="sm" onClick={() => navigate(`/academics/exams/${exam.id}`)}>Enter Marks</Button>
                  <Button size="sm" variant="secondary" disabled={!exam.results_count} onClick={() => syncExam(exam.id)}>Sync to CBC</Button>
                  <Button size="sm" variant="secondary" onClick={() => navigate(`/academics/exams/${exam.id}/results`)}>View Results</Button>
                </div>
              </Card>
            )
          })}
        </div>
      )}
      {configOpen && <ExamConfigModal onClose={() => setConfigOpen(false)} />}
      {createOpen && <CreateExamModal classrooms={classrooms} onClose={() => setCreateOpen(false)} onDone={fetchData} />}
    </div>
  )
}