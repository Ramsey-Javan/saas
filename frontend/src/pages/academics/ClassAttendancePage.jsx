import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Download, X, ClipboardList } from 'lucide-react'
import { academicsApi } from '@/api/academics'
import { studentsApi } from '@/api/students'
import { useAuthStore } from '@/store/authStore'
import { Badge, Button, Card, Input, PageHeader, Select, Spinner } from '@/components/ui'
import { StatCard, TERMS, downloadRowsAsCSV, listFromResponse, thisYear } from './shared'

function statusFor(percentage) {
  if (percentage >= 90) return { label: 'Good', variant: 'active' }
  if (percentage >= 75) return { label: 'Fair', variant: 'pending' }
  return { label: 'At Risk', variant: 'inactive' }
}

export default function ClassAttendancePage() {
  const { classroomId } = useParams()
  const navigate = useNavigate()
  const [classroom, setClassroom] = useState(null)
  const [rows, setRows] = useState([])
  const [filters, setFilters] = useState({ term: 'term1', academic_year: thisYear() })
  const [selected, setSelected] = useState(null)
  const [history, setHistory] = useState(null)
  const [loading, setLoading] = useState(true)

  const user = useAuthStore(state => state.user)
  const isAdmin = useAuthStore(state => state.hasRole('admin', 'superadmin'))

  const fetchSummary = useCallback(async () => {
    setLoading(true)
    try {
      const [summaryRes, classroomRes] = await Promise.all([
        academicsApi.getClassAttendanceSummary({ classroom: classroomId, term: filters.term, academic_year: filters.academic_year }),
        studentsApi.getClassroom(classroomId),
      ])
      setRows(listFromResponse(summaryRes.data))
      setClassroom(classroomRes.data)
    } finally {
      setLoading(false)
    }
  }, [classroomId, filters])

  useEffect(() => { fetchSummary() }, [fetchSummary])

  const stats = useMemo(() => {
    const totalSessions = Math.max(...rows.map(r => r.total || 0), 0)
    const avg = rows.length ? Math.round(rows.reduce((sum, row) => sum + (row.percentage || 0), 0) / rows.length) : 0
    return { avg, atRisk: rows.filter(r => (r.percentage || 0) < 80).length, totalSessions }
  }, [rows])

  const openHistory = async (row) => {
    setSelected(row)
    const { data } = await academicsApi.getStudentAttendanceSummary({ student: row.student_id, term: filters.term, academic_year: filters.academic_year })
    setHistory(data)
  }

  const exportCsv = () => {
    downloadRowsAsCSV('class_attendance.csv', [
      ['Student', 'Present', 'Absent', 'Late', 'Excused', 'Total', 'Percentage', 'Status'],
      ...rows.map(row => [row.student_name, row.present, row.absent, row.late, row.excused || 0, row.total, row.percentage, statusFor(row.percentage).label]),
    ])
  }

  // This shortcut leads to the daily register, which is homeroom-only
  // (see academics/views/school_life.py: REGISTER_SESSION_TYPES check).
  // Subject teachers can still mark their own lesson-level sessions —
  // just not from this particular shortcut, since this page is a
  // term-long register summary, not a single lesson view.
  const isClassTeacher = isAdmin || classroom?.class_teacher_id === user?.id

  if (loading) return <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div>

  return (
    <div className="space-y-6">
      <PageHeader
        title={`${classroom?.name || 'Class'} Attendance Summary`}
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={exportCsv} className="gap-2">
              <Download size={16} /> Export CSV
            </Button>
            {isClassTeacher && (
              <Button
                onClick={() => navigate(`/academics/attendance?classroom=${classroomId}`)}
                className="gap-2"
              >
                <ClipboardList size={16} /> Mark Attendance
              </Button>
            )}
          </div>
        }
      />

      {!isClassTeacher && (
        <div className="rounded-lg border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-yellow-800">
          Only the class teacher can mark the daily register for this class. If you teach a subject
          here, you can still mark attendance for your own lessons from that lesson's session.
        </div>
      )}

      <Card className="p-4 grid grid-cols-1 md:grid-cols-2 gap-3">
        <Select label="Term" value={filters.term} onChange={e => setFilters(f => ({ ...f, term: e.target.value }))}>
          {TERMS.map(term => <option key={term.value} value={term.value}>{term.label}</option>)}
        </Select>
        <Input label="Academic Year" type="number" value={filters.academic_year} onChange={e => setFilters(f => ({ ...f, academic_year: e.target.value }))} />
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard label="Average Attendance" value={`${stats.avg}%`} />
        <StatCard label="Students Below 80%" value={stats.atRisk} tone="red" />
        <StatCard label="Total Sessions" value={stats.totalSessions} tone="purple" />
      </div>

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                {['Student', 'Present', 'Absent', 'Late', 'Excused', 'Total', 'Percentage', 'Status'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {rows.map(row => {
                const status = statusFor(row.percentage || 0)
                return (
                  <tr key={row.student_id} onClick={() => openHistory(row)} className="cursor-pointer hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">{row.student_name}</td>
                    <td className="px-4 py-3">{row.present || 0}</td>
                    <td className="px-4 py-3">{row.absent || 0}</td>
                    <td className="px-4 py-3">{row.late || 0}</td>
                    <td className="px-4 py-3">{row.excused || 0}</td>
                    <td className="px-4 py-3">{row.total || 0}</td>
                    <td className="px-4 py-3">{row.percentage || 0}%</td>
                    <td className="px-4 py-3"><Badge label={status.label} variant={status.variant} /></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {selected && (
        <div className="fixed inset-y-0 right-0 z-40 w-full max-w-md bg-white p-5 shadow-xl">
          <button onClick={() => { setSelected(null); setHistory(null) }} className="absolute right-4 top-4 rounded p-1 hover:bg-gray-100"><X size={18} /></button>
          <h2 className="text-lg font-semibold text-gray-900">{selected.student_name}</h2>
          <p className="mt-1 text-sm text-gray-500">Attendance history summary</p>
          {history && (
            <div className="mt-5 space-y-3 text-sm">
              {Object.entries(history).map(([key, value]) => (
                <div key={key} className="flex justify-between border-b border-gray-50 py-2">
                  <span className="capitalize text-gray-500">{key.replaceAll('_', ' ')}</span>
                  <span className="font-medium text-gray-900">{value}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}