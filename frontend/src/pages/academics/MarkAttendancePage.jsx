import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Lock } from 'lucide-react'
import { academicsApi } from '@/api/academics'
import { studentsApi } from '@/api/students'
import { useAuthStore } from '@/store/authStore'
import { ATTENDANCE_STATUS, listFromResponse } from './shared'
import { Button, Card, Input, PageHeader, Spinner } from '@/components/ui'

export default function MarkAttendancePage() {
  const [searchParams] = useSearchParams()
  const sessionId = searchParams.get('session')
  const navigate = useNavigate()
  const isAdmin = useAuthStore(state => state.hasRole('admin', 'superadmin'))
  const [session, setSession] = useState(null)
  const [students, setStudents] = useState([])
  const [records, setRecords] = useState({})
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!sessionId) return
    const draftKey = `attendance-session-${sessionId}`
    academicsApi.getSession(sessionId).then(async ({ data }) => {
      setSession(data)
      const studentsRes = await studentsApi.getClassroomStudents(data.classroom)
      const studentList = listFromResponse(studentsRes.data)
      setStudents(studentList)
      const existing = Object.fromEntries((data.records || []).map(record => [record.student, { status: record.status, remarks: record.remarks || '' }]))
      const localDraft = JSON.parse(localStorage.getItem(draftKey) || '{}')
      const next = {}
      studentList.forEach(student => {
        next[student.id] = localDraft[student.id] || existing[student.id] || { status: 'P', remarks: '' }
      })
      setRecords(next)
    }).finally(() => setLoading(false))
  }, [sessionId])

  useEffect(() => {
    if (!sessionId || loading || session?.is_locked) return
    localStorage.setItem(`attendance-session-${sessionId}`, JSON.stringify(records))
  }, [records, sessionId, loading, session])

  const filteredStudents = useMemo(() => {
    const q = search.toLowerCase()
    return students.filter(s => `${s.full_name} ${s.admission_number}`.toLowerCase().includes(q))
  }, [students, search])

  const setStatus = (studentId, status) => {
    if (session?.is_locked) return
    setRecords(current => ({ ...current, [studentId]: { ...(current[studentId] || {}), status } }))
  }

  const setRemarks = (studentId, remarks) => {
    if (session?.is_locked) return
    setRecords(current => ({ ...current, [studentId]: { ...(current[studentId] || {}), remarks } }))
  }

  const bulk = (status) => {
    setRecords(current => Object.fromEntries(students.map(student => [student.id, { ...(current[student.id] || {}), status }])))
  }

  const save = async () => {
    setSaving(true)
    try {
      await academicsApi.markAttendance(sessionId, {
        records: students.map(student => ({
          student_id: student.id,
          status: records[student.id]?.status || 'P',
          remarks: records[student.id]?.remarks || '',
        })),
      })
      localStorage.removeItem(`attendance-session-${sessionId}`)
      setMessage('Attendance saved')
      navigate('/academics/attendance')
    } finally {
      setSaving(false)
    }
  }

  const lock = async () => {
    await academicsApi.lockSession(sessionId)
    const { data } = await academicsApi.getSession(sessionId)
    setSession(data)
  }

  if (loading) return <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div>
  if (!session) return <Card className="p-6 text-sm text-gray-500">Session not found.</Card>

  return (
    <div className="space-y-5">
      <PageHeader
        title={`${session.classroom_name} - ${session.date} - ${session.session_type}`}
        description={session.is_locked ? 'This session is locked' : 'Changes are stored locally until you save.'}
        action={
          <div className="flex flex-wrap gap-2">
            {isAdmin && !session.is_locked && <Button variant="secondary" onClick={lock} className="gap-2"><Lock size={16} /> Lock Session</Button>}
            {!session.is_locked && <Button onClick={save} loading={saving}>Save Attendance</Button>}
          </div>
        }
      />
      {session.is_locked && <div className="rounded-lg border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-yellow-800">This session is locked. Attendance is read-only.</div>}
      {message && <div className="rounded-lg bg-green-50 px-4 py-3 text-sm text-green-700">{message}</div>}

      <Card className="p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search student..." className="md:w-80" />
          {!session.is_locked && (
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => bulk('P')}>Mark All Present</Button>
              <Button variant="secondary" onClick={() => bulk('A')}>Mark All Absent</Button>
            </div>
          )}
        </div>
      </Card>

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Student name</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Adm No</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Remarks</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {filteredStudents.map(student => (
                <tr key={student.id}>
                  <td className="px-4 py-3 font-medium text-gray-900">{student.full_name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-600">{student.admission_number}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1">
                      {Object.keys(ATTENDANCE_STATUS).map(status => (
                        <button
                          key={status}
                          disabled={session.is_locked}
                          onClick={() => setStatus(student.id, status)}
                          className={`rounded border px-3 py-1 text-xs font-semibold disabled:cursor-not-allowed ${records[student.id]?.status === status ? ATTENDANCE_STATUS[status].className : 'border-gray-200 bg-white text-gray-500'}`}
                        >
                          {status}
                        </button>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <input
                      value={records[student.id]?.remarks || ''}
                      onChange={e => setRemarks(student.id, e.target.value)}
                      disabled={session.is_locked}
                      className="w-full rounded-lg border border-gray-200 px-3 py-1.5 text-sm outline-none focus:border-blue-400 disabled:bg-gray-50"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
