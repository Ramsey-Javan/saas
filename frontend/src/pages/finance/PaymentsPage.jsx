import { useEffect, useState } from 'react'
import { financeApi } from '@/api/finance'
import { Card, Badge, Button, Spinner } from '@/components/ui'
import { Download } from 'lucide-react'

const formatMoney = (value) => `KES ${parseFloat(value || 0).toLocaleString()}`

const statusVariant = (status) => {
  if (status === 'completed' || status === 'confirmed') return 'active'
  if (status === 'pending') return 'pending'
  return 'inactive'
}

export default function PaymentsPage() {
  const [payments, setPayments] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    financeApi.getPayments({ page: 1 }).then(res => {
      setPayments(res.data.results || res.data || [])
      setLoading(false)
    })
  }, [])

  if (loading) return <div className="flex justify-center py-20"><Spinner ClassName="h-7 w-7"/></div>

  const handleDownloadReceipt = async (paymentId) => {
    const res = await financeApi.downloadReceipt(paymentId)
    const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
    window.open(url, '_blank', 'noopener,noreferrer')
    window.URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Payments</h1>
        <p className="text-sm text-gray-500">All recorded payments across students.</p>
      </div>

      <Card className="p-5">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b text-gray-500">
              <tr>
                <th className="text-left py-2">Student</th>
                <th className="text-left py-2">Amount</th>
                <th className="text-left py-2">Method</th>
                <th className="text-left py-2">Receipt</th>
                <th className="text-left py-2">Download</th>
                <th className="text-left py-2">Status</th>
                <th className="text-left py-2">Date</th>
              </tr>
            </thead>
            <tbody>
              {payments.map(payment => (
                <tr key={payment.id} className="border-b border-gray-50">
                  <td className="py-2">
                    <p className="font-medium">{payment.student_name || '—'}</p>
                    <p className="text-xs text-gray-500">{payment.admission_number || payment.student}</p>
                  </td>
                  <td className="py-2 font-mono">{formatMoney(payment.amount)}</td>
                  <td className="py-2 capitalize">{payment.payment_method}</td>
                  <td className="py-2 text-xs text-gray-500">{payment.receipt_number || payment.mpesa_receipt_number || '—'}</td>
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
                  <td className="py-2"><Badge label={payment.status} variant={statusVariant(payment.status)} /></td>
                  <td className="py-2 text-gray-500">{new Date(payment.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
