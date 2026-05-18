import { useEffect, useState } from 'react'
import { financeApi } from '@/api/finance'
import { Card, Button, Spinner, Input } from '@/components/ui'
import { CheckCircle, XCircle } from 'lucide-react'

const formatMoney = (value) => `KES ${parseFloat(value || 0).toLocaleString()}`

const daysBetween = (dateValue) => {
  if (!dateValue) return 0
  const start = new Date(dateValue)
  const today = new Date()
  const diff = Math.max(today - start, 0)
  return Math.floor(diff / (1000 * 60 * 60 * 24))
}

export default function PendingChequesPage() {
  const [payments, setPayments] = useState([])
  const [loading, setLoading] = useState(true)
  const [statusMessage, setStatusMessage] = useState('')
  const [reason, setReason] = useState('')
  const [activePayment, setActivePayment] = useState(null)
  const [actionLoading, setActionLoading] = useState(false)

  const loadPayments = () => {
    setLoading(true)
    financeApi.getPayments({ payment_method: 'cheque', status: 'pending' }).then(res => {
      setPayments(res.data.results || res.data || [])
      setLoading(false)
    }).catch(() => setLoading(false))
  }

  useEffect(() => {
    loadPayments()
  }, [])

  const handleClear = async (paymentId) => {
    setActionLoading(true)
    try {
      const res = await financeApi.clearCheque(paymentId)
      setStatusMessage(`Cheque cleared. Receipt: ${res.data.receipt_number}`)
      loadPayments()
    } catch (err) {
      setStatusMessage(err.response?.data?.error || 'Failed to clear cheque.')
    } finally {
      setActionLoading(false)
    }
  }

  const handleBounce = async () => {
    if (!activePayment) return
    if (!reason.trim()) {
      setStatusMessage('Provide a bounce reason before continuing.')
      return
    }
    setActionLoading(true)
    try {
      await financeApi.bounceCheque(activePayment.id, { reason })
      setStatusMessage('Cheque marked as bounced.')
      setReason('')
      setActivePayment(null)
      loadPayments()
    } catch (err) {
      setStatusMessage(err.response?.data?.error || 'Failed to bounce cheque.')
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) return <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div>

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Pending Cheques</h1>
        <p className="text-sm text-gray-500">Cheque payments awaiting clearance.</p>
      </div>

      {statusMessage && (
        <div className="px-4 py-3 rounded-lg bg-blue-50 text-blue-700 text-sm">
          {statusMessage}
        </div>
      )}

      <Card className="p-5">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b text-gray-500">
              <tr>
                <th className="text-left py-2">Student</th>
                <th className="text-left py-2">Class</th>
                <th className="text-left py-2">Amount</th>
                <th className="text-left py-2">Cheque No.</th>
                <th className="text-left py-2">Bank</th>
                <th className="text-left py-2">Drawer</th>
                <th className="text-left py-2">Date</th>
                <th className="text-left py-2">Days Pending</th>
                <th className="text-left py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {payments.map(payment => (
                <tr key={payment.id} className="border-b border-gray-50">
                  <td className="py-2">
                    <p className="font-medium">{payment.student_name || '—'}</p>
                    <p className="text-xs text-gray-500">{payment.admission_number || payment.student}</p>
                  </td>
                  <td className="py-2">{payment.classroom_name || '—'}</td>
                  <td className="py-2 font-mono">{formatMoney(payment.amount)}</td>
                  <td className="py-2 font-mono">{payment.cheque_number || '—'}</td>
                  <td className="py-2">{payment.bank_name || '—'}</td>
                  <td className="py-2">{payment.drawer_name || '—'}</td>
                  <td className="py-2 text-gray-500">
                    {new Date(payment.payment_date || payment.created_at).toLocaleDateString()}
                  </td>
                  <td className="py-2">
                    {daysBetween(payment.payment_date || payment.created_at)} days
                  </td>
                  <td className="py-2">
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="secondary"
                        className="gap-1"
                        onClick={() => handleClear(payment.id)}
                        disabled={actionLoading}
                      >
                        <CheckCircle size={14} /> Mark Cleared
                      </Button>
                      <Button
                        size="sm"
                        variant="danger"
                        className="gap-1"
                        onClick={() => setActivePayment(payment)}
                        disabled={actionLoading}
                      >
                        <XCircle size={14} /> Mark Bounced
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
              {payments.length === 0 && (
                <tr>
                  <td colSpan={9} className="py-6 text-center text-sm text-gray-500">No pending cheques.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {activePayment && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-lg max-w-sm w-full p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Bounce Cheque</h3>
            <Input
              label="Reason"
              value={reason}
              onChange={e => setReason(e.target.value)}
              placeholder="e.g. Insufficient funds"
            />
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="secondary" onClick={() => { setActivePayment(null); setReason('') }}>
                Cancel
              </Button>
              <Button variant="danger" onClick={handleBounce} loading={actionLoading}>
                Confirm Bounce
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
