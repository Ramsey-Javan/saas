import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, CheckCircle } from 'lucide-react'
import { studentsApi } from '@/api/students'
import { financeApi } from '@/api/finance'
import { Card, Badge, Avatar, Spinner, Button } from '@/components/ui'

const CATEGORY_CHOICES = [
  { value: 'full_waiver', label: 'Full Waiver' },
  { value: 'staff_child', label: 'Staff Child' },
  { value: 'bursary', label: 'Bursary' },
  { value: 'sibling', label: 'Sibling Discount' },
  { value: 'sponsor', label: 'Sponsor' },
  { value: 'partial', label: 'Partial Waiver' },
  { value: 'orphan', label: 'Orphan' },
]

const categoryMap = new Map(CATEGORY_CHOICES.map(c => [c.value, c.label]))

export default function StudentWaiverPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [student, setStudent] = useState(null)
  const [waivers, setWaivers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [infoMessage, setInfoMessage] = useState('')

  const handleCheckActive = () => {
    const activeCount = waivers.filter(w => w.is_active).length
    setInfoMessage(
      activeCount > 0 ? `Student has ${activeCount} active waiver(s).` : 'No active waivers for this student.'
    )
  }

  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      try {
        const [studentRes, waiversRes] = await Promise.all([
          studentsApi.getStudent(id),
          financeApi.getWaivers({ student__id: id }),
        ])
        setStudent(studentRes.data)
        setWaivers(waiversRes.data.results || waiversRes.data || [])
      } catch (err) {
        setError('Failed to load student or waivers data.')
        console.error(err)
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [id])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-7 w-7" />
      </div>
    )
  }

  if (!student) return null

  return (
    <div className="max-w-4xl">
      <button
        onClick={() => navigate(`/students/${id}`)}
        className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 mb-4 transition-colors"
      >
        <ArrowLeft size={15} /> Back to Student
      </button>

      {/* Header */}
      <div className="flex items-center justify-between gap-4 mb-6">
        <div className="flex items-center gap-4">
          <Avatar name={student.full_name} photo={student.photo} size="lg" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{student.full_name}</h1>
            <p className="text-sm text-gray-500">{student.admission_number}</p>
          </div>
        </div>
        <div>
          <Button variant="secondary" onClick={handleCheckActive}>
            Check Active Waiver
          </Button>
        </div>
      </div>

      {infoMessage && (
        <div className="mb-5 px-4 py-3 rounded-lg bg-green-50 border border-green-200 text-green-700 text-sm">
          {infoMessage}
        </div>
      )}

      {error && (
        <div className="mb-5 px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Waivers List */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <CheckCircle size={20} className="text-emerald-600" />
          Student Waivers
        </h2>

        {waivers.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            No waivers assigned to this student.
          </div>
        ) : (
          <div className="space-y-3">
            {waivers.map((waiver) => (
              <div
                key={waiver.id}
                className="rounded-lg border border-gray-200 p-4 hover:border-gray-300 hover:shadow-sm transition-all"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="font-semibold text-gray-900">
                        {categoryMap.get(waiver.policy_category) || waiver.policy_category}
                      </span>
                      <Badge
                        label={waiver.is_active ? 'Active' : 'Inactive'}
                        variant={waiver.is_active ? 'active' : 'inactive'}
                      />
                    </div>
                    <p className="text-sm text-gray-600 mb-1">
                      <span className="font-medium">Discount:</span> {waiver.policy_discount}
                    </p>
                    <p className="text-sm text-gray-600 mb-1">
                      <span className="font-medium">Valid Until:</span>{' '}
                      {waiver.valid_until_year
                        ? `${waiver.valid_until_term} ${waiver.valid_until_year}`
                        : 'Permanent'}
                    </p>
                    {waiver.approved_by_name && (
                      <p className="text-sm text-gray-600">
                        <span className="font-medium">Approved By:</span> {waiver.approved_by_name}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
