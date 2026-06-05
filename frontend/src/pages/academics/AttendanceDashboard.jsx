import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { academicsApi } from '@/api/academics'
import { studentsApi } from '@/api/students'
import { useAuthStore } from '@/store/authStore'
import { Button, Card, Input, PageHeader, Select, Spinner } from '@/components/ui'
import { EmptyTableRow, Modal, TERMS, classroomLabel, listFromResponse, thisYear, todayISO } from './shared'

function CreateSessionModal({ classrooms, subjects, onClose }) {
  const navigate = useNavigate()
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({ classroom: '', session_type: 'daily', subject: '', date: todayISO(), term: 'term1', academic_year: thisYear() })
  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      const payload = { ...form, subject: form.session_type === 'lesson' ? form.subject : null }
      const { data } = await academicsApi.createSession(payload)
      navigate(`/academics/attendance/mark?session=${data.id}`)
    } finally {
      setSaving(false)
    }
  }
  return (
    <Modal title="New Attendance Session" onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" form="session-form" loading={saving}>Create Session</Button></>}>
      <form id="session-form" onSubmit={submit} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Select label="Classroom" value={form.classroom} onChange={e => setForm(f => ({ ...f, classroom: e.target.value }))} required>
          <option value="">Select class</option>
          {classrooms.map(c => <option key={c.id} value={c.id}>{classroomLabel(c)}</option>)}
        </Select>
        <Select label="Session Type" value={form.session_type} onChange={e => setForm(f => ({ ...f, session_type: e.target.value }))}>
          {['daily', 'morning', 'afternoon', 'lesson'].map(type => <option key={type} value={type}>{type}</option>)}
        </Select>
        {form.session_type === 'lesson' && (
          <Select label="Subject" value={form.subject} onChange={e => setForm(f => ({ ...f, subject: e.target.value }))} required>
            <option value="">Select subject</option>
            {subjects.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </Select>
        )}
        <Input label="Date" type="date" value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))} required />
        <Select label="Term" value={form.term} onChange={e => setForm(f => ({ ...f, term: e.target.value }))}>
          {TERMS.map(term => <option key={term.value} value={term.value}>{term.label}</option>)}
        </Select>
        <Input label="Academic Year" type="number" value={form.academic_year} onChange={e => setForm(f => ({ ...f, academic_year: e.target.value }))} required />
      </form>
    </Modal>
  )
}

