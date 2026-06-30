import { useCallback, useEffect, useState } from 'react'
import { financeApi } from '@/api/finance'
import { Button, Input, Select, Spinner } from '@/components/ui'
import { X } from 'lucide-react'

const TERM_OPTIONS = [
  { value: 'term1', label: 'Term 1' },
  { value: 'term2', label: 'Term 2' },
  { value: 'term3', label: 'Term 3' },
  { value: 'annual', label: 'Annual' },
]

const currentYear = new Date().getFullYear()

export default function WaiverAssignmentModal({ isOpen, onClose, student, fee, onSuccess }) {
  const [policies, setPolicies] = useState([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const buildDefaultForm = useCallback(() => ({
    policy: '',
    valid_from_term: fee?.fee_term || 'term1',
    valid_from_year: fee?.fee_academic_year || currentYear,
    valid_until_term: '',
    valid_until_year: '',
    notes: '',
    supporting_document: null,
  }), [fee])

  const [form, setForm] = useState(buildDefaultForm())

  useEffect(() => {
    if (!isOpen) {
      setError('')
      setSaving(false)
      return
    }

    setLoading(true)
    financeApi.getWaiverPolicies({ is_active: true })
      .then((res) => setPolicies(res.data.results || res.data || []))
      .catch(() => setError('Unable to load waiver policies.'))
      .finally(() => setLoading(false))
  }, [isOpen])

  useEffect(() => {
    if (!isOpen) return
    setForm(buildDefaultForm())
  }, [isOpen, fee, buildDefaultForm])

  if (!isOpen) return null

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (!student?.id || !form.policy) {
      setError('Select a policy before saving.')
      return
    }

    const payload = new FormData()
    payload.append('student', student.id)
    payload.append('policy', form.policy)
    payload.append('is_active', 'true')
    payload.append('valid_from_term', form.valid_from_term)
    payload.append('valid_from_year', String(form.valid_from_year))
    if (form.valid_until_term) payload.append('valid_until_term', form.valid_until_term)
    if (form.valid_until_year) payload.append('valid_until_year', String(form.valid_until_year))
    if (form.notes) payload.append('notes', form.notes)
    if (form.supporting_document) payload.append('supporting_document', form.supporting_document)

    setSaving(true)
    setError('')
    try {
      await financeApi.createWaiver(payload)
      onSuccess?.()
      onClose()
    } catch (err) {
      const response = err.response?.data
      setError(response?.detail || response?.error || 'Failed to assign waiver.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Assign Waiver</h3>
            <p className="text-sm text-gray-500">{student?.full_name || 'Selected student'}</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-700">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 px-5 py-4">
          {error && (
            <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-10">
              <Spinner className="h-6 w-6" />
            </div>
          ) : (
            <>
              <Select
                label="Waiver Policy"
                value={form.policy}
                onChange={(e) => setForm((current) => ({ ...current, policy: e.target.value }))}
                required
              >
                <option value="">Select a policy</option>
                {policies.map((policy) => (
                  <option key={policy.id} value={policy.id}>
                    {policy.description || policy.category}
                  </option>
                ))}
              </Select>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <Select
                  label="Start Term"
                  value={form.valid_from_term}
                  onChange={(e) => setForm((current) => ({ ...current, valid_from_term: e.target.value }))}
                >
                  {TERM_OPTIONS.map((term) => (
                    <option key={term.value} value={term.value}>{term.label}</option>
                  ))}
                </Select>
                <Input
                  label="Start Year"
                  type="number"
                  value={form.valid_from_year}
                  onChange={(e) => setForm((current) => ({ ...current, valid_from_year: e.target.value }))}
                />
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <Select
                  label="End Term"
                  value={form.valid_until_term}
                  onChange={(e) => setForm((current) => ({ ...current, valid_until_term: e.target.value }))}
                >
                  <option value="">Permanent</option>
                  {TERM_OPTIONS.map((term) => (
                    <option key={term.value} value={term.value}>{term.label}</option>
                  ))}
                </Select>
                <Input
                  label="End Year"
                  type="number"
                  value={form.valid_until_year}
                  onChange={(e) => setForm((current) => ({ ...current, valid_until_year: e.target.value }))}
                  placeholder="Optional"
                />
              </div>

              <Input
                label="Supporting Document"
                type="file"
                onChange={(e) => setForm((current) => ({ ...current, supporting_document: e.target.files?.[0] || null }))}
              />

              <div>
                <label className="mb-1.5 block text-sm font-medium text-gray-700">Notes</label>
                <textarea
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-[var(--brand-primary)] focus:ring-2 focus:ring-[var(--brand-primary-ring)]"
                  rows={3}
                  value={form.notes}
                  onChange={(e) => setForm((current) => ({ ...current, notes: e.target.value }))}
                  placeholder="Optional waiver remarks"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <Button type="button" variant="secondary" onClick={onClose}>
                  Cancel
                </Button>
                <Button type="submit" loading={saving}>
                  Assign Waiver
                </Button>
              </div>
            </>
          )}
        </form>
      </div>
    </div>
  )
}
