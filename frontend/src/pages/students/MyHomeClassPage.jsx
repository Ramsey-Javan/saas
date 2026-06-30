import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Crown, Search, Users } from 'lucide-react'
import { studentsApi } from '@/api/students'
import { useAuthStore } from '@/store/authStore'
import { Avatar, Badge, Card, EmptyState, PageHeader, Spinner } from '@/components/ui'

const listFromResponse = (data) => data?.results || (Array.isArray(data) ? data : [])

const STATUS_LABELS = {
  active: 'Active',
  transferred: 'Transferred',
  graduated: 'Graduated',
  dropped: 'Dropped',
}

const classroomLabel = (classroom) => (
  `${classroom.name}${classroom.stream ? ` ${classroom.stream}` : ''} (${classroom.academic_year})`
)

export default function MyHomeClassPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const user = useAuthStore(state => state.user)

  const [classrooms, setClassrooms] = useState([])
  const [loadingClassrooms, setLoadingClassrooms] = useState(true)
  const selectedClassroomId = searchParams.get('classroom') || ''

  const [students, setStudents] = useState([])
  const [loadingStudents, setLoadingStudents] = useState(false)
  const [search, setSearch] = useState('')

  // Load every classroom this teacher is homeroom for. If there's only
  // one, auto-select it via the URL param so the roster renders
  // immediately without an extra click through a picker that only ever
  // has one option.
  useEffect(() => {
    if (!user?.id) return
    studentsApi.getClassrooms({ class_teacher: user.id }).then(r => {
      const list = listFromResponse(r.data)
      setClassrooms(list)
      if (list.length === 1 && !searchParams.get('classroom')) {
        setSearchParams({ classroom: String(list[0].id) }, { replace: true })
      }
    }).finally(() => setLoadingClassrooms(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id])

  useEffect(() => {
    if (!selectedClassroomId) return
    setLoadingStudents(true)
    studentsApi.getStudents({ classroom: selectedClassroomId, status: 'active' })
      .then(r => setStudents(listFromResponse(r.data)))
      .finally(() => setLoadingStudents(false))
  }, [selectedClassroomId])

  const selectedClassroom = useMemo(
    () => classrooms.find(c => String(c.id) === String(selectedClassroomId)),
    [classrooms, selectedClassroomId]
  )

  const filteredStudents = useMemo(() => {
    const q = search.toLowerCase()
    if (!q) return students
    return students.filter(s =>
      `${s.full_name} ${s.admission_number}`.toLowerCase().includes(q)
    )
  }, [students, search])

  if (loadingClassrooms) {
    return <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div>
  }

  if (classrooms.length === 0) {
    return (
      <Card className="p-8">
        <EmptyState
          icon={Crown}
          title="No home class assigned"
          description="You haven't been assigned as a class teacher (homeroom) for any classroom yet. Ask your school admin to assign you from the Staff page."
        />
      </Card>
    )
  }

  // Picker: shown when homeroom for more than one classroom and none
  // chosen yet (or to let them switch between their classes).
  if (classrooms.length > 1 && !selectedClassroomId) {
    return (
      <div>
        <PageHeader title="Home Class" description="Choose which class to view" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {classrooms.map(classroom => (
            <button
              key={classroom.id}
              type="button"
              onClick={() => setSearchParams({ classroom: String(classroom.id) })}
              className="rounded-lg border border-gray-200 bg-white p-5 text-left transition-all hover:border-[var(--brand-primary)] hover:shadow-sm"
            >
              <div className="flex items-center gap-2">
                <Crown size={16} className="text-amber-500" />
                <p className="font-semibold text-gray-900">{classroom.name}{classroom.stream ? ` ${classroom.stream}` : ''}</p>
              </div>
              <p className="mt-1 text-sm text-gray-500">{classroom.academic_year} · {classroom.student_count} students</p>
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        title={selectedClassroom ? `${selectedClassroom.name}${selectedClassroom.stream ? ` ${selectedClassroom.stream}` : ''}` : 'Home Class'}
        description={selectedClassroom ? `Your home class · ${classroomLabel(selectedClassroom)}` : undefined}
        action={classrooms.length > 1 && (
          <button
            type="button"
            onClick={() => setSearchParams({})}
            className="text-sm text-[var(--brand-primary)] hover:underline"
          >
            Switch class
          </button>
        )}
      />

      <Card className="p-4 mb-4">
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search by name or admission number..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 rounded-lg border border-gray-200 text-sm outline-none focus:ring-2 focus:ring-[var(--brand-primary-ring)] focus:border-[var(--brand-primary)]"
          />
        </div>
      </Card>

      <Card>
        {loadingStudents ? (
          <div className="flex items-center justify-center py-20">
            <Spinner className="h-7 w-7" />
          </div>
        ) : filteredStudents.length === 0 ? (
          <EmptyState
            icon={Users}
            title="No students found"
            description={search ? 'Try a different search term.' : 'No active students in this class yet.'}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Student</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Adm No.</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Gender</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Guardian</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {filteredStudents.map(student => (
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
                    <td className="px-4 py-3">
                      <Badge label={student.gender === 'M' ? 'Male' : 'Female'} variant={student.gender} />
                    </td>
                    <td className="px-4 py-3 text-gray-600">{student.guardian_phone || '—'}</td>
                    <td className="px-4 py-3">
                      <Badge label={STATUS_LABELS[student.status] || student.status} variant={student.status} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        className="text-xs text-[var(--brand-primary)] hover:underline"
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
        )}
      </Card>
    </div>
  )
}