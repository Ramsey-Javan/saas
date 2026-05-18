import { useEffect, useMemo, useState } from 'react'
import { financeApi } from '@/api/finance'
import { studentsApi } from '@/api/students'
import { Card, Button, Input, Select, Spinner, Badge } from '@/components/ui'

const termOptions = [
  { value: 'term1', label: 'Term 1' },
  { value: 'term2', label: 'Term 2' },
  { value: 'term3', label: 'Term 3' },
  { value: 'annual', label: 'Annual' },
]

const formatMoney = (value) => `KES ${parseFloat(value || 0).toLocaleString()}`

export default function FeeStructuresPage() {
  const currentYear = new Date().getFullYear()
  const [classrooms, setClassrooms] = useState([])
  const [structures, setStructures] = useState([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [copying, setCopying] = useState(false)
  const [message, setMessage] = useState('')
  const [filters, setFilters] = useState({ academic_year: currentYear, term: '' })
  const [form, setForm] = useState({
    classroom: '',
    term: 'term1',
    academic_year: currentYear,
    base_amount: '',
    due_date: '',
    late_penalty_amount: 0,
    late_penalty_days: 0,
    is_active: true,
  })
  const [editing, setEditing] = useState(null)

  const classroomMap = useMemo(() => {
    const map = new Map()
    classrooms.forEach(c => map.set(String(c.id), c))
    return map
  }, [classrooms])

  const loadData = async () => {
    setLoading(true)
    try {
      const [classroomRes, structureRes] = await Promise.all([
        studentsApi.getClassrooms(),
        financeApi.getStructures({
          academic_year: filters.academic_year || undefined,
          term: filters.term || undefined,
        })
      ])
      setClassrooms(classroomRes.data.results || classroomRes.data || [])
      setStructures(structureRes.data.results || structureRes.data || [])
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
      classroom: '',
      term: 'term1',
      academic_year: currentYear,
      base_amount: '',
      due_date: '',
      late_penalty_amount: 0,
      late_penalty_days: 0,
      is_active: true,
    })
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setSubmitting(true)
    setMessage('')
    const payload = {
      classroom: form.classroom,
      term: form.term,
      academic_year: Number(form.academic_year),
      base_amount: Number(form.base_amount),
      due_date: form.due_date || null,
      late_penalty_amount: Number(form.late_penalty_amount || 0),
      late_penalty_days: Number(form.late_penalty_days || 0),
      is_active: true,
    }

    try {
      if (editing) {
        await financeApi.updateStructure(editing.id, payload)
        setMessage('Fee structure updated.')
      } else {
        await financeApi.createStructure(payload)
        setMessage('Fee structure created.')
      }
      await loadData()
      resetForm()
    } catch (err) {
      setMessage(err.response?.data?.error || 'Could not save fee structure.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleEdit = (structure) => {
    setEditing(structure)
    setForm({
      classroom: String(structure.classroom),
      term: structure.term,
      academic_year: structure.academic_year,
      base_amount: structure.base_amount,
      due_date: structure.due_date || '',
      late_penalty_amount: structure.late_penalty_amount || 0,
      late_penalty_days: structure.late_penalty_days || 0,
      is_active: structure.is_active,
    })
  }

  const handleDelete = async (structure) => {
    const confirmed = window.confirm('Delete this fee structure? This is only safe if no invoices have been generated.')
    if (!confirmed) return
    try {
      await financeApi.deleteStructure(structure.id)
      setMessage('Fee structure deleted.')
      await loadData()
    } catch (err) {
      setMessage(err.response?.data?.error || 'Unable to delete fee structure.')
    }
  }

  const handleCopyPrevious = async () => {
    const targetYear = Number(filters.academic_year)
    if (!targetYear) return
    setCopying(true)
    setMessage('')
    try {
      const sourceYear = targetYear - 1
      const [sourceRes, targetRes] = await Promise.all([
        financeApi.getStructures({ academic_year: sourceYear }),
        financeApi.getStructures({ academic_year: targetYear }),
      ])
      const source = sourceRes.data.results || sourceRes.data || []
      const target = targetRes.data.results || targetRes.data || []
      const existingKeys = new Set(target.map(s => `${s.classroom}-${s.term}`))
      const toCreate = source.filter(s => !existingKeys.has(`${s.classroom}-${s.term}`))
      const results = await Promise.allSettled(toCreate.map(s => (
        financeApi.createStructure({
          classroom: s.classroom,
          term: s.term,
          academic_year: targetYear,
          base_amount: s.base_amount,
          due_date: s.due_date,
          late_penalty_amount: s.late_penalty_amount,
          late_penalty_days: s.late_penalty_days,
          is_active: s.is_active,
        })
      )))
      const successCount = results.filter(r => r.status === 'fulfilled').length
      setMessage(`Copied ${successCount} fee structure(s) from ${sourceYear}.`)
      await loadData()
    } catch (err) {
      setMessage(err.response?.data?.error || 'Copy failed.')
    } finally {
      setCopying(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Fee Structures</h1>
          <p className="text-sm text-gray-500">Set fees per classroom, term, and academic year.</p>
        </div>
        <Button variant="secondary" onClick={handleCopyPrevious} loading={copying}>
          Copy Last Year
        </Button>
      </div>

      {message && (
        <div className="px-4 py-3 rounded-lg bg-blue-50 text-blue-700 text-sm">
          {message}
        </div>
      )}

      <Card className="p-5">
        <form className="grid grid-cols-1 md:grid-cols-3 gap-4" onSubmit={handleSubmit}>
          <Select
            label="Classroom"
            value={form.classroom}
            onChange={e => setForm(f => ({ ...f, classroom: e.target.value }))}
            required
          >
            <option value="">Select classroom</option>
            {classrooms.map(c => (
              <option key={c.id} value={c.id}>{c.name}{c.stream ? ` ${c.stream}` : ''}</option>
            ))}
          </Select>
          <Select
            label="Term"
            value={form.term}
            onChange={e => setForm(f => ({ ...f, term: e.target.value }))}
            required
          >
            {termOptions.map(term => (
              <option key={term.value} value={term.value}>{term.label}</option>
            ))}
          </Select>
          <Input
            label="Academic Year"
            type="number"
            value={form.academic_year}
            onChange={e => setForm(f => ({ ...f, academic_year: e.target.value }))}
            required
          />
          <Input
            label="Base Amount"
            type="number"
            value={form.base_amount}
            onChange={e => setForm(f => ({ ...f, base_amount: e.target.value }))}
            required
          />
          <Input
            label="Due Date"
            type="date"
            value={form.due_date}
            onChange={e => setForm(f => ({ ...f, due_date: e.target.value }))}
          />
          <Input
            label="Late Penalty Amount"
            type="number"
            value={form.late_penalty_amount}
            onChange={e => setForm(f => ({ ...f, late_penalty_amount: e.target.value }))}
          />
          <Input
            label="Late Penalty Days"
            type="number"
            value={form.late_penalty_days}
            onChange={e => setForm(f => ({ ...f, late_penalty_days: e.target.value }))}
          />
          <div className="flex gap-2 items-end">
            <Button type="submit" loading={submitting}>
              {editing ? 'Update Structure' : 'Create Structure'}
            </Button>
            {editing && (
              <Button type="button" variant="secondary" onClick={resetForm}>
                Cancel
              </Button>
            )}
          </div>
        </form>
      </Card>

      <Card className="p-5">
        <div className="flex flex-wrap gap-3 mb-4">
          <Input
            label="Academic Year"
            type="number"
            value={filters.academic_year}
            onChange={e => setFilters(f => ({ ...f, academic_year: e.target.value }))}
          />
          <Select
            label="Term"
            value={filters.term}
            onChange={e => setFilters(f => ({ ...f, term: e.target.value }))}
          >
            <option value="">All Terms</option>
            {termOptions.map(term => (
              <option key={term.value} value={term.value}>{term.label}</option>
            ))}
          </Select>
        </div>

        {loading ? (
          <div className="flex justify-center py-10"><Spinner /></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b text-gray-500">
                <tr>
                  <th className="text-left py-2">Classroom</th>
                  <th className="text-left py-2">Term</th>
                  <th className="text-left py-2">Year</th>
                  <th className="text-left py-2">Amount</th>
                  <th className="text-left py-2">Due Date</th>
                  <th className="text-left py-2">Penalty</th>
                  <th className="text-left py-2">Status</th>
                  <th className="text-right py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {structures.map(structure => {
                  const classroom = classroomMap.get(String(structure.classroom))
                  return (
                    <tr key={structure.id} className="border-b border-gray-50">
                      <td className="py-2">
                        {classroom ? `${classroom.name}${classroom.stream ? ` ${classroom.stream}` : ''}` : structure.classroom}
                      </td>
                      <td className="py-2 capitalize">{structure.term}</td>
                      <td className="py-2">{structure.academic_year}</td>
                      <td className="py-2 font-mono">{formatMoney(structure.base_amount)}</td>
                      <td className="py-2">{structure.due_date || '—'}</td>
                      <td className="py-2 text-xs text-gray-500">
                        KES {structure.late_penalty_amount} / {structure.late_penalty_days} days
                      </td>
                      <td className="py-2">
                        <Badge label={structure.is_active ? 'Active' : 'Inactive'} variant={structure.is_active ? 'active' : 'inactive'} />
                      </td>
                      <td className="py-2 text-right">
                        <div className="flex justify-end gap-2">
                          <Button size="sm" variant="secondary" onClick={() => handleEdit(structure)}>
                            Edit
                          </Button>
                          <Button size="sm" variant="danger" onClick={() => handleDelete(structure)}>
                            Delete
                          </Button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
