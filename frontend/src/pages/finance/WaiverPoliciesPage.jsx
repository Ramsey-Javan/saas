import { useEffect, useRef, useState } from 'react'
import { financeApi } from '@/api/finance'
import { Card, Button, Input, Select, Spinner, Badge } from '@/components/ui'

const CATEGORY_CHOICES = [
  { value: 'full_waiver', label: 'Full Waiver' },
  { value: 'staff_child', label: 'Staff Child' },
  { value: 'bursary', label: 'Bursary' },
  { value: 'sibling', label: 'Sibling Discount' },
  { value: 'sponsor', label: 'Sponsor' },
  { value: 'partial', label: 'Partial Waiver' },
  { value: 'orphan', label: 'Orphan' },
]

const DISCOUNT_TYPE_CHOICES = [
  { value: 'percentage', label: 'Percentage (%)' },
  { value: 'fixed', label: 'Fixed Amount (KES)' },
]

const formatMoney = (value) => `KES ${parseFloat(value || 0).toLocaleString()}`

export default function WaiverPoliciesPage() {
  const [policies, setPolicies] = useState([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState('')
  const [filters, setFilters] = useState({ is_active: 'true' })
  const [form, setForm] = useState({
    category: '',
    discount_type: 'percentage',
    discount_value: '',
    is_active: true,
    description: '',
  })
  const [editing, setEditing] = useState(null)
  const formRef = useRef(null)

  const categoryMap = new Map(CATEGORY_CHOICES.map(c => [c.value, c.label]))
  const loadData = async () => {
    setLoading(true)
    try {
      const params = {}
      if (filters.is_active === 'true') params.is_active = true
      if (filters.is_active === 'false') params.is_active = false
      
      const res = await financeApi.getWaiverPolicies(params)
      setPolicies(res.data.results || res.data || [])
    } catch (err) {
      setMessage('Failed to load waiver policies.')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [filters])

  const resetForm = () => {
    setEditing(null)
    setForm({
      category: '',
      discount_type: 'percentage',
      discount_value: '',
      is_active: true,
      description: '',
    })
  }

  const handleNewPolicy = () => {
    resetForm()
    formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setMessage('')

    if (!form.category || form.discount_value === '') {
      setMessage('Please fill in all required fields.')
      setSubmitting(false)
      return
    }

    if (form.discount_type === 'percentage' && Number(form.discount_value) > 100) {
      setMessage('Percentage discount cannot exceed 100%.')
      setSubmitting(false)
      return
    }

    const payload = {
      category: form.category,
      discount_type: form.discount_type,
      discount_value: Number(form.discount_value),
      is_active: form.is_active,
      description: form.description,
    }

    try {
      if (editing) {
        await financeApi.updateWaiverPolicy(editing.id, payload)
        setMessage('Waiver policy updated.')
      } else {
        await financeApi.createWaiverPolicy(payload)
        setMessage('Waiver policy created.')
      }
      await loadData()
      resetForm()
    } catch (err) {
      setMessage(err.response?.data?.error || 'Could not save waiver policy.')
      console.error(err)
    } finally {
      setSubmitting(false)
    }
  }

  const handleEdit = (policy) => {
    setEditing(policy)
    setForm({
      category: policy.category,
      discount_type: policy.discount_type,
      discount_value: policy.discount_value,
      is_active: policy.is_active,
      description: policy.description,
    })
  }

  const handleDelete = async (policy) => {
    if (!window.confirm('Delete this waiver policy? This cannot be undone.')) return
    try {
      await financeApi.deleteWaiverPolicy(policy.id)
      setMessage('Waiver policy deleted.')
      await loadData()
    } catch (err) {
      setMessage(err.response?.data?.error || 'Unable to delete waiver policy.')
      console.error(err)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Waiver Policies</h1>
          <p className="text-gray-600">Manage student fee waiver categories and discounts</p>
        </div>
        <Button onClick={handleNewPolicy}>New Policy</Button>
      </div>

      {/* Filters */}
      <Card>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Select
            label="Status"
            value={filters.is_active}
            onChange={(e) => setFilters({ ...filters, is_active: e.target.value })}
          >
            <option value="all">All Policies</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </Select>
        </div>
      </Card>

      {/* Form */}
      <div ref={formRef}>
        <Card>
          <h2 className="text-xl font-semibold mb-4">
            {editing ? 'Edit Waiver Policy' : 'New Waiver Policy'}
          </h2>
          <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Select
              label="Category *"
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
              required
            >
              <option value="">Select category</option>
              {CATEGORY_CHOICES.map((choice) => (
                <option key={choice.value} value={choice.value}>{choice.label}</option>
              ))}
            </Select>
            <Select
              label="Discount Type *"
              value={form.discount_type}
              onChange={(e) => setForm({
                ...form,
                discount_type: e.target.value,
                discount_value: form.discount_value && e.target.value === 'percentage'
                  ? String(Math.min(Number(form.discount_value), 100))
                  : form.discount_value,
              })}
              required
            >
              {DISCOUNT_TYPE_CHOICES.map((choice) => (
                <option key={choice.value} value={choice.value}>{choice.label}</option>
              ))}
            </Select>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input
              label={`Discount Value ${form.discount_type === 'percentage' ? '(%)' : '(KES)'} *`}
              type="number"
              step={form.discount_type === 'percentage' ? '0.01' : '0.01'}
              min="0"
              max={form.discount_type === 'percentage' ? '100' : undefined}
              value={form.discount_value}
              onChange={(e) => {
                const nextValue = e.target.value
                if (form.discount_type === 'percentage' && Number(nextValue) > 100) {
                  setForm({ ...form, discount_value: '100' })
                  return
                }
                setForm({ ...form, discount_value: nextValue })
              }}
              required
            />
            <div className="flex items-end">
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                  className="rounded"
                />
                <span>Active</span>
              </label>
            </div>
          </div>

          <Input
            label="Description"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder="e.g., For children of school staff"
          />

          {message && (
            <div className={`p-3 rounded ${message.includes('error') || message.includes('Unable') ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
              {message}
            </div>
          )}

            <div className="flex gap-2">
              <Button type="submit" disabled={submitting}>
                {submitting ? 'Saving...' : editing ? 'Update Policy' : 'Create Policy'}
              </Button>
              {editing && (
                <Button type="button" variant="secondary" onClick={resetForm}>
                  Cancel
                </Button>
              )}
            </div>
          </form>
        </Card>
      </div>

      {/* List */}
      <Card>
        <h2 className="text-xl font-semibold mb-4">Waiver Policies</h2>
        {loading ? (
          <div className="flex justify-center py-8">
            <Spinner />
          </div>
        ) : policies.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            No waiver policies found.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Category</th>
                  <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Discount</th>
                  <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Description</th>
                  <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Status</th>
                  <th className="px-6 py-3 text-right text-sm font-semibold text-gray-900">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {policies.map((policy) => (
                  <tr key={policy.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm text-gray-900">
                      {categoryMap.get(policy.category)}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">
                      {policy.discount_type === 'percentage'
                        ? `${policy.discount_value}%`
                        : formatMoney(policy.discount_value)
                      }
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {policy.description || '-'}
                    </td>
                    <td className="px-6 py-4 text-sm">
                      <Badge
                        label={policy.is_active ? 'Active' : 'Inactive'}
                        variant={policy.is_active ? 'active' : 'inactive'}
                      />
                    </td>
                    <td className="px-6 py-4 text-right text-sm space-x-2">
                      <button
                        onClick={() => handleEdit(policy)}
                        className="text-blue-600 hover:text-blue-900 font-medium"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(policy)}
                        className="text-red-600 hover:text-red-900 font-medium"
                      >
                        Delete
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
