import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Edit2, Phone, BookOpen, User, CheckCircle, CreditCard } from 'lucide-react'
import { studentsApi } from '@/api/students'
import { useAuthStore } from '@/store/authStore'
import { Card, Badge, Avatar, Button, Spinner, Select } from '@/components/ui'

const listFromResponse = (data) => data?.results || (Array.isArray(data) ? data : [])

const STATUS_LABELS = {
  active: 'Active',
  transferred: 'Transferred',
  graduated: 'Graduated',
  dropped: 'Dropped',
}

const STATUS_OPTIONS = [
  { value: 'active', label: 'Active' },
  { value: 'transferred', label: 'Transferred' },
  { value: 'graduated', label: 'Graduated' },
  { value: 'dropped', label: 'Dropped' },
]

const classroomLabel = (classroom) => (
  `${classroom.name}${classroom.stream ? ` ${classroom.stream}` : ''}`
)

function InfoRow({ label, value }) {
  return (
    <div className="flex justify-between py-2.5 border-b border-gray-50 last:border-0">
      <span className="text-sm text-gray-500">{label}</span>
      <span className="text-sm font-medium text-gray-900 text-right max-w-[60%]">
        {value || <span className="text-gray-300">—</span>}
      </span>
    </div>
  )
}

export default function StudentDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const canGenerateIdCard = useAuthStore(state => state.hasRole('admin', 'bursar'))
  const [student, setStudent] = useState(null)
  const [loading, setLoading] = useState(true)
  const [transferLoading, setTransferLoading] = useState(false)
  const [statusLoading, setStatusLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedClassroom, setSelectedClassroom] = useState('')
  const [selectedStatus, setSelectedStatus] = useState('active')
  const [classrooms, setClassrooms] = useState([])

  useEffect(() => {
    studentsApi.getStudent(id)
      .then(r => {
        setStudent(r.data)
        setSelectedStatus(r.data.status)
      })
      .catch(() => navigate('/students'))
      .finally(() => setLoading(false))
  }, [id, navigate])

  useEffect(() => {
    studentsApi.getClassrooms().then(r => setClassrooms(listFromResponse(r.data)))
  }, [])

  const handleTransfer = async () => {
    if (!selectedClassroom) return

    setTransferLoading(true)
    setError('')
    try {
      await studentsApi.transferStudent(id, selectedClassroom)
      navigate(0)
    } catch (err) {
      setError(`Transfer failed: ${err.response?.data?.detail || 'Try again'}`)
    } finally {
      setTransferLoading(false)
    }
  }

  const handleStatusChange = async () => {
    if (selectedStatus === student.status) return

    const statusLabel = STATUS_LABELS[selectedStatus] || selectedStatus
    const confirmed = window.confirm(
      `Change ${student.full_name}'s status to ${statusLabel}? Archived statuses are hidden from the active list.`
    )
    if (!confirmed) return

    setStatusLoading(true)
    setError('')
    try {
      const { data } = await studentsApi.updateStudentStatus(id, selectedStatus)
      setStudent(data.student)
    } catch (err) {
      setError(`Status update failed: ${err.response?.data?.detail || 'Try again'}`)
    } finally {
      setStatusLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-7 w-7" />
      </div>
    )
  }

  if (!student) return null

  const guardian = student.primary_guardian_data
  const classroom = student.classroom_data

  return (
    <div className="max-w-4xl">
      <button
        onClick={() => navigate('/students')}
        className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 mb-4 transition-colors"
      >
        <ArrowLeft size={15} /> Back to Students
      </button>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div className="flex items-center gap-4">
          <Avatar name={student.full_name} photo={student.photo} size="lg" />
          <div>
            <h1 className="text-xl font-bold text-gray-900">{student.full_name}</h1>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-sm text-gray-500 font-mono">{student.admission_number}</span>
              <span className="text-gray-300">·</span>
              <Badge label={STATUS_LABELS[student.status] || student.status} variant={student.status} />
              <Badge label={student.gender === 'M' ? 'Male' : 'Female'} variant={student.gender} />
            </div>
          </div>
        </div>
        <Button
          variant="secondary"
          onClick={() => navigate(`/students/${id}/edit`)}
          className="gap-1.5"
        >
          <Edit2 size={14} /> Edit
        </Button>
      </div>

      {error && (
        <div className="mb-5 px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

        {/* Academic info */}
        <div className="lg:col-span-2 space-y-5">
          <Card className="p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <BookOpen size={15} className="text-blue-600" /> Academic Details
            </h2>
            <InfoRow label="Class" value={classroom ? `${classroomLabel(classroom)} (${classroom.academic_year})` : null} />
            <InfoRow label="Grade Level" value={classroom?.grade_level} />
            <InfoRow label="Class Teacher" value={classroom?.class_teacher_name} />
            <InfoRow label="Admission Date" value={student.admission_date} />
            <InfoRow label="NEMIS UPI No." value={student.nemis_no} />
          </Card>

          <Card className="p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <User size={15} className="text-blue-600" /> Personal Details
            </h2>
            <InfoRow label="Date of Birth" value={student.date_of_birth} />
            <InfoRow label="Age" value={student.age ? `${student.age} years` : null} />
            <InfoRow label="Gender" value={student.gender === 'M' ? 'Male' : 'Female'} />
            <InfoRow label="Birth Certificate No." value={student.birth_certificate_no} />
            <InfoRow label="Blood Group" value={student.blood_group} />
            {student.medical_notes && (
              <div className="pt-2.5">
                <p className="text-sm text-gray-500 mb-1">Medical Notes</p>
                <p className="text-sm text-gray-700 bg-yellow-50 rounded-lg p-3 border border-yellow-100">
                  {student.medical_notes}
                </p>
              </div>
            )}
          </Card>
        </div>

        {/* Guardian */}
        <div className="space-y-5">
          <Card className="p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Phone size={15} className="text-blue-600" /> Primary Guardian
            </h2>
            {guardian ? (
              <>
                <div className="flex items-center gap-3 mb-3">
                  <Avatar name={`${guardian.first_name} ${guardian.last_name}`} />
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {guardian.first_name} {guardian.last_name}
                    </p>
                    <p className="text-xs text-gray-500 capitalize">{guardian.relationship}</p>
                  </div>
                </div>
                <InfoRow label="Phone" value={guardian.phone} />
                {guardian.alt_phone && <InfoRow label="Alt Phone" value={guardian.alt_phone} />}
                {guardian.email && <InfoRow label="Email" value={guardian.email} />}
                {guardian.national_id && <InfoRow label="ID No." value={guardian.national_id} />}
                {guardian.occupation && <InfoRow label="Occupation" value={guardian.occupation} />}
              </>
            ) : (
              <p className="text-sm text-gray-400">No guardian linked.</p>
            )}
          </Card>

          {/* Quick actions */}
          <Card className="p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">Quick Actions</h2>
            <div className="space-y-2">
              <Select
                value={selectedClassroom}
                onChange={e => setSelectedClassroom(e.target.value)}
              >
                <option value="">Select new class...</option>
                {classrooms.map(c => (
                  <option key={c.id} value={c.id}>{classroomLabel(c)} ({c.academic_year})</option>
                ))}
              </Select>
              <Button
                variant="secondary"
                size="sm"
                className="w-full justify-start gap-2"
                onClick={handleTransfer}
                disabled={!selectedClassroom || transferLoading}
              >
                {transferLoading ? <Spinner className="h-4 w-4" /> : 'Transfer Class'}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                className="w-full justify-start gap-2"
                onClick={() => navigate(`/finance?student=${id}`)}
              >
                View Fee Balance
              </Button>
              <Button
                variant="secondary"
                size="sm"
                className="w-full justify-start gap-2"
                onClick={() => navigate(`/academics/attendance?student=${id}`)}
              >
                Attendance History
              </Button>
              {canGenerateIdCard && (
                <Button
                  variant="secondary"
                  size="sm"
                  className="w-full justify-start gap-2"
                  onClick={() => navigate(`/students/${id}/id-card`)}
                >
                  <CreditCard size={14} /> Generate ID Card
                </Button>
              )}
              <Select
                value={selectedStatus}
                onChange={e => setSelectedStatus(e.target.value)}
                disabled={statusLoading}
              >
                {STATUS_OPTIONS.map(option => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </Select>
              <Button
                variant={selectedStatus === 'active' ? 'secondary' : 'danger'}
                size="sm"
                className="w-full justify-start gap-2"
                onClick={handleStatusChange}
                disabled={selectedStatus === student.status || statusLoading}
              >
                {statusLoading ? <Spinner className="h-4 w-4" /> : <CheckCircle size={14} />}
                Apply Status
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
