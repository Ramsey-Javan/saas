import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertCircle, BookOpen, CalendarCheck, Users } from 'lucide-react'
import { academicsApi } from '@/api/academics'
import { useAuthStore } from '@/store/authStore'
import { Button, Card, PageHeader, Spinner } from '@/components/ui'
import { StatCard, listFromResponse, userName } from '@/pages/academics/shared'

export default function TeacherDashboard() {
  const navigate = useNavigate()
  const user = useAuthStore(state => state.user)
  const [assignments, setAssignments] = useState([])
  const [sessions, setSessions] = useState([])
  const [draftReports, setDraftReports] = useState([])
  const [atRiskCount, setAtRiskCount] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      academicsApi.getMyClasses(),
      academicsApi.getTodaySessions(),
      academicsApi.getReportCards({ status: 'draft' }),
    ]).then(async ([assignRes, sessionsRes, reportsRes]) => {
      const classAssignments = listFromResponse(assignRes.data)
      setAssignments(classAssignments)
      setSessions(listFromResponse(sessionsRes.data))
      setDraftReports(listFromResponse(reportsRes.data))
      const classroomIds = [...new Set(classAssignments.map(a => a.classroom))]
      const summaries = await Promise.allSettled(classroomIds.map(classroom => academicsApi.getClassAttendanceSummary({ classroom })))
      setAtRiskCount(summaries.reduce((sum, result) => {
        if (result.status !== 'fulfilled') return sum
        return sum + listFromResponse(result.value.data).filter(row => (row.percentage || 0) < 75).length
      }, 0))
    }).finally(() => setLoading(false))
  }, [])

  const classes = useMemo(() => {
    const map = new Map()
    assignments.forEach(assignment => {
      const group = map.get(assignment.classroom) || { id: assignment.classroom, name: assignment.classroom_name, subjects: [] }
      group.subjects.push(assignment)
      map.set(assignment.classroom, group)
    })
    return [...map.values()]
  }, [assignments])

  if (loading) return <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div>

  return (
    <div className="space-y-6">
      <PageHeader title={`Welcome back, ${userName(user)}`} />
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard icon={Users} label="My Classes" value={classes.length} />
        <StatCard icon={CalendarCheck} label="Today Sessions" value={sessions.length} tone="green" />
        <StatCard icon={BookOpen} label="Pending Report Cards" value={draftReports.length} tone="orange" />
        <StatCard icon={AlertCircle} label="Students At Risk" value={atRiskCount} tone="red" />
      </div>
      <Card className="p-5">
        <h2 className="mb-4 font-semibold text-gray-900">My Classes</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
          {assignments.map(assignment => (
            <div key={assignment.id} className="rounded-lg border border-gray-100 p-4">
              <p className="font-semibold text-gray-900">{assignment.classroom_name}</p>
              <p className="text-sm text-gray-500">{assignment.subject_name} · {assignment.term}</p>
              <div className="mt-4 flex gap-2">
                <Button size="sm" variant="secondary" onClick={() => navigate(`/academics/attendance?classroom=${assignment.classroom}`)}>Mark Attendance</Button>
                <Button size="sm" onClick={() => navigate(`/academics/grades/${assignment.classroom}/${assignment.subject}?term=${assignment.term}&year=${assignment.academic_year}`)}>Enter Grades</Button>
              </div>
            </div>
          ))}
        </div>
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
