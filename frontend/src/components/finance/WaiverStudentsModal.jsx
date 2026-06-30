import { useCallback, useEffect, useState } from 'react'
import { financeApi } from '@/api/finance'
import { Button, Spinner, Badge } from '@/components/ui'
import { X, Trash2, Edit2, FileText } from 'lucide-react'

const TERM_MAP = {
  'term1': 'Term 1',
  'term2': 'Term 2',
  'term3': 'Term 3',
  'annual': 'Annual',
}

export default function WaiverStudentsModal({ isOpen, onClose, policy, onUpdate }) {
  const [students, setStudents] = useState([])
  const [loading, setLoading] = useState(false)
  const [deleting, setDeleting] = useState(null)
  const [error, setError] = useState('')

  const loadStudents = useCallback(async () => {
    if (!policy?.id) return
    
    setLoading(true)
    setError('')
    try {
      const res = await financeApi.getWaiversByPolicy(policy.id)
      setStudents(res.data.results || res.data || [])
    } catch (err) {
      setError('Failed to load students.')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [policy?.id])

  useEffect(() => {
    if (isOpen && policy?.id) {
      loadStudents()
    }
  }, [isOpen, policy?.id, loadStudents])

  const handleRemoveWaiver = async (waiverId) => {
    if (!window.confirm('Remove this waiver from the student?')) return

    setDeleting(waiverId)
    setError('')
    try {
      await financeApi.deleteWaiver(waiverId)
      setStudents(students.filter(s => s.id !== waiverId))
      onUpdate?.()
    } catch (err) {
      setError('Failed to remove waiver.')
      console.error(err)
    } finally {
      setDeleting(null)
    }
  }

  const handleDeactivateWaiver = async (waiverId) => {
    if (!window.confirm('Deactivate this waiver for the student?')) return

    setDeleting(waiverId)
    setError('')
    try {
      await financeApi.updateWaiver(waiverId, { is_active: false })
      setStudents(students.filter(s => s.id !== waiverId))
      onUpdate?.()
    } catch (err) {
      setError('Failed to deactivate waiver.')
      console.error(err)
    } finally {
      setDeleting(null)
    }
  }

  if (!isOpen) return null

  const formatMoney = (value) => `KES ${parseFloat(value || 0).toLocaleString()}`

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 overflow-y-auto">
      <div className="w-full max-w-3xl rounded-2xl bg-white shadow-2xl my-8">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-100 px-6 py-5">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">
              {policy?.category?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
            </h2>
            <p className="text-sm text-gray-500 mt-1">
              Discount: {policy?.discount_type === 'percentage'
                ? `${policy?.discount_value}%`
                : formatMoney(policy?.discount_value)
              }
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {error && (
            <div className="mb-4 px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex justify-center py-12">
              <Spinner />
            </div>
          ) : students.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <p className="mb-4">No students assigned to this waiver yet.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {students.map((waiver) => (
                <div
                  key={waiver.id}
                  className="p-4 border border-gray-200 rounded-lg hover:shadow-sm transition-shadow"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="font-semibold text-gray-900 truncate">
                          {waiver.student_name}
                        </h3>
                        <Badge variant="success" className="text-xs">
                          {waiver.admission_number}
                        </Badge>
                      </div>

                      <div className="grid grid-cols-2 gap-3 text-sm text-gray-600 mt-2">
                        <div>
                          <p className="text-xs text-gray-500">Class</p>
                          <p className="font-medium">{waiver.classroom_name}</p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-500">Valid From</p>
                          <p className="font-medium">
                            {TERM_MAP[waiver.valid_from_term]} {waiver.valid_from_year}
                          </p>
                        </div>
                      </div>

                      {waiver.valid_until_year && (
                        <div className="mt-2 text-sm text-gray-600">
                          <p className="text-xs text-gray-500">Valid Until</p>
                          <p className="font-medium">
                            {TERM_MAP[waiver.valid_until_term]} {waiver.valid_until_year}
                          </p>
                        </div>
                      )}

                      {waiver.supporting_document && (
                        <div className="mt-3">
                          <a
                            href={waiver.supporting_document}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-2 text-xs text-[var(--brand-primary)] hover:opacity-80"
                          >
                            <FileText size={14} />
                            View Document
                          </a>
                        </div>
                      )}

                      {waiver.notes && (
                        <p className="text-sm text-gray-600 mt-2 italic">
                          Note: {waiver.notes}
                        </p>
                      )}
                    </div>

                    <div className="flex items-center gap-2 flex-shrink-0">
                      <button
                        onClick={() => handleDeactivateWaiver(waiver.id)}
                        disabled={deleting === waiver.id}
                        className="p-2 text-gray-400 hover:text-orange-600 hover:bg-orange-50 rounded-lg transition-colors disabled:opacity-50"
                        title="Deactivate waiver"
                      >
                        <Edit2 size={16} />
                      </button>
                      <button
                        onClick={() => handleRemoveWaiver(waiver.id)}
                        disabled={deleting === waiver.id}
                        className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
                        title="Remove student"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-gray-100 px-6 py-4 flex justify-end">
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  )
}
