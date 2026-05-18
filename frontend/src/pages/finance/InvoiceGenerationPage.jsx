import { useEffect, useMemo, useState } from 'react'
import { financeApi } from '@/api/finance'
import { studentsApi } from '@/api/students'
import { Card, Button, Select, Input, Spinner } from '@/components/ui'

const termOptions = [
  { value: 'term1', label: 'Term 1' },
  { value: 'term2', label: 'Term 2' },
  { value: 'term3', label: 'Term 3' },
  { value: 'annual', label: 'Annual' },
]

const formatMoney = (value) => `KES ${parseFloat(value || 0).toLocaleString()}`

export default function InvoiceGenerationPage() {
  const currentYear = new Date().getFullYear()
  const [term, setTerm] = useState('term1')
  const [academicYear, setAcademicYear] = useState(currentYear)
  const [classrooms, setClassrooms] = useState([])
  const [structures, setStructures] = useState([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [progress, setProgress] = useState({ done: 0, total: 0 })
  const [message, setMessage] = useState('')

  const loadPreview = async () => {
    if (!academicYear || !term) return
    setLoading(true)
    try {
      const [classroomRes, structureRes] = await Promise.all([
        studentsApi.getClassrooms(),
        financeApi.getStructures({ academic_year: academicYear, term }),
      ])
      setClassrooms(classroomRes.data.results || classroomRes.data || [])
      setStructures(structureRes.data.results || structureRes.data || [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadPreview()
  }, [term, academicYear])

  const structureMap = useMemo(() => {
    const map = new Map()
    structures.forEach(structure => map.set(String(structure.classroom), structure))
    return map
  }, [structures])

  const rows = useMemo(() => (
    classrooms.map(classroom => {
      const structure = structureMap.get(String(classroom.id))
      return {
        classroom,
        structure,
        students: classroom.student_count || 0,
        amount: structure?.base_amount || 0,
      }
    })
  ), [classrooms, structureMap])

  const missingStructures = rows.filter(row => row.students > 0 && !row.structure)
  const eligibleRows = rows.filter(row => row.structure)

  const handleGenerate = async () => {
    if (!academicYear || !term) return
    setGenerating(true)
    setMessage('')
    setProgress({ done: 0, total: eligibleRows.length })

    let completed = 0
    let hadError = false
    for (const row of eligibleRows) {
      try {
        await financeApi.generateBulkInvoices({
          classroom: row.classroom.id,
          term,
          academic_year: academicYear,
        })
      } catch (err) {
        const errorMessage = err.response?.data?.error || 'Failed to generate invoices.'
        setMessage(`${row.classroom.name}${row.classroom.stream ? ` ${row.classroom.stream}` : ''}: ${errorMessage}`)
        hadError = true
      }
      completed += 1
      setProgress({ done: completed, total: eligibleRows.length })
    }

    setGenerating(false)
    if (!hadError) setMessage('Invoice generation complete.')
  }

  const progressPercent = progress.total ? Math.round((progress.done / progress.total) * 100) : 0

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Generate Invoices</h1>
          <p className="text-sm text-gray-500">Preview and generate fee invoices per classroom.</p>
        </div>
        <Button onClick={handleGenerate} loading={generating} disabled={eligibleRows.length === 0}>
          Generate Invoices
        </Button>
      </div>

      <Card className="p-5 grid grid-cols-1 md:grid-cols-3 gap-4">
        <Select label="Term" value={term} onChange={e => setTerm(e.target.value)}>
          {termOptions.map(option => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </Select>
        <Input
          label="Academic Year"
          type="number"
          value={academicYear}
          onChange={e => setAcademicYear(e.target.value)}
        />
      </Card>

      {message && (
        <div className="px-4 py-3 rounded-lg bg-blue-50 text-blue-700 text-sm">
          {message}
        </div>
      )}

      {generating && (
        <Card className="p-4">
          <div className="flex items-center justify-between text-sm">
            <span>Generating invoices...</span>
            <span>{progress.done}/{progress.total}</span>
          </div>
          <div className="w-full bg-gray-100 rounded-full h-2 mt-3">
            <div className="bg-blue-600 h-2 rounded-full" style={{ width: `${progressPercent}%` }} />
          </div>
        </Card>
      )}

      <Card className="p-5">
        <h3 className="font-semibold text-gray-900 mb-3">Preview</h3>
        {loading ? (
          <div className="flex justify-center py-10"><Spinner /></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b text-gray-500">
                <tr>
                  <th className="text-left py-2">Classroom</th>
                  <th className="text-left py-2">Students</th>
                  <th className="text-left py-2">Amount</th>
                  <th className="text-left py-2">Total</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(row => (
                  <tr key={row.classroom.id} className="border-b border-gray-50">
                    <td className="py-2">
                      {row.classroom.name}{row.classroom.stream ? ` ${row.classroom.stream}` : ''}
                    </td>
                    <td className="py-2">{row.students}</td>
                    <td className="py-2 font-mono">
                      {row.structure ? formatMoney(row.amount) : '—'}
                    </td>
                    <td className="py-2 font-mono">
                      {row.structure ? formatMoney(row.amount * row.students) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card className="p-5">
        <h3 className="font-semibold text-gray-900 mb-3">Needs Attention</h3>
        {missingStructures.length === 0 ? (
          <p className="text-sm text-gray-500">All classrooms have fee structures for this term and year.</p>
        ) : (
          <ul className="text-sm text-red-600 space-y-1">
            {missingStructures.map(row => (
              <li key={row.classroom.id}>
                {row.classroom.name}{row.classroom.stream ? ` ${row.classroom.stream}` : ''} has {row.students} students but no fee structure.
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
