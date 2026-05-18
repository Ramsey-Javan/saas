import { useState, useEffect } from 'react'
import { financeApi } from '@/api/finance'
import { studentsApi } from '@/api/students'
import { Card, Badge, Button, Spinner, EmptyState, Select } from '@/components/ui'
import { FileText, Download, MessageSquare } from 'lucide-react'
import PaymentModal from '@/components/finance/PaymentModal'

export default function InvoicesListPage() {
  const [invoices, setInvoices] = useState([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ status: '', term: '', fee_structure__academic_year: '', student__classroom: '' })
  const [selectedIds, setSelectedIds] = useState([])
  const [activeInvoice, setActiveInvoice] = useState(null)
  const [classrooms, setClassrooms] = useState([])
  const [smsStatus, setSmsStatus] = useState('')
  const [smsSending, setSmsSending] = useState(false)

  useEffect(() => {
    setLoading(true)
    financeApi.getInvoices(filters).then(r => {
      setInvoices(r.data.results || r.data)
      setLoading(false)
    })
  }, [filters])

  useEffect(() => {
    studentsApi.getClassrooms().then(r => setClassrooms(r.data.results || r.data || []))
  }, [])

  const statusColors = {
    unpaid: { variant: 'inactive' },
    partial: { variant: 'pending' },
    paid: { variant: 'active' },
    overdue: { variant: 'inactive', className: 'bg-red-200 text-red-800' },
    waived: { variant: 'default' },
  }

  const exportCSV = () => {
    const headers = ['Adm No', 'Name', 'Expected', 'Waived', 'Paid', 'Balance', 'Credit', 'Status']
    const rows = invoices.map(i => [
      i.admission_number, i.student_name, i.expected_amount, i.waived_amount || '0.00', i.paid_amount, 
      i.balance, i.credit || '0.00', i.status
    ])
    const csv = [headers, ...rows].map(r => r.join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = 'fee_invoices.csv'; a.click()
  }

  const refreshInvoices = () => {
    financeApi.getInvoices(filters).then(r => setInvoices(r.data.results || r.data))
  }

  const handleBulkPdf = async () => {
    if (!filters.term || !filters.fee_structure__academic_year) {
      setSmsStatus('Select term and academic year before downloading the PDF.')
      return
    }
    const res = await financeApi.bulkInvoicesPdf({
      term: filters.term,
      academic_year: filters.fee_structure__academic_year,
      classroom: filters.student__classroom || undefined,
    })
    const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
    const link = document.createElement('a')
    link.href = url
    link.download = 'invoice_slips.pdf'
    link.click()
    window.URL.revokeObjectURL(url)
  }

  const handleBulkSms = async () => {
    if (selectedIds.length === 0) return
    setSmsSending(true)
    setSmsStatus('Sending SMS reminders...')
    try {
      const res = await financeApi.bulkInvoicesSms({ invoice_ids: selectedIds })
      setSmsStatus(`SMS sent: ${res.data.sent}, failed: ${res.data.failed}`)
    } catch (err) {
      setSmsStatus(err.response?.data?.error || 'Failed to send SMS reminders.')
    } finally {
      setSmsSending(false)
    }
  }

  const toggleAll = (checked) => {
    setSelectedIds(checked ? invoices.map(i => i.id) : [])
  }

  const toggleOne = (id) => {
    setSelectedIds(ids => ids.includes(id) ? ids.filter(item => item !== id) : [...ids, id])
  }

  if (loading) return <div className="flex justify-center py-20"><Spinner ClassName="h-7 w-7"/></div>

  return (
    <div className="space-y-5">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Fee Invoices</h1>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={exportCSV} className="gap-2">
            <Download size={16} /> Export CSV
          </Button>
          <Button variant="secondary" onClick={handleBulkPdf} className="gap-2">
            <Download size={16} /> Download Invoices PDF
          </Button>
          <Button
            variant="secondary"
            className="gap-2"
            disabled={selectedIds.length === 0 || smsSending}
            onClick={handleBulkSms}
          >
            <MessageSquare size={16} /> Send SMS to Selected
          </Button>
        </div>
      </div>

      {smsStatus && (
        <div className="px-4 py-3 rounded-lg bg-blue-50 text-blue-700 text-sm">
          {smsStatus}
        </div>
      )}

      <Card className="p-4 flex gap-3">
        <Select value={filters.status} onChange={e => setFilters(f => ({...f, status: e.target.value}))}>
          <option value="">All Status</option>
          <option value="unpaid">Unpaid</option>
          <option value="partial">Partial</option>
          <option value="paid">Paid</option>
          <option value="overdue">Overdue</option>
          <option value="waived">Waived</option>
        </Select>
        <Select value={filters.term} onChange={e => setFilters(f => ({...f, term: e.target.value}))}>
          <option value="">All Terms</option>
          <option value="term1">Term 1</option>
          <option value="term2">Term 2</option>
          <option value="term3">Term 3</option>
        </Select>
        <Select value={filters.student__classroom} onChange={e => setFilters(f => ({...f, student__classroom: e.target.value}))}>
          <option value="">All Classes</option>
          {classrooms.map(c => (
            <option key={c.id} value={c.id}>{c.name}{c.stream ? ` ${c.stream}` : ''}</option>
          ))}
        </Select>
        <Select value={filters.fee_structure__academic_year} onChange={e => setFilters(f => ({...f, fee_structure__academic_year: e.target.value}))}>
          <option value="">All Years</option>
          {[...new Set(invoices.map(i => i.fee_academic_year))].filter(Boolean).map(year => (
            <option key={year} value={year}>{year}</option>
          ))}
        </Select>
      </Card>

      <Card>
        {invoices.length === 0 ? (
          <EmptyState icon={FileText} title="No invoices found" description="Generate bulk invoices to get started." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b">
                <tr className="text-gray-500">
                  <th className="text-left py-3 px-4">
                    <input
                      type="checkbox"
                      checked={selectedIds.length > 0 && selectedIds.length === invoices.filter(i => parseFloat(i.balance) > 0).length}
                      onChange={e => toggleAll(e.target.checked)}
                    />
                  </th>
                  <th className="text-left py-3 px-4">Student</th>
                  <th className="text-left py-3 px-4">Class</th>
                  <th className="text-left py-3 px-4">Expected</th>
                  <th className="text-left py-3 px-4">Waived</th>
                  <th className="text-left py-3 px-4">Paid</th>
                  <th className="text-left py-3 px-4">Balance</th>
                  <th className="text-left py-3 px-4">Credit</th>
                  <th className="text-left py-3 px-4">Status</th>
                  <th className="py-3 px-4"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {invoices.map(inv => (
                  <tr key={inv.id} className="hover:bg-gray-50">
                    <td className="py-3 px-4">
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(inv.id)}
                        onChange={() => toggleOne(inv.id)}
                      />
                    </td>
                    <td className="py-3 px-4">
                      <p className="font-medium">{inv.student_name}</p>
                      <p className="text-xs text-gray-500">{inv.admission_number}</p>
                    </td>
                    <td className="py-3 px-4">{inv.classroom_name}</td>
                    <td className="py-3 px-4 font-mono">KES {inv.expected_amount}</td>
                    <td className="py-3 px-4 font-mono text-emerald-600">KES {inv.waived_amount || '0.00'}</td>
                    <td className="py-3 px-4 font-mono">KES {inv.paid_amount}</td>
                    <td className={`py-3 px-4 font-mono font-medium ${parseFloat(inv.effective_balance || inv.balance) > 0 ? 'text-red-600' : 'text-green-600'}`}>
                      KES {inv.effective_balance ?? inv.balance}
                    </td>
                    <td className={`py-3 px-4 font-mono ${parseFloat(inv.credit || 0) > 0 ? 'text-green-600' : 'text-gray-500'}`}>
                      {parseFloat(inv.credit || 0) > 0 ? `KES ${inv.credit}` : '—'}
                    </td>
                    <td className="py-3 px-4">
                      <Badge
                        label={inv.status}
                        variant={statusColors[inv.status]?.variant || 'default'}
                        className={statusColors[inv.status]?.className}
                      />
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Button size="sm" variant="secondary" onClick={() => setActiveInvoice(inv)}>
                        Record Payment
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <PaymentModal
        isOpen={Boolean(activeInvoice)}
        onClose={() => setActiveInvoice(null)}
        student={activeInvoice ? {
          id: activeInvoice.student,
          admission_number: activeInvoice.admission_number,
          full_name: activeInvoice.student_name,
        } : null}
        fee={activeInvoice}
        onSuccess={() => {
          setActiveInvoice(null)
          refreshInvoices()
        }}
      />
    </div>
  )
}
