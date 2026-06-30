import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Lock } from 'lucide-react'
import { academicsApi } from '@/api/academics'
import { studentsApi } from '@/api/students'
import { useAuthStore } from '@/store/authStore'
import { ATTENDANCE_STATUS, listFromResponse } from './shared'
import { Button, Card, Input, PageHeader, Spinner } from '@/components/ui'

const REGISTER_SESSION_TYPES = new Set(['daily', 'morning', 'afternoon'])

export default function MarkAttendancePage() {
  const [searchParams] = useSearchParams()
  const sessionId = searchParams.get('session')
  const navigate = useNavigate()

  const isAdmin = useAuthStore(state => state.hasRole('admin', 'superadmin'))
  const user = useAuthStore(state => state.user)

  const [session, setSession] = useState(null)
  const [students, setStudents] = useState([])
  const [records, setRecords] = useState({})
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  // Mirrors the backend's _check_attendance_permission in
  // academics/views/school_life.py:
  // - Register sessions (daily/morning/afternoon): homeroom teacher only.
  // - Lesson sessions: any teacher with a subject assignment in this
  //   classroom may also act, in addition to the homeroom teacher.
  // session.class_teacher_id and session.is_my_subject_class are expected
  // on the session payload (AttendanceSessionSerializer) — is_my_subject_class
  // should reflect whether the current teacher has a ClassSubjectAssignment
  // for this session's classroom. If that field isn't present yet, this
  // falls back to homeroom-only, which is the safe default (matches what
  // the backend will reject anyway, just without a friendly pre-check).
  const isRegisterSession = session ? REGISTER_SESSION_TYPES.has(session.session_type) : true
  const isHomeroomTeacher = session?.class_teacher_id === user?.id
  const isSubjectTeacherHere = Boolean(session?.is_my_subject_class)

  const canManageThisSession = isAdmin || isHomeroomTeacher || (!isRegisterSession && isSubjectTeacherHere)

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
    if (!sessionId || loading || session?.is_locked || !canManageThisSession) return
    localStorage.setItem(`attendance-session-${sessionId}`, JSON.stringify(records))
  }, [records, sessionId, loading, session, canManageThisSession])

  const filteredStudents = useMemo(() => {
    const q = search.toLowerCase()
    return students.filter(s => `${s.full_name} ${s.admission_number}`.toLowerCase().includes(q))
  }, [students, search])

  const setStatus = (studentId, status) => {
    if (session?.is_locked || !canManageThisSession) return
    setRecords(current => ({ ...current, [studentId]: { ...(current[studentId] || {}), status } }))
  }

  const setRemarks = (studentId, remarks) => {
    if (session?.is_locked || !canManageThisSession) return
    setRecords(current => ({ ...current, [studentId]: { ...(current[studentId] || {}), remarks } }))
  }

  const bulk = (status) => {
    if (session?.is_locked || !canManageThisSession) return
    setRecords(current => Object.fromEntries(students.map(student => [student.id, { ...(current[student.id] || {}), status }])))
  }

  const save = async () => {
    if (!canManageThisSession) return
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
    } catch (err) {
      setMessage(err.response?.data?.error || err.response?.data?.detail || 'Failed to save attendance.')
    } finally {
      setSaving(false)
    }
  }

  const lock = async () => {
    if (!isAdmin) return
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
            {isAdmin && !session.is_locked && (
              <Button variant="secondary" onClick={lock} className="gap-2">
                <Lock size={16} /> Lock Session
              </Button>
            )}
            {canManageThisSession && !session.is_locked && (
              <Button onClick={save} loading={saving}>Save Attendance</Button>
            )}
          </div>
        }
      />

      {!canManageThisSession && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {isRegisterSession
            ? 'Only the class teacher can mark the daily register for this class.'
            : 'You can only mark lesson attendance for classes and subjects you teach.'}
        </div>
      )}

      {session.is_locked && (
        <div className="rounded-lg border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-yellow-800">
          This session is locked. Attendance is read-only.
        </div>
      )}
      {message && <div className="rounded-lg bg-[var(--brand-primary-light)] px-4 py-3 text-sm text-[var(--brand-primary)]">{message}</div>}

      <Card className="p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search student..." className="md:w-80" />
          {canManageThisSession && !session.is_locked && (
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
                            disabled={session.is_locked || !canManageThisSession}
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
                        disabled={session.is_locked || !canManageThisSession}
                        className="w-full rounded-lg border border-gray-200 px-3 py-1.5 text-sm outline-none focus:border-[var(--brand-primary)] disabled:bg-gray-50"
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