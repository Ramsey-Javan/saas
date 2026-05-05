import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Users, Search, Plus, Upload } from 'lucide-react'
import { studentsApi } from '@/api/students'
import { PageHeader, Card, Badge, Avatar, Button, Spinner, EmptyState, Select } from '@/components/ui'

const GRADE_LEVELS = [
  'PP1','PP2','Grade 1','Grade 2','Grade 3','Grade 4',
  'Grade 5','Grade 6','Grade 7','Grade 8','Grade 9',
]

const listFromResponse = (data) => data?.results || (Array.isArray(data) ? data : [])

const STATUS_LABELS = {
  active: 'Active',
  transferred: 'Transferred',
  graduated: 'Graduated',
  dropped: 'Dropped',
}

const STATUS_FILTERS = [
  { value: 'active', label: 'Active Students' },
  { value: 'transferred', label: 'Transferred' },
  { value: 'graduated', label: 'Graduated' },
  { value: 'dropped', label: 'Dropped' },
  { value: 'all', label: 'All Statuses' },
]

const classroomLabel = (classroom) => (
  `${classroom.name}${classroom.stream ? ` ${classroom.stream}` : ''} (${classroom.academic_year})`
)

export default function StudentsPage() {
  const navigate = useNavigate()
  const [students, setStudents] = useState([])
  const [classrooms, setClassrooms] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filters, setFilters] = useState({ classroom: '', gender: '', grade: '', status: 'active' })
  const [page, setPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)

  const PAGE_SIZE = 25

  useEffect(() => {
    studentsApi.getClassrooms().then(r => setClassrooms(listFromResponse(r.data)))
  }, [])

  useEffect(() => {
    fetchStudents()
  }, [search, filters, page])

  const fetchStudents = async () => {
    setLoading(true)
    try {
      const params = {
        page,
        search: search || undefined,
        classroom: filters.classroom || undefined,
        gender: filters.gender || undefined,
        status: filters.status !== 'all' ? filters.status : undefined,
        show_all: filters.status !== 'active' ? 'true' : undefined,
        'classroom__grade_level': filters.grade || undefined,
      }
      const { data } = await studentsApi.getStudents(params)
      const list = listFromResponse(data)
      setStudents(list)
      setTotalCount(data.count || list.length)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const totalPages = Math.ceil(totalCount / PAGE_SIZE)
  const filteredClassrooms = filters.grade
    ? classrooms.filter(classroom => classroom.grade_level === filters.grade)
    : classrooms

  return (
    <div>
      <PageHeader
        title="Students"
        description={`${totalCount} ${filters.status === 'active' ? 'active' : 'matching'} students`}
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => navigate('/students/import')} className="gap-2">
              <Upload size={16} /> Bulk Import
            </Button>
            <Button onClick={() => navigate('/students/new')} className="gap-2">
              <Plus size={16} /> Admit Student
            </Button>
          </div>
        }
      />

      {/* Search + Filters */}
      <Card className="p-4 mb-4">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search by name or admission number..."
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1) }}
              className="w-full pl-9 pr-4 py-2 rounded-lg border border-gray-200 text-sm outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-400"
            />
          </div>
          <div className="flex gap-2">
            <Select
              value={filters.status}
              onChange={e => { setFilters(f => ({ ...f, status: e.target.value, classroom: '' })); setPage(1) }}
              className="w-40"
            >
              {STATUS_FILTERS.map(option => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </Select>
            <Select
              value={filters.grade}
              onChange={e => { setFilters(f => ({ ...f, grade: e.target.value, classroom: '' })); setPage(1) }}
              className="w-36"
            >
              <option value="">All Grades</option>
              {GRADE_LEVELS.map(g => <option key={g} value={g}>{g}</option>)}
            </Select>
            <Select
              value={filters.classroom}
              onChange={e => { setFilters(f => ({ ...f, classroom: e.target.value })); setPage(1) }}
              className="w-40"
            >
              <option value="">All Classes</option>
              {filteredClassrooms.map(c => (
                <option key={c.id} value={c.id}>{classroomLabel(c)}</option>
              ))}
            </Select>
            <Select
              value={filters.gender}
              onChange={e => { setFilters(f => ({ ...f, gender: e.target.value })); setPage(1) }}
              className="w-32"
            >
              <option value="">All Genders</option>
              <option value="M">Male</option>
              <option value="F">Female</option>
            </Select>
          </div>
        </div>
      </Card>

      {/* Table */}
      <Card>
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Spinner className="h-7 w-7" />
          </div>
        ) : students.length === 0 ? (
          <EmptyState
            icon={Users}
            title="No students found"
            description={search ? 'Try a different search term.' : 'Admit your first student to get started.'}
            action={
              !search && (
                <Button onClick={() => navigate('/students/new')}>
                  <Plus size={14} /> Admit Student
                </Button>
              )
            }
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100">
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Student</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Adm No.</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Class</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Gender</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Guardian</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {students.map(student => (
                    <tr
                      key={student.id}
                      className="hover:bg-gray-50 cursor-pointer transition-colors"
                      onClick={() => navigate(`/students/${student.id}`)}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <Avatar name={student.full_name} photo={student.photo} />
                          <div>
                            <p className="font-medium text-gray-900">{student.full_name}</p>
                            <p className="text-xs text-gray-500">Age {student.age}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-gray-600 font-mono text-xs">{student.admission_number}</td>
                      <td className="px-4 py-3 text-gray-700">{student.classroom_name || '—'}</td>
                      <td className="px-4 py-3">
                        <Badge
                          label={student.gender === 'M' ? 'Male' : 'Female'}
                          variant={student.gender}
                        />
                      </td>
                      <td className="px-4 py-3 text-gray-600">{student.guardian_phone || '—'}</td>
                      <td className="px-4 py-3">
                        <Badge label={STATUS_LABELS[student.status] || student.status} variant={student.status} />
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          className="text-xs text-blue-600 hover:underline"
                          onClick={e => { e.stopPropagation(); navigate(`/students/${student.id}`) }}
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100">
                <p className="text-sm text-gray-500">
                  Page {page} of {totalPages} · {totalCount} students
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="secondary" size="sm"
                    onClick={() => setPage(p => p - 1)} disabled={page <= 1}
                  >Previous</Button>
                  <Button
                    variant="secondary" size="sm"
                    onClick={() => setPage(p => p + 1)} disabled={page >= totalPages}
                  >Next</Button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  )
}
