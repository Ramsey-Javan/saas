import { useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { financeApi } from '@/api/finance'
import { Card, Button, Badge, Spinner, Avatar } from '@/components/ui'
import { Download } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import PaymentModal from '@/components/finance/PaymentModal'

const formatMoney = (value) => `KES ${parseFloat(value || 0).toLocaleString()}`
const formatWaiverScope = (scope) => {
  if (!scope) return null
  if (scope === 'termly') return 'Termly waiver'
  if (scope === 'yearly') return 'Yearly waiver'
  return 'Permanent waiver'
}

const statusStyles = {
  unpaid: { variant: 'inactive' },
  partial: { variant: 'pending' },
  paid: { variant: 'active' },
  overdue: { variant: 'inactive', className: 'bg-red-200 text-red-800' },
  waived: { variant: 'default' },
}

export default function StudentStatementPage() {
  const { studentId } = useParams()
  const navigate = useNavigate()
  const user = useAuthStore(state => state.user)
  const [statement, setStatement] = useState(null)
  const [loading, setLoading] = useState(true)
  const [payInvoice, setPayInvoice] = useState(null)
  const [downloadStatus, setDownloadStatus] = useState('')
  const [smsStatus, setSmsStatus] = useState('')

  useEffect(() => {
    setLoading(true)
    financeApi.getStudentStatement(studentId).then(res => {
      setStatement(res.data)
      setLoading(false)
    })
  }, [studentId])


  const student = statement?.student
  const summary = statement?.summary
  const invoices = statement?.invoices || []
  const payments = statement?.payments || []
  const canManageFees = ['admin', 'superadmin', 'bursar'].includes(user?.role)

  const payableInvoice = useMemo(() => (
    invoices && invoices.length ? invoices[0] : null
  ), [invoices])

  const handleDownloadPdf = async () => {
    if (!statement) return
    setDownloadStatus('Preparing statement PDF...')
    const res = await financeApi.getStudentStatementPdf(studentId)
    const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
    const link = document.createElement('a')
    link.href = url
    link.download = 'student_statement.pdf'
    link.click()
    window.URL.revokeObjectURL(url)
    setDownloadStatus('')
  }

  const handleSendSms = async () => {
    const invoiceIds = invoices.filter(inv => parseFloat(inv.balance) > 0).map(inv => inv.id)
    if (invoiceIds.length === 0) {
      setSmsStatus('No outstanding invoices to remind.')
      return
    }
    setSmsStatus('Sending SMS reminder...')
    try {
      const res = await financeApi.bulkInvoicesSms({ invoice_ids: invoiceIds })
      setSmsStatus(`SMS sent: ${res.data.sent}, failed: ${res.data.failed}`)
    } catch (err) {
      setSmsStatus(err.response?.data?.error || 'Failed to send SMS reminder.')
    }
  }

  const handleDownloadReceipt = async (paymentId) => {
    const res = await financeApi.downloadReceipt(paymentId)
    const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
    window.open(url, '_blank', 'noopener,noreferrer')
    window.URL.revokeObjectURL(url)
  }


  if (loading) return <div className="flex justify-center py-20"><Spinner ClassName="h-7 w-7" /></div>

  if (!statement) return null

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <button
            onClick={() => navigate(`/students/${studentId}`)}
            className="text-sm text-gray-500 hover:text-gray-900"
          >
            Back
          </button>
          <h1 className="text-2xl font-bold text-gray-900">Student Statement</h1>
          <div className="mt-2 flex items-center gap-3">
            <Avatar name={student?.full_name} photo={student?.photo} size="sm" />
            <div className="text-sm text-gray-500">
              {student?.full_name} · {student?.admission_number} · {student?.classroom_name || 'No class'}
            </div>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {canManageFees && (
            <Button
              onClick={() => setPayInvoice(payableInvoice)}
            >
              Record Payment
            </Button>
          )}
          <Button variant="secondary" onClick={handleDownloadPdf}>
            Download PDF statement
          </Button>
          {canManageFees && (
            <Button variant="secondary" onClick={handleSendSms}>
              Send SMS reminder
            </Button>
          )}
        </div>
      </div>

      {downloadStatus && (
        <div className="px-4 py-3 rounded-lg bg-blue-50 text-blue-700 text-sm">
          {downloadStatus}
        </div>
      )}

      {smsStatus && (
        <div className="px-4 py-3 rounded-lg bg-blue-50 text-blue-700 text-sm">
          {smsStatus}
        </div>
      )}

      <Card className="p-5 grid grid-cols-1 md:grid-cols-4 gap-4">
        <div>
          <p className="text-xs text-gray-500">Total billed</p>
          <p className="text-lg font-semibold">{formatMoney(summary?.total_billed)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Total waived</p>
          <p className="text-lg font-semibold text-emerald-600">{formatMoney(summary?.total_waived)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Total paid</p>
          <p className="text-lg font-semibold">{formatMoney(summary?.total_paid)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Carried forward</p>
          <p className="text-lg font-semibold">{formatMoney(summary?.carried_forward)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Balance due</p>
          <p className={`text-lg font-semibold ${parseFloat(summary?.total_balance || 0) > 0 ? 'text-red-600' : 'text-green-600'}`}>
            {formatMoney(summary?.total_balance)}
          </p>
        </div>
      </Card>

      <Card className="p-5">
        <h3 className="font-semibold text-gray-900 mb-3">Invoice history</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b text-gray-500">
              <tr>
                <th className="text-left py-2">Term</th>
                <th className="text-left py-2">Year</th>
                <th className="text-left py-2">Billed</th>
                <th className="text-left py-2">Waived</th>
                <th className="text-left py-2">Paid</th>
                <th className="text-left py-2">Carry Forward</th>
                <th className="text-left py-2">Balance</th>
                <th className="text-left py-2">Credit</th>
                <th className="text-left py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map(inv => (
                <tr key={inv.id} className="border-b border-gray-50">
                  <td className="py-2 capitalize">{inv.term}</td>
                  <td className="py-2">{inv.academic_year}</td>
                  <td className="py-2 font-mono">{formatMoney(inv.amount_due)}</td>
                  <td className="py-2">
                    <div className="font-mono text-emerald-600">{formatMoney(inv.waived_amount)}</div>
                    {inv.waiver_scope && (
                      <div className="text-xs text-emerald-700">
                        {formatWaiverScope(inv.waiver_scope)}{inv.waiver_reason ? ` · ${inv.waiver_reason}` : ''}
                      </div>
                    )}
                  </td>
                  <td className="py-2 font-mono">{formatMoney(inv.amount_paid)}</td>
                  <td className="py-2 font-mono">{formatMoney(inv.carried_forward)}</td>
                  <td className={`py-2 font-mono ${parseFloat(inv.balance) > 0 ? 'text-red-600' : 'text-green-600'}`}>
                    {formatMoney(inv.balance)}
                  </td>
                  <td className={`py-2 font-mono ${parseFloat(inv.credit || 0) > 0 ? 'text-green-600' : 'text-gray-500'}`}>
                    {parseFloat(inv.credit || 0) > 0
                      ? `${formatMoney(inv.credit)} -> carried to next term`
                      : '—'}
                  </td>
                  <td className="py-2">
                    <Badge
                      label={inv.status}
                      variant={statusStyles[inv.status]?.variant || 'default'}
                      className={statusStyles[inv.status]?.className}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card className="p-5">
        <h3 className="font-semibold text-gray-900 mb-3">Payment history</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b text-gray-500">
              <tr>
                <th className="text-left py-2">Date</th>
                <th className="text-left py-2">Amount</th>
                <th className="text-left py-2">Method</th>
                <th className="text-left py-2">Receipt</th>
                <th className="text-left py-2">Download</th>
                <th className="text-left py-2">M-Pesa Ref</th>
                <th className="text-left py-2">Recorded By</th>
              </tr>
            </thead>
            <tbody>
              {payments.map(payment => (
                <tr key={payment.id} className="border-b border-gray-50">
                  <td className="py-2 text-gray-500">{new Date(payment.date).toLocaleDateString()}</td>
                  <td className="py-2 font-mono">{formatMoney(payment.amount)}</td>
                  <td className="py-2 capitalize">{payment.method}</td>
                  <td className="py-2 text-xs text-gray-500">{payment.receipt_number || '—'}</td>
                  <td className="py-2">
                    {payment.receipt_number && (
                      <Button
                        size="sm"
                        variant="secondary"
                        className="gap-1"
                        onClick={() => handleDownloadReceipt(payment.id)}
                      >
                        <Download size={14} /> Receipt
                      </Button>
                    )}
                  </td>
                  <td className="py-2 text-xs text-gray-500">{payment.mpesa_receipt_number || '—'}</td>
                  <td className="py-2 text-xs text-gray-500">{payment.recorded_by || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <PaymentModal
        isOpen={Boolean(payInvoice)}
        onClose={() => setPayInvoice(null)}
        student={student ? {
          id: student.id,
          admission_number: student.admission_number,
          full_name: student.full_name,
        } : null}
        fee={payInvoice}
        onSuccess={() => {
          setPayInvoice(null)
          financeApi.getStudentStatement(studentId).then(res => setStatement(res.data))
        }}
      />
    </div>
  )
}
