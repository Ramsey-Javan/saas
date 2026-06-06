import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BookOpen, CalendarCheck, FileText, GraduationCap } from 'lucide-react'
import { academicsApi } from '@/api/academics'
import { Button, Card, EmptyState, PageHeader, Spinner } from '@/components/ui'
import { EmptyTableRow, StatCard, StatusBadge, countFromResponse, listFromResponse, termLabel } from './shared'

export default function AcademicsDashboard() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [subjectsCount, setSubjectsCount] = useState(0)
  const [assignmentsCount, setAssignmentsCount] = useState(0)
  const [todaySessions, setTodaySessions] = useState([])
  const [reportCards, setReportCards] = useState([])

  useEffect(() => {
    Promise.all([
      academicsApi.getSubjects(),
      academicsApi.getAssignments(),
      academicsApi.getTodaySessions(),
      academicsApi.getReportCards({ page_size: 5 }),
    ]).then(([subjectsRes, assignmentsRes, sessionsRes, reportsRes]) => {
      setSubjectsCount(countFromResponse(subjectsRes.data))
      setAssignmentsCount(countFromResponse(assignmentsRes.data))
      setTodaySessions(listFromResponse(sessionsRes.data))
      setReportCards(listFromResponse(reportsRes.data).slice(0, 5))
    }).finally(() => setLoading(false))
  }, [])

  const present = todaySessions.reduce((sum, s) => sum + (s.present_count || 0), 0)
  const total = todaySessions.reduce((sum, s) => sum + (s.total_students || 0), 0)
  const attendanceRate = total ? `${Math.round((present / total) * 100)}%` : '0%'

  if (loading) return <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div>

  return (
    <div className="space-y-6">
      <PageHeader
        title="Academics"
        description="Curriculum, assessment, attendance, timetables, and reports"
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => navigate('/academics/curriculum')}>Curriculum</Button>
            <Button variant="secondary" onClick={() => navigate('/academics/assignments')}>Assignments</Button>
            <Button onClick={() => navigate('/academics/grades')}>Grade Entry</Button>
          </div>
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard icon={BookOpen} label="Total Subjects" value={subjectsCount} />
        <StatCard icon={GraduationCap} label="Classes Assigned" value={assignmentsCount} tone="purple" />
        <StatCard icon={CalendarCheck} label="Attendance Today" value={attendanceRate} tone="green" />
        <StatCard icon={FileText} label="Report Cards This Term" value={countFromResponse({ results: reportCards })} tone="orange" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <Card className="p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-900">Today&apos;s Attendance Sessions</h2>
            <Button size="sm" variant="secondary" onClick={() => navigate('/academics/attendance')}>View All</Button>
          </div>
          {todaySessions.length === 0 ? (
            <EmptyState icon={CalendarCheck} title="No sessions today" description="Create sessions from the attendance page." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100">
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-gray-500">Classroom</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-gray-500">Type</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-gray-500">Present</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-gray-500">Absent</th>
                    <th className="px-3 py-2" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {todaySessions.map(session => (
                    <tr key={session.id}>
                      <td className="px-3 py-3 font-medium text-gray-900">{session.classroom_name}</td>
                      <td className="px-3 py-3 capitalize text-gray-600">{session.session_type}</td>
                      <td className="px-3 py-3 text-green-700">{session.present_count || 0}</td>
                      <td className="px-3 py-3 text-red-700">{session.absent_count || 0}</td>
                      <td className="px-3 py-3 text-right">
                        <Button size="sm" onClick={() => navigate(`/academics/attendance/mark?session=${session.id}`)}>Mark Attendance</Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-900">Recent Report Cards</h2>
            <Button size="sm" variant="secondary" onClick={() => navigate('/academics/report-cards')}>View All</Button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-gray-500">Student</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-gray-500">Class</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-gray-500">Term</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-gray-500">Status</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {reportCards.length === 0 ? <EmptyTableRow colSpan={5} message="No report cards found." /> : reportCards.map(card => (
                  <tr key={card.id}>
                    <td className="px-3 py-3 font-medium text-gray-900">{card.student_name}</td>
                    <td className="px-3 py-3 text-gray-600">{card.classroom_name || '—'}</td>
                    <td className="px-3 py-3 text-gray-600">{termLabel(card.term)}</td>
                    <td className="px-3 py-3"><StatusBadge status={card.status} /></td>
                    <td className="px-3 py-3 text-right">
                      <Button size="sm" variant="secondary" onClick={() => navigate(`/academics/report-cards/${card.id}`)}>View</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  )
}
