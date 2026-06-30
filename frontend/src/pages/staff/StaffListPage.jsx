import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Plus, Users } from 'lucide-react'
import { staffApi } from '@/api/staff'
import { studentsApi } from '@/api/students'
import DeactivateStaffModal from '@/components/staff/DeactivateStaffModal'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import EmptyState from '@/components/ui/EmptyState'
import PageHeader from '@/components/ui/PageHeader'

const departments = ['all', 'teaching', 'administration', 'support']
const jobTitles = [
  'teacher', 'bursar', 'cook', 'cleaner', 'security', 'driver',
  'librarian', 'accountant', 'nurse', 'groundskeeper', 'other',
]

const listFromResponse = (data) => data?.results || (Array.isArray(data) ? data : [])

const statusVariant = (status) => {
  if (status === 'active') return 'active'
  if (status === 'on_leave') return 'pending'
  if (status === 'suspended') return 'pending'
  return 'default'
}

function StaffAvatar({ staff }) {
  if (staff.photo) {
    return <img src={staff.photo} alt="" className="h-9 w-9 rounded-full object-cover" />
  }
  const initials = `${staff.first_name?.[0] || ''}${staff.last_name?.[0] || ''}`.toUpperCase()
  return (
    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gray-100 text-xs font-semibold text-gray-600">
      {initials || '?'}
    </div>
  )
}

function classroomLabel(classroom) {
  return `${classroom.name}${classroom.stream ? ` ${classroom.stream}` : ''}`
}

export default function StaffListPage() {
  const location = useLocation()
  const [staff, setStaff] = useState([])
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState(location.state?.message || '')
  const [filters, setFilters] = useState({ department: 'all', employment_status: '', job_title: '' })
  const [deactivateTarget, setDeactivateTarget] = useState(null)
  // Maps CustomUser id -> array of classroom labels they're homeroom for.
  const [classTeacherMap, setClassTeacherMap] = useState({})

  const load = () => {
    setLoading(true)
    const params = {}
    if (filters.department !== 'all') params.department = filters.department
    if (filters.employment_status) params.employment_status = filters.employment_status
    if (filters.job_title) params.job_title = filters.job_title
    staffApi.getStaff(params)
      .then(({ data }) => setStaff(data.results || data))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [filters])

  // Build the class-teacher lookup once classrooms are known. We only
  // need this when teachers are visible in the current filter, but it's
  // cheap enough (one extra list call) to just always fetch active
  // classrooms tenant-wide and group by class_teacher id client-side,
  // rather than firing one request per teacher.
  useEffect(() => {
    studentsApi.getClassrooms({ is_active: true }).then((r) => {
      const classrooms = listFromResponse(r.data)
      const map = {}
      classrooms.forEach((classroom) => {
        if (!classroom.class_teacher) return
        const key = String(classroom.class_teacher)
        if (!map[key]) map[key] = []
        map[key].push(classroomLabel(classroom))
      })
      setClassTeacherMap(map)
    }).catch(() => setClassTeacherMap({}))
  }, [])

  return (
    <div>
      <PageHeader
        title="Staff Management"
        action={<Link to="/staff/new"><Button><Plus size={16} className="mr-2" />Add Staff Member</Button></Link>}
      />
      {message && (
        <div className="mb-4 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
          {message}
        </div>
      )}
      <div className="mb-4 flex flex-wrap gap-2">
        {departments.map((department) => (
          <button
            key={department}
            type="button"
            onClick={() => setFilters((f) => ({ ...f, department }))}
            className={`rounded-lg px-4 py-2 text-sm font-medium capitalize ${filters.department === department ? 'bg-[var(--brand-primary)] text-white' : 'bg-white border border-gray-200 text-gray-600'}`}
          >
            {department}
          </button>
        ))}
        <select
          value={filters.job_title}
          onChange={(event) => setFilters((f) => ({ ...f, job_title: event.target.value }))}
          className="rounded-lg border border-gray-200 px-3 py-2 text-sm"
        >
          <option value="">Any job title</option>
          {jobTitles.map((title) => (
            <option key={title} value={title}>{title.replace('_', ' ')}</option>
          ))}
        </select>
        <select
          value={filters.employment_status}
          onChange={(event) => setFilters((f) => ({ ...f, employment_status: event.target.value }))}
          className="rounded-lg border border-gray-200 px-3 py-2 text-sm"
        >
          <option value="">Any status</option>
          <option value="active">Active</option>
          <option value="on_leave">On Leave</option>
          <option value="suspended">Suspended</option>
          <option value="terminated">Terminated</option>
        </select>
      </div>
      <Card className="overflow-hidden">
        {loading ? (
          <p className="p-8 text-center text-sm text-gray-500">Loading staff...</p>
        ) : staff.length === 0 ? (
          <EmptyState icon={Users} title="No staff found" description="Add teaching and non-teaching staff for this school." />
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3">Photo</th>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Employee No.</th>
                <th className="px-4 py-3">Job Title</th>
                <th className="px-4 py-3">Class Teacher</th>
                <th className="px-4 py-3">Phone</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Login</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {staff.map((item) => {
                const homerooms = item.user ? classTeacherMap[String(item.user)] : null
                return (
                  <tr key={item.id}>
                    <td className="px-4 py-3"><StaffAvatar staff={item} /></td>
                    <td className="px-4 py-3 font-medium text-gray-900">{item.full_name}</td>
                    <td className="px-4 py-3 text-gray-600">{item.employee_number}</td>
                    <td className="px-4 py-3 capitalize text-gray-600">{item.job_title.replace('_', ' ')}</td>
                    <td className="px-4 py-3">
                      {item.job_title !== 'teacher' ? (
                        <span className="text-gray-400">—</span>
                      ) : homerooms?.length ? (
                        <div className="flex flex-wrap gap-1">
                          {homerooms.map((label) => (
                            <Badge key={label} label={label} variant="active" />
                          ))}
                        </div>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-600">{item.phone}</td>
                    <td className="px-4 py-3">
                      <Badge label={item.employment_status.replace('_', ' ')} variant={statusVariant(item.employment_status)} />
                    </td>
                    <td className="px-4 py-3 text-gray-600">{item.has_login ? 'Yes' : 'No'}</td>
                    <td className="px-4 py-3 text-right space-x-3">
                      <Link className="text-[var(--brand-primary)] hover:underline" to={`/staff/${item.id}`}>View</Link>
                      {item.employment_status !== 'terminated' && (
                        <button type="button" className="text-red-600 hover:underline" onClick={() => setDeactivateTarget(item)}>
                          Deactivate
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </Card>
      {deactivateTarget && (
        <DeactivateStaffModal
          staff={deactivateTarget}
          onClose={() => setDeactivateTarget(null)}
          onDone={() => { setDeactivateTarget(null); load() }}
        />
      )}
    </div>
  )
}