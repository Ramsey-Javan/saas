import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Award, Plus } from 'lucide-react'
import { academicsApi } from '@/api/academics'
import { studentsApi } from '@/api/students'
import { Button, Card, EmptyState, Input, PageHeader, Select, Spinner } from '@/components/ui'
import { Modal, classroomLabel, listFromResponse, thisYear } from './shared'

const SESSIONS = [
  { value: 'KEYA', label: 'KEYA – Grade 3 (Kenya Early Years Assessment)' },
  { value: 'KPSEA', label: 'KPSEA – Grade 6 (Kenya Primary School Education Assessment)' },
  { value: 'KJSEA', label: 'KJSEA – Grade 9 (Kenya Junior School Education Assessment)' },
]

const EXAM_GRADE_MAP = {
  KEYA: 'Grade 3',
  KPSEA: 'Grade 6',
  KJSEA: 'Grade 9',
}

function CreateSessionModal({ classrooms, name, onClose, onDone }) {
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({ name, academic_year: thisYear(), classroom: '', centre_number: '', centre_name: '', exam_date: '', notes: '' })

  const targetGrade = EXAM_GRADE_MAP[form.name] || ''
  const filteredClassrooms = useMemo(() => {
    if (!targetGrade) return classrooms
    return classrooms.filter(c => c.grade_level === targetGrade)
  }, [classrooms, targetGrade])

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      await academicsApi.createNationalSession(form)
      onDone()
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="Register Exam Session" onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" form="national-session-form" loading={saving}>Create Session</Button></>}>
      <form id="national-session-form" onSubmit={submit} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Select label="Exam" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value, classroom: '' }))}>
          {SESSIONS.map(session => <option key={session.value} value={session.value}>{session.label}</option>)}
        </Select>
        <Input label="Academic Year" type="number" value={form.academic_year} onChange={e => setForm(f => ({ ...f, academic_year: e.target.value }))} required />
        <Select label="Classroom" value={form.classroom} onChange={e => setForm(f => ({ ...f, classroom: e.target.value }))} required>
          <option value="">Select class</option>
          {filteredClassrooms.map(c => <option key={c.id} value={c.id}>{classroomLabel(c)}</option>)}
        </Select>
        <Input label="Centre Number" value={form.centre_number} onChange={e => setForm(f => ({ ...f, centre_number: e.target.value }))} />
        <Input label="Centre Name" value={form.centre_name} onChange={e => setForm(f => ({ ...f, centre_name: e.target.value }))} />
        <Input label="Exam Date" type="date" value={form.exam_date} onChange={e => setForm(f => ({ ...f, exam_date: e.target.value }))} />
      </form>
    </Modal>
  )
}

export default function NationalExamsDashboard() {
  const navigate = useNavigate()
  const [active, setActive] = useState('KEYA')
  const [sessions, setSessions] = useState([])
  const [classrooms, setClassrooms] = useState([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const [sessionRes, classRes] = await Promise.all([
        academicsApi.getNationalSessions({ name: active }),
        studentsApi.getClassrooms(),
      ])
      setSessions(listFromResponse(sessionRes.data))
      setClassrooms(listFromResponse(classRes.data))
    } finally {
      setLoading(false)
    }
  }, [active])

  useEffect(() => { fetchData() }, [fetchData])

  return (
    <div className="space-y-6">
      <PageHeader title="National Examinations (KNEC)" action={<Button onClick={() => setModalOpen(true)} className="gap-2"><Plus size={16} /> Register Exam Session</Button>} />
      <Card className="p-2">
        <div className="flex flex-wrap gap-2">
          {SESSIONS.map(session => (
            <button key={session.value} onClick={() => setActive(session.value)} className={`rounded-lg px-4 py-2 text-sm font-medium ${active === session.value ? 'bg-[var(--brand-primary)] text-white' : 'text-gray-600 hover:bg-gray-100'}`}>
              {session.label}
            </button>
          ))}
        </div>
      </Card>
      {loading ? <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div> : sessions.length === 0 ? (
        <Card><EmptyState title="No national exam sessions" description="Register a KNEC exam session for the selected assessment." /></Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {sessions.map(session => (
            <Card key={session.id} className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-gray-900">{session.name} {session.academic_year}</p>
                  <p className="text-sm text-gray-500">{session.classroom_name} - {session.centre_number || 'No centre number'}</p>
                </div>
                <Award size={20} className="text-[var(--brand-primary)]" />
              </div>
              <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                <div><p className="text-gray-500">Candidates</p><p className="font-semibold">{session.registered_count}/{session.candidates_count}</p></div>
                <div><p className="text-gray-500">Results</p><p className={`font-semibold ${session.is_results_entered ? 'text-green-700' : 'text-orange-700'}`}>{session.is_results_entered ? 'Results Entered' : 'Awaiting Results'}</p></div>
              </div>
              <div className="mt-4 flex gap-2">
                <Button size="sm" onClick={() => navigate(`/academics/national-exams/${session.id}?tab=candidates`)}>Manage Candidates</Button>
                <Button size="sm" variant="secondary" onClick={() => navigate(`/academics/national-exams/${session.id}?tab=results`)}>Enter Results</Button>
              </div>
            </Card>
          ))}
        </div>
      )}
      {modalOpen && <CreateSessionModal classrooms={classrooms} name={active} onClose={() => setModalOpen(false)} onDone={fetchData} />}
    </div>
  )
}