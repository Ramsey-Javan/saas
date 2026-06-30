import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertCircle, BookOpen, CalendarCheck, Crown, Users } from 'lucide-react'
import { academicsApi } from '@/api/academics'
import { studentsApi } from '@/api/students'
import { useAuthStore } from '@/store/authStore'
import { Button, Card, PageHeader, Select, Spinner } from '@/components/ui'
import { StatCard, listFromResponse, userName } from '@/pages/academics/shared'

function ClassExamPanel({ classroomId }) {
  const [exams, setExams] = useState([])
  const [examsLoading, setExamsLoading] = useState(true)
  const [selectedExam, setSelectedExam] = useState('')
  const [average, setAverage] = useState(null)
  const [averageLoading, setAverageLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    academicsApi.getExamSetups({ classroom: classroomId })
      .then(r => setExams(listFromResponse(r.data)))
      .catch(() => setError('Could not load exams for this class.'))
      .finally(() => setExamsLoading(false))
  }, [classroomId])

  useEffect(() => {
    if (!selectedExam) {
      setAverage(null)
      return
    }
    setAverageLoading(true)
    setError('')
    academicsApi.getClassExamAverage({ classroom: classroomId, exam: selectedExam })
      .then(r => setAverage(r.data))
      .catch(() => setError('Could not load results for this exam.'))
      .finally(() => setAverageLoading(false))
  }, [selectedExam, classroomId])

  if (examsLoading) return <Spinner className="h-4 w-4" />

  if (exams.length === 0) {
    return <p className="text-xs text-gray-400">No exams set up for this class yet.</p>
  }

  return (
    <div className="mt-3 border-t border-gray-100 pt-3">
      <select
        value={selectedExam}
        onChange={(e) => setSelectedExam(e.target.value)}
        className="w-full rounded-lg border border-gray-200 px-3 py-2 text-xs text-gray-700 outline-none focus:border-[var(--brand-primary)] focus:ring-2 focus:ring-[var(--brand-primary-ring)]"
      >
        <option value="">View exam average...</option>
        {exams.map(exam => (
          <option key={exam.id} value={exam.id}>{exam.name} ({exam.term} {exam.academic_year})</option>
        ))}
      </select>

      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}

      {averageLoading && <div className="mt-2"><Spinner className="h-4 w-4" /></div>}

      {average && !averageLoading && (
        <div className="mt-3 space-y-2">
          <div className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2">
            <span className="text-xs font-medium text-gray-600">Overall class average</span>
            <span className="text-sm font-bold text-gray-900">
              {average.overall_average_percentage != null ? `${average.overall_average_percentage}%` : '—'}
            </span>
          </div>
          {average.subjects.length > 0 && (
            <div className="space-y-1">
              {average.subjects.map(subj => (
                <div key={subj.subject_id} className="flex items-center justify-between px-3 py-1 text-xs">
                  <span className="text-gray-600">{subj.subject_name}</span>
                  <span className="font-medium text-gray-900">
                    {subj.average_percentage != null ? `${subj.average_percentage}%` : 'No marks yet'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function TeacherDashboard() {
  const navigate = useNavigate()
  const user = useAuthStore(state => state.user)
  const [assignments, setAssignments] = useState([])
  const [homeroomClassrooms, setHomeroomClassrooms] = useState([])
  const [sessions, setSessions] = useState([])
  const [draftReports, setDraftReports] = useState([])
  const [atRiskCount, setAtRiskCount] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      academicsApi.getMyClasses(),
      academicsApi.getTodaySessions(),
      academicsApi.getReportCards({ status: 'draft' }),
      user?.id ? studentsApi.getClassrooms({ class_teacher: user.id }) : Promise.resolve({ data: [] }),
    ]).then(async ([assignRes, sessionsRes, reportsRes, homeroomRes]) => {
      const classAssignments = listFromResponse(assignRes.data)
      setAssignments(classAssignments)
      setSessions(listFromResponse(sessionsRes.data))
      setDraftReports(listFromResponse(reportsRes.data))
      setHomeroomClassrooms(listFromResponse(homeroomRes.data))

      const classroomIds = [...new Set(classAssignments.map(a => a.classroom))]
      const summaries = await Promise.allSettled(classroomIds.map(classroom => academicsApi.getClassAttendanceSummary({ classroom })))
      setAtRiskCount(summaries.reduce((sum, result) => {
        if (result.status !== 'fulfilled') return sum
        return sum + listFromResponse(result.value.data).filter(row => (row.percentage || 0) < 75).length
      }, 0))
    }).finally(() => setLoading(false))
  }, [user?.id])

  const myClasses = useMemo(() => {
    const map = new Map()

    assignments.forEach(assignment => {
      const existing = map.get(assignment.classroom) || {
        id: assignment.classroom,
        name: assignment.classroom_name,
        isHomeroom: false,
        subjects: [],
      }
      existing.subjects.push(assignment)
      map.set(assignment.classroom, existing)
    })

    homeroomClassrooms.forEach(classroom => {
      const existing = map.get(classroom.id) || {
        id: classroom.id,
        name: `${classroom.name}${classroom.stream ? ` ${classroom.stream}` : ''}`,
        isHomeroom: false,
        subjects: [],
      }
      existing.isHomeroom = true
      map.set(classroom.id, existing)
    })

    return [...map.values()]
  }, [assignments, homeroomClassrooms])

  if (loading) return <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div>

  return (
    <div className="space-y-6">
      <PageHeader title={`Welcome back, ${userName(user)}`} />
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard icon={Users} label="My Classes" value={myClasses.length} />
        <StatCard icon={CalendarCheck} label="Today Sessions" value={sessions.length} tone="green" />
        <StatCard icon={BookOpen} label="Pending Report Cards" value={draftReports.length} tone="orange" />
        <StatCard icon={AlertCircle} label="Students At Risk" value={atRiskCount} tone="red" />
      </div>
      <Card className="p-5">
        <h2 className="mb-4 font-semibold text-gray-900">My Classes</h2>
        {myClasses.length === 0 ? (
          <p className="text-sm text-gray-500">
            You're not currently assigned to teach any subjects or act as class teacher for any class.
          </p>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {myClasses.map(classGroup => (
              <div key={classGroup.id} className="rounded-lg border border-gray-100 p-4">
                <div className="flex items-center gap-2">
                  <p className="font-semibold text-gray-900">{classGroup.name}</p>
                  {classGroup.isHomeroom && (
                    <span className="flex items-center gap-1 rounded-full bg-[var(--brand-primary-light)] px-2 py-0.5 text-[10px] font-medium text-[var(--brand-primary)]">
                      <Crown size={10} /> Class Teacher
                    </span>
                  )}
                </div>

                {classGroup.subjects.length > 0 ? (
                  <p className="text-sm text-gray-500">
                    {classGroup.subjects.map(s => s.subject_name).join(', ')}
                  </p>
                ) : (
                  <p className="text-sm text-gray-400">No subjects assigned to you in this class</p>
                )}

                <div className="mt-4 flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => navigate(`/academics/attendance?classroom=${classGroup.id}`)}
                  >
                    {classGroup.isHomeroom ? 'View Attendance' : 'Mark Attendance'}
                  </Button>
                  {classGroup.subjects.map(assignment => (
                    <button
                      key={assignment.id}
                      type="button"
                      onClick={() => navigate(`/academics/grades/${assignment.classroom}/${assignment.subject}?term=${assignment.term}&year=${assignment.academic_year}`)}
                      className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-[var(--brand-primary)] hover:bg-[var(--brand-primary-light)]"
                    >
                      Enter Grades{classGroup.subjects.length > 1 ? ` (${assignment.subject_name})` : ''}
                    </button>
                  ))}
                </div>

                <ClassExamPanel classroomId={classGroup.id} />
              </div>
            ))}
          </div>
        )}
      </Card>
      <Card className="p-5">
        <h2 className="mb-4 font-semibold text-gray-900">Today&apos;s Attendance</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-gray-100"><th className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Class</th><th className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Type</th><th className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Status</th><th className="px-4 py-3" /></tr></thead>
            <tbody className="divide-y divide-gray-50">
              {sessions.map(session => {
                const marked = (session.total_students || 0) > 0
                return (
                  <tr key={session.id}>
                    <td className="px-4 py-3 font-medium text-gray-900">{session.classroom_name}</td>
                    <td className="px-4 py-3 capitalize text-gray-600">{session.session_type}</td>
                    <td className="px-4 py-3">{marked ? 'marked' : 'unmarked'}</td>
                    <td className="px-4 py-3 text-right">{!marked && <Button size="sm" onClick={() => navigate(`/academics/attendance/mark?session=${session.id}`)}>Mark Now</Button>}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}