function SessionsTable({ sessions, onLock }) {
  const navigate = useNavigate()
  const isAdmin = useAuthStore(state => state.hasRole('admin', 'superadmin'))
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100">
            {['Class', 'Type', 'Date', 'Present', 'Absent', 'Total', 'Locked', 'Actions'].map(h => <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">{h}</th>)}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {sessions.length === 0 ? <EmptyTableRow colSpan={8} message="No sessions found." /> : sessions.map(s => (
            <tr key={s.id}>
              <td className="px-4 py-3 font-medium text-gray-900">{s.classroom_name}</td>
              <td className="px-4 py-3 capitalize text-gray-600">{s.session_type}</td>
              <td className="px-4 py-3 text-gray-600">{s.date}</td>
              <td className="px-4 py-3 text-green-700">{s.present_count || 0}</td>
              <td className="px-4 py-3 text-red-700">{s.absent_count || 0}</td>
              <td className="px-4 py-3 text-gray-600">{s.total_students || 0}</td>
              <td className="px-4 py-3">{s.is_locked ? 'Yes' : 'No'}</td>
              <td className="px-4 py-3">
                <div className="flex gap-2">
                  <Button size="sm" onClick={() => navigate(`/academics/attendance/mark?session=${s.id}`)}>{s.is_locked ? 'View' : 'Mark'}</Button>
                  {isAdmin && !s.is_locked && <Button size="sm" variant="secondary" onClick={() => onLock(s.id)}>Lock</Button>}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function AttendanceDashboard() {
  const [searchParams] = useSearchParams()
  const [tab, setTab] = useState('today')
  const [sessions, setSessions] = useState([])
  const [classrooms, setClassrooms] = useState([])
  const [subjects, setSubjects] = useState([])
  const [filters, setFilters] = useState({ classroom: searchParams.get('classroom') || '', term: '', academic_year: thisYear(), date_after: '', date_before: '' })
  const [studentSummary, setStudentSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)

  const fetchSessions = useCallback(async () => {
    setLoading(true)
    try {
      if (tab === 'today') {
        const { data } = await academicsApi.getTodaySessions()
        setSessions(listFromResponse(data))
      } else {
        const params = { classroom: filters.classroom || undefined, term: filters.term || undefined, academic_year: filters.academic_year || undefined }
        const { data } = await academicsApi.getSessions(params)
        setSessions(listFromResponse(data))
      }
    } finally {
      setLoading(false)
    }
  }, [tab, filters])

  useEffect(() => {
    Promise.all([studentsApi.getClassrooms(), academicsApi.getSubjects()]).then(([classRes, subjectRes]) => {
      setClassrooms(listFromResponse(classRes.data))
      setSubjects(listFromResponse(subjectRes.data))
    })
  }, [])
  useEffect(() => { fetchSessions() }, [fetchSessions])

  const studentFilter = searchParams.get('student')
  useEffect(() => {
    if (!studentFilter) {
      setStudentSummary(null)
      return
    }
    academicsApi.getStudentAttendanceSummary({ student: studentFilter })
      .then(res => setStudentSummary(res.data))
      .catch(() => setStudentSummary(null))
  }, [studentFilter])
  const visibleSessions = useMemo(() => {
    if (tab !== 'week') return sessions
    const now = new Date()
    const start = new Date(now)
    start.setDate(now.getDate() - ((now.getDay() + 6) % 7))
    start.setHours(0, 0, 0, 0)
    const end = new Date(start)
    end.setDate(start.getDate() + 7)
    return sessions.filter(s => new Date(s.date) >= start && new Date(s.date) < end)
  }, [sessions, tab])

  const lock = async (id) => {
    await academicsApi.lockSession(id)
    fetchSessions()
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Attendance" description={studentFilter ? `Filtered for student ${studentFilter}` : ''} action={<Button onClick={() => setModalOpen(true)} className="gap-2"><Plus size={16} /> New Session</Button>} />
      {studentSummary && (
        <Card className="p-4 grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
          <div><p className="text-gray-500">Present</p><p className="font-semibold text-gray-900">{studentSummary.present}</p></div>
          <div><p className="text-gray-500">Absent</p><p className="font-semibold text-gray-900">{studentSummary.absent}</p></div>
          <div><p className="text-gray-500">Late</p><p className="font-semibold text-gray-900">{studentSummary.late}</p></div>
          <div><p className="text-gray-500">Excused</p><p className="font-semibold text-gray-900">{studentSummary.excused}</p></div>
          <div><p className="text-gray-500">Attendance</p><p className="font-semibold text-gray-900">{studentSummary.attendance_percentage}%</p></div>
        </Card>
      )}
      <Card className="p-2">
        <div className="flex gap-2">
          {['today', 'week', 'history'].map(name => <button key={name} onClick={() => setTab(name)} className={`rounded-lg px-4 py-2 text-sm font-medium capitalize ${tab === name ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'}`}>{name === 'week' ? 'This Week' : name}</button>)}
        </div>
      </Card>
      {tab === 'history' && (
        <Card className="p-4 grid grid-cols-1 md:grid-cols-4 gap-3">
          <Select label="Classroom" value={filters.classroom} onChange={e => setFilters(f => ({ ...f, classroom: e.target.value }))}>
            <option value="">All classes</option>
            {classrooms.map(c => <option key={c.id} value={c.id}>{classroomLabel(c)}</option>)}
          </Select>
          <Select label="Term" value={filters.term} onChange={e => setFilters(f => ({ ...f, term: e.target.value }))}>
            <option value="">All terms</option>
            {TERMS.map(term => <option key={term.value} value={term.value}>{term.label}</option>)}
          </Select>
          <Input label="Academic Year" type="number" value={filters.academic_year} onChange={e => setFilters(f => ({ ...f, academic_year: e.target.value }))} />
        </Card>
      )}
      {tab === 'week' && <p className="text-sm text-gray-500">Showing sessions from the current school week.</p>}
      <Card>{loading ? <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div> : <SessionsTable sessions={visibleSessions} onLock={lock} />}</Card>
      {modalOpen && <CreateSessionModal classrooms={classrooms} subjects={subjects} onClose={() => setModalOpen(false)} />}
    </div>
  )
}
