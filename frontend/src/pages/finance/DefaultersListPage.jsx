import { useEffect, useMemo, useState } from 'react'
import { financeApi } from '@/api/finance'
import { Card, Button, Spinner } from '@/components/ui'
import { Download, MessageSquare } from 'lucide-react'

const formatMoney = (value) => `KES ${parseFloat(value || 0).toLocaleString()}`

const daysOverdue = (dueDate) => {
  if (!dueDate) return 0
  const due = new Date(dueDate)
  const now = new Date()
  const diff = now.setHours(0, 0, 0, 0) - due.setHours(0, 0, 0, 0)
  return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)))
}

export default function DefaultersListPage() {
  const [defaulters, setDefaulters] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    financeApi.getDefaulters().then(res => {
      setDefaulters(res.data.results || res.data || [])
      setLoading(false)
    })
  }, [])

  const sorted = useMemo(() => (
    [...defaulters].sort((a, b) => parseFloat(b.effective_balance || b.balance || 0) - parseFloat(a.effective_balance || a.balance || 0))
  ), [defaulters])

  const exportCSV = () => {
    const headers = ['Adm No', 'Name', 'Class', 'Balance', 'Due Date', 'Days Overdue']
    const rows = sorted.map(row => [
      row.admission_number,
      row.student_name,
      row.classroom_name,
      row.effective_balance ?? row.balance,
      row.due_date,
      daysOverdue(row.due_date),
    ])
    const csv = [headers, ...rows].map(r => r.join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'defaulters.csv'
    a.click()
  }

  if (loading) return <div className="flex justify-center py-20"><Spinner ClassName="h-7 w-7"/></div>

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Defaulters</h1>
          <p className="text-sm text-gray-500">Students with balances past due date.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" className="gap-2" onClick={exportCSV}>
            <Download size={16} /> Export CSV
          </Button>
          <Button
            variant="secondary"
            className="gap-2"
            onClick={() => alert('SMS reminders queued for defaulters.')}
          >
            <MessageSquare size={16} /> Bulk SMS
          </Button>
        </div>
      </div>

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b text-gray-500">
              <tr>
                <th className="text-left py-3 px-4">Student</th>
                <th className="text-left py-3 px-4">Class</th>
                <th className="text-left py-3 px-4">Balance</th>
                <th className="text-left py-3 px-4">Due Date</th>
                <th className="text-left py-3 px-4">Days Overdue</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {sorted.map(row => (
                <tr key={row.id}>
                  <td className="py-3 px-4">
                    <p className="font-medium">{row.student_name}</p>
                    <p className="text-xs text-gray-500">{row.admission_number}</p>
                  </td>
                  <td className="py-3 px-4">{row.classroom_name}</td>
                  <td className="py-3 px-4 font-mono text-red-600">
                    {formatMoney(row.effective_balance ?? row.balance)}
                  </td>
                  <td className="py-3 px-4">{row.due_date}</td>
                  <td className="py-3 px-4">{daysOverdue(row.due_date)} days</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
