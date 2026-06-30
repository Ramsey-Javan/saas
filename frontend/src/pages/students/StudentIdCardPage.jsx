import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Printer, CreditCard } from 'lucide-react'
import { studentsApi } from '@/api/students'
import { Avatar, Badge, Button, Card, Spinner } from '@/components/ui'

const STATUS_LABELS = {
  active: 'Active',
  transferred: 'Transferred',
  graduated: 'Graduated',
  dropped: 'Dropped',
}

const classroomLabel = (classroom) => (
  classroom ? `${classroom.name}${classroom.stream ? ` ${classroom.stream}` : ''}` : 'Unassigned'
)

export default function StudentIdCardPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [student, setStudent] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    studentsApi.getStudent(id)
      .then(response => setStudent(response.data))
      .catch(() => navigate('/students'))
      .finally(() => setLoading(false))
  }, [id, navigate])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-7 w-7" />
      </div>
    )
  }

  if (!student) return null

  const classroom = student.classroom_data
  const className = classroomLabel(classroom)

  return (
    <div className="max-w-3xl">
      <style>{`
        @media print {
          body * { visibility: hidden; }
          #student-id-print, #student-id-print * { visibility: visible; }
          #student-id-print {
            position: absolute;
            left: 0;
            top: 0;
            width: 100%;
          }
          .no-print { display: none !important; }
        }
      `}</style>

      <div className="no-print mb-5 flex items-center justify-between gap-3">
        <button
          onClick={() => navigate(`/students/${id}`)}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 transition-colors"
        >
          <ArrowLeft size={15} /> Back to Student
        </button>
        <Button onClick={() => window.print()} className="gap-2">
          <Printer size={16} /> Print ID Card
        </Button>
      </div>

      <Card className="p-6 no-print mb-5">
        <h1 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <CreditCard size={18} className="text-[var(--brand-primary)]" /> Student ID Card
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Print this card or save it as PDF from the print dialog.
        </p>
      </Card>

      <div id="student-id-print" className="flex justify-center">
        <div className="w-[340px] rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
          <div className="bg-[var(--brand-primary)] px-5 py-4 text-white">
            <p className="text-xs uppercase tracking-wide opacity-80">Student Identification</p>
            <h2 className="text-lg font-bold">School ID Card</h2>
          </div>

          <div className="p-5">
            <div className="flex items-center gap-4">
              <Avatar name={student.full_name} photo={student.photo} size="lg" />
              <div className="min-w-0">
                <h3 className="text-base font-bold text-gray-900 leading-tight">{student.full_name}</h3>
                <p className="text-xs text-gray-500 font-mono mt-1">{student.admission_number}</p>
              </div>
            </div>

            <div className="mt-5 space-y-2 text-sm">
              <div className="flex items-center justify-between border-b border-gray-100 pb-2">
                <span className="text-gray-500">Class</span>
                <span className="font-medium text-gray-900">{className}</span>
              </div>
              <div className="flex items-center justify-between border-b border-gray-100 pb-2">
                <span className="text-gray-500">Academic Year</span>
                <span className="font-medium text-gray-900">{classroom?.academic_year || '—'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-500">Status</span>
                <Badge label={STATUS_LABELS[student.status] || student.status} variant={student.status} />
              </div>
            </div>

            <div className="mt-5 rounded-lg bg-gray-50 px-3 py-2">
              <p className="text-[11px] text-gray-500">
                If found, please return this card to the school office.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